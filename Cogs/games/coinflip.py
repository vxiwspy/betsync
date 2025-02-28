
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, side=None, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.side = side
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
                
                # Start a new game with max amount, passing the previous side choice
                if self.side:
                    await self.cog.coinflip(self.ctx, str(bet_amount), None, self.side)
                else:
                    await self.cog.coinflip(self.ctx, str(bet_amount))
            
            @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
            async def cancel_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)
                
                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                await i.followup.send("Coinflip cancelled.", ephemeral=True)
            
            confirm_view.add_item(confirm_button)
            confirm_view.add_item(cancel_button)
            
            await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
        else:
            # User can afford the same bet
            await interaction.followup.send("Starting a new game with the same bet...", ephemeral=True)
            # Pass the previous side choice if available
            if self.side:
                await self.cog.coinflip(self.ctx, str(self.bet_amount), None, self.side)
            else:
                await self.cog.coinflip(self.ctx, str(self.bet_amount))
    
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


class CoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["cf", "coin", "flip"])
    async def coinflip(self, ctx, bet_amount: str = None, currency_type: str = None, side: str = None):
        """Play coinflip - bet on heads or tails to win 1.95x your bet!"""
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Coinflip",
                description=(
                    "**Coinflip** is a game where you bet on the outcome of a coin toss.\n\n"
                    "**Usage:** `!coinflip <amount> [currency_type] [heads/tails]`\n"
                    "**Example:** `!coinflip 100` or `!coinflip 100 tokens heads`\n\n"
                    "- **If you don't specify heads or tails, one will be chosen randomly**\n"
                    "- **If you win, you receive 1.95x your bet!**\n"
                    "- **If you lose, you lose your bet**\n"
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
            title=f"{loading_emoji} | Preparing Coinflip Game...",
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
            # Check if the user provided a side instead of currency
            elif currency_type.lower() in ['heads', 'tails', 'h', 't']:
                side = currency_type
                currency_type = None

        # Check if user specified a side in any argument
        if side:
            side = side.lower()
            if side in ['h', 'heads']:
                side = 'heads'
            elif side in ['t', 'tails']:
                side = 'tails'
            else:
                side = random.choice(['heads', 'tails'])
        else:
            side = random.choice(['heads', 'tails'])

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
            "bet_amount": total_bet,
            "side": side
        }

        # Delete loading message
        await loading_message.delete()

        try:
            # Create initial embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Coinflip Game",
                description=f"{bet_description}\n**Your Choice:** {side.capitalize()}\n\n{coin_flip_animated} Flipping coin...",
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Send initial message
            message = await ctx.reply(embed=initial_embed)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Determine the result
            result = random.choice(['heads', 'tails'])
            
            # Use custom coin emojis
            heads_emoji = "<:heads:1344974756448833576>"
            tails_emoji = "<:tails:1344974822009999451>"
            
            result_emoji = heads_emoji if result == 'heads' else tails_emoji
            
            # Determine if user won
            user_won = side == result

            # Define the multiplier (for a win)
            # House edge of ~2.5%
            multiplier = 1.95

            # Calculate winnings
            winnings = 0
            if user_won:
                winnings = total_bet * multiplier
                
                # Update user balance - use increment operator to add to existing balance
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")
                
                # Add to win history
                win_entry = {
                    "type": "win",
                    "game": "coinflip",
                    "bet": total_bet,
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
                        "game": "coinflip",
                        "user_id": ctx.author.id,
                        "user_name": ctx.author.name,
                        "bet": total_bet,
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
            else:
                # Add to loss history
                loss_entry = {
                    "type": "loss",
                    "game": "coinflip",
                    "bet": total_bet,
                    "amount": total_bet,
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
                        "game": "coinflip",
                        "user_id": ctx.author.id,
                        "user_name": ctx.author.name,
                        "bet": total_bet,
                        "timestamp": int(time.time())
                    }
                    server_db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$push": {"server_bet_history": {"$each": [server_loss_entry], "$slice": -100}}}
                    )
                    
                    # Update server profit
                    server_db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {"$inc": {"total_profit": total_bet}}
                    )
                
                # Update user stats
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {"$inc": {"total_lost": 1}}
                )

            # Create result embed
            if user_won:
                result_embed = discord.Embed(
                    title="🪙 | Coinflip Result",
                    description=(
                        f"{bet_description}\n"
                        f"**Your Choice:** {side.capitalize()}\n\n"
                        f"{result_emoji} **Result: {result.capitalize()}**\n\n"
                        f"🎉 **You won {winnings:.2f} credits!**\n"
                        f"Multiplier: {multiplier}x"
                    ),
                    color=0x00FF00
                )
            else:
                result_embed = discord.Embed(
                    title="🪙 | Coinflip Result",
                    description=(
                        f"{bet_description}\n"
                        f"**Your Choice:** {side.capitalize()}\n\n"
                        f"{result_emoji} **Result: {result.capitalize()}**\n\n"
                        f"❌ **You lost your bet.**"
                    ),
                    color=0xFF0000
                )

            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            
            # Create view with play again button, including the player's choice for next game
            play_again_view = PlayAgainView(self, ctx, total_bet, side)
            
            # Update message with result
            await message.edit(embed=result_embed, view=play_again_view)
            
            # Store message reference in view for timeout handling
            play_again_view.message = message
            
            # Clear ongoing game
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]
                
        except Exception as e:
            # Handle any errors
            print(f"Error in coinflip game: {e}")
            error_embed = discord.Embed(
                title="❌ | Error",
                description="An error occurred while playing coinflip. Please try again later.",
                color=0xFF0000
            )
            await ctx.send(embed=error_embed)
            
            # Make sure to clean up
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]


def setup(bot):
    bot.add_cog(CoinflipCog(bot))
