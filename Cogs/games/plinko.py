import discord
import random
import asyncio
import time
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PlinkoSetupView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.difficulty = "LOW"
        self.rows = 12
        self.add_difficulty_buttons()
        self.add_row_buttons()

    def add_difficulty_buttons(self):
        difficulties = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
        for difficulty in difficulties:
            button = discord.ui.Button(
                label=difficulty.capitalize(),
                style=discord.ButtonStyle.primary if difficulty == "LOW" else discord.ButtonStyle.secondary,
                custom_id=f"difficulty_{difficulty}"
            )
            button.callback = self.difficulty_callback
            self.add_item(button)

    def add_row_buttons(self):
        rows_options = [8, 9, 10, 11, 12, 13, 14, 15, 16]
        for i, rows in enumerate(rows_options):
            button = discord.ui.Button(
                label=f"{rows} Rows",
                style=discord.ButtonStyle.primary if rows == 12 else discord.ButtonStyle.secondary,
                custom_id=f"rows_{rows}",
                row=1 + (i // 3)
            )
            button.callback = self.rows_callback
            self.add_item(button)

        # Add Start button
        start_button = discord.ui.Button(
            label="Start",
            style=discord.ButtonStyle.success,
            custom_id="start_game",
            row=4
        )
        start_button.callback = self.start_callback
        self.add_item(start_button)

    async def difficulty_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Update selected difficulty
        self.difficulty = interaction.data["custom_id"].split("_")[1]

        # Update button styles
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("difficulty_"):
                difficulty = item.custom_id.split("_")[1]
                item.style = discord.ButtonStyle.primary if difficulty == self.difficulty else discord.ButtonStyle.secondary

        # Update embed
        embed = self.create_setup_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def rows_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Update selected rows
        self.rows = int(interaction.data["custom_id"].split("_")[1])

        # Update button styles
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.startswith("rows_"):
                rows = int(item.custom_id.split("_")[1])
                item.style = discord.ButtonStyle.primary if rows == self.rows else discord.ButtonStyle.secondary

        # Update embed
        embed = self.create_setup_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def start_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable all buttons to prevent multiple clicks
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)

        # Start the game
        await self.cog.start_plinko_game(
            self.ctx, 
            self.bet_amount, 
            self.difficulty,
            self.rows
        )

    def create_setup_embed(self):
        # Get the multipliers based on selected difficulty and rows
        multipliers = self.cog.get_multipliers(self.difficulty, self.rows)

        # Format the multipliers as a string
        multiplier_str = ", ".join([str(m) + "x" for m in multipliers])
        max_profit = max(multipliers) * self.bet_amount

        # Create embed
        embed = discord.Embed(
            title="ℹ️ | Plinko Game",
            description=(
                f"You are betting {self.bet_amount} points.\n"
                f"Difficulty: {self.difficulty} | Rows: {self.rows} Rows\n\n"
                f"Possible Payouts:\n"
                f"{multiplier_str}\n"
                f"Maximum profit: {max_profit} points"
            ),
            color=0x3498db
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)
        return embed

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
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

        tokens_balance = user_data['tokens']
        credits_balance = user_data['credits']

        # Determine if the user can make the same bet or needs to use max available
        if tokens_balance + credits_balance < self.bet_amount:
            # User doesn't have enough for the same bet - use max instead
            bet_amount = tokens_balance + credits_balance
            if bet_amount <= 0:
                return await interaction.followup.send("You don't have enough funds to play again.", ephemeral=True)

            # Ask user to confirm playing with max amount
            confirm_embed = discord.Embed(
                title="⚠️ Insufficient Funds for Same Bet",
                description=f"You don't have enough to bet {self.bet_amount:.2f} again.\nWould you like to bet your maximum available amount ({bet_amount:.2f}) instead?",
                color=0xFFAA00
            )

            confirm_view = discord.ui.View(timeout=30)

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
            async def confirm_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)

                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)

                # Start a new game with max amount
                await self.cog.plinko(self.ctx, str(bet_amount))

            @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
            async def cancel_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)

                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                await i.followup.send("Plinko game cancelled.", ephemeral=True)

            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
        else:
            # User can afford the same bet
            await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
            await self.cog.plinko(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True

        # Try to update the message if it exists
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"Error updating message on timeout: {e}")


class PlinkoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

        # Define difficulty settings
        self.difficulty_settings = {
            "LOW": {
                "left_prob": 0.5,    # 50% chance to go left at each peg
                "variance": 0.1      # Small variance in probabilities
            },
            "MEDIUM": {
                "left_prob": 0.5,
                "variance": 0.15
            },
            "HIGH": {
                "left_prob": 0.5,
                "variance": 0.2
            },
            "EXTREME": {
                "left_prob": 0.5,
                "variance": 0.25
            }
        }

        # Multiplier templates for different row counts
        # Each list represents the multipliers from left to right
        self.multiplier_templates = {
            8: {
                "LOW": [5, 2, 1.4, 1, 0.5, 1, 1.4, 2, 5],
                "MEDIUM": [7, 2, 1.2, 0.8, 0.3, 0.8, 1.2, 2, 7],
                "HIGH": [10, 3, 1.3, 0.7, 0.2, 0.7, 1.3, 3, 10],
                "EXTREME": [15, 5, 1, 0.5, 0.1, 0.5, 1, 5, 15]
            },
            12: {
                "LOW": [9, 3, 1.5, 1.3, 1.1, 0.9, 0.4, 0.9, 1.1, 1.3, 1.5, 3, 9],
                "MEDIUM": [12, 4, 2, 1.3, 0.9, 0.6, 0.2, 0.6, 0.9, 1.3, 2, 4, 12],
                "HIGH": [18, 6, 2, 1.2, 0.7, 0.4, 0.1, 0.4, 0.7, 1.2, 2, 6, 18],
                "EXTREME": [30, 10, 3, 1, 0.5, 0.2, 0.05, 0.2, 0.5, 1, 3, 10, 30]
            },
            16: {
                "LOW": [14, 8, 4, 2, 1.5, 1.3, 1.1, 0.9, 0.4, 0.9, 1.1, 1.3, 1.5, 2, 4, 8, 14],
                "MEDIUM": [20, 10, 5, 2.5, 1.5, 1, 0.7, 0.5, 0.2, 0.5, 0.7, 1, 1.5, 2.5, 5, 10, 20],
                "HIGH": [30, 15, 6, 3, 1.5, 0.8, 0.5, 0.3, 0.1, 0.3, 0.5, 0.8, 1.5, 3, 6, 15, 30],
                "EXTREME": [50, 25, 10, 5, 2, 1, 0.5, 0.2, 0.05, 0.2, 0.5, 1, 2, 5, 10, 25, 50]
            }
        }

    def get_multipliers(self, difficulty, rows):
        """Get multipliers for a specific difficulty and row count"""
        # If the exact row count exists in templates, use it
        if rows in self.multiplier_templates:
            return self.multiplier_templates[rows][difficulty]

        # Otherwise, interpolate between the closest templates
        templates = sorted(self.multiplier_templates.keys())
        if rows < templates[0]:
            # Use the smallest template with adjusted size
            base_multipliers = self.multiplier_templates[templates[0]][difficulty]
            # Scale down to match the desired row count
            return self._scale_multipliers(base_multipliers, rows + 1)
        elif rows > templates[-1]:
            # Use the largest template with adjusted size
            base_multipliers = self.multiplier_templates[templates[-1]][difficulty]
            # Scale up to match the desired row count
            return self._scale_multipliers(base_multipliers, rows + 1)
        else:
            # Find the closest templates to interpolate between
            lower_template = max([t for t in templates if t <= rows])
            upper_template = min([t for t in templates if t >= rows])

            if lower_template == upper_template:
                return self.multiplier_templates[lower_template][difficulty]

            # Interpolate between the two closest templates
            lower_multipliers = self.multiplier_templates[lower_template][difficulty]
            upper_multipliers = self.multiplier_templates[upper_template][difficulty]

            # Scale the multipliers to match the desired row count
            return self._scale_multipliers(lower_multipliers, rows + 1)

    def _scale_multipliers(self, base_multipliers, target_slots):
        """Scale a set of multipliers to have the correct length"""
        if len(base_multipliers) == target_slots:
            return base_multipliers

        # Simple approach: create a new list with the correct number of slots
        result = []
        # Always include the highest multipliers on the edges
        highest_multiplier = max(base_multipliers)
        result.append(highest_multiplier)  # Leftmost

        # Fill in the middle slots
        middle_slots = target_slots - 2
        if middle_slots > 0:
            middle_values = base_multipliers[1:-1]
            # If we have fewer or more values than needed, we need to interpolate
            if len(middle_values) != middle_slots:
                step = (len(middle_values) - 1) / (middle_slots - 1) if middle_slots > 1 else 0
                for i in range(middle_slots):
                    idx = min(i * step, len(middle_values) - 1)
                    # Linear interpolation between the two closest values
                    lower_idx = int(idx)
                    upper_idx = min(lower_idx + 1, len(middle_values) - 1)
                    fraction = idx - lower_idx

                    if lower_idx == upper_idx:
                        value = middle_values[lower_idx]
                    else:
                        value = middle_values[lower_idx] * (1 - fraction) + middle_values[upper_idx] * fraction
                    result.append(value)
            else:
                result.extend(middle_values)

        result.append(highest_multiplier)  # Rightmost
        return result

    @commands.command(aliases=["pl"])
    async def plinko(self, ctx, bet_amount: str = None, difficulty: str = None, rows: int = None):
        """Play Plinko - watch the ball bounce through pegs to determine your win!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🎮 How to Play Plinko",
                description=(
                    "**Plinko** is a game where a ball drops through a pegboard and lands in a prize slot.\n\n"
                    "**Usage:** `!plinko <amount> [difficulty] [rows]`\n"
                    "**Example:** `!plinko 100` or `!plinko 100 low 12`\n\n"
                    "- **Difficulty determines risk vs. reward (LOW, MEDIUM, HIGH, EXTREME)**\n"
                    "- **More rows = more bounces and different multiplier distributions**\n"
                    "- **The ball bounces unpredictably through the pegs**\n"
                    "- **Land in high multiplier slots to win big!**\n"
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

        # Send loading message
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Preparing Plinko Game...",
            description="Please wait while we set up your game.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Process bet amount
        db = Users()
        user_data = db.fetch_user(ctx.author.id)

        if user_data == False:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="You don't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Validate bet amount
        try:
            # Handle 'all' or 'max' bet
            if bet_amount.lower() in ['all', 'max']:
                bet_amount_value = user_data['tokens'] + user_data['credits']
            else:
                # Check if bet has 'k' or 'm' suffix
                if bet_amount.lower().endswith('k'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000
                elif bet_amount.lower().endswith('m'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000000
                else:
                    bet_amount_value = float(bet_amount)

            bet_amount_value = float(bet_amount_value)  # Keep as float to support decimals

            if bet_amount_value <= 0:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        except ValueError:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Amount",
                description="Please enter a valid number or 'all'.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Get user balances
        tokens_balance = user_data['tokens']
        credits_balance = user_data['credits']

        # Determine which currency to use 
        tokens_used = 0
        credits_used = 0

        # Auto determine what to use
        if bet_amount_value <= tokens_balance:
            tokens_used = bet_amount_value
        elif bet_amount_value <= credits_balance:
            credits_used = bet_amount_value
        elif bet_amount_value <= tokens_balance + credits_balance:
            # Use all tokens and some credits
            tokens_used = tokens_balance
            credits_used = bet_amount_value - tokens_balance
        else:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough funds. Your balance: **{tokens_balance:.2f} tokens** and **{credits_balance:.2f} credits**",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Deduct from user balances
        if tokens_used > 0:
            db.update_balance(ctx.author.id, tokens_balance - tokens_used, "tokens")

        if credits_used > 0:
            db.update_balance(ctx.author.id, credits_balance - credits_used, "credits")

        # Get total amount bet
        total_bet = tokens_used + credits_used

        # Record game stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": total_bet}}
        )

        # Format bet description
        if tokens_used > 0 and credits_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used:.2f} tokens + {credits_used:.2f} credits"
        elif tokens_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used:.2f} tokens"
        else:
            bet_description = f"**Bet Amount:** {credits_used:.2f} credits"

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": total_bet
        }

        # Delete loading message
        await loading_message.delete()

        # If difficulty and rows are provided, start the game directly
        if difficulty and rows:
            try:
                difficulty = difficulty.upper()
                rows = int(rows)

                # Validate difficulty
                if difficulty not in self.difficulty_settings:
                    difficulty = "LOW"  # Default to LOW if invalid

                # Validate rows (ensure between 8 and 16)
                rows = max(8, min(16, rows))

                # Start the game
                await self.start_plinko_game(ctx, total_bet, difficulty, rows)
            except Exception as e:
                print(f"Error starting direct plinko game: {e}")
                # Fallback to setup view
                await self.show_setup_view(ctx, total_bet)
        else:
            # Show the setup view for the user to select difficulty and rows
            await self.show_setup_view(ctx, total_bet)

    async def show_setup_view(self, ctx, bet_amount):
        """Show the setup view for selecting difficulty and rows"""
        setup_view = PlinkoSetupView(self, ctx, bet_amount)
        embed = setup_view.create_setup_embed()
        await ctx.reply(embed=embed, view=setup_view)

    async def start_plinko_game(self, ctx, bet_amount, difficulty, rows):
        """Start the actual Plinko game with selected settings"""
        try:
            # Get the multipliers for this difficulty and row count
            multipliers = self.get_multipliers(difficulty, rows)

            # Simulate the ball's path
            path, landing_position = self.simulate_plinko(rows, difficulty)

            # Get the multiplier at the landing position
            multiplier = multipliers[landing_position]

            # Calculate winnings
            winnings = bet_amount * multiplier

            # Generate the Plinko board image
            plinko_image = self.generate_plinko_image(rows, path, landing_position, multipliers)

            # Create results embed
            if multiplier >= 1:
                result_color = 0x00FF00  # Green for win
                result_title = "✅ | Plinko Results"
            else:
                result_color = 0xFF0000  # Red for loss
                result_title = "❌ | Plinko Results"

            # Create file from the image
            img_buffer = io.BytesIO()
            plinko_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            file = discord.File(img_buffer, filename="plinko_result.png")

            # Create embed with results
            result_embed = discord.Embed(
                title=result_title,
                description=f"You won {winnings:.2f} points ({multiplier:.2f}x)! 🎉",
                color=result_color
            )
            result_embed.add_field(
                name="Details", 
                value=f"Difficulty: {difficulty} - Rows: {rows}\nPlayed by: \"{ctx.author.name}\"",
                inline=False
            )
            result_embed.set_image(url="attachment://plinko_result.png")
            result_embed.set_footer(text="BetSync Casino", icon_url=ctx.bot.user.avatar.url)

            # Create a play again view
            play_again_view = PlayAgainView(self, ctx, bet_amount)

            # Send the result
            message = await ctx.reply(embed=result_embed, file=file, view=play_again_view)
            play_again_view.message = message

            # Get database connection
            db = Users()

            # Process the game outcome
            if winnings > 0:
                # Credit the user with winnings
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")

                # Add to win history
                win_entry = {
                    "type": "win",
                    "game": "plinko",
                    "bet": bet_amount,
                    "amount": winnings,
                    "multiplier": multiplier,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$push": {"history": {"$each": [win_entry], "$slice": -100}}}
                )

                # Update server history
                server_db = Servers()
                server_data = server_db.fetch_server(ctx.guild.id)

                if server_data:
                    server_win_entry = {
                        "type": "win",
                        "game": "plinko",
                        "user_id": ctx.author.id,
                        "user_name": ctx.author.name,
                        "bet": bet_amount,
                        "amount": winnings,
                        "multiplier": multiplier,
                        "timestamp": int(time.time())
                    }
                    server_db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
                    )

                # Update user stats
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$inc": {"total_won": 1, "total_earned": winnings}}
                )

                # If user lost money overall, update server profit
                if winnings < bet_amount:
                    profit = bet_amount - winnings
                    server_db.update_server_profit(ctx.guild.id, profit)
                else:
                    # User won more than bet, server has a loss
                    loss = winnings - bet_amount
                    server_db.update_server_profit(ctx.guild.id, -loss)
            else:
                # Add to loss history
                loss_entry = {
                    "type": "loss",
                    "game": "plinko",
                    "bet": bet_amount,
                    "amount": bet_amount,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$push": {"history": {"$each": [loss_entry], "$slice": -100}}}
                )

                # Update server history
                server_db = Servers()
                server_data = server_db.fetch_server(ctx.guild.id)

                if server_data:
                    server_loss_entry = {
                        "type": "loss",
                        "game": "plinko",
                        "user_id": ctx.author.id,
                        "user_name": ctx.author.name,
                        "bet": bet_amount,
                        "timestamp": int(time.time())
                    }
                    server_db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
                    )

                    # Update server profit
                    server_db.update_server_profit(ctx.guild.id, bet_amount)

                # Update user stats
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$inc": {"total_lost": 1}}
                )

            # Clear the ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

        except Exception as e:
            print(f"Error in plinko game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing plinko. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    def simulate_plinko(self, rows, difficulty):
        """
        Simulate the path of a ball through the Plinko board
        Returns the path and the final landing position
        """
        # Get difficulty settings
        settings = self.difficulty_settings[difficulty]
        base_prob = settings["left_prob"]  # Base probability of going left
        variance = settings["variance"]    # Variance in probabilities

        # Initialize the path
        path = [(0, 0)]  # Start at the top (row 0, col 0)

        # For each row, determine if the ball goes left or right
        for row in range(rows):
            x, y = path[-1]

            # Add some randomness to the probability for each peg
            # This makes the path less predictable
            adjusted_prob = base_prob + (random.random() - 0.5) * variance

            # Determine if the ball goes left or right
            if random.random() < adjusted_prob:
                # Ball goes left
                next_x = x
            else:
                # Ball goes right
                next_x = x + 1

            # Add the new position to the path
            path.append((next_x, y + 1))

        # The landing position is the x-coordinate in the final row
        landing_position = path[-1][0]

        return path, landing_position

    def generate_plinko_image(self, rows, path, landing_position, multipliers):
        """Generate an image of the Plinko board with the ball's path"""
        # Define colors and sizes
        bg_color = (33, 33, 33)        # Dark background
        peg_color = (200, 200, 200)    # Light gray pegs
        ball_color = (0, 255, 0)       # Green ball
        path_color = (0, 200, 0, 128)  # Semi-transparent green path
        text_color = (255, 255, 255)   # White text
        multiplier_colors = {
            'high': (255, 50, 50),     # Red for high multipliers
            'medium': (255, 165, 0),   # Orange
            'low': (255, 255, 0),      # Yellow for low multipliers
            'very_low': (150, 150, 150)  # Gray for very low multipliers
        }

        # Base dimensions
        width = 800
        height = 800

        # Scale elements based on row count to prevent cutting off
        scale_factor = 1.0
        if rows >= 11:
            # Gradually reduce size as rows increase
            scale_factor = 1.0 - ((rows - 10) * 0.05)
            scale_factor = max(0.7, scale_factor)  # Don't go below 70% scaling

        # Adjust sizes based on scale factor
        peg_radius = int(10 * scale_factor)
        ball_radius = int(15 * scale_factor)

        # Create a new image with dark background
        img = Image.new('RGBA', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Add the "BetSync Plinko" watermark with consistent coloring
        watermark_font = ImageFont.truetype("roboto.ttf", int(80 * scale_factor))
        watermark_text = "BetSync"
        # Always use white with transparency for watermark
        watermark_color = (255, 255, 255, 30)
        draw.text((width//2, height//2), watermark_text, font=watermark_font, fill=watermark_color, anchor="mm")
        draw.text((width//2, height//2 + int(80 * scale_factor)), "Plinko", font=watermark_font, fill=watermark_color, anchor="mm")

        # Calculate spacing based on rows
        horizontal_spacing = width / (rows + 1)
        # Increase the divisor to create more vertical space for multipliers at bottom
        vertical_spacing = height / (rows + 2.5)  # +2.5 to leave more room for multipliers

        # Draw the pegs
        for row in range(rows + 1):
            for col in range(row + 1):
                x = (width - row * horizontal_spacing) / 2 + col * horizontal_spacing
                y = vertical_spacing + row * vertical_spacing

                # Check if this peg is part of the ball's path
                peg_in_path = False
                for path_x, path_y in path:
                    if path_y == row and path_x == col:
                        peg_in_path = True
                        break

                # Draw the peg
                if peg_in_path:
                    # Draw ball path (slightly larger circle behind the peg)
                    draw.ellipse((x - ball_radius, y - ball_radius, x + ball_radius, y + ball_radius), fill=path_color)

                # Always draw the peg
                draw.ellipse((x - peg_radius, y - peg_radius, x + peg_radius, y + peg_radius), fill=peg_color)

        # Draw the landing slots (bottom row)
        slot_width = width / len(multipliers)
        slot_height = 40
        slot_y = vertical_spacing + rows * vertical_spacing + 30  # Below the last row of pegs

        # Draw the multipliers
        multiplier_font = ImageFont.truetype("roboto.ttf", int(20 * scale_factor))
        for i, multiplier in enumerate(multipliers):
            # Determine color based on multiplier value
            if multiplier >= 5:
                color = multiplier_colors['high']
            elif multiplier >= 1:
                color = multiplier_colors['medium'] 
            elif multiplier >= 0.5:
                color = multiplier_colors['low']
            else:
                color = multiplier_colors['very_low']

            # Draw multiplier text
            x = i * slot_width + slot_width / 2
            y = slot_y + int(20 * scale_factor)
            multiplier_text = f"{multiplier:.1f}x" #Reduce decimal places for better readability at smaller scales
            draw.text((x, y), multiplier_text, font=multiplier_font, fill=color, anchor="mm")

            # Highlight the landing slot
            if i == landing_position:
                # Draw a rectangle around the winning multiplier
                padding = int(5 * scale_factor)
                text_bbox = draw.textbbox((x, y), multiplier_text, font=multiplier_font, anchor="mm")
                draw.rectangle(
                    (
                        text_bbox[0] - padding,
                        text_bbox[1] - padding,
                        text_bbox[2] + padding,
                        text_bbox[3] + padding
                    ),
                    outline=ball_color,
                    width=int(2 * scale_factor)
                )

        # Draw the ball at its final position
        final_x, final_y = path[-1]
        ball_x = (width - rows * horizontal_spacing) / 2 + final_x * horizontal_spacing
        # Position ball centered in the bucket
        bucket_center_y = vertical_spacing + rows * vertical_spacing + (vertical_spacing * 0.5)
        ball_y = bucket_center_y - (vertical_spacing * 0.25)  # Position ball slightly above center for better visibility

        # First draw an outline (simple anti-aliasing)
        draw.ellipse((ball_x - ball_radius - 2, ball_y - ball_radius - 2, 
                      ball_x + ball_radius + 2, ball_y + ball_radius + 2), fill=(0, 0, 0))
        # Then draw the actual ball
        draw.ellipse((ball_x - ball_radius, ball_y - ball_radius, 
                      ball_x + ball_radius, ball_y + ball_radius), fill=ball_color)

        return img

    @plinko.before_invoke
    async def before_plinko(self, ctx):
        # Ensure the user has an account
        db = Users()
        if db.fetch_user(ctx.author.id) == False:
            dump = {
                "discord_id": ctx.author.id,
                "tokens": 0,
                "credits": 0, 
                "history": [],
                "total_deposit_amount": 0,
                "total_withdraw_amount": 0,
                "total_spent": 0,
                "total_earned": 0,
                'total_played': 0,
                'total_won': 0,
                'total_lost': 0
            }
            db.register_new_user(dump)

            embed = discord.Embed(
                title=":wave: Welcome to BetSync Casino!",
                color=0x00FFAE,
                description="**Type** `!guide` **to get started**"
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await ctx.reply("By using BetSync, you agree to our TOS. Type `!tos` to know more.", embed=embed)


def setup(bot):
    bot.add_cog(PlinkoCog(bot))