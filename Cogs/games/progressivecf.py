import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PCFView(discord.ui.View):
    def __init__(self, cog, ctx, message, bet_amount, currency_used, initial_multiplier=1.96, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.message = message
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.current_flips = 0
        self.current_multiplier = initial_multiplier
        self.max_flips = 15
        self.choice = None
        self.last_result = None

    @discord.ui.button(label="HEADS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def heads_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "heads"
        await self.flip_coin(interaction)

    @discord.ui.button(label="TAILS", style=discord.ButtonStyle.primary, emoji="🪙")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "tails"
        await self.flip_coin(interaction)

    @discord.ui.button(label="CASH OUT", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.current_flips == 0:
            return await interaction.response.send_message("You need to flip at least once before cashing out!", ephemeral=True)

        # Disable all buttons to prevent further interactions
        for item in self.children:
            item.disabled = True

        # Update the view first
        await interaction.response.edit_message(view=self)

        # Process cashout
        await self.cog.process_cashout(self.ctx, interaction, self.message, 
                                      self.bet_amount, self.currency_used, 
                                      self.current_flips, self.current_multiplier)

    async def flip_coin(self, interaction):
        # Check if we've already done 15 flips
        if self.current_flips >= self.max_flips:
            # Automatically cash out at max flips
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(view=self)

            await self.cog.process_cashout(self.ctx, interaction, self.message, 
                                          self.bet_amount, self.currency_used, 
                                          self.current_flips, self.current_multiplier,
                                          auto_cashout=True)
            return

        # Flip the coin (50/50 chance)
        result = random.choice(["heads", "tails"])
        self.last_result = result

        # Check if the player won this round
        if result == self.choice:
            # Player guessed correctly
            self.current_flips += 1
            self.current_multiplier *= 1.96  # Multiply by 1.96 for each correct guess

            # Create updated embed
            embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=f"You flipped **{result.upper()}** and chose **{self.choice.upper()}**\n\n**YOU WIN!**\n\nCurrent Multiplier: **{self.current_multiplier:.2f}x**\nCurrent Flips: **{self.current_flips}/{self.max_flips}**\n\nChoose your next flip or cash out!",
                color=0x00FF00
            )
            # Update embed footer
            embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)

            # Enable buttons for next round
            for item in self.children:
                item.disabled = False

            # Send the updated embed
            await interaction.response.edit_message(embed=embed, view=self)

            # Reset choice for next round
            self.choice = None

        else:
            # Player lost
            # Create losing embed
            embed = discord.Embed(
                title="🪙 | Progressive Coinflip - GAME OVER!",
                description=f"You flipped **{result.upper()}** and chose **{self.choice.upper()}**\n\n**YOU LOSE!**\n\nCurrent Flips: **{self.current_flips}/{self.max_flips}**\nMultiplier: **{self.current_multiplier:.2f}x**",
                color=0xFF0000
            )
            # Update embed footer
            embed.set_footer(text="BetSync Casino", icon_url=self.ctx.bot.user.avatar.url)

            # Disable all buttons
            for item in self.children:
                item.disabled = True

            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)

            # Process loss (if they've already flipped some coins)
            if self.current_flips > 0:
                # Register the loss in history
                db = Users()

                loss_entry = {
                    "type": "loss",
                    "game": "progressive_coinflip",
                    "bet": self.bet_amount,
                    "flips": self.current_flips,
                    "multiplier": self.current_multiplier,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": self.ctx.author.id},
                    {"$push": {"history": {"$each": [loss_entry], "$slice": -100}}}
                )

                # Update server history if available
                server_db = Servers()
                server_data = server_db.fetch_server(self.ctx.guild.id)

                if server_data:
                    server_loss_entry = {
                        "type": "loss",
                        "game": "progressive_coinflip",
                        "user_id": self.ctx.author.id,
                        "user_name": self.ctx.author.name,
                        "bet": self.bet_amount,
                        "flips": self.current_flips,
                        "timestamp": int(time.time())
                    }
                    server_db.collection.update_one(
                        {"server_id": self.ctx.guild.id},
                        {
                            "$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}},
                            "$inc": {"total_profit": self.bet_amount}
                        }
                    )

                # Update user stats
                db.collection.update_one(
                    {"discord_id": self.ctx.author.id},
                    {"$inc": {"total_lost": 1}}
                )

            # Remove from ongoing games
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]

    async def on_timeout(self):
        # If player doesn't choose, auto cash out
        if not self.choice and self.current_flips > 0:
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)

                # Process automatic cashout
                await self.cog.process_cashout(self.ctx, None, self.message, 
                                              self.bet_amount, self.currency_used, 
                                              self.current_flips, self.current_multiplier,
                                              auto_cashout=True)
            except:
                pass
        else:
            # Just disable the buttons
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)
            except:
                pass

            # Clean up ongoing game
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]


class ProgressiveCoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pcf"])
    async def progressivecf(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play progressive coinflip - win multiple times to increase your multiplier!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Progressive Coinflip",
                description=(
                    "**Progressive Coinflip** is a game where you can win multiple times in a row for increasing rewards.\n\n"
                    "**Usage:** `!progressivecf <amount> [currency]`\n"
                    "**Example:** `!progressivecf 100` or `!progressivecf 100 tokens`\n\n"
                    "**How to Play:**\n"
                    "1. Choose heads or tails for each flip\n"
                    "2. Each correct guess multiplies your winnings by 1.96x\n"
                    "3. You can cash out anytime or continue flipping\n"
                    "4. Maximum 15 flips allowed\n"
                    "5. If you lose a flip, you get nothing\n\n"
                    "**Currency Options:**\n"
                    "- You can bet using tokens (T) or credits (C)\n"
                    "- Winnings are always paid in credits"
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
            title=f"{loading_emoji} | Preparing Progressive Coinflip...",
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

        # Process bet amount
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
            db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Get total amount bet
        total_bet = tokens_used + credits_used

        # Delete loading message
        await loading_message.delete()

        # Create initial game embed
        initial_embed = discord.Embed(
            title="🪙 | Progressive Coinflip",
            description=(
                f"**Bet:** {total_bet:.2f} {'tokens' if tokens_used > 0 else 'credits'}\n"
                f"**Initial Multiplier:** 1.96x\n\n"
                "Choose heads or tails to start flipping!"
            ),
            color=0x00FFAE
        )
        initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Send initial game message
        game_message = await ctx.reply(embed=initial_embed)

        # Create game view
        game_view = PCFView(self, ctx, game_message, total_bet, 'tokens' if tokens_used > 0 else 'credits')
        await game_message.edit(view=game_view)

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": total_bet,
            "view": game_view
        }

    async def process_cashout(self, ctx, interaction, message, bet_amount, currency_used, flips, multiplier, auto_cashout=False):
        """Process cashout for the player"""
        # Calculate winnings (only credits)
        winnings = bet_amount * multiplier

        # Create cashout embed
        cashout_embed = discord.Embed(
            title="🪙 | Progressive Coinflip - CASHED OUT!",
            description=(
                f"**Initial Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Successful Flips:** {flips}\n"
                f"**Final Multiplier:** {multiplier:.2f}x\n\n"
                f"**Winnings:** {winnings:.2f} credits"
            ),
            color=0x00FF00
        )

        if auto_cashout:
            cashout_embed.description += "\n\n*Automatically cashed out due to maximum flips reached or timeout.*"

        cashout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Update message
        try:
            await message.edit(embed=cashout_embed, view=None)
        except:
            pass

        # Process win
        # Add credits to user
        db = Users()
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "progressive_coinflip",
            "bet": bet_amount,
            "amount": winnings,
            "flips": flips,
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
                "game": "progressive_coinflip",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "flips": flips,
                "multiplier": multiplier,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative because player won)
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$inc": {"total_profit": -(winnings - bet_amount)}}
            )

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings, "total_played": 1}}
        )

        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

    async def start_progressive_game(self, ctx, message, bet_amount, currency_used, side):
        """Start the progressive coinflip game after the user selects a side"""

        # Initial multiplier
        initial_multiplier = 1

        # Create animated coinflip
        try:
            # Update embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=(
                    f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Initial Multiplier:** {initial_multiplier}x\n\n"
                    f"{coin_flip_animated} Flipping coin..."
                ),
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            await message.edit(embed=initial_embed, view=None)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Start the progressive coinflip game
            await self.continue_progressive_flips(
                ctx, 
                None, 
                message,
                bet_amount, 
                currency_used, 
                side, 
                0, 
                initial_multiplier
            )

        except Exception as e:
            # Handle any errors
            print(f"Error in progressive coinflip game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing progressive coinflip. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def continue_progressive_flips(self, ctx, interaction, message, bet_amount, currency_used, side, current_flips, current_multiplier):
        """Continue flipping in progressive coinflip"""

        # Determine the result
        result = random.choice(['heads', 'tails'])

        # Use custom coin emojis
        heads_emoji = "<:heads:1344974756448833576>"
        tails_emoji = "<:tails:1344974822009999451>"

        result_emoji = heads_emoji if result == 'heads' else tails_emoji

        # Determine if user won
        user_won = side == result

        # Update flips count
        current_flips += 1

        # Create result embed
        if user_won:
            # Calculate new multiplier (multiply by 1.96)
            new_multiplier = round(current_multiplier * 1.96, 2)

            # Calculate current potential winnings
            potential_winnings = round(bet_amount * new_multiplier, 2)

            # Check if max flips reached
            max_flips_reached = current_flips >= 15

            if max_flips_reached:
                # Auto cash out at max flips
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - MAX FLIPS REACHED!",
                    description=(
                        f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Final Multiplier:** {new_multiplier}x\n\n"
                        f"🎉 **YOU WON {potential_winnings:.2f} CREDITS!** 🎉\n"
                        f"*Maximum flips reached - auto cashed out!*"
                    ),
                    color=0x00FF00
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Update message
                await message.edit(embed=result_embed, view=None)

                # Process win
                await self.process_win(ctx, bet_amount, new_multiplier, current_flips)

                # Add play again button
                play_again_view = PlayAgainView(self, ctx, bet_amount, currency_used)
                await message.edit(view=play_again_view)
                play_again_view.message = message

                # Remove from ongoing games
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]
            else:
                # Continue game
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - YOU WON!",
                    description=(
                        f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Current Multiplier:** {new_multiplier}x\n"
                        f"**Potential Win:** {potential_winnings:.2f} credits\n\n"
                        f"Would you like to continue flipping or cash out?"
                    ),
                    color=0x00FFAE
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Create continue/cashout view
                continue_view = ContinueOrCashoutView(
                    self, ctx, message, bet_amount, currency_used, 
                    current_flips, new_multiplier
                )

                # Update message with continue options
                if interaction:
                    await interaction.response.edit_message(embed=result_embed, view=continue_view)
                else:
                    await message.edit(embed=result_embed, view=continue_view)
        else:
            # User lost
            result_embed = discord.Embed(
                title="🪙 | Progressive Coinflip - YOU LOST!",
                description=(
                    f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Result:** {result.capitalize()} {result_emoji}\n"
                    f"**Flips:** {current_flips}/15\n\n"
                    f"❌ **YOU LOST EVERYTHING!** ❌"
                ),
                color=0xFF0000
            )
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            if interaction:
                await interaction.response.edit_message(embed=result_embed, view=None)
            else:
                await message.edit(embed=result_embed, view=None)

            # Process loss
            await self.process_loss(ctx, bet_amount, current_flips)

            # Add play again button
            play_again_view = PlayAgainView(self, ctx, bet_amount, currency_used)
            await message.edit(view=play_again_view)
            play_again_view.message = message

            # Remove from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def process_win(self, ctx, bet_amount, multiplier, flips):
        """Process win for progressive coinflip"""
        # Calculate winnings
        winnings = bet_amount * multiplier

        # Get database connection
        db = Users()

        # Add credits to user (always give credits for winnings)
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "pcf",
            "bet": bet_amount,
            "amount": winnings,
            "multiplier": multiplier,
            "flips": flips,
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
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "multiplier": multiplier,
                "flips": flips,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative value because server loses when player wins)
            profit = winnings - bet_amount
            server_db.update_server_profit(ctx.guild.id, -profit)

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings}}
        )

    async def process_loss(self, ctx, bet_amount, flips):
        """Process loss for progressive coinflip"""
        # Get database connection
        db = Users()

        # Add to loss history
        loss_entry = {
            "type": "loss",
            "game": "pcf",
            "bet": bet_amount,
            "amount": bet_amount,
            "flips": flips,
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
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "flips": flips,
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


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction):
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

        if (self.currency_type == "tokens" and tokens_balance >= self.bet_amount) or \
           (self.currency_type == "credits" and credits_balance >= self.bet_amount):
            # User can afford the same bet
            await self.cog.progressivecf(self.ctx, str(self.bet_amount), self.currency_type)
        elif tokens_balance + credits_balance >= self.bet_amount:
            # Ask which currency to use
            if tokens_balance >= self.bet_amount:
                await self.cog.progressivecf(self.ctx, str(self.bet_amount), "tokens")
            else:
                await self.cog.progressivecf(self.ctx, str(self.bet_amount), "credits")
        else:
            # User doesn't have enough funds
            max_bet = max(tokens_balance, credits_balance)

            if max_bet <= 0:
                return await interaction.followup.send("You don't have enough funds to play again. Please deposit first.", ephemeral=True)

            confirm_embed = discord.Embed(
                title="⚠️ Insufficient Funds",
                description=f"You don't have enough to bet {self.bet_amount:.2f} {self.currency_type} again.\nWould you like to bet your maximum available amount ({max_bet:.2f}) instead?",
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

                # Start a new game with max bet
                if tokens_balance >= credits_balance:
                    await self.cog.progressivecf(self.ctx, str(max_bet), "tokens")
                else:
                    await self.cog.progressivecf(self.ctx, str(max_bet), "credits")

            @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
            async def cancel_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)

                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                await i.followup.send("Progressive Coinflip cancelled.", ephemeral=True)

            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


class ProgressiveCoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pcf"])
    async def progressivecf(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play progressive coinflip - win multiple times to increase your multiplier!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Progressive Coinflip",
                description=(
                    "**Progressive Coinflip** is a game where you can win multiple times in a row for increasing rewards.\n\n"
                    "**Usage:** `!progressivecf <amount> [currency]`\n"
                    "**Example:** `!progressivecf 100` or `!progressivecf 100 tokens`\n\n"
                    "**How to Play:**\n"
                    "1. Choose heads or tails for each flip\n"
                    "2. Each correct guess multiplies your winnings by 1.96x\n"
                    "3. You can cash out anytime or continue flipping\n"
                    "4. Maximum 15 flips allowed\n"
                    "5. If you lose a flip, you get nothing\n\n"
                    "**Currency Options:**\n"
                    "- You can bet using tokens (T) or credits (C)\n"
                    "- Winnings are always paid in credits"
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
            title=f"{loading_emoji} | Preparing Progressive Coinflip...",
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

        # Process bet amount
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
            db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Get total amount bet
        total_bet = tokens_used + credits_used

        # Delete loading message
        await loading_message.delete()

        # Create initial game embed
        initial_embed = discord.Embed(
            title="🪙 | Progressive Coinflip",
            description=(
                f"**Bet:** {total_bet:.2f} {'tokens' if tokens_used > 0 else 'credits'}\n"
                f"**Initial Multiplier:** 1.96x\n\n"
                "Choose heads or tails to start flipping!"
            ),
            color=0x00FFAE
        )
        initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Send initial game message
        game_message = await ctx.reply(embed=initial_embed)

        # Create game view
        game_view = PCFView(self, ctx, game_message, total_bet, 'tokens' if tokens_used > 0 else 'credits')
        await game_message.edit(view=game_view)

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": total_bet,
            "view": game_view
        }

    async def process_cashout(self, ctx, interaction, message, bet_amount, currency_used, flips, multiplier, auto_cashout=False):
        """Process cashout for the player"""
        # Calculate winnings (only credits)
        winnings = bet_amount * multiplier

        # Create cashout embed
        cashout_embed = discord.Embed(
            title="🪙 | Progressive Coinflip - CASHED OUT!",
            description=(
                f"**Initial Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Successful Flips:** {flips}\n"
                f"**Final Multiplier:** {multiplier:.2f}x\n\n"
                f"**Winnings:** {winnings:.2f} credits"
            ),
            color=0x00FF00
        )

        if auto_cashout:
            cashout_embed.description += "\n\n*Automatically cashed out due to maximum flips reached or timeout.*"

        cashout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Update message
        try:
            await message.edit(embed=cashout_embed, view=None)
        except:
            pass

        # Process win
        # Add credits to user
        db = Users()
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "progressive_coinflip",
            "bet": bet_amount,
            "amount": winnings,
            "flips": flips,
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
                "game": "progressive_coinflip",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "flips": flips,
                "multiplier": multiplier,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative because player won)
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$inc": {"total_profit": -(winnings - bet_amount)}}
            )

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings, "total_played": 1}}
        )

        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]

    async def start_progressive_game(self, ctx, message, bet_amount, currency_used, side):
        """Start the progressive coinflip game after the user selects a side"""

        # Initial multiplier
        initial_multiplier = 1

        # Create animated coinflip
        try:
            # Update embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=(
                    f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Initial Multiplier:** {initial_multiplier}x\n\n"
                    f"{coin_flip_animated} Flipping coin..."
                ),
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            await message.edit(embed=initial_embed, view=None)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Start the progressive coinflip game
            await self.continue_progressive_flips(
                ctx, 
                None, 
                message,
                bet_amount, 
                currency_used, 
                side, 
                0, 
                initial_multiplier
            )

        except Exception as e:
            # Handle any errors
            print(f"Error in progressive coinflip game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing progressive coinflip. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)

            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def continue_progressive_flips(self, ctx, interaction, message, bet_amount, currency_used, side, current_flips, current_multiplier):
        """Continue flipping in progressive coinflip"""

        # Determine the result
        result = random.choice(['heads', 'tails'])

        # Use custom coin emojis
        heads_emoji = "<:heads:1344974756448833576>"
        tails_emoji = "<:tails:1344974822009999451>"

        result_emoji = heads_emoji if result == 'heads' else tails_emoji

        # Determine if user won
        user_won = side == result

        # Update flips count
        current_flips += 1

        # Create result embed
        if user_won:
            # Calculate new multiplier (multiply by 1.96)
            new_multiplier = round(current_multiplier * 1.96, 2)

            # Calculate current potential winnings
            potential_winnings = round(bet_amount * new_multiplier, 2)

            # Check if max flips reached
            max_flips_reached = current_flips >= 15

            if max_flips_reached:
                # Auto cash out at max flips
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - MAX FLIPS REACHED!",
                    description=(
                        f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Final Multiplier:** {new_multiplier}x\n\n"
                        f"🎉 **YOU WON {potential_winnings:.2f} CREDITS!** 🎉\n"
                        f"*Maximum flips reached - auto cashed out!*"
                    ),
                    color=0x00FF00
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Update message
                await message.edit(embed=result_embed, view=None)

                # Process win
                await self.process_win(ctx, bet_amount, new_multiplier, current_flips)

                # Add play again button
                play_again_view = PlayAgainView(self, ctx, bet_amount, currency_used)
                await message.edit(view=play_again_view)
                play_again_view.message = message

                # Remove from ongoing games
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]
            else:
                # Continue game
                result_embed = discord.Embed(
                    title="🪙 | Progressive Coinflip - YOU WON!",
                    description=(
                        f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                        f"**Your Choice:** {side.capitalize()}\n"
                        f"**Result:** {result.capitalize()} {result_emoji}\n"
                        f"**Flips:** {current_flips}/15\n"
                        f"**Current Multiplier:** {new_multiplier}x\n"
                        f"**Potential Win:** {potential_winnings:.2f} credits\n\n"
                        f"Would you like to continue flipping or cash out?"
                    ),
                    color=0x00FFAE
                )
                result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

                # Create continue/cashout view
                continue_view = ContinueOrCashoutView(
                    self, ctx, message, bet_amount, currency_used, 
                    current_flips, new_multiplier
                )

                # Update message with continue options
                if interaction:
                    await interaction.response.edit_message(embed=result_embed, view=continue_view)
                else:
                    await message.edit(embed=result_embed, view=continue_view)
        else:
            # User lost
            result_embed = discord.Embed(
                title="🪙 | Progressive Coinflip - YOU LOST!",
                description=(
                    f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Result:** {result.capitalize()} {result_emoji}\n"
                    f"**Flips:** {current_flips}/15\n\n"
                    f"❌ **YOU LOST EVERYTHING!** ❌"
                ),
                color=0xFF0000
            )
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Update message
            if interaction:
                await interaction.response.edit_message(embed=result_embed, view=None)
            else:
                await message.edit(embed=result_embed, view=None)

            # Process loss
            await self.process_loss(ctx, bet_amount, current_flips)

            # Add play again button
            play_again_view = PlayAgainView(self, ctx, bet_amount, currency_used)
            await message.edit(view=play_again_view)
            play_again_view.message = message

            # Remove from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    async def process_win(self, ctx, bet_amount, multiplier, flips):
        """Process win for progressive coinflip"""
        # Calculate winnings
        winnings = bet_amount * multiplier

        # Get database connection
        db = Users()

        # Add credits to user (always give credits for winnings)
        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

        # Add to win history
        win_entry = {
            "type": "win",
            "game": "pcf",
            "bet": bet_amount,
            "amount": winnings,
            "multiplier": multiplier,
            "flips": flips,
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
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "amount": winnings,
                "multiplier": multiplier,
                "flips": flips,
                "timestamp": int(time.time())
            }
            server_db.collection.update_one(
                {"server_id": ctx.guild.id},
                {"$push": {"server_bet_history": {"$each": [server_win_entry], "$slice": -100}}}
            )

            # Update server profit (negative value because server loses when player wins)
            profit = winnings - bet_amount
            server_db.update_server_profit(ctx.guild.id, -profit)

        # Update user stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_won": 1, "total_earned": winnings}}
        )

    async def process_loss(self, ctx, bet_amount, flips):
        """Process loss for progressive coinflip"""
        # Get database connection
        db = Users()

        # Add to loss history
        loss_entry = {
            "type": "loss",
            "game": "pcf",
            "bet": bet_amount,
            "amount": bet_amount,
            "flips": flips,
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
                "game": "pcf",
                "user_id": ctx.author.id,
                "user_name": ctx.author.name,
                "bet": bet_amount,
                "flips": flips,
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


class ContinueOrCashoutView(discord.ui.View):
    def __init__(self, cog, ctx, message, bet_amount, currency_used, current_flips, current_multiplier):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.message = message
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.current_flips = current_flips
        self.current_multiplier = current_multiplier
        self.choice = None

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary, emoji="<:heads:1344974756448833576>")
    async def heads_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "heads"
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        await self.message.edit(view=self)

        # Continue flipping with heads
        await self.cog.continue_progressive_flips(
            self.ctx, 
            interaction, 
            self.message, 
            self.bet_amount, 
            self.currency_used, 
            "heads", 
            self.current_flips, 
            self.current_multiplier
        )

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="<:tails:1344974822009999451>")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "tails"
        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        await self.message.edit(view=self)

        # Continue flipping with tails
        await self.cog.continue_progressive_flips(
            self.ctx, 
            interaction, 
            self.message, 
            self.bet_amount, 
            self.currency_used, 
            "tails", 
            self.current_flips, 
            self.current_multiplier
        )

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Verify user can cash out (at least one flip made)
        if self.current_flips == 0:
            await interaction.response.send_message("You need to flip at least once before cashing out!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.defer()
        await self.message.edit(view=self)

        # Process cashout
        await self.cog.process_cashout(self.ctx, interaction, self.message, 
                                      self.bet_amount, self.currency_used, 
                                      self.current_flips, self.current_multiplier)

    async def on_timeout(self):
        # If player doesn't choose, auto cash out
        if not self.choice and self.current_flips > 0:
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)

                # Process automatic cashout
                await self.cog.process_cashout(self.ctx, None, self.message, 
                                              self.bet_amount, self.currency_used, 
                                              self.current_flips, self.current_multiplier,
                                              auto_cashout=True)
            except:
                pass
        else:
            # Just disable the buttons
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)
            except:
                pass

            # Clean up ongoing game
            if self.ctx.author.id in self.cog.ongoing_games:
                del self.cog.ongoing_games[self.ctx.author.id]


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction):
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

        if (self.currency_type == "tokens" and tokens_balance >= self.bet_amount) or \
           (self.currency_type == "credits" and credits_balance >= self.bet_amount):
            # User can afford the same bet
            await self.cog.progressivecf(self.ctx, str(self.bet_amount), self.currency_type)
        elif tokens_balance + credits_balance >= self.bet_amount:
            # Ask which currency to use
            if tokens_balance >= self.bet_amount:
                await self.cog.progressivecf(self.ctx, str(self.bet_amount), "tokens")
            else:
                await self.cog.progressivecf(self.ctx, str(self.bet_amount), "credits")
        else:
            # User doesn't have enough funds
            max_bet = max(tokens_balance, credits_balance)

            if max_bet <= 0:
                return await interaction.followup.send("You don't have enough funds to play again. Please deposit first.", ephemeral=True)

            confirm_embed = discord.Embed(
                title="⚠️ Insufficient Funds",
                description=f"You don't have enough to bet {self.bet_amount:.2f} {self.currency_type} again.\nWould you like to bet your maximum available amount ({max_bet:.2f}) instead?",
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

                # Start a new game with max bet
                if tokens_balance >= credits_balance:
                    await self.cog.progressivecf(self.ctx, str(max_bet), "tokens")
                else:
                    await self.cog.progressivecf(self.ctx, str(max_bet), "credits")

            @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
            async def cancel_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)

                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                await i.followup.send("Progressive Coinflip cancelled.", ephemeral=True)

            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)

            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True

        try:
            await self.message.edit(view=self)
        except:
            pass


def setup(bot):
    bot.add_cog(ProgressiveCoinflipCog(bot))