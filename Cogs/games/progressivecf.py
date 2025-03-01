import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class CoinChoiceView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_type):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_type = currency_type
        self.choice = None
        self.message = None

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary, emoji="<:heads:1344974756448833576>")
    async def heads_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "heads"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Start the game with heads
        await self.cog.start_progressive_game(self.ctx, self.message, self.bet_amount, self.currency_type, "heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="<:tails:1344974822009999451>")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "tails"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Start the game with tails
        await self.cog.start_progressive_game(self.ctx, self.message, self.bet_amount, self.currency_type, "tails")

    async def on_timeout(self):
        if not self.choice:
            for item in self.children:
                item.disabled = True

            try:
                await self.message.edit(view=self)
                await self.ctx.send(f"{self.ctx.author.mention} Game cancelled due to inactivity.")

                # Clean up ongoing game
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            except:
                pass


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
        await interaction.response.edit_message(view=self)

        # Continue flipping with heads
        await self.cog.continue_progressive_flips(self.ctx, interaction, self.message, 
                                                 self.bet_amount, self.currency_used, 
                                                 "heads", self.current_flips, 
                                                 self.current_multiplier)

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="<:tails:1344974822009999451>")
    async def tails_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.choice = "tails"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Continue flipping with tails
        await self.cog.continue_progressive_flips(self.ctx, interaction, self.message, 
                                                 self.bet_amount, self.currency_used, 
                                                 "tails", self.current_flips, 
                                                 self.current_multiplier)

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout_button(self, button, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

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
            await self.cog.pcf(self.ctx, str(self.bet_amount), self.currency_type)
        elif tokens_balance + credits_balance >= self.bet_amount:
            # Ask which currency to use
            if tokens_balance >= self.bet_amount:
                await self.cog.pcf(self.ctx, str(self.bet_amount), "tokens")
            else:
                await self.cog.pcf(self.ctx, str(self.bet_amount), "credits")
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
                    await self.cog.pcf(self.ctx, str(max_bet), "tokens")
                else:
                    await self.cog.pcf(self.ctx, str(max_bet), "credits")

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

    @commands.command(aliases=["progressive", "progressiveflip", "progcoin"])
    async def pcf(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Progressive Coinflip - keep winning to multiply your profits!"""

        # Show usage if no bet amount provided
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Progressive Coinflip",
                description=(
                    "**Progressive Coinflip** is a game where you can keep flipping coins to increase your multiplier!\n\n"
                    "**Usage:** `!pcf <amount> [currency_type]`\n"
                    "**Example:** `!pcf 100` or `!pcf 100 tokens`\n\n"
                    "- Each successful flip increases your multiplier by 1.96x\n"
                    "- You can flip up to 15 times in a row\n"
                    "- Cash out anytime after the first flip to secure your winnings\n"
                    "- If you lose a flip, you lose everything\n"
                    "- Winnings are always paid in credits\n\n"
                    "**Maximum potential multiplier:** 1.96^15 = 12,621.99x"
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
            title=f"{loading_emoji} | Preparing Progressive Coinflip Game...",
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

        # Process currency type
        if currency_type is None or currency_type.lower() in ['t', 'token', 'tokens']:
            currency_type = 'tokens'
            display_currency = 'tokens'
        elif currency_type.lower() in ['c', 'credit', 'credits']:
            currency_type = 'credits'
            display_currency = 'credits'
        else:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description="Please use 'tokens' (t) or 'credits' (c).",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Process bet amount
        try:
            # Handle 'all' or 'max' bet
            if bet_amount.lower() in ['all', 'max']:
                if currency_type == 'tokens':
                    bet_amount_value = user_data['tokens']
                else:
                    bet_amount_value = user_data['credits']
            else:
                # Check if bet_amount has 'k' or 'm' suffix
                if bet_amount.lower().endswith('k'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000
                elif bet_amount.lower().endswith('m'):
                    bet_amount_value = float(bet_amount[:-1]) * 1000000
                else:
                    bet_amount_value = float(bet_amount)
        except ValueError:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Please enter a valid bet amount.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Ensure bet amount is positive
        if bet_amount_value <= 0:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Bet amount must be greater than 0.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if the user has enough balance for the specified currency
        if currency_type == 'tokens':
            if user_data['tokens'] < bet_amount_value:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Tokens",
                    description=f"You don't have enough tokens. Your balance: **{user_data['tokens']:.2f} tokens**\nRequired: **{bet_amount_value:.2f} tokens**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:  # credits
            if user_data['credits'] < bet_amount_value:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Credits",
                    description=f"You don't have enough credits. Your balance: **{user_data['credits']:.2f} credits**\nRequired: **{bet_amount_value:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Deduct bet from user's balance
        db.update_balance(ctx.author.id, -bet_amount_value, currency_type, "$inc")

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount_value,
            "currency_type": currency_type
        }

        # Update game stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": bet_amount_value}}
        )

        # Delete loading message
        await loading_message.delete()

        # Create bet description text
        bet_description = f"**Bet:** {bet_amount_value:.2f} {display_currency}"

        # Create game start embed with heads/tails buttons
        start_embed = discord.Embed(
            title="🪙 | Progressive Coinflip",
            description=(
                f"{bet_description}\n"
                f"Choose heads or tails to start flipping!"
            ),
            color=0x00FFAE
        )
        start_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Create view with heads/tails buttons
        coin_choice_view = CoinChoiceView(self, ctx, bet_amount_value, display_currency)
        message = await ctx.reply(embed=start_embed, view=coin_choice_view)
        coin_choice_view.message = message

    async def start_progressive_game(self, ctx, message, bet_amount, currency_used, side):
        """Start the progressive coinflip game after the user selects a side"""

        # Initial multiplier
        initial_multiplier = 1.96

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

    async def process_cashout(self, ctx, interaction, message, bet_amount, currency_used, flips, multiplier, auto_cashout=False):
        """Process cashout from progressive coinflip"""

        # Calculate winnings
        winnings = round(bet_amount * multiplier, 2)

        # Create cashout embed
        cashout_embed = discord.Embed(
            title="🪙 | Progressive Coinflip - CASHED OUT!",
            description=(
                f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Flips:** {flips}/15\n"
                f"**Final Multiplier:** {multiplier}x\n\n"
                f"💰 **YOU WON {winnings:.2f} CREDITS!** 💰"
            ),
            color=0x00FF00
        )

        if auto_cashout:
            cashout_embed.description += "\n*Auto-cashed out due to inactivity*"

        cashout_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        # Update message
        if interaction:
            await interaction.response.edit_message(embed=cashout_embed, view=None)
        else:
            await message.edit(embed=cashout_embed, view=None)

        # Process win
        await self.process_win(ctx, bet_amount, multiplier, flips)

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


def setup(bot):
    bot.add_cog(ProgressiveCoinflipCog(bot))