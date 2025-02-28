
import discord
import random
import time
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount):
        super().__init__(timeout=15)  # 15 second timeout
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄")
    async def play_again(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable button to prevent multiple clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Start a new game with the same bet
        await interaction.response.defer()
        await self.cog.dicegame(self.ctx, str(self.bet_amount))

    async def on_timeout(self):
        # Disable button after timeout
        for item in self.children:
            item.disabled = True
        
        # Try to update the message if it exists
        try:
            await self.message.edit(view=self)
        except:
            pass

class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["dice", "roll", "d"])
    async def dicegame(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play the dice game - roll higher than the dealer to win!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":game_die: How to Play Dice",
                description=(
                    "**Dice** is a game where you roll against the dealer. Higher number wins!\n\n"
                    "**Usage:** `!dicegame <amount> [currency_type]`\n"
                    "**Example:** `!dicegame 100` or `!dicegame 100 tokens`\n\n"
                    "- You and the dealer each roll a dice (1-6)\n"
                    "- If your number is higher, you win!\n"
                    "- If there's a tie or dealer wins, you lose your bet\n"
                    "- House edge: 4% (you need to roll higher, not equal)\n\n"
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
            title=f"{loading_emoji} | Preparing Dice Game...",
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

        # Format bet description
        if tokens_used > 0 and credits_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens + {credits_used} credits"
        elif tokens_used > 0:
            bet_description = f"**Bet Amount:** {tokens_used} tokens"
        else:
            bet_description = f"**Bet Amount:** {credits_used} credits"

        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "bet_amount": total_bet
        }

        # Delete loading message
        await loading_message.delete()

        try:
            # Create initial embed with rolling animation
            rolling_dice = "<a:rollingdice:1328757546345042034>"
            initial_embed = discord.Embed(
                title="🎲 | Dice Game",
                description=f"{bet_description}\n\n{rolling_dice} Rolling the dice... {rolling_dice}",
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Send initial message
            message = await ctx.reply(embed=initial_embed)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Roll the dice
            user_roll = random.randint(1, 6)
            dealer_roll = random.randint(1, 6)

            # Use custom dice emojis
            dice_emojis = {
                1: "<:d1:1344966667628970025>",
                2: "<:d2:1344966647798300786>",
                3: "<:d3:1344966630458789919>",
                4: "<:d4:1344966603544199258>",
                5: "<:d5:1344966572883574835>",
                6: "<:d6:1344966538775629965>"
            }

            user_dice = dice_emojis.get(user_roll, "🎲")
            dealer_dice = dice_emojis.get(dealer_roll, "🎲")

            # Determine the winner
            user_won = user_roll > dealer_roll

            # Define the multiplier (for a win)
            # House edge of at least 4%
            multiplier = 1.9  # With 6 sides, fair would be 2.0, so 1.9 gives ~5% house edge

            # Create result embed
            if user_won:
                # Calculate winnings
                winnings = round(total_bet * multiplier, 2)
                profit = winnings - total_bet

                result_embed = discord.Embed(
                    title="🎲 | Dice Game - You Won! 🎉",
                    description=(
                        f"{bet_description}\n\n"
                        f"Your Roll: {user_dice} ({user_roll})\n"
                        f"Dealer Roll: {dealer_dice} ({dealer_roll})\n\n"
                        f"**Multiplier:** {multiplier}x\n"
                        f"**Winnings:** {winnings} credits\n"
                        f"**Profit:** {profit} credits"
                    ),
                    color=0x00FF00
                )

                # Update user balance
                db = Users()
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")

                # Update server profit (negative value because server loses when player wins)
                servers_db = Servers()
                server_profit = -profit  # Server loses money when player wins
                servers_db.update_server_profit(ctx.guild.id, server_profit)

                # Add to history
                history_entry = {
                    "type": "win",
                    "game": "dice",
                    "bet": total_bet,
                    "amount": winnings,
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
                    {"$inc": {"total_won": 1, "total_earned": winnings}}
                )

            else:
                result_embed = discord.Embed(
                    title="🎲 | Dice Game - You Lost 😢",
                    description=(
                        f"{bet_description}\n\n"
                        f"Your Roll: {user_dice} ({user_roll})\n"
                        f"Dealer Roll: {dealer_dice} ({dealer_roll})\n\n"
                        f"**Result:** You lost your bet!"
                    ),
                    color=0xFF0000
                )

                # Update history for loss
                db = Users()
                servers_db = Servers()

                history_entry = {
                    "type": "loss",
                    "game": "dice",
                    "bet": total_bet,
                    "amount": total_bet,
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
                servers_db.update_server_profit(ctx.guild.id, total_bet)

            # Add play again button that expires after 15 seconds
            play_again_view = PlayAgainView(self, ctx, total_bet)
            
            # Update the message with result
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            await message.edit(embed=result_embed, view=play_again_view)
            
            # Store message reference in view for timeout handling
            play_again_view.message = message

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

                # Refund the bet
                db = Users()
                if tokens_used > 0:
                    current_tokens = db.fetch_user(ctx.author.id)['tokens']
                    db.update_balance(ctx.author.id, current_tokens + tokens_used, "tokens")

                if credits_used > 0:
                    current_credits = db.fetch_user(ctx.author.id)['credits']
                    db.update_balance(ctx.author.id, current_credits + credits_used, "credits")
            except Exception as refund_error:
                print(f"Error refunding bet: {refund_error}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(DiceCog(bot))
