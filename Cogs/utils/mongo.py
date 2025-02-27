from pymongo import MongoClient
import os

mongodb = MongoClient(os.environ["MONGO"])


class Users:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Users, cls).__new__(cls)
            cls._client = MongoClient(os.environ["MONGO"])
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'db'):
            self.db = self._client["BetSync"]
            self.collection = self.db["users"]

    def get_all_users(self):
        return self.collection.find()

    def register_new_user(self, user_data):
        discordid = user_data["discord_id"]
        if self.collection.count_documents({"discord_id": discordid}):
            return False
        else:
            new_user = self.collection.insert_one(user_data)
            return new_user.inserted_id

    def fetch_user(self, user_id):
        if self.collection.count_documents({"discord_id": user_id}):
            return self.collection.find_one({"discord_id": user_id})

        else:
            return False

    def update_balance(self, user_id, amount, currency: str = "tokens", operation = "$set"):
        try:
            self.collection.update_one({"discord_id": user_id}, {operation: {currency: amount}})
            return True
        except Exception as e:
            return False

class Servers:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Servers, cls).__new__(cls)
            cls._client = MongoClient(os.environ["MONGO"])
            return cls._instance

    def __init__(self):
        if not hasattr(self, 'db'):
            self.db = self._client["BetSync"]
            self.collection = self.db["servers"]

    def get_total_all_servers(self):
        return self.collection.count_documents({})

    def new_server(self, dump):
        server_id = dump["server_id"]
        if self.collection.count_documents({"server_id": server_id}):
            return False
        else:
            new_server_ = self.collection.insert_one(dump) 
            return self.collection.find_one({"server_id": server_id})
            
    def update_server_profit(self, server_id, profit_amount):
        """
        Updates the total profit value for a server.
        
        Args:
            server_id: The ID of the server to update
            profit_amount: The amount to add to the total profit (negative for player wins)
        
        Returns:
            bool: True if the update was successful, False otherwise
        """
        try:
            self.collection.update_one(
                {"server_id": server_id},
                {"$inc": {"total_profit": profit_amount}}
            )
            return True
        except Exception as e:
            print(f"Error updating server profit: {e}")
            return False

    def update_history(self, server_id, history_data):
            if self.collection.count_documents({"server_id": server_id}):
                self.collection.update_one(
                    {"server_id": server_id},
                    {"$push": {"server_bet_history": history_data}}
                )
                return True
            else:
                return False