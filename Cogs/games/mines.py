import discord
import random
import asyncio
import time
import math
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, mines_count=None, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.mines_count = mines_count
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
                if self.mines_count:
                    await self.cog.mines(self.ctx, str(bet_amount), None, str(self.mines_count))
                else:
                    await self.cog.mines(self.ctx, str(bet_amount))

            @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
            async def cancel_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)

                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                await i.followup.send("Mines game cancelled.", ephemeral=True)

            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
        else:
            # User can afford the same bet
            await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
            if self.mines_count:
                await self.cog.mines(self.ctx, str(self.bet_amount), None, str(self.mines_count))
            else:
                await self.cog.mines(self.ctx, str(self.bet_amount))

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


class MinesTileView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, mines_count, board_size=5, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.mines_count = mines_count
        self.board_size = board_size

        # Create 5x5 grid of mine locations (True = mine, False = safe)
        self.mine_locations = []
        self.generate_mines()

        # Track revealed tiles
        self.revealed_tiles = []

        # Track game state
        self.game_over = False
        self.cashed_out = False
        self.current_multiplier = 1.0
        self.message = None

        # Generate buttons for the 5x5 grid (using emojis instead of buttons)
        # We'll use a single reaction emoji to reveal tiles

    def generate_mines(self):
        """Generate random mine locations"""
        total_cells = self.board_size * self.board_size
        mine_indices = random.sample(range(total_cells), self.mines_count)

        # Create a flat list first, then convert to 2D grid
        flat_grid = [False] * total_cells
        for idx in mine_indices:
            flat_grid[idx] = True

        # Convert to 2D grid for easier access
        self.mine_locations = []
        for i in range(self.board_size):
            row = flat_grid[i * self.board_size : (i+1) * self.board_size]
            self.mine_locations.append(row)

    def get_multiplier(self, revealed_count):
        """Calculate multiplier based on number of revealed cells"""
        total_cells = self.board_size * self.board_size
        remaining_cells = total_cells - revealed_count
        safe_cells = total_cells - self.mines_count
        remaining_safe = safe_cells - revealed_count

        # Base formula with house edge of ~3-5%
        house_edge = 0.96  # 4% house edge

        if remaining_safe == 0:
            # All safe cells revealed, max multiplier
            return (total_cells / safe_cells) * house_edge

        # Calculate fair multiplier and apply house edge
        multiplier = (total_cells - revealed_count) / (total_cells - self.mines_count - revealed_count) * house_edge

        # Round to 2 decimal places
        return round(multiplier, 2)

    def is_game_over(self, row, col):
        """Check if the selected cell contains a mine"""
        return self.mine_locations[row][col]

    def get_board_display(self, reveal_all=False):
        """Generate visual representation of the board"""
        board_display = []
        for row in range(self.board_size):
            row_display = []
            for col in range(self.board_size):
                pos = (row, col)

                if reveal_all:
                    # Show all mines and gems
                    if self.mine_locations[row][col]:
                        row_display.append("💣")  # Mine
                    else:
                        row_display.append("💎")  # Gem
                elif pos in self.revealed_tiles:
                    # Show revealed tile
                    row_display.append("💎")  # Gem (safe tile)
                else:
                    # Show unrevealed tile
                    row_display.append("❓")  # Unrevealed

            board_display.append(" ".join(row_display))

        return "\n".join(board_display)

    def create_embed(self, status="playing"):
        """Create embed for current game state"""
        # Format bet amount
        bet_description = f"**Bet Amount:** {self.bet_amount:.2f} credits"

        # Calculate current profit
        potential_winnings = self.bet_amount * self.current_multiplier
        profit = potential_winnings - self.bet_amount

        if status == "playing":
            embed = discord.Embed(
                title="💎 | Mines Game",
                description=(
                    f"{bet_description}\n"
                    f"**Mines:** {self.mines_count}/{self.board_size*self.board_size}\n"
                    f"**Current Multiplier:** {self.current_multiplier:.2f}x\n"
                    f"**Potential Winnings:** {potential_winnings:.2f} credits\n"
                    f"**Profit:** {profit:.2f} credits\n\n"
                    "Type a position (e.g., `A1`, `C3`) to reveal a tile or type `cash out` to take your winnings!\n\n"
                    "⏰ This game will timeout after 2 minutes. If you've revealed tiles, you'll auto-cashout."
                ),
                color=0x00FFAE
            )

            # Add column labels (A-E) and row numbers (1-5)
            board_with_labels = "⠀⠀A⠀⠀B⠀⠀C⠀⠀D⠀⠀E\n"  # Using invisible character for alignment
            board_lines = self.get_board_display().split("\n")
            for i, line in enumerate(board_lines):
                board_with_labels += f"{i+1} {line}\n"

            embed.add_field(name="Game Board", value=board_with_labels, inline=False)

        elif status == "win":
            embed = discord.Embed(
                title="💰 | You Cashed Out!",
                description=(
                    f"{bet_description}\n"
                    f"**Mines:** {self.mines_count}/{self.board_size*self.board_size}\n"
                    f"**Final Multiplier:** {self.current_multiplier:.2f}x\n"
                    f"**Winnings:** {potential_winnings:.2f} credits\n"
                    f"**Profit:** {profit:.2f} credits\n\n"
                    "Congratulations! You've successfully cashed out."
                ),
                color=0x00FF00
            )

            # Show full board with mines revealed
            board_with_labels = "⠀⠀A⠀⠀B⠀⠀C⠀⠀D⠀⠀E\n"
            board_lines = self.get_board_display(reveal_all=True).split("\n")
            for i, line in enumerate(board_lines):
                board_with_labels += f"{i+1} {line}\n"

            embed.add_field(name="Game Board", value=board_with_labels, inline=False)

        elif status == "lose":
            embed = discord.Embed(
                title="💣 | Game Over!",
                description=(
                    f"{bet_description}\n"
                    f"**Mines:** {self.mines_count}/{self.board_size*self.board_size}\n"
                    f"**Final Multiplier:** {self.current_multiplier:.2f}x\n"
                    f"**Winnings:** 0 credits\n\n"
                    "You hit a mine! Better luck next time."
                ),
                color=0xFF0000
            )

            # Show full board with mines revealed
            board_with_labels = "⠀⠀A⠀⠀B⠀⠀C⠀⠀D⠀⠀E\n"
            board_lines = self.get_board_display(reveal_all=True).split("\n")
            for i, line in enumerate(board_lines):
                board_with_labels += f"{i+1} {line}\n"

            embed.add_field(name="Game Board", value=board_with_labels, inline=False)

        embed.set_footer(text="BetSync Casino", icon_url=self.cog.bot.user.avatar.url)
        return embed

    async def process_win(self, ctx):
        """Process a win when user cashes out"""
        db = Users()
        total_winnings = self.bet_amount * self.current_multiplier

        # Give credits to the user
        db.update_balance(ctx.author.id, total_winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "mines",
            "bet": self.bet_amount,
            "amount": total_winnings,
            "multiplier": self.current_multiplier,
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
                "game": "mines",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": self.bet_amount,
                "amount": total_winnings,
                "multiplier": self.current_multiplier,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": total_winnings}}
        )

        # Update server profit (negative because player won)
        profit = self.bet_amount - total_winnings
        server_db.update_server_profit(ctx.guild.id, profit)

    async def process_loss(self, ctx):
        """Process a loss when user hits a mine"""
        db = Users()

        # Add to loss history
        loss_entry = {
            "type": "loss",
            "game": "mines",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
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
                "game": "mines",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": self.bet_amount,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
            )

            # Update server profit
            server_db.update_server_profit(ctx.guild.id, self.bet_amount)

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_lost": 1}}
        )

    async def on_timeout(self):
        """Handle timeout - auto cash out if possible"""
        if not self.game_over and not self.cashed_out and len(self.revealed_tiles) > 0:
            # Auto cash out
            self.cashed_out = True

            try:
                # Process winnings
                await self.process_win(self.ctx)

                # Update message with win state
                embed = self.create_embed(status="win")

                # Create play again view
                play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount, self.mines_count, timeout=15)
                await self.message.edit(embed=embed, view=play_again_view)
                play_again_view.message = self.message

                # Clear game from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]

            except Exception as e:
                print(f"Error in auto cash out: {e}")
        elif not self.game_over and not self.cashed_out and len(self.revealed_tiles) == 0:
            # Deduct bet amount if no tiles revealed
            db = Users()
            db.update_balance(self.ctx.author.id, self.bet_amount, "credits")
            await self.message.edit(content = f"Time ran out! You did not reveal any tiles. Your bet of {self.bet_amount:.2f} credits has been deducted.")

        else:
            # Just disable the view
            if self.message:
                try:
                    await self.message.edit(view=None)
                except:
                    pass


class MinesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    async def handle_tile_selection(self, message, ctx, game_view):
        """Handle tile selection via message"""
        if game_view.game_over or game_view.cashed_out:
            return

        # Parse the position (like A1, B3, etc.)
        content = message.content.upper()

        # Check for cash out
        if content.lower() in ["CASH OUT", "CASHOUT", "CASH", "OUT", "STOP"]:
            if len(game_view.revealed_tiles) > 0:
                # User wants to cash out
                game_view.cashed_out = True

                # Process win
                await game_view.process_win(ctx)

                # Update message with win state
                embed = game_view.create_embed(status="win")

                # Create play again view with 15-second timeout
                play_again_view = PlayAgainView(self, ctx, game_view.bet_amount, game_view.mines_count, timeout=15)
                await game_view.message.edit(embed=embed, view=play_again_view)
                play_again_view.message = game_view.message

                # Clear game from ongoing games
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]
            else:
                # Can't cash out before revealing any tiles
                await ctx.send("You need to reveal at least one tile before cashing out.", delete_after=5)

            return

        # Check for position format (A1, B3, etc.)
        if len(content) != 2 or not content[0].isalpha() or not content[1].isdigit():
            return

        # Convert letter to column (A=0, B=1, etc.)
        try:
            col = ord(content[0]) - ord('A')
            # Convert number to row (1=0, 2=1, etc.)
            row = int(content[1]) - 1

            # Check if valid position
            if row < 0 or row >= game_view.board_size or col < 0 or col >= game_view.board_size:
                return

            # Check if already revealed
            if (row, col) in game_view.revealed_tiles:
                await ctx.send("That tile is already revealed. Choose another position.", delete_after=5)
                return

            # Check if it's a mine
            if game_view.is_game_over(row, col):
                # Game over - hit a mine
                game_view.game_over = True

                # Process loss
                await game_view.process_loss(ctx)

                # Update message with loss state
                embed = game_view.create_embed(status="lose")

                # Create play again view with 15-second timeout
                play_again_view = PlayAgainView(self, ctx, game_view.bet_amount, game_view.mines_count, timeout=15)
                await game_view.message.edit(embed=embed, view=play_again_view)
                play_again_view.message = game_view.message

                # Clear game from ongoing games
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]

                return

            # Reveal tile and update multiplier
            game_view.revealed_tiles.append((row, col))
            game_view.current_multiplier = game_view.get_multiplier(len(game_view.revealed_tiles))

            # Update message with new board state
            embed = game_view.create_embed(status="playing")
            await game_view.message.edit(embed=embed)

        except Exception as e:
            print(f"Error handling tile selection: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for tile selections from active games"""
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if user has an active game
        if message.author.id in self.ongoing_games:
            ctx = await self.bot.get_context(message)
            if ctx.command is None:  # Only process if not a command
                game_data = self.ongoing_games.get(message.author.id)
                if game_data and "view" in game_data:
                    await self.handle_tile_selection(message, ctx, game_data["view"])

    def calculate_max_mines(self):
        """Calculate maximum mines possible on a 5x5 grid"""
        # We need at least one safe tile
        return 24  # 5x5 grid - 1 safe tile

    @commands.command(aliases=["mine", "m"])
    async def mines(self, ctx, bet_amount: str = None, currency_type: str = None, mines_count: str = None):
        """Play the mines game - avoid the mines and cash out with a profit!"""
        if not bet_amount:
            # Show usage embed
            embed = discord.Embed(
                title="💎 How to Play Mines",
                description=(
                    "**Mines** is a game where you reveal tiles to find gems while avoiding mines.\n\n"
                    "**Usage:** `!mines <amount> [currency_type] [mine_count]`\n"
                    "**Example:** `!mines 100` or `!mines 100 tokens 5`\n\n"
                    "- **Reveal tiles by typing the position (e.g., A1, C3)**\n"
                    "- **Each safe tile increases your multiplier**\n"
                    "- **Type `cash out` to take your winnings at any time**\n"
                    "- **Hit a mine and you lose your bet**\n"
                    f"- **You can set 1-24 mines (default is 5)**\n"
                    "**Game Timeout:** 2 minutes. Auto cash-out if you have revealed any tiles before the timeout.\n"
                    "**Play Again Timeout:** 15 seconds after the game ends."
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
            title=f"{loading_emoji} | Preparing Mines Game...",
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

        # Format currency type if provided    
        if currency_type:
            currency_type = currency_type.lower()
            # Allow shorthand T for tokens and C for credits
            if currency_type == 't':
                currency_type = 'tokens'
            elif currency_type == 'c':
                currency_type = 'credits'
            elif currency_type.isdigit():
                # User may have specified mine count as second parameter
                mines_count = currency_type
                currency_type = None

        # Set default mines count
        if mines_count is None:
            mines_count = 5
        else:
            try:
                mines_count = int(mines_count)
                max_mines = self.calculate_max_mines()

                if mines_count < 1:
                    mines_count = 1
                    await ctx.send(f"Mines count must be at least 1. Setting to 1 mine.", delete_after=5)
                elif mines_count > max_mines:
                    mines_count = max_mines
                    await ctx.send(f"Maximum mines allowed is {max_mines}. Setting to {max_mines} mines.", delete_after=5)
            except ValueError:
                mines_count = 5
                await ctx.send("Invalid mines count. Using default of 5 mines.", delete_after=5)

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

        # Determine which currency to use based on the logic:
        # 1. If specific currency requested, try to use that
        # 2. If has enough tokens, use tokens
        # 3. If not enough tokens but enough credits, use credits
        # 4. If neither is enough alone but combined they work, use both
        tokens_used = 0
        credits_used = 0

        if currency_type == 'tokens':
            # User specifically wants to use tokens
            if bet_amount_value <= tokens_balance:
                tokens_used = bet_amount_value
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Tokens",
                    description=f"You don't have enough tokens. Your balance: **{tokens_balance:.2f} tokens**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        elif currency_type == 'credits':
            # User specifically wants to use credits
            if bet_amount_value <= credits_balance:
                credits_used = bet_amount_value
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Credits",
                    description=f"You don't have enough credits. Your balance: **{credits_balance:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:
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

        # Create game view
        game_view = MinesTileView(self, ctx, total_bet, mines_count)

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": total_bet,
            "mines_count": mines_count,
            "view": game_view
        }

        # Delete loading message
        await loading_message.delete()

        # Send initial game message
        initial_embed = game_view.create_embed(status="playing")
        game_message = await ctx.reply(embed=initial_embed)

        # Store message reference in game view
        game_view.message = game_message

        # Inform user how to play
        instruction_message = await ctx.send(
            "💡 **How to play:** Type a position (like `A1` or `C3`) to reveal a tile. Type `cash out` to collect your winnings.  The game will timeout after 2 minutes.",
            delete_after=10
        )


def setup(bot):
    bot.add_cog(MinesCog(bot))