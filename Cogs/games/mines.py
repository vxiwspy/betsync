
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji


class MineButton(discord.ui.Button):
    def __init__(self, row, col, parent_view):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="?",
            row=row
        )
        self.row_idx = row
        self.col_idx = col
        self.parent_view = parent_view
        self.revealed = False
        self.is_mine = False
        self.update_appearance()

    def update_appearance(self):
        if not self.revealed:
            self.style = discord.ButtonStyle.primary
            self.label = "?"
            self.emoji = None
        elif self.is_mine:
            self.style = discord.ButtonStyle.danger
            self.label = ""
            self.emoji = "💣"
        else:
            self.style = discord.ButtonStyle.success
            self.label = ""
            self.emoji = "💎"
        
        # Disable if revealed or game over
        self.disabled = self.revealed or self.parent_view.game_over or self.parent_view.cashed_out

    async def callback(self, interaction: discord.Interaction):
        # Check if it's the player's turn
        if interaction.user.id != self.parent_view.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Check if game is already over
        if self.parent_view.game_over or self.parent_view.cashed_out:
            return await interaction.response.defer()
        
        # Calculate position in flat grid
        position = self.row_idx * self.parent_view.board_size + self.col_idx
        
        # Check if this tile is a mine
        self.is_mine = self.parent_view.mine_locations[self.row_idx][self.col_idx]
        self.revealed = True
        
        if self.is_mine:
            # Game over - player hit a mine
            self.parent_view.game_over = True
            
            # Reveal all mines
            for row in range(self.parent_view.board_size):
                for col in range(self.parent_view.board_size):
                    button = self.parent_view.get_button(row, col)
                    if self.parent_view.mine_locations[row][col]:
                        button.is_mine = True
                        button.revealed = True
                    button.update_appearance()
            
            # Update the message
            embed = self.parent_view.create_embed(status="lose")
            await interaction.response.edit_message(embed=embed, view=self.parent_view)
            
            # Process loss
            await self.parent_view.process_loss(self.parent_view.ctx)
            
            # Create play again view
            play_again_view = PlayAgainView(
                self.parent_view.cog, 
                self.parent_view.ctx, 
                self.parent_view.bet_amount, 
                self.parent_view.mines_count,
                timeout=15
            )
            play_again_view.message = self.parent_view.message
            
            # Edit message with play again button
            await self.parent_view.message.edit(view=play_again_view)
            
            # Clear from ongoing games
            if self.parent_view.ctx.author.id in self.parent_view.cog.ongoing_games:
                del self.parent_view.cog.ongoing_games[self.parent_view.ctx.author.id]
                
        else:
            # Safe tile revealed
            if position not in self.parent_view.revealed_tiles:
                self.parent_view.revealed_tiles.append(position)
                
                # Calculate new multiplier
                self.parent_view.update_multiplier()
                
                # Update all buttons
                for row in range(self.parent_view.board_size):
                    for col in range(self.parent_view.board_size):
                        self.parent_view.get_button(row, col).update_appearance()
                
                # Update the message
                embed = self.parent_view.create_embed(status="playing")
                await interaction.response.edit_message(embed=embed, view=self.parent_view)
                
                # Check if all safe tiles revealed (auto cash out)
                if len(self.parent_view.revealed_tiles) == (self.parent_view.board_size * self.parent_view.board_size) - self.parent_view.mines_count:
                    # Auto cash out
                    self.parent_view.cashed_out = True
                    
                    # Process win
                    await self.parent_view.process_win(self.parent_view.ctx)
                    
                    # Update message with win state
                    embed = self.parent_view.create_embed(status="win")
                    
                    # Create play again view
                    play_again_view = PlayAgainView(
                        self.parent_view.cog, 
                        self.parent_view.ctx, 
                        self.parent_view.bet_amount, 
                        self.parent_view.mines_count,
                        timeout=15
                    )
                    play_again_view.message = self.parent_view.message
                    
                    # Edit message with play again button
                    await self.parent_view.message.edit(embed=embed, view=play_again_view)
                    
                    # Clear from ongoing games
                    if self.parent_view.ctx.author.id in self.parent_view.cog.ongoing_games:
                        del self.parent_view.cog.ongoing_games[self.parent_view.ctx.author.id]
            else:
                # Tile already revealed
                await interaction.response.defer()


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
    def __init__(self, cog, ctx, bet_amount, mines_count, board_size=5, timeout=120):
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

        # Generate buttons for the 5x5 grid
        self._create_buttons()
        
    def _create_buttons(self):
        """Create all buttons for the 5x5 grid"""
        for row in range(self.board_size):
            for col in range(self.board_size):
                self.add_item(MineButton(row, col, self))
    
    def get_button(self, row, col):
        """Get a button at the specified position"""
        for item in self.children:
            if isinstance(item, MineButton) and item.row_idx == row and item.col_idx == col:
                return item
        return None

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

    def update_multiplier(self):
        """Calculate current multiplier based on revealed tiles"""
        # Base formula for multiplier
        # The more mines and the more tiles revealed, the higher the multiplier
        total_cells = self.board_size * self.board_size
        safe_cells = total_cells - self.mines_count
        
        # Base multiplier calculation
        # Example formula: More tiles revealed = higher multiplier
        # This can be tuned for game balance
        if len(self.revealed_tiles) == 0:
            self.current_multiplier = 1.0
        else:
            # Calculate fair multiplier based on probability
            # House edge factored in by multiplying by ~0.97 (3% edge)
            # This gives proper expected value
            base_multi = (safe_cells / (safe_cells - len(self.revealed_tiles))) * 0.97
            
            # Round to 2 decimal places
            self.current_multiplier = round(base_multi, 2)
            
            # Ensure minimum is 1.0
            self.current_multiplier = max(1.0, self.current_multiplier)

    def create_embed(self, status="playing"):
        """Create the game embed based on current state"""
        if status == "playing":
            color = 0x3498db  # Blue
            title = "🎮 | Mines Game"
        elif status == "win":
            color = 0x00FF00  # Green
            title = "💰 | You Won!"
        elif status == "lose":
            color = 0xFF0000  # Red
            title = "❌ | Game Over!"
        else:
            color = 0x3498db
            title = "🎮 | Mines Game"
            
        # Calculate profit
        profit = 0
        if status == "win" and len(self.revealed_tiles) > 0:
            profit = (self.bet_amount * self.current_multiplier) - self.bet_amount
            
        # Create description based on game state
        description = f"**Bet Amount:** {self.bet_amount:.2f}\n**Current Multiplier:** {self.current_multiplier:.2f}x\n"
        
        if status == "playing":
            description += f"**Profit:** {profit:.2f} points\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎"
            
            # Add cash out instruction
            if len(self.revealed_tiles) > 0:
                description += "\n\nReact with 💰 to cash out!"
        elif status == "win":
            winnings = self.bet_amount * self.current_multiplier
            description += f"**Profit:** {profit:.2f} points\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎\n\n"
            description += f"**You won {winnings:.2f} credits!**"
        elif status == "lose":
            description += f"**Profit:** 0 points\n"
            description += f"**Mines:** {self.mines_count}/{self.board_size * self.board_size} | {len(self.revealed_tiles)}💎\n\n"
            description += "**You lost!**"
            
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)
        return embed
        
    async def process_win(self, ctx):
        """Process win for the player"""
        # Calculate winnings
        winnings = self.bet_amount * self.current_multiplier
        
        # Get database connection
        db = Users()
        
        # Add credits to user (always give credits for winnings)
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")
        
        # Add to win history
        win_entry = {
            "type": "win",
            "game": "mines",
            "bet": self.bet_amount,
            "amount": winnings,
            "multiplier": self.current_multiplier,
            "mines": self.mines_count,
            "tiles_revealed": len(self.revealed_tiles),
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
                "amount": winnings,
                "multiplier": self.current_multiplier,
                "mines": self.mines_count,
                "tiles_revealed": len(self.revealed_tiles),
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )
            
            # Update server profit (negative value because server loses when player wins)
            profit = winnings - self.bet_amount
            server_db.update_server_profit(ctx.guild.id, -profit)
        
        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings}}
        )
        
    async def process_loss(self, ctx):
        """Process loss for the player"""
        # Get database connection
        db = Users()
        
        # Add to loss history
        loss_entry = {
            "type": "loss",
            "game": "mines",
            "bet": self.bet_amount,
            "amount": self.bet_amount,
            "mines": self.mines_count,
            "tiles_revealed": len(self.revealed_tiles),
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
                "mines": self.mines_count,
                "tiles_revealed": len(self.revealed_tiles),
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
            )
            
            # Update server profit
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$inc": {"total_profit": self.bet_amount}}
            )
        
        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_lost": 1}}
        )
    
    async def on_timeout(self):
        """Handle timeout - auto cash out if player has revealed tiles"""
        if not self.game_over and not self.cashed_out:
            if len(self.revealed_tiles) > 0:
                # Auto cash out
                self.cashed_out = True
                
                # Process win
                await self.process_win(self.ctx)
                
                # Update message with win state
                embed = self.create_embed(status="win")
                embed.description += "\n\n*Game auto-cashed out due to timeout.*"
                
                # Create play again view
                play_again_view = PlayAgainView(
                    self.cog, 
                    self.ctx, 
                    self.bet_amount, 
                    self.mines_count,
                    timeout=15
                )
                
                # Update message
                try:
                    await self.message.edit(embed=embed, view=play_again_view)
                    play_again_view.message = self.message
                except:
                    pass
                
                # Clear from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            else:
                # No tiles revealed, count as loss
                self.game_over = True
                
                # Process loss
                await self.process_loss(self.ctx)
                
                # Update message
                embed = self.create_embed(status="lose")
                embed.description += "\n\n*Game timed out without any tiles revealed.*"
                
                # Create play again view
                play_again_view = PlayAgainView(
                    self.cog, 
                    self.ctx, 
                    self.bet_amount, 
                    self.mines_count,
                    timeout=15
                )
                
                # Update message
                try:
                    await self.message.edit(embed=embed, view=play_again_view)
                    play_again_view.message = self.message
                except:
                    pass
                
                # Clear from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]


class MinesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Check if this is a cash out reaction for a mines game
        if str(reaction.emoji) == "💰" and user.id in self.ongoing_games:
            game_data = self.ongoing_games.get(user.id)
            if game_data and "view" in game_data:
                game_view = game_data["view"]
                # Only process if it's the game owner and the game is still active
                if (user.id == game_view.ctx.author.id and 
                    reaction.message.id == game_view.message.id and
                    not game_view.game_over and not game_view.cashed_out and
                    len(game_view.revealed_tiles) > 0):
                    
                    # Set cash out
                    game_view.cashed_out = True
                    
                    # Process win
                    await game_view.process_win(game_view.ctx)
                    
                    # Update message with win state
                    embed = game_view.create_embed(status="win")
                    
                    # Create play again view
                    play_again_view = PlayAgainView(
                        self, 
                        game_view.ctx, 
                        game_view.bet_amount, 
                        game_view.mines_count,
                        timeout=15
                    )
                    
                    # Update the message
                    await game_view.message.edit(embed=embed, view=play_again_view)
                    play_again_view.message = game_view.message
                    
                    # Clear from ongoing games
                    if user.id in self.ongoing_games:
                        del self.ongoing_games[user.id]

    def calculate_max_mines(self):
        """Calculate maximum allowed mines"""
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
                    "- **Click on buttons to reveal tiles**\n"
                    "- **Each safe tile increases your multiplier**\n"
                    "- **React with 💰 to cash out your winnings**\n"
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

        # Add cash out reaction
        await game_message.add_reaction("💰")

        # Inform user about timeout
        await ctx.send(
            "💡 **Click on the buttons to reveal tiles, and react with 💰 to cash out.** The game will timeout after 2 minutes.",
            delete_after=10
        )


def setup(bot):
    bot.add_cog(MinesCog(bot))
