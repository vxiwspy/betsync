
import discord
import random
from discord.ext import commands
from datetime import datetime
from Cogs.utils.mongo import Users, Servers

class RoleSelectionView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.message = None

    @discord.ui.button(label="Penalty Taker", style=discord.ButtonStyle.primary, emoji="⚽", custom_id="taker")
    async def taker_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(view=self)
        
        # Start game as penalty taker
        await self.cog.start_as_taker(self.ctx, interaction, self.bet_amount, self.currency_type)

    @discord.ui.button(label="Goalkeeper", style=discord.ButtonStyle.success, emoji="🧤", custom_id="goalkeeper")
    async def goalkeeper_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(view=self)
        
        # Start game as goalkeeper
        await self.cog.start_as_goalkeeper(self.ctx, interaction, self.bet_amount, self.currency_type)

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


class PenaltyButtonView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, role="taker", timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.role = role
        self.message = None
        self.clicked = False  # Prevent multiple clicks

    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="⬅️", custom_id="left")
    async def left_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "left", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "left", self.bet_amount)

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="⬆️", custom_id="middle")
    async def middle_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "middle", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "middle", self.bet_amount)

    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="➡️", custom_id="right")
    async def right_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        if self.clicked:
            return await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            
        self.clicked = True  # Mark that a button has been clicked

        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        
        # Acknowledge the interaction first
        await interaction.response.edit_message(view=self)
        
        # Process the choice based on role
        if self.role == "taker":
            await self.cog.process_penalty_shot(self.ctx, interaction, "right", self.bet_amount)
        else:
            await self.cog.process_goalkeeper_save(self.ctx, interaction, "right", self.bet_amount)

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


class PenaltyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pen", "pk"])
    async def penalty(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play penalty shootout - choose to be a penalty taker or goalkeeper!"""
        if not bet_amount:
            embed = discord.Embed(
                title="⚽ How to Play Penalty",
                description=(
                    "**Penalty** is a game where you can be either a penalty taker or a goalkeeper!\n\n"
                    "**Usage:** `!penalty <amount> [currency_type]`\n"
                    "**Example:** `!penalty 100` or `!penalty 100 credits`\n\n"
                    "**Choose your role:**\n"
                    "- **As Penalty Taker:** Choose where to shoot (left/middle/right). If the goalkeeper dives in a different direction, you score and win 1.5x your bet!\n"
                    "- **As Goalkeeper:** Choose where to dive (left/middle/right). If you guess correctly where the striker will shoot, you save and win 2.1x your bet!\n"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if currency type is valid
        currency_type = currency_type.lower() if currency_type else "credits"
        if currency_type not in ["credits", "tokens"]:
            return await ctx.reply("Invalid currency type! Please use either 'credits' or 'tokens'.")

        # Check if bet amount is valid
        try:
            if bet_amount.lower() == "all":
                db = Users()
                user_data = db.fetch_user(ctx.author.id)
                if not user_data:
                    return await ctx.reply("Your account couldn't be found. Please try again later.")
                
                bet_amount = user_data[currency_type]
                if bet_amount <= 0:
                    return await ctx.reply(f"You don't have any {currency_type} to bet!")
            else:
                bet_amount = float(bet_amount)
        except ValueError:
            return await ctx.reply("Invalid bet amount! Please enter a number.")

        # Check if bet amount is positive
        if bet_amount <= 0:
            return await ctx.reply("Bet amount must be positive!")

        # Check if user has enough balance
        db = Users()
        user_data = db.fetch_user(ctx.author.id)
        if not user_data:
            return await ctx.reply("Your account couldn't be found. Please try again later.")
        
        balance = user_data[currency_type]
        
        # Initialize tokens and credits used
        tokens_used = 0
        credits_used = 0
        
        if balance < bet_amount:
            return await ctx.reply(f"You don't have enough {currency_type} to place this bet! Your balance: {balance:,.2f} {currency_type}")
        
        # Set the amount used based on currency type
        if currency_type == "tokens":
            tokens_used = bet_amount
        else:
            credits_used = bet_amount

        # Loading message
        loading_message = await ctx.reply("⚽ Setting up the penalty game...")

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount,
            "currency_type": currency_type
        }

        # Deduct bet from user's balance
        if tokens_used > 0:
            db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Create role selection embed
        embed = discord.Embed(
            title="⚽ PENALTY KICK - CHOOSE YOUR ROLE",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n\n"
                "**Choose your role:**\n"
                "**🧤 Goalkeeper:** You dive to save the shot. Win 2.1x if you save!\n"
                "**⚽ Penalty Taker:** You shoot at goal. Win 1.5x if you score!"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Delete loading message
        await loading_message.delete()

        # Create view with role selection buttons
        view = RoleSelectionView(self, ctx, bet_amount, currency_type, timeout=30)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    async def start_as_taker(self, ctx, interaction, bet_amount, currency_type):
        """Start the game as a penalty taker"""
        embed = discord.Embed(
            title="⚽ PENALTY KICK - YOU ARE THE TAKER",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n"
                f"**Potential win:** {bet_amount*1.5:,.2f} credits\n\n"
                "**Choose where to shoot by clicking a button below:**"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with shooting buttons
        view = PenaltyButtonView(self, ctx, bet_amount, role="taker", timeout=30)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message

    async def start_as_goalkeeper(self, ctx, interaction, bet_amount, currency_type):
        """Start the game as a goalkeeper"""
        embed = discord.Embed(
            title="🧤 PENALTY KICK - YOU ARE THE GOALKEEPER",
            description=(
                f"**Your bet:** {bet_amount:,.2f} {currency_type}\n"
                f"**Potential win:** {bet_amount*2.1:,.2f} credits\n\n"
                "**Choose where to dive by clicking a button below:**"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with diving buttons
        view = PenaltyButtonView(self, ctx, bet_amount, role="goalkeeper", timeout=30)
        message = await interaction.followup.send(embed=embed, view=view)
        view.message = message

    async def process_penalty_shot(self, ctx, interaction, shot_direction, bet_amount):
        """Process the penalty shot when user is the taker"""
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

        # Create result embed
        if goal_scored:
            title = "🎉 GOAL! YOU SCORED! 🎉"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")

            # Update statistics
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}}
            )

            # Result text
            result_text = f"**You shot {shot_direction.upper()} and the goalkeeper went {goalkeeper_direction.upper()}!**"
        else:
            title = "❌ SAVED! THE GOALKEEPER STOPPED YOUR SHOT! ❌"
            description = f"You shot **{shot_direction.upper()}**, the goalkeeper dove **{goalkeeper_direction.upper()}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

            # Result text
            result_text = f"**You shot {shot_direction.upper()} and the goalkeeper went {goalkeeper_direction.upper()}!**"

        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"{result_text}\n\n{description}",
            color=color
        )
        embed.set_footer(text="BetSync Casino | Want to try again?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_taker", bet_amount, shot_direction, goalkeeper_direction, goal_scored, multiplier, winnings)

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await interaction.followup.send(embed=embed, view=play_again_view)
        play_again_view.message = message

    async def process_goalkeeper_save(self, ctx, interaction, dive_direction, bet_amount):
        """Process the penalty save when user is the goalkeeper"""
        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

        # Striker picks a random direction
        striker_directions = ["left", "middle", "right"]
        striker_direction = random.choice(striker_directions)

        # Determine the outcome
        save_made = dive_direction == striker_direction

        # Calculate winnings
        multiplier = 2.1  # Higher multiplier for goalkeeper
        winnings = bet_amount * multiplier if save_made else 0

        # Create result embed
        if save_made:
            title = "🎉 SAVE! YOU STOPPED THE SHOT! 🎉"
            description = f"You dove **{dive_direction.upper()}**, the striker shot **{striker_direction.upper()}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win

            # Update user balance with winnings
            db = Users()
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")

            # Update statistics
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}}
            )

            # Result text
            result_text = f"**You dove {dive_direction.upper()} and the striker shot {striker_direction.upper()}!**"
        else:
            title = "❌ GOAL! THE STRIKER SCORED PAST YOU! ❌"
            description = f"You dove **{dive_direction.upper()}**, the striker shot **{striker_direction.upper()}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss

            # Update statistics
            db = Users()
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {"$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_amount}}
            )

            # Result text
            result_text = f"**You dove {dive_direction.upper()} and the striker shot {striker_direction.upper()}!**"

        # Create embed
        embed = discord.Embed(
            title=title,
            description=f"{result_text}\n\n{description}",
            color=color
        )
        embed.set_footer(text="BetSync Casino | Want to try again?", icon_url=self.bot.user.avatar.url)

        # Add betting history
        self.update_bet_history(ctx, "penalty_goalkeeper", bet_amount, dive_direction, striker_direction, save_made, multiplier, winnings)

        # Create "Play Again" button
        play_again_view = PlayAgainView(self, ctx, bet_amount, timeout=15)
        message = await interaction.followup.send(embed=embed, view=play_again_view)
        play_again_view.message = message

    def update_bet_history(self, ctx, game_type, bet_amount, user_choice, ai_choice, won, multiplier, winnings):
        """Update bet history in database"""
        # Create timestamp
        timestamp = int(datetime.utcnow().timestamp())
        
        # Create game data
        game_data = {
            "game": game_type,
            "type": "win" if won else "loss",
            "bet": bet_amount,
            "amount": winnings if won else bet_amount,
            "multiplier": multiplier if won else 0,
            "choice": user_choice,
            "outcome": ai_choice,
            "win": won,
            "timestamp": timestamp
        }
        
        # Update user history
        db = Users()
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [game_data], "$slice": -100}}}
        )

        # Update server history with additional user information
        server_db = Servers()
        server_id = ctx.guild.id if ctx.guild else None
        
        if server_id:
            server_game_data = game_data.copy()
            server_game_data["user_id"] = ctx.author.id
            server_game_data["user_name"] = str(ctx.author)
            
            server_db.update_history(server_id, server_game_data)


def setup(bot):
    bot.add_cog(PenaltyCog(bot))
