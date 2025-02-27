
import discord
import os
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.admin_ids = self.load_admin_ids()
    
    def load_admin_ids(self):
        """Load admin IDs from admins.txt file"""
        admin_ids = []
        try:
            with open("admins.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        admin_ids.append(int(line))
        except Exception as e:
            print(f"Error loading admin IDs: {e}")
        return admin_ids
    
    def is_admin(self, user_id):
        """Check if a user ID is in the admin list"""
        return user_id in self.admin_ids
    
    @commands.command(name="addcash")
    async def addcash(self, ctx, user: discord.Member, amount: float, currency_type: str):
        """Add tokens or credits to a user (Admin only)
        
        Usage: !addcash @user 100 tokens
               !addcash @user 50 credits
        """
        # Check if command user is an admin
        if not self.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Access Denied",
                description="This command is restricted to administrators only.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Validate currency type
        currency_type = currency_type.lower()
        if currency_type not in ["token", "tokens", "credit", "credits"]:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description="Please specify either 'tokens' or 'credits'.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Normalize currency type
        if currency_type in ["token", "tokens"]:
            db_field = "tokens"
            display_currency = "tokens"
        else:
            db_field = "credits"
            display_currency = "credits"
        
        # Add the amount to the user's balance
        db = Users()
        user_data = db.fetch_user(user.id)
        
        # If user doesn't exist, register them
        if not user_data:
            dump = {"discord_id": user.id, "tokens": 0, "credits": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0}
            db.register_new_user(dump)
            user_data = db.fetch_user(user.id)
        
        # Update user balance
        current_amount = user_data[db_field]
        new_amount = current_amount + amount
        db.update_balance(user.id, new_amount, db_field)
        
        # Add to history
        history_entry = {
            "type": "admin_add",
            "amount": amount,
            "currency": db_field,
            "timestamp": int(discord.utils.utcnow().timestamp()),
            "admin_id": ctx.author.id
        }
        
        db.collection.update_one(
            {"discord_id": user.id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}  # Keep last 100 entries
        )
        
        # Send confirmation message
        money_emoji = emoji()["money"]
        embed = discord.Embed(
            title=f"{money_emoji} | Admin Action: Added {display_currency.capitalize()}",
            description=f"Successfully added **{amount:,.2f} {display_currency}** to {user.mention}'s balance.",
            color=0x00FFAE
        )
        embed.add_field(
            name="New Balance",
            value=f"**{new_amount:,.2f} {display_currency}**",
            inline=False
        )
        embed.set_footer(text=f"Admin: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(AdminCommands(bot))
