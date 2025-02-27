#put only game commands here
import discord
import random
import asyncio
import matplotlib.pyplot as plt
import io
import numpy as np
import time
import math
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from PIL import Image, ImageDraw

class CrashGame:
    def __init__(self, cog, ctx, bet_amount, user_id):
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.user_id = user_id
        self.crashed = False
        self.cashed_out = False
        self.current_multiplier = 1.0
        self.cash_out_multiplier = 0.0
        self.tokens_used = 0
        self.credits_used = 0
        self.message = None

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = None

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

            confirm_embed = discord.Embed(
                title="🎮 Max Bet Confirmation",
                description=f"You don't have enough for the previous bet of **{self.bet_amount}**.\nPlay with your max bet of **{bet_amount}** instead?",
                color=0x00FFAE
            )

            # Create a confirmation view
            confirm_view = discord.ui.View(timeout=30)

            @discord.ui.button(label="Confirm Max Bet", style=discord.ButtonStyle.success)
            async def confirm_max_bet(b, i):
                await i.response.defer()
                for child in confirm_view.children:
                    child.disabled = True
                await i.message.edit(view=confirm_view)

                # Start a new game with max bet
                await self.cog.crash(self.ctx, str(bet_amount))

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_max_bet(b, i):
                await i.response.defer()
                for child in confirm_view.children:
                    child.disabled = True
                await i.message.edit(view=confirm_view)

                await i.followup.send("Max bet cancelled.", ephemeral=True)

            confirm_view.add_item(confirm_max_bet)
            confirm_view.add_item(cancel_max_bet)

            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
        else:
            # User can afford the same bet
            await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
            await self.cog.crash(self.ctx, str(self.bet_amount))

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Check if this is a cash out reaction for a crash game
        if str(reaction.emoji) == "💰" and user.id in self.ongoing_games:
            game_data = self.ongoing_games.get(user.id)
            if game_data and "crash_game" in game_data:
                crash_game = game_data["crash_game"]
                # Only process if it's the game owner and the game is still active
                if (user.id == crash_game.user_id and 
                    reaction.message.id == crash_game.message.id and
                    not crash_game.crashed and not crash_game.cashed_out):
                    # Set cash out values
                    crash_game.cashed_out = True
                    crash_game.cash_out_multiplier = crash_game.current_multiplier

    @commands.command(aliases=["cr"])
    async def crash(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play the crash game - bet before the graph crashes!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":bulb: How to Play Crash",
                description=(
                    "**Crash** is a multiplier game where you place a bet and cash out before the graph crashes.\n\n"
                    "**Usage:** `!crash <amount> [currency_type]`\n"
                    "**Example:** `!crash 100` or `!crash 100 tokens`\n\n"
                    "- Watch as the multiplier increases in real-time\n"
                    "- React with 💰 before it crashes to cash out and win\n"
                    "- If it crashes before you cash out, you lose your bet\n"
                    "- The longer you wait, the higher the potential reward!\n\n"
                    "You can bet using tokens (T) or credits (C):\n"
                    "- If you have enough tokens, they will be used first\n"
                    "- If you don't have enough tokens, credits will be used\n"
                    "- If needed, both will be combined to meet your bet amount"
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
            title=f"{loading_emoji} | Preparing Crash Game...",
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
                        description=f"You don't have enough tokens. Your balance: **{tokens_balance} tokens**",
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
                        description=f"You don't have enough credits. Your balance: **{credits_balance} credits**",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)

            else:
                # Auto-determine what to use
                if tokens_balance >= bet_amount_value:
                    # Use tokens first if available
                    tokens_used = bet_amount_value
                elif credits_balance >= bet_amount_value:
                    # Use credits if not enough tokens
                    credits_used = bet_amount_value
                elif tokens_balance + credits_balance >= bet_amount_value:
                    # Use a combination of both
                    tokens_used = tokens_balance
                    credits_used = bet_amount_value - tokens_balance
                else:
                    # Not enough funds
                    await loading_message.delete()
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Insufficient Funds",
                        description=(
                            f"You don't have enough funds for this bet.\n"
                            f"Your balance: **{tokens_balance} tokens** and **{credits_balance} credits**\n"
                            f"Required: **{bet_amount_value}**"
                        ),
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

        # Create CrashGame object instead of a view
        crash_game = CrashGame(self, ctx, total_bet, ctx.author.id)

        # Generate crash point with a more balanced distribution
        # House edge is around 4-5% with this implementation
        try:
            # Adjust the minimum crash point to ensure some minimum payout
            min_crash = 1.0
            
            # Use a better distribution to increase median crash points
            # Lower alpha value (1.7 instead of 2) means higher multipliers are more common
            alpha = 1.7
            
            # Generate base crash point, modified for fairer distribution
            r = random.random()
            
            # House edge factor (0.96 gives ~4% edge to house in the long run)
            house_edge = 0.96
            
            # Calculate crash point using improved formula
            # This gives better distribution with more points between 1.5x-3x
            if r < 0.01:  # 1% chance for instant crash (higher house edge)
                crash_point = 1.0
            else:
                # Main distribution calculation
                crash_point = min_crash + ((1 / (1 - r)) ** (1 / alpha) - 1) * house_edge
                
                # Round to 2 decimal places
                crash_point = math.floor(crash_point * 100) / 100
            
            # We don't want unrealistically high crash points
            crash_point = min(crash_point, 30.0)  # Increased max from 20x to 30x
            
            # Ensure crash point is at least 1.0
            crash_point = max(crash_point, 1.0)
            
        except Exception as e:
            print(f"Error generating crash point: {e}")
            crash_point = random.uniform(1.0, 3.0)  # Fallback

        # Format bet amount description
        bet_description = ""
        if tokens_used > 0 and credits_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens + {credits_used} credits"
        elif tokens_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens"
        else:
            bet_description = f"**Bet Amount:** {credits_used} credits"

        # Create initial graph
        try:
            initial_embed, initial_file = self.generate_crash_graph(1.0, False)
            initial_embed.title = "🚀 | Crash Game Started"
            initial_embed.description = (
                f"{bet_description}\n"
                f"**Current Multiplier:** 1.00x\n\n"
                "React with 💰 to cash out before it crashes!"
            )
        except Exception as e:
            print(f"Error generating crash graph: {e}")
            # Create a simple embed if graph fails
            initial_embed = discord.Embed(
                title="🚀 | Crash Game Started", 
                description=(
                    f"{bet_description}\n"
                    f"**Current Multiplier:** 1.00x\n\n"
                    "Click **Cash Out** before it crashes to win!"
                ),
                color=0x00FFAE
            )
            initial_file = None

        # Delete loading message and send initial game message
        await loading_message.delete()

        # Send message with file attachment if available
        if initial_file:
            message = await ctx.reply(embed=initial_embed, file=initial_file)
        else:
            message = await ctx.reply(embed=initial_embed)

        # Add cash out reaction
        await message.add_reaction("💰")

        # Store message in the crash game object
        crash_game.message = message

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "message": message,
            "crash_game": crash_game,
            "tokens_used": tokens_used,
            "credits_used": credits_used
        }

        # Track the currency used for winning calculation
        crash_game.tokens_used = tokens_used
        crash_game.credits_used = credits_used

        # Start the game
        await self.run_crash_game(ctx, message, crash_game, crash_point, total_bet)

    async def run_crash_game(self, ctx, message, crash_game, crash_point, bet_amount):
        """Run the crash game animation and handle the result"""
        try:
            multiplier = 1.0
            growth_rate = 0.05  # Controls how fast the multiplier increases

            # Format bet amount description based on tokens and credits used
            if hasattr(crash_game, 'tokens_used') and hasattr(crash_game, 'credits_used'):
                tokens_used = crash_game.tokens_used
                credits_used = crash_game.credits_used

                if tokens_used > 0 and credits_used > 0:
                    bet_description = f"**Bet Amount:** {tokens_used} tokens + {credits_used} credits"
                elif tokens_used > 0:
                    bet_description = f"**Bet Amount:** {tokens_used} tokens"
                else:
                    bet_description = f"**Bet Amount:** {credits_used} credits"
            else:
                bet_description = f"**Bet Amount:** {bet_amount}"

            # Create an event to track reaction cash out
            cash_out_event = asyncio.Event()

            # Set up reaction check
            def reaction_check(reaction, user):
                # Only check reactions from the game owner on the game message with 💰 emoji
                return (user.id == ctx.author.id and 
                        reaction.message.id == message.id and 
                        str(reaction.emoji) == "💰" and
                        not crash_game.crashed)

            # Start reaction listener task
            async def reaction_listener():
                try:
                    # Wait for the cash out reaction
                    reaction, user = await self.bot.wait_for('reaction_add', check=reaction_check)
                    if not crash_game.crashed and not crash_game.cashed_out:
                        # Set cash out values
                        crash_game.cashed_out = True
                        crash_game.cash_out_multiplier = crash_game.current_multiplier
                        # Set the event to notify the main loop
                        cash_out_event.set()

                        # Send immediate feedback to player
                        winnings = round(bet_amount * crash_game.cash_out_multiplier, 2)  # Round to 2 decimal places
                        feedback_embed = discord.Embed(
                            title="✅ Cash Out Successful!",
                            description=f"You cashed out at **{crash_game.cash_out_multiplier:.2f}x**\nWinnings: **{winnings} credits**",
                            color=0x00FF00
                        )
                        await ctx.send(embed=feedback_embed, delete_after=5)
                except Exception as e:
                    print(f"Error in reaction listener: {e}")

            # Start the reaction listener in the background
            reaction_task = asyncio.create_task(reaction_listener())

            # Continue incrementing the multiplier until crash or cash out
            while multiplier < crash_point and not crash_game.cashed_out:
                # Wait a bit between updates (faster at the start, slower as multiplier increases)
                delay = 1.0 / (1 + multiplier * 0.5)
                delay = max(0.3, min(delay, 0.8))  # Keep delay between 0.3 and 0.8 seconds

                # Wait for either the delay to pass or cash out event to be triggered
                try:
                    await asyncio.wait_for(cash_out_event.wait(), timeout=delay)
                    # If we get here, the cash out event was triggered
                    break
                except asyncio.TimeoutError:
                    # Timeout means the delay passed normally, continue with game
                    pass

                # Increase multiplier with a bit of randomness
                multiplier += growth_rate * (1 + random.uniform(-0.2, 0.2))
                crash_game.current_multiplier = multiplier

                try:
                    # Generate updated graph and embed
                    embed, file = self.generate_crash_graph(multiplier, False)
                    embed.title = "🚀 | Crash Game In Progress"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                        "React with 💰 to cash out before it crashes!"
                    )

                    # Update the message with new graph
                    view = discord.ui.View() # Added view creation here.
                    await message.edit(embed=embed, files=[file], view=view)
                except Exception as graph_error:
                    print(f"Error updating graph: {graph_error}")
                    # Simple fallback in case graph generation fails
                    try:
                        embed = discord.Embed(
                            title="🚀 | Crash Game In Progress", 
                            description=(
                                f"{bet_description}\n"
                                f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                                "React with 💰 to cash out before it crashes!"
                            ),
                            color=0x00FFAE
                        )
                        view = discord.ui.View() # Added view creation here.
                        await message.edit(embed=embed, view=view)
                    except Exception as fallback_error:
                        print(f"Error updating fallback message: {fallback_error}")

            # Cancel the reaction task if it's still running
            if not reaction_task.done():
                reaction_task.cancel()

            # Game ended - either crashed or cashed out
            crash_game.crashed = True

            # Try to clear reactions
            try:
                await message.clear_reactions()
            except:
                pass

            # Get database connection
            db = Users()

            # Handle crash
            if not crash_game.cashed_out:
                try:
                    # Generate crash graph
                    embed, file = self.generate_crash_graph(multiplier, True)
                    embed.title = "💥 | CRASHED!"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Crashed At:** {multiplier:.2f}x\n\n"
                        f"**Result:** You lost your bet!"
                    )
                    embed.color = 0xFF0000

                    # Add to history
                    history_entry = {
                        "type": "loss",
                        "game": "crash",
                        "bet": bet_amount,
                        "amount": bet_amount,
                        "multiplier": round(multiplier, 2),
                        "timestamp": int(time.time())
                    }
                    db.collection.update_one(
                        {"discord_id": ctx.author.id},
                        {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                    )

                    # Update stats
                    db.collection.update_one(
                        {"discord_id": ctx.author.id},
                        {"$inc": {"total_lost": 1}}
                    )

                    # Create Play Again view with button
                    play_again_view = discord.ui.View()
                    play_again_button = discord.ui.Button(
                        label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄"
                    )

                    async def play_again_callback(interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message("This is not your game!", ephemeral=True)

                        # Start a new game with the same bet
                        await interaction.response.defer()
                        await self.crash(ctx, str(bet_amount))

                    play_again_button.callback = play_again_callback
                    play_again_view.add_item(play_again_button)

                    # Update message with crash result and Play Again button
                    await message.edit(embed=embed, files=[file], view=play_again_view)

                except Exception as crash_error:
                    print(f"Error handling crash: {crash_error}")
                    # Simple fallback
                    try:
                        embed = discord.Embed(
                            title="💥 | CRASHED!", 
                            description=(
                                f"{bet_description}\n"
                                f"**Crashed At:** {multiplier:.2f}x\n\n"
                                f"**Result:** You lost your bet!"
                            ),
                            color=0xFF0000
                        )
                        # Add Play Again button
                        play_again_view = discord.ui.View()
                        play_again_button = discord.ui.Button(
                            label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄"
                        )

                        async def play_again_callback(interaction):
                            if interaction.user.id != ctx.author.id:
                                return await interaction.response.send_message("This is not your game!", ephemeral=True)

                            # Start a new game with the same bet
                            await interaction.response.defer()
                            await self.crash(ctx, str(bet_amount))

                        play_again_button.callback = play_again_callback
                        play_again_view.add_item(play_again_button)

                        await message.edit(embed=embed, view=play_again_view)

                    except Exception as fallback_error:
                        print(f"Error updating fallback crash message: {fallback_error}")

            else:
                try:
                    # User cashed out successfully
                    cash_out_multiplier = crash_game.cash_out_multiplier
                    winnings = round(bet_amount * cash_out_multiplier, 2)  # Round to 2 decimal places
                    profit = winnings - bet_amount

                    # Generate success graph
                    embed, file = self.generate_crash_graph(cash_out_multiplier, False, cash_out=True)
                    embed.title = "💰 | CASHED OUT!"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Cashed Out At:** {cash_out_multiplier:.2f}x\n"
                        f"**Winnings:** {winnings} credits\n"
                        f"**Profit:** {profit} credits"
                    )
                    embed.color = 0x00FF00

                    # Add credits to user balance
                    db.update_balance(ctx.author.id, winnings, "credits", "$inc")

                    # Add to history
                    history_entry = {
                        "type": "win",
                        "game": "crash",
                        "bet": bet_amount,
                        "amount": winnings,
                        "multiplier": round(cash_out_multiplier, 2),
                        "winnings": winnings,
                        "timestamp": int(time.time())
                    }
                    db.collection.update_one(
                        {"discord_id": ctx.author.id},
                        {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                    )

                    # Update stats
                    db.collection.update_one(
                        {"discord_id": ctx.author.id},
                        {"$inc": {"total_won": 1, "total_earned": winnings}}
                    )

                    # Create Play Again view with button
                    play_again_view = discord.ui.View()
                    play_again_button = discord.ui.Button(
                        label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄"
                    )

                    async def play_again_callback(interaction):
                        if interaction.user.id != ctx.author.id:
                            return await interaction.response.send_message("This is not your game!", ephemeral=True)

                        # Start a new game with the same bet
                        await interaction.response.defer()
                        await self.crash(ctx, str(bet_amount))

                    play_again_button.callback = play_again_callback
                    play_again_view.add_item(play_again_button)

                    # Update message with win result and Play Again button
                    await message.edit(embed=embed, files=[file], view=play_again_view)

                except Exception as win_error:
                    print(f"Error handling win: {win_error}")
                    # Simple fallback
                    try:
                        embed = discord.Embed(
                            title="💰 | CASHED OUT!", 
                            description=(
                                f"{bet_description}\n"
                                f"**Cashed Out At:** {cash_out_multiplier:.2f}x\n"
                                f"**Winnings:** {winnings} credits\n"
                                f"**Profit:** {profit} credits"
                            ),
                            color=0x00FF00
                        )
                        # Add Play Again button
                        play_again_view = discord.ui.View()
                        play_again_button = discord.ui.Button(
                            label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄"
                        )

                        async def play_again_callback(interaction):
                            if interaction.user.id != ctx.author.id:
                                return await interaction.response.send_message("This is not your game!", ephemeral=True)

                            # Start a new game with the same bet
                            await interaction.response.defer()
                            await self.crash(ctx, str(bet_amount))

                        play_again_button.callback = play_again_callback
                        play_again_view.add_item(play_again_button)

                        # Make sure winnings are credited even if graph fails
                        db.update_balance(ctx.author.id, winnings, "credits", "$inc")

                        await message.edit(embed=embed, view=play_again_view)

                    except Exception as fallback_error:
                        print(f"Error updating fallback win message: {fallback_error}")

        except Exception as e:
            print(f"Error in crash game: {e}")
            # Try to send error message to user
            try:
                error_embed = discord.Embed(
                    title="❌ | Game Error",
                    description="An error occurred during the game. Your bet has been refunded.",
                    color=0xFF0000
                )
                await ctx.reply(embed=error_embed)

                # Refund the bet if there was an error
                db = Users()
                if hasattr(crash_game, 'tokens_used') and crash_game.tokens_used > 0:
                    current_tokens = db.fetch_user(ctx.author.id)['tokens']
                    db.update_balance(ctx.author.id, current_tokens + crash_game.tokens_used, "tokens")

                if hasattr(crash_game, 'credits_used') and crash_game.credits_used > 0:
                    current_credits = db.fetch_user(ctx.author.id)['credits']
                    db.update_balance(ctx.author.id, current_credits + crash_game.credits_used, "credits")
            except Exception as refund_error:
                print(f"Error refunding bet: {refund_error}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

    def generate_crash_graph(self, current_multiplier, crashed=False, cash_out=False):
        """Generate a crash game graph with Stake-like visuals"""
        try:
            # Clear and close previous plots to prevent memory issues
            plt.close('all')
            fig = plt.figure(figsize=(10, 6), dpi=100)

            # Set dark background similar to Stake's design
            bg_color = '#0F1923'  # Darker blue-black, similar to Stake
            plt.gca().set_facecolor(bg_color)
            plt.gcf().set_facecolor(bg_color)

            # Generate x and y coordinates for smoother curve with more points
            # Use more points for higher multipliers to make the curve smoother
            point_count = min(500, int(300 + current_multiplier * 20))
            x = np.linspace(0, current_multiplier, point_count)

            # Create curve with exponential growth - similar to Stake's curve
            # This creates a curve that starts flat and increases exponentially
            base = 1.1 + (current_multiplier / 50)  # Adjust base for different curve steepness
            y = np.power(base, x) - 1
            
            # Normalize to match current multiplier
            y = y * (current_multiplier / y[-1]) if y[-1] > 0 else y
            
            # Adjust x-axis for better time representation (similar to Stake)
            # This stretches the x-axis slightly to match the actual time feel
            x = np.linspace(0, current_multiplier * 1.05, len(y))
            
            # Setup figure
            fig.set_facecolor(bg_color)
            ax = plt.gca()
            ax.set_facecolor(bg_color)

            # Create grid with subtle lines for a more professional look
            plt.grid(True, linestyle='-', alpha=0.05, color='#FFFFFF')
            
            # Add horizontal lines at significant multiplier values (like Stake)
            significant_multipliers = [1.5, 2, 3, 5, 10, 20, 50, 100]
            for mult in significant_multipliers:
                if mult <= current_multiplier * 1.2:
                    plt.axhline(y=mult, color='#FFFFFF', alpha=0.08, linewidth=1)
                    # Add multiplier labels on y-axis
                    plt.text(-0.02 * current_multiplier, mult, f"{mult}x", 
                             color='#FFFFFF', alpha=0.5, fontsize=8, ha='right', va='center')
            
            # Define colors based on state - using Stake's color scheme
            if crashed:
                # Red theme for crash
                main_color = '#FF4747'  # Stake's crash red
                glow_color = '#FF2424'
                accent_color = '#FF0000'
            elif cash_out:
                # Green theme for cash out
                main_color = '#00C853'  # Stake's success green
                glow_color = '#00E676'
                accent_color = '#00FF00'
            else:
                # Blue theme for active game - changes based on multiplier
                if current_multiplier < 1.5:
                    main_color = '#00A3FF'  # Light blue
                    glow_color = '#00B8FF'
                elif current_multiplier < 2.5:
                    main_color = '#18BFFF'  # Cyan-blue
                    glow_color = '#00CCFF'
                elif current_multiplier < 5:
                    main_color = '#FFB800'  # Yellow-orange
                    glow_color = '#FFC107'
                else:
                    main_color = '#FF9800'  # Orange
                    glow_color = '#FFAB00'
                accent_color = main_color
            
            # Draw line glow effect - subtle for a professional look
            for width, alpha in [(4, 0.1), (3, 0.15), (2, 0.2)]:
                plt.plot(x, y, color=glow_color, linewidth=width, alpha=alpha, zorder=2)
            
            # Main line with solid color
            plt.plot(x, y, color=main_color, linewidth=2, linestyle='-', zorder=3)
            
            # Add small dots along the curve like Stake's graph
            if not crashed and not cash_out:
                # Less points for cleaner look - Stake's graph is clean
                n_points = min(int(current_multiplier * 3), 25)
                point_indices = np.linspace(0, len(x)-20, n_points, dtype=int)
                
                # Small subtle dots
                plt.scatter(x[point_indices], y[point_indices], color=main_color, 
                           s=20, alpha=0.7, zorder=4, edgecolor='white', linewidth=0.5)
            
            # Add crash or cash out indicators - clean and professional
            if crashed:
                # Simple clean crash indicator
                plt.scatter([x[-1]], [y[-1]], color=main_color, s=100, marker='x', 
                           linewidth=2, zorder=10)
                
                # Text indicator with clean box
                plt.text(x[-1] - 0.05 * current_multiplier, y[-1] + 0.1 * current_multiplier, 
                        f"CRASH @ {current_multiplier:.2f}x", 
                        color='white', fontweight='bold', fontsize=12, ha='right', va='bottom',
                        bbox=dict(boxstyle="round,pad=0.4", facecolor=main_color, alpha=0.9, 
                                 edgecolor='none'))
                
            elif cash_out:
                # Diamond for cash out - cleaner than previous version
                plt.scatter([x[-1]], [y[-1]], color=main_color, s=100, marker='D', 
                           zorder=10, edgecolor='white', linewidth=0.5)
                
                # Cash out indicator with clean styling
                plt.text(x[-1] - 0.05 * current_multiplier, y[-1] + 0.1 * current_multiplier, 
                        f"CASHED OUT @ {current_multiplier:.2f}x", 
                        color='white', fontweight='bold', fontsize=12, ha='right', va='bottom',
                        bbox=dict(boxstyle="round,pad=0.4", facecolor=main_color, alpha=0.9, 
                                 edgecolor='none'))
            
            # Add the multiplier in a clean box at top-right - Stake style
            if not crashed and not cash_out:
                # Draw clean box with multiplier in top right
                plt.text(0.97, 0.95, f"{current_multiplier:.2f}x", 
                        transform=plt.gca().transAxes, color='white', fontsize=18, fontweight='bold', 
                        ha='right', va='top',
                        bbox=dict(boxstyle="round,pad=0.4", facecolor=main_color, alpha=0.9, 
                                 edgecolor='none'))
            
            # Clean up axes
            plt.xlim(0, max(1.5, current_multiplier * 1.1))
            plt.ylim(0, max(1.5, current_multiplier * 1.1))
            
            # Remove tick labels for a cleaner look
            plt.xticks([])
            plt.yticks([])
            
            # Remove border lines
            for spine in plt.gca().spines.values():
                spine.set_visible(False)
                
            # Add subtle grid lines along x-axis (time)
            for i in range(1, int(current_multiplier) + 1):
                if i <= current_multiplier:
                    plt.axvline(x=i, color='#FFFFFF', alpha=0.05, linewidth=1)
            
            # Add subtle branding in bottom like Stake
            plt.text(0.5, 0.03, "BetSync Casino", transform=plt.gca().transAxes,
                    color='white', alpha=0.3, fontsize=12, fontweight='normal', ha='center')
            
            # Add subtle graph overlay to make it look more professional
            if not crashed and not cash_out:
                # Draw subtle gradient overlay
                gradient = np.linspace(0, 1, 100).reshape(-1, 1)
                plt.imshow(gradient, extent=[0, max(1.5, current_multiplier * 1.1), 
                                           0, max(1.5, current_multiplier * 1.1)],
                          aspect='auto', cmap='Blues', alpha=0.05)
            
            # Save plot with high quality
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=bg_color)
            buf.seek(0)
            
            # Create discord File object
            file = discord.File(buf, filename="crash_graph.png")
            
            # Create embed with the graph
            embed = discord.Embed(color=0x2B2D31)
            embed.set_image(url="attachment://crash_graph.png")
            
            return embed, file
        except Exception as e:
            # Error handling for graph generation
            print(f"Error generating crash graph: {e}")

            # Create a simple fallback embed
            embed = discord.Embed(
                title="Crash Game", 
                description=f"Current Multiplier: {current_multiplier:.2f}x",
                color=0x2B2D31
            )

            # Create a simple colored rectangle as fallback
            try:
                # Create a simple colored rectangle
                color = 'red' if crashed else 'green' if cash_out else 'blue'
                img = Image.new('RGB', (800, 400), color=bg_color)
                draw = ImageDraw.Draw(img)

                # Draw a simple line representing the curve
                points = [(i, 400 - int(min(i**1.5, 399))) for i in range(0, 800, 10)]
                draw.line(points, fill=color, width=5)

                # Add text
                if crashed:
                    text = f"CRASHED: {current_multiplier:.2f}x"
                elif cash_out:
                    text = f"CASHED OUT: {current_multiplier:.2f}x"
                else:
                    text = f"MULTIPLIER: {current_multiplier:.2f}x"

                # Convert to bytes
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                file = discord.File(buf, filename="crash_fallback.png")

                embed.set_image(url="attachment://crash_fallback.png")
                return embed, file
            except Exception:
                # Ultimate fallback with no image
                return embed, None

def setup(bot):
    bot.add_cog(Games(bot))