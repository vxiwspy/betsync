
import discord
import datetime
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji


class Tip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token_value = 0.0212  # USD value of 1 token

    @commands.command(aliases=["give", "donate"])
    async def tip(self, ctx, amount=None, currency=None, user: discord.Member = None):
        """Tip other users with tokens or credits
        
        Usage:
        - !tip <amount> <token/credit> @user
        - !tip <amount> <token/credit> <user_id>
        - Reply to a message with !tip <amount> <token/credit>
        """
        if ctx.message.reference and ctx.message.reference.resolved:
            # Handle reply-based tip
            recipient = ctx.message.reference.resolved.author
            if amount is None or currency is None:
                return await self.show_usage(ctx)
        else:
            # Handle regular command
            if amount is None or currency is None:
                return await self.show_usage(ctx)
            
            # If user is passed as a parameter
            if user is None:
                # Check if the currency param is actually a member mention or ID
                try:
                    user_id = int(''.join(filter(str.isdigit, currency)))
                    possible_user = await self.bot.fetch_user(user_id)
                    if possible_user:
                        user = possible_user
                        currency = None  # Reset currency as it was actually a user
                except:
                    pass
            
            if user is None:
                return await self.show_usage(ctx)
            
            recipient = user
        
        # Prevent self-tips
        if recipient.id == ctx.author.id:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Tip Yourself",
                description="You cannot tip yourself. Please select another user.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Prevent bot tips
        if recipient.bot:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Cannot Tip Bots",
                description="You cannot tip bot accounts.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Try to parse amount
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please enter a valid positive number for the tip amount.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Validate currency
        if currency is None:
            currency = "token"  # Default to token if not specified
        
        # Normalize currency input
        currency = currency.lower()
        if currency in ["token", "tokens", "t"]:
            currency = "tokens"
            formatted_currency = "tokens"
            db_field = "tokens"
        elif currency in ["credit", "credits", "c"]:
            currency = "credits"
            formatted_currency = "credits"
            db_field = "credits"
        else:
            return await self.show_usage(ctx)
        
        # Check if sender has an account
        db = Users()
        sender_data = db.fetch_user(ctx.author.id)
        if not sender_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Required",
                description="You need an account to tip others. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Check if recipient has an account
        recipient_data = db.fetch_user(recipient.id)
        if not recipient_data:
            # Auto-register recipient
            dump = {"discord_id": recipient.id, "tokens": 0, "credits": 0, "history": [], 
                   "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                   "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost': 0}
            db.register_new_user(dump)
            recipient_data = db.fetch_user(recipient.id)
        
        # Process token to credit conversion if needed
        if currency == "credits" and formatted_currency == "tokens":
            # Convert tokens to credits (1:1 ratio as per the value)
            formatted_currency = "credits"
            db_field = "credits"
        
        # Check if sender has enough balance
        sender_balance = sender_data.get(db_field, 0)
        if sender_balance < amount:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Balance",
                description=f"You don't have enough {formatted_currency}. Your balance: **{sender_balance:.2f} {formatted_currency}**",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Process the tip
        # Deduct from sender
        db.update_balance(ctx.author.id, sender_balance - amount, db_field, "$set")
        
        # Add to recipient
        recipient_balance = recipient_data.get(db_field, 0)
        db.update_balance(recipient.id, recipient_balance + amount, "tokens", "$set")
        
        # Record in history for both users
        timestamp = int(datetime.datetime.now().timestamp())
        
        # Sender history (sent tip)
        sender_history = {
            "type": "tip_sent",
            "amount": amount,
            "currency": formatted_currency,
            "recipient": recipient.id,
            "timestamp": timestamp
        }
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [sender_history], "$slice": -100}}}
        )
        
        # Recipient history (received tip)
        recipient_history = {
            "type": "tip_received",
            "amount": amount,
            "currency": formatted_currency,
            "sender": ctx.author.id,
            "timestamp": timestamp
        }
        db.collection.update_one(
            {"discord_id": recipient.id},
            {"$push": {"history": {"$each": [recipient_history], "$slice": -100}}}
        )
        
        # Send success message
        embed = discord.Embed(
            title=":gift: Tip Sent Successfully!",
            description=f"You sent **{amount:.2f} {formatted_currency}** to {recipient.mention}",
            color=0x00FFAE
        )
        embed.add_field(
            name="Your New Balance",
            value=f"**{(sender_balance - amount):.2f} {formatted_currency}**",
            inline=True
        )
        embed.add_field(
            name="USD Value",
            value=f"**${(amount * self.token_value):.2f}**",
            inline=True
        )
        embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)
        
        # Notify recipient
        try:
            recipient_embed = discord.Embed(
                title=":tada: You Received a Tip!",
                description=f"{ctx.author.mention} sent you **{amount:.2f} {formatted_currency}**!",
                color=0x00FFAE
            )
            recipient_embed.add_field(
                name="Your New Balance",
                value=f"**{(recipient_balance + amount):.2f} {formatted_currency}**",
                inline=True
            )
            recipient_embed.add_field(
                name="USD Value",
                value=f"**${(amount * self.token_value):.2f}**",
                inline=True
            )
            recipient_embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
            await recipient.send(embed=recipient_embed)
        except:
            # If DM fails, just continue without notification
            pass
    
    async def show_usage(self, ctx):
        """Show command usage information"""
        embed = discord.Embed(
            title=":bulb: How to Use `!tip`",
            description="Send tokens or credits to another user.",
            color=0xFFD700
        )
        embed.add_field(
            name="Usage Options",
            value=(
                "**Direct Mention:**\n`!tip 100 token @user` or `!tip 100 t @user`\n\n"
                "**User ID:**\n`!tip 50 credit 123456789012345678` or `!tip 50 c 123456789012345678`\n\n"
                "**Reply to Message:**\n`!tip 75 token` or `!tip 75 t` (as a reply)\n\n"
                "**Shortcuts:**\n"
                "`!give` and `!donate` also work as aliases.\n"
                "`t` and `c` can be used for token and credit."
            ),
            inline=False
        )
        embed.add_field(
            name="Tips",
            value=(
                "• Amount must be a positive number\n"
                "• Currency can be `token` or `credit`\n"
                "• You can't tip yourself or bots\n"
                "• The recipient will be notified by DM"
            ),
            inline=False
        )
        embed.set_footer(text="BetSync Casino • Tipping System", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Tip(bot))
