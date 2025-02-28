
import os
import discord
import random
import asyncio
from discord.ext import commands
from datetime import datetime

from Cogs.utils.mongo import Users, Servers

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="play_again")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Check if user can afford the same bet
        db = Users()
        user_data = db.fetch_user(interaction.user.id)
        if not user_data:
            return await interaction.followup.send("Your account couldn't be found. Please try again later.", ephemeral=True)

        credits_balance = user_data['credits']

        if credits_balance < self.bet_amount:
            return await interaction.followup.send(f"You don't have enough credits to play again. You need {self.bet_amount} credits.", ephemeral=True)

        # Create a new penalty game with the same bet amount
        await self.cog.penalty(self.ctx, str(self.bet_amount), "credits")

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class PenaltyButtonView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None
        self.clicked = False  # Prevent multiple clicks

    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="⬅️", custom_id="left")
    async def left_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your shot!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Then process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "left", self.bet_amount)

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="⬆️", custom_id="middle")
    async def middle_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your shot!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Then process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "middle", self.bet_amount)

    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="➡️", custom_id="right")
    async def right_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your shot!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Then process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "right", self.bet_amount)

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
                
                # Remove from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            except:
                pass


class PenaltyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pen", "pk"])
    async def penalty(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play penalty shootout - aim your shot and try to score!"""
        if not bet_amount:
            embed = discord.Embed(
                title="⚽ How to Play Penalty",
                description=(
                    "**Penalty** is a game where you take a penalty kick against a goalkeeper!\n\n"
                    "**Usage:** `!penalty <amount> [currency_type]`\n"
                    "**Example:** `!penalty 100` or `!penalty 100 credits`\n\n"
                    "- **Choose to shoot left, middle, or right**\n"
                    "- **If the goalkeeper dives in a different direction, you score and win 1.5x your bet!**\n"
                    "- **If the goalkeeper saves your shot, you lose your bet**\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if the user already has an ongoing game
        if ctx.author.id in self.ongoing_games:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Game In Progress",
                description="You already have an ongoing game. Please finish it first.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Process bet info
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        if not user_data:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Account Not Found",
                description="Your account couldn't be found. Please try again later.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Determine currency type (default to credits)
        if not currency_type or currency_type.lower() not in ["credits", "tokens"]:
            currency_type = "credits"
        else:
            currency_type = currency_type.lower()
            if currency_type == "token" or currency_type == "token":
                currency_type = "tokens"
            elif currency_type == "credit" or currency_type == "credit":
                currency_type = "credits"

        # Currency handling is done below - we'll accept tokens but payout in credits

        # Validate bet amount
        try:
            bet_amount = float(bet_amount)
            if bet_amount <= 0:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Bet",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        except ValueError:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Bet amount must be a number.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get user balances
        tokens_balance = user_data['tokens']
        credits_balance = user_data['credits']

        # Determine which currency to use
        tokens_used = 0
        credits_used = 0

        if currency_type == 'tokens':
            # User specifically wants to use tokens
            if bet_amount <= tokens_balance:
                tokens_used = bet_amount
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Tokens",
                    description=f"You don't have enough tokens. Your balance: **{tokens_balance:,.2f} tokens**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        elif currency_type == 'credits':
            # User specifically wants to use credits
            if bet_amount <= credits_balance:
                credits_used = bet_amount
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Credits",
                    description=f"You don't have enough credits. Your balance: **{credits_balance:,.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:
            # Auto determine what to use
            if bet_amount <= tokens_balance:
                tokens_used = bet_amount
            elif bet_amount <= credits_balance:
                credits_used = bet_amount
            elif bet_amount <= tokens_balance + credits_balance:
                # Use all tokens and some credits
                tokens_used = tokens_balance
                credits_used = bet_amount - tokens_balance
            else:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Funds",
                    description=f"You don't have enough funds. Your balance: **{tokens_balance:,.2f} tokens** and **{credits_balance:,.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Loading message
        loading_message = await ctx.reply("⚽ Setting up the penalty kick...")

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount
        }

        # Deduct bet from user's balance
        if tokens_used > 0:
            db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Create a very simple and clear embed
        embed = discord.Embed(
            title="⚽ PENALTY KICK",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n"
                f"**Potential win:** {bet_amount*1.5:,.2f} credits\n\n"
                "**Choose where to shoot:**"
            ),
            color=0x00FFAE
        )

        # Ultra simple visual representation
        field_value = (
            "```\n"
            "    [GOAL]    \n"
            "   🥅 🥅 🥅   \n"
            "     🧤       \n\n"
            " LEFT  MID  RIGHT\n"
            "```"
        )
        embed.add_field(name="Click a button below to shoot", value=field_value, inline=False)
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Delete loading message
        await loading_message.delete()

        # Create view with buttons
        view = PenaltyButtonView(self, ctx, bet_amount, timeout=30)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    async def process_penalty_shot(self, ctx, interaction, shot_direction, bet_amount):
        """Process the penalty shot and determine the outcome"""
        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

        # Goalkeeper picks a random direction
        goalkeeper_directions = ["left", "middle", "right"]
        goalkeeper_direction = random.choice(goalkeeper_directions)

        # Determine the outcome
        goal_scored = shot_direction != goalkeeper_direction

        # Calculate winnings
        multiplier = 1.5
        winnings = bet_amount * multiplier if goal_scored else 0

        # User and GK direction symbols for the ASCII art
        directions = {
            "left": "LEFT",
            "middle": "MID",
            "right": "RIGHT"
        }

        # Create result embed
        if goal_scored:
            title = "🎉 GOAL! YOU SCORED! 🎉"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")

            # Update statistics - instead of using update_game_statistics method
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}}
            )

            # Create simple ASCII art for goal
            result_ascii = (
                "```\n"
                "    GOAL! ⚽     \n"
                "   🥅 🥅 🥅   \n\n"
                f"You shot: {shot_direction.upper()}\n"
                f"Goalkeeper: {goalkeeper_direction.upper()}\n"
                "```"
            )
        else:
            title = "❌ SAVED! THE GOALKEEPER STOPPED YOUR SHOT! ❌"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss

            # Update statistics - instead of using update_game_statistics method
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

            # Create simple ASCII art for save
            result_ascii = (
                "```\n"
                "    SAVED! 🧤     \n"
                "   🥅 🥅 🥅   \n\n"
                f"You shot: {shot_direction.upper()}\n"
                f"Goalkeeper: {goalkeeper_direction.upper()}\n"
                "```"
            )

        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.add_field(name="Result", value=result_ascii, inline=False)
        embed.set_footer(text="BetSync Casino | Want to try again?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        server_db = Servers()
        # Get the pending game data to determine which currency was used
        game_info = self.ongoing_games.get(ctx.author.id, {})
        
        game_data = {
            "game": "penalty",
            "user_id": ctx.author.id,
            "user_name": str(ctx.author),
            "bet_amount": bet_amount,
            "currency_type": "credits",  # Always record payouts in credits
            "multiplier": multiplier if goal_scored else 0,
            "winnings": winnings,
            "choice": shot_direction,
            "outcome": goalkeeper_direction,
            "win": goal_scored,
            "time": datetime.utcnow()
        }

        # Update server history
        server_id = ctx.guild.id if ctx.guild else None
        if server_id:
            server_db.update_history(server_id, game_data)

        # Update user history
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [game_data], "$slice": -100}}}
        )

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await interaction.followup.send(embed=embed, view=play_again_view)
        play_again_view.message = message


def setup(bot):
    bot.add_cog(PenaltyCog(bot))
