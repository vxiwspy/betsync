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

class CrashCog(commands.Cog):
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
                    from Cogs.utils.mongo import Servers
                    db = Servers()
                    db.update_server_profit(ctx.guild.id, bet_amount)
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

                    # Update server profit (negative value because server loses when player wins)
                    from Cogs.utils.mongo import Servers
                    servers_db = Servers()
                    server_profit = -profit  # Server loses money when player wins
                    servers_db.update_server_profit(ctx.guild.id, server_profit)
                    
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
                    
                    # Update server profit (negative value because server loses when player wins)
                    from Cogs.utils.mongo import Servers
                    servers_db = Servers()
                    server_profit = -profit  # Server loses money when player wins
                    servers_db.update_server_profit(ctx.guild.id, server_profit)

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
        """Generate a crash game graph with improved visuals"""
        try:
            # Clear and close previous plots to prevent memory issues
            plt.close('all')
            fig = plt.figure(figsize=(10, 6), dpi=100)

            # Set background color with a darker theme
            bg_color = '#1E1F22'
            plt.gca().set_facecolor(bg_color)
            plt.gcf().set_facecolor(bg_color)

            # Generate x and y coordinates with more points for smoother curve
            x = np.linspace(0, current_multiplier, 300)  # Increased for smoother curve

            # Create a more dynamic curve that starts slower and grows faster
            if current_multiplier <= 1.5:
                # For small multipliers, use simple exponential
                y = np.exp(x) - 1
            else:
                # For larger multipliers, use a combination for more dramatic curve
                y = np.power(1.5, x) - 0.5

            # Scale y values to match the current multiplier
            y = y * (current_multiplier / y[-1])

            # Use the existing figure and set its properties
            fig.set_facecolor(bg_color)
            ax = plt.gca()
            ax.set_facecolor(bg_color)

            # Create a custom gradient that changes based on multiplier and state
            if crashed:
                gradient_colors = plt.cm.hot(np.linspace(0, 1, 100))
                gradient_alpha = 0.15
            elif cash_out:
                gradient_colors = plt.cm.viridis(np.linspace(0, 1, 100))
                gradient_alpha = 0.15
            else:
                if current_multiplier < 2:
                    gradient_colors = plt.cm.viridis(np.linspace(0, 1, 100))
                elif current_multiplier < 5:
                    gradient_colors = plt.cm.plasma(np.linspace(0, 1, 100))
                else:
                    gradient_colors = plt.cm.inferno(np.linspace(0, 1, 100))
                gradient_alpha = 0.12 + min(0.03, current_multiplier * 0.005)  # Increases with multiplier

            # Apply gradient background
            gradient = np.linspace(0, 1, 100).reshape(-1, 1)
            plt.imshow(gradient, extent=[0, max(2, current_multiplier * 1.1), 0, max(2, current_multiplier * 1.1)], 
                      aspect='auto', cmap='viridis', alpha=gradient_alpha)

            # Add subtle glowing effect
            for i, alpha in zip(range(3), [0.05, 0.03, 0.01]):
                plt.plot(x, y, color='white', linewidth=6+i*2, alpha=alpha, zorder=1)

            # Determine line color and style based on game state
            if crashed:
                line_color = '#FF5555'  # Bright red for crash
                line_style = '-'
                line_width = 4
                glow_color = '#FF0000'
            elif cash_out:
                line_color = '#55FF55'  # Bright green for cashout
                line_style = '-'
                line_width = 4
                glow_color = '#00FF00'
            else:
                # Create a gradient line color based on multiplier
                if current_multiplier < 1.5:
                    line_color = '#00FFAE'  # Teal/cyan color
                    glow_color = '#00FFAE'
                elif current_multiplier < 3:
                    line_color = '#FFDD00'  # Yellow
                    glow_color = '#FFDD00'
                elif current_multiplier < 7:
                    line_color = '#FF8800'  # Orange
                    glow_color = '#FF8800'
                else:
                    line_color = '#FF4400'  # Deep orange/red
                    glow_color = '#FF4400'
                line_style = '-'
                line_width = 3.5

            # Add subtle line glow effect
            for i, alpha in zip(range(3), [0.2, 0.1, 0.05]):
                plt.plot(x, y, color=glow_color, linewidth=line_width+i, alpha=alpha, zorder=3)

            # Plot the main line
            plt.plot(x, y, color=line_color, linewidth=line_width, linestyle=line_style, zorder=4)

            # Add points along the curve for visual effect
            if not crashed and not cash_out and current_multiplier > 1.2:
                # More points for higher multipliers
                n_points = min(int(current_multiplier * 4), 40)
                point_indices = np.linspace(0, len(x)-1, n_points, dtype=int)

                # Add glow to points
                for i, alpha in zip(range(3), [0.1, 0.05, 0.02]):
                    plt.scatter(x[point_indices], y[point_indices], color='white', s=20+i*10, alpha=alpha, zorder=4)

                # Main points with pulsating sizes based on index
                sizes = 15 + 10 * np.sin(np.linspace(0, 2*np.pi, len(point_indices)))
                plt.scatter(x[point_indices], y[point_indices], color='white', s=sizes, alpha=0.7, zorder=5)

            # Add special markers and text for crash or cash out points
            if crashed:
                # Create explosion effect for crash
                for i, alpha in zip(range(5), [0.05, 0.1, 0.15, 0.2, 0.3]):
                    plt.scatter([current_multiplier], [current_multiplier], color='darkred', 
                               s=400-i*50, marker='*', alpha=alpha, zorder=5+i)

                # Main explosion
                plt.scatter([current_multiplier], [current_multiplier], color='red', s=150, marker='*', zorder=10)

                # Add "boom" lines radiating from crash point
                n_lines = 12
                for i in range(n_lines):
                    angle = 2 * np.pi * i / n_lines
                    length = 0.3 + 0.1 * np.random.random()
                    dx, dy = length * np.cos(angle), length * np.sin(angle)
                    plt.plot([current_multiplier, current_multiplier+dx], 
                            [current_multiplier, current_multiplier+dy],
                            color='red', alpha=0.6, linewidth=1.5, zorder=9)

                # Add crash text without shadow effect
                plt.text(current_multiplier, current_multiplier + 0.3, f"CRASHED AT {current_multiplier:.2f}x", 
                         color='white', fontweight='bold', fontsize=14, ha='right', va='bottom',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor='red', alpha=0.8, edgecolor='darkred'))

            elif cash_out:
                # Add diamond symbol for cash out with glowing effect
                for i, alpha in zip(range(5), [0.05, 0.1, 0.15, 0.2, 0.3]):
                    plt.scatter([current_multiplier], [current_multiplier], color='darkgreen', 
                               s=300-i*30, marker='D', alpha=alpha, zorder=5+i)

                # Main diamond
                plt.scatter([current_multiplier], [current_multiplier], color='lime', s=130, marker='D', zorder=10)

                # Add shine effect on diamond
                plt.plot([current_multiplier-0.1, current_multiplier+0.1], 
                        [current_multiplier+0.1, current_multiplier-0.1],
                        color='white', alpha=0.8, linewidth=1.5, zorder=11)

                # Add cash out text without shadow effect
                plt.text(current_multiplier, current_multiplier + 0.3, f"CASHED OUT AT {current_multiplier:.2f}x", 
                         color='white', fontweight='bold', fontsize=14, ha='right', va='bottom',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor='green', alpha=0.8, edgecolor='darkgreen'))

            # Add current multiplier display
            # Create a more prominent display in top-right corner
            if not crashed and not cash_out:
                # Add glowing effect around the multiplier text
                for i, alpha in zip(range(3), [0.1, 0.07, 0.04]):
                    plt.text(0.95, 0.95, f"{current_multiplier:.2f}x", 
                             transform=plt.gca().transAxes, color='white', fontsize=22+i, fontweight='bold', 
                             ha='right', va='top', alpha=alpha)

                # Main multiplier text
                plt.text(0.95, 0.95, f"{current_multiplier:.2f}x", 
                         transform=plt.gca().transAxes, color='white', fontsize=22, fontweight='bold', 
                         ha='right', va='top',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor=line_color, alpha=0.8, edgecolor='white', linewidth=1))

            # Set axes properties with improved grid
            plt.grid(True, linestyle='--', alpha=0.15, color='white')

            # Add grid highlights at important multiplier levels
            highlight_multipliers = [2, 5, 10, 15]
            for m in highlight_multipliers:
                if m <= current_multiplier * 1.1:
                    plt.axhline(y=m, color='white', alpha=0.2, linestyle='-', linewidth=0.8)
                    plt.text(0.05, m, f"{m}x", color='white', alpha=0.5, fontsize=8, va='bottom')

            # Set limits with more headroom for visual effect
            plt.xlim(0, max(2, current_multiplier * 1.15))
            plt.ylim(0, max(2, current_multiplier * 1.15))

            # Remove axis numbers, keep only the graph
            plt.xticks([])
            plt.yticks([])

            # Remove spines (borders)
            for spine in plt.gca().spines.values():
                spine.set_visible(False)

            # Add subtle BetSync watermark/branding
            # Add BetSync watermark
            plt.text(0.5, 0.03, "BetSync Casino", transform=plt.gca().transAxes,
                    color='white', alpha=0.3, fontsize=14, fontweight='bold', ha='center')

            # Save plot to bytes buffer with higher quality
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', transparent=False)
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
    bot.add_cog(CrashCog(bot))