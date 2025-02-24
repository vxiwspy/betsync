from pymongo import MongoClient

mongodb = MongoClient(os.environ["MONGO_URI"])


class Users():
    def __init__(self):
        self.db = mongodb["BetSync"]
        self.collection = self.db["Users"]
        
	def get_all_users(self):
		return self.collection.find()

	def register_new_user(self, user_data):
        
		discordid = userdata_["discord_id"]
        if self.collection.count_documents({"discord_id": discordid}):
            return False
        else:
        	new_user = self.collection.insert_one(user_data)
        	return new_user.inserted_id

	def fetch_user(self, user_id):
        return self.collection.find({"discord_id": user_id})

