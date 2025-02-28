
import discord
import random
import time
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class DiceGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["dice", "roll"])
    async def dicegame(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play a dice game against the dealer. Win if your roll is higher!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":game_die: How to Play Dice",
                description=(
                    "**Dice** is a game where you roll against the dealer. If your roll is higher, you win!\n\n"
                    "**Usage:** `!dice <amount> [currency_type]`\n"
                    "**Example:** `!dice 100` or `!dice 100 tokens`\n\n"
                    "- Roll a dice from 1-6\n"
                    "- Dealer rolls a dice from 1-6\n"
                    "- If your roll is higher, you win 1.8x your bet\n"
                    "- If you tie, you get your bet back\n"
                    "- If dealer wins, you lose your bet\n\n"
                    "You can bet using tokens (T) or credits (C):\n"
                    "- If you have enough tokens, they will be used first\n"
                    "- If you don't have enough tokens, credits will be used\n"
                    "- If needed, both will be combined to meet your bet amount"
                ),
                color=0x00FFAE
            )
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            return await ctx.reply(embed=embed)

        # Check if user already has an ongoing game
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
            title=f"{loading_emoji} | Rolling Dice...",
            description="Please wait while we prepare your game.",
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

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "total_bet": total_bet
        }

        await loading_message.delete()

        # Run the dice game
        await self.run_dice_game(ctx, total_bet)

    async def run_dice_game(self, ctx, bet_amount):
        """Execute the dice game logic"""
        try:
            # Create suspense with animated dice roll
            dice_emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
            
            # Initial rolling embed
            rolling_embed = discord.Embed(
                title="🎲 | Rolling Dice...",
                description=(
                    f"**Bet Amount:** {bet_amount}\n\n"
                    "**Your Roll:** Rolling...\n"
                    "**Dealer Roll:** Waiting..."
                ),
                color=0x00FFAE
            )
            message = await ctx.reply(embed=rolling_embed)
            
            # Animated dice roll for player
            for i in range(3):
                random_dice = random.choice(dice_emojis)
                rolling_embed.description = (
                    f"**Bet Amount:** {bet_amount}\n\n"
                    f"**Your Roll:** {random_dice} Rolling...\n"
                    "**Dealer Roll:** Waiting..."
                )
                await message.edit(embed=rolling_embed)
                await asyncio.sleep(0.7)
            
            # Get the actual player roll (with house edge)
            # House edge implementation: slightly lower chance for higher numbers
            player_roll_options = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 6]  # Balanced distribution
            player_roll = random.choice(player_roll_options)
            player_dice = dice_emojis[player_roll - 1]
            
            rolling_embed.description = (
                f"**Bet Amount:** {bet_amount}\n\n"
                f"**Your Roll:** {player_dice} {player_roll}\n"
                "**Dealer Roll:** Rolling..."
            )
            await message.edit(embed=rolling_embed)
            await asyncio.sleep(1)
            
            # Animated dice roll for dealer
            for i in range(2):
                random_dice = random.choice(dice_emojis)
                rolling_embed.description = (
                    f"**Bet Amount:** {bet_amount}\n\n"
                    f"**Your Roll:** {player_dice} {player_roll}\n"
                    f"**Dealer Roll:** {random_dice} Rolling..."
                )
                await message.edit(embed=rolling_embed)
                await asyncio.sleep(0.7)
            
            # Get the actual dealer roll (with house edge)
            # House edge implementation: slightly higher chance for higher numbers
            dealer_roll_options = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 6, 6]  # Higher chance for 6
            dealer_roll = random.choice(dealer_roll_options)
            dealer_dice = dice_emojis[dealer_roll - 1]
            
            # Determine the result
            db = Users()
            servers_db = Servers()
            
            if player_roll > dealer_roll:
                # Player wins (1.8x multiplier with house edge)
                multiplier = 1.8
                winnings = round(bet_amount * multiplier, 2)
                profit = winnings - bet_amount
                
                result_embed = discord.Embed(
                    title="🎲 | You Won!",
                    description=(
                        f"**Bet Amount:** {bet_amount}\n\n"
                        f"**Your Roll:** {player_dice} {player_roll}\n"
                        f"**Dealer Roll:** {dealer_dice} {dealer_roll}\n\n"
                        f"**Result:** You win with a higher roll!\n"
                        f"**Multiplier:** {multiplier}x\n"
                        f"**Winnings:** {winnings} credits\n"
                        f"**Profit:** {profit} credits"
                    ),
                    color=0x00FF00  # Green color for win
                )
                
                # Add credits to user balance
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")
                
                # Add to history
                history_entry = {
                    "type": "win",
                    "game": "dice",
                    "bet": bet_amount,
                    "amount": winnings,
                    "multiplier": multiplier,
                    "winnings": winnings,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
                
                # Update server history
                history_entry["user_id"] = ctx.author.id
                history_entry["user_name"] = ctx.author.name
                servers_db.update_history(ctx.guild.id, history_entry)
                
                # Update stats
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$inc": {"total_won": 1, "total_earned": winnings}}
                )
                
                # Update server profit (negative because server loses)
                server_profit = -profit
                servers_db.update_server_profit(ctx.guild.id, server_profit)
                
            elif player_roll == dealer_roll:
                # Tie - player gets their bet back
                result_embed = discord.Embed(
                    title="🎲 | It's a Tie!",
                    description=(
                        f"**Bet Amount:** {bet_amount}\n\n"
                        f"**Your Roll:** {player_dice} {player_roll}\n"
                        f"**Dealer Roll:** {dealer_dice} {dealer_roll}\n\n"
                        f"**Result:** It's a tie! Your bet has been refunded."
                    ),
                    color=0xFFD700  # Gold color for tie
                )
                
                # Refund the bet as credits
                db.update_balance(ctx.author.id, bet_amount, "credits", "$inc")
                
                # Add to history
                history_entry = {
                    "type": "tie",
                    "game": "dice",
                    "bet": bet_amount,
                    "amount": bet_amount,
                    "multiplier": 1.0,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
                
                # Update server history
                history_entry["user_id"] = ctx.author.id
                history_entry["user_name"] = ctx.author.name
                servers_db.update_history(ctx.guild.id, history_entry)
                
            else:
                # Player loses
                multiplier = 0
                result_embed = discord.Embed(
                    title="🎲 | You Lost!",
                    description=(
                        f"**Bet Amount:** {bet_amount}\n\n"
                        f"**Your Roll:** {player_dice} {player_roll}\n"
                        f"**Dealer Roll:** {dealer_dice} {dealer_roll}\n\n"
                        f"**Result:** You lose with a lower roll."
                    ),
                    color=0xFF0000  # Red color for loss
                )
                
                # Add to history
                history_entry = {
                    "type": "loss",
                    "game": "dice",
                    "bet": bet_amount,
                    "amount": bet_amount,
                    "multiplier": multiplier,
                    "timestamp": int(time.time())
                }
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}
                )
                
                # Update server history
                history_entry["user_id"] = ctx.author.id
                history_entry["user_name"] = ctx.author.name
                servers_db.update_history(ctx.guild.id, history_entry)
                
                # Update stats
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$inc": {"total_lost": 1}}
                )
                
                # Update server profit
                servers_db.update_server_profit(ctx.guild.id, bet_amount)
            
            # Add play again button
            play_again_view = discord.ui.View()
            play_again_button = discord.ui.Button(
                label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄"
            )

            async def play_again_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("This is not your game!", ephemeral=True)

                # Start a new game with the same bet
                await interaction.response.defer()
                await self.dicegame(ctx, str(bet_amount))

            play_again_button.callback = play_again_callback
            play_again_view.add_item(play_again_button)
            
            # Update the message with result
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await message.edit(embed=result_embed, view=play_again_view)
            
        except Exception as e:
            print(f"Error in dice game: {e}")
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
                if ctx.author.id in self.ongoing_games:
                    game_data = self.ongoing_games[ctx.author.id]
                    if "tokens_used" in game_data and game_data["tokens_used"] > 0:
                        current_tokens = db.fetch_user(ctx.author.id)['tokens']
                        db.update_balance(ctx.author.id, current_tokens + game_data["tokens_used"], "tokens")

                    if "credits_used" in game_data and game_data["credits_used"] > 0:
                        current_credits = db.fetch_user(ctx.author.id)['credits']
                        db.update_balance(ctx.author.id, current_credits + game_data["credits_used"], "credits")
            except Exception as refund_error:
                print(f"Error refunding bet: {refund_error}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(DiceGame(bot))
