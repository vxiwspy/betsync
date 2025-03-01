
import discord
import random
import asyncio
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, side=None, timeout=30):
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

        if tokens_balance >= self.bet_amount:
            # Use tokens preferentially
            await self.cog.pcf(self.ctx, str(self.bet_amount), "tokens", self.side)
        elif credits_balance >= self.bet_amount:
            # Use credits if not enough tokens
            await self.cog.pcf(self.ctx, str(self.bet_amount), "credits", self.side)
        else:
            # Not enough funds, ask if they want to bet a smaller amount
            confirm_embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough funds to bet {self.bet_amount}. Would you like to bet a lower amount?",
                color=0xFF0000
            )
            
            # Create confirm view for smaller bet
            confirm_view = discord.ui.View(timeout=30)
            
            @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
            async def confirm_button(b, i):
                if i.user.id != self.ctx.author.id:
                    return await i.response.send_message("This is not your game!", ephemeral=True)
                
                for child in confirm_view.children:
                    child.disabled = True
                await i.response.edit_message(view=confirm_view)
                
                max_bet = max(tokens_balance, credits_balance)
                bet_amount = min(max_bet, self.bet_amount)
                
                if bet_amount <= 0:
                    return await i.followup.send("You don't have any funds to play. Please deposit first.", ephemeral=True)
                
                # Start a new game with the maximum affordable bet
                if tokens_balance >= bet_amount:
                    await self.cog.pcf(self.ctx, str(bet_amount), "tokens", self.side)
                else:
                    await self.cog.pcf(self.ctx, str(bet_amount), "credits", self.side)
            
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
        # Disable button after timeout
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(view=self)
        except:
            pass

class ContinueFlipView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, currency_used, side, current_flips, current_multiplier, timeout=45):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.currency_used = currency_used
        self.side = side
        self.flips = current_flips
        self.multiplier = current_multiplier
        self.message = None

    @discord.ui.button(label="Continue Flipping", style=discord.ButtonStyle.primary, emoji="🪙")
    async def continue_flipping(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable the buttons
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Continue the game
        await self.cog.continue_progressive_flips(
            self.ctx, 
            interaction, 
            self.message,
            self.bet_amount, 
            self.currency_used, 
            self.side, 
            self.flips, 
            self.multiplier
        )

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, emoji="💰")
    async def cash_out(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Process cash out
        current_winnings = self.bet_amount * self.multiplier
        
        # Update database
        db = Users()
        db.update_balance(self.ctx.author.id, current_winnings, "credits", "$inc")
        
        # Update history for user
        history_entry = {
            "type": "win",
            "game": "pcf",
            "bet": self.bet_amount,
            "amount": current_winnings,
            "multiplier": self.multiplier,
            "flips": self.flips,
            "timestamp": int(time.time())
        }
        
        db.collection.update_one(
            {"discord_id": self.ctx.author.id},
            {
                "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                "$inc": {
                    "total_played": 1,
                    "total_won": 1,
                    "total_earned": current_winnings
                }
            }
        )
        
        # Update server history
        server_db = Servers()
        server_data = server_db.fetch_server(self.ctx.guild.id)
        
        if server_data:
            server_history_entry = {
                "type": "win",
                "game": "pcf",
                "user_id": self.ctx.author.id,
                "user_name": self.ctx.author.name,
                "bet": self.bet_amount,
                "amount": current_winnings,
                "multiplier": self.multiplier,
                "flips": self.flips,
                "timestamp": int(time.time())
            }
            
            server_db.collection.update_one(
                {"server_id": self.ctx.guild.id},
                {
                    "$push": {"server_bet_history": {"$each": [server_history_entry], "$slice": -100}},
                    "$inc": {"total_profit": -current_winnings + self.bet_amount}
                }
            )
        
        # Create winnings embed
        winnings_embed = discord.Embed(
            title="💰 | Progressive Coinflip Cash Out",
            description=(
                f"You've cashed out after **{self.flips}** successful flips!\n\n"
                f"**Initial Bet:** {self.bet_amount} {self.currency_used}\n"
                f"**Final Multiplier:** {self.multiplier:.2f}x\n"
                f"**Winnings:** {current_winnings:.2f} credits"
            ),
            color=0x00FF00
        )
        
        heads_emoji = "<:heads:1344974756448833576>"
        tails_emoji = "<:tails:1344974822009999451>"
        chosen_emoji = heads_emoji if self.side == "heads" else tails_emoji
        
        winnings_embed.add_field(
            name="Your Streak",
            value=f"{chosen_emoji} " * self.flips,
            inline=False
        )
        
        winnings_embed.set_footer(text="BetSync Casino", icon_url=self.cog.bot.user.avatar.url)
        
        # Edit message with winnings info
        await self.message.edit(embed=winnings_embed)
        
        # Send additional confirmation
        await interaction.followup.send(
            f"💰 You successfully cashed out {current_winnings:.2f} credits!", 
            ephemeral=True
        )
        
        # Add play again view
        play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount, self.side)
        await self.message.edit(embed=winnings_embed, view=play_again_view)
        play_again_view.message = self.message

    async def on_timeout(self):
        # Auto cash out on timeout
        for item in self.children:
            item.disabled = True
            
        try:
            await self.message.edit(view=self)
            
            # Only process cash out if user hasn't already continued or cashed out
            if not all(child.disabled for child in self.children):
                current_winnings = self.bet_amount * self.multiplier
                
                # Update database
                db = Users()
                db.update_balance(self.ctx.author.id, current_winnings, "credits", "$inc")
                
                # Update user history
                history_entry = {
                    "type": "win",
                    "game": "pcf",
                    "bet": self.bet_amount,
                    "amount": current_winnings,
                    "multiplier": self.multiplier,
                    "flips": self.flips,
                    "timestamp": int(time.time())
                }
                
                db.collection.update_one(
                    {"discord_id": self.ctx.author.id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {
                            "total_played": 1,
                            "total_won": 1,
                            "total_earned": current_winnings
                        }
                    }
                )
                
                # Update server history
                server_db = Servers()
                server_data = server_db.fetch_server(self.ctx.guild.id)
                
                if server_data:
                    server_history_entry = {
                        "type": "win",
                        "game": "pcf",
                        "user_id": self.ctx.author.id,
                        "user_name": self.ctx.author.name,
                        "bet": self.bet_amount,
                        "amount": current_winnings,
                        "multiplier": self.multiplier,
                        "flips": self.flips,
                        "timestamp": int(time.time())
                    }
                    
                    server_db.collection.update_one(
                        {"server_id": self.ctx.guild.id},
                        {
                            "$push": {"server_bet_history": {"$each": [server_history_entry], "$slice": -100}},
                            "$inc": {"total_profit": -current_winnings + self.bet_amount}
                        }
                    )
                
                # Create auto cash out embed
                timeout_embed = discord.Embed(
                    title="⏰ | Auto Cash Out - Time Expired",
                    description=(
                        f"Time expired - you've been automatically cashed out after **{self.flips}** successful flips!\n\n"
                        f"**Initial Bet:** {self.bet_amount} {self.currency_used}\n"
                        f"**Final Multiplier:** {self.multiplier:.2f}x\n"
                        f"**Winnings:** {current_winnings:.2f} credits"
                    ),
                    color=0x00FFAE
                )
                
                heads_emoji = "<:heads:1344974756448833576>"
                tails_emoji = "<:tails:1344974822009999451>"
                chosen_emoji = heads_emoji if self.side == "heads" else tails_emoji
                
                timeout_embed.add_field(
                    name="Your Streak",
                    value=f"{chosen_emoji} " * self.flips,
                    inline=False
                )
                
                timeout_embed.set_footer(text="BetSync Casino", icon_url=self.cog.bot.user.avatar.url)
                
                # Edit message with auto cash out info
                await self.message.edit(embed=timeout_embed)
                
                # Add play again view
                play_again_view = PlayAgainView(self.cog, self.ctx, self.bet_amount, self.side)
                await self.message.edit(embed=timeout_embed, view=play_again_view)
                play_again_view.message = self.message
        except:
            pass

class ProgressiveCoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pcf", "progressive", "progressiveflip", "progcoin"])
    async def pcf(self, ctx, bet_amount: str = None, currency_type: str = None, side: str = None):
        """Progressive Coinflip - keep winning to multiply your profits!"""
        
        # Show usage if no bet amount provided
        if not bet_amount:
            embed = discord.Embed(
                title="🪙 How to Play Progressive Coinflip",
                description=(
                    "**Progressive Coinflip** is a game where you can keep flipping coins to increase your multiplier!\n\n"
                    "**Usage:** `!pcf <amount> [currency_type] [heads/tails]`\n"
                    "**Example:** `!pcf 100` or `!pcf 100 tokens heads`\n\n"
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

        # Auto-select currency if not specified
        if currency_type is None:
            tokens_balance = user_data['tokens']
            credits_balance = user_data['credits']
            
            # Use currency with higher balance, or tokens if equal
            if tokens_balance >= credits_balance and tokens_balance > 0:
                currency_type = "tokens"
            elif credits_balance > 0:
                currency_type = "credits"
            else:
                currency_type = "tokens"  # Default to tokens if both are 0

        # Process bet amount
        try:
            # Handle 'all' or 'max' bet
            if bet_amount.lower() in ['all', 'max']:
                tokens_balance = user_data['tokens']
                credits_balance = user_data['credits']
                
                # Determine which currency to use if not specified
                if currency_type is None:
                    # Use tokens if available, otherwise credits
                    if tokens_balance > 0:
                        bet_amount_value = tokens_balance
                        currency_type = 'tokens'
                    elif credits_balance > 0:
                        bet_amount_value = credits_balance
                        currency_type = 'credits'
                    else:
                        embed = discord.Embed(
                            title="<:no:1344252518305234987> | Insufficient Funds",
                            description="You don't have any tokens or credits to bet.",
                            color=0xFF0000
                        )
                        await loading_message.delete()
                        return await ctx.reply(embed=embed)
                elif currency_type.lower() in ['t', 'token', 'tokens']:
                    bet_amount_value = tokens_balance
                    currency_type = 'tokens'
                elif currency_type.lower() in ['c', 'credit', 'credits']:
                    bet_amount_value = credits_balance
                    currency_type = 'credits'
                else:
                    await loading_message.delete()
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Currency",
                        description="Please use 'tokens' (t) or 'credits' (c).",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)
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

        # Process currency type
        if currency_type is None or currency_type.lower() in ['t', 'token', 'tokens']:
            currency_type = 'tokens'
            db_field = 'tokens'
            display_currency = 'tokens'
        elif currency_type.lower() in ['c', 'credit', 'credits']:
            currency_type = 'credits'
            db_field = 'credits'
            display_currency = 'credits'
        else:
            # If currency_type is actually the side
            if side is None and currency_type.lower() in ['h', 'head', 'heads', 't', 'tail', 'tails']:
                side = currency_type.lower()
                currency_type = 'tokens' if user_data['tokens'] >= bet_amount_value else 'credits'
                db_field = currency_type
                display_currency = currency_type
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Currency",
                    description="Please use 'tokens' (t) or 'credits' (c).",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Check if the user has enough balance
        user_balance = user_data[db_field]
        if user_balance < bet_amount_value:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Insufficient Funds",
                description=f"You don't have enough {display_currency}. Your balance: **{user_balance:.2f} {display_currency}**\nRequired: **{bet_amount_value:.2f} {display_currency}**",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Normalize side
        if side is None:
            # Randomly choose if not provided
            side = random.choice(['heads', 'tails'])
        elif side.lower() in ['h', 'head', 'heads']:
            side = 'heads'
        elif side.lower() in ['t', 'tail', 'tails']:
            side = 'tails'
        else:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Side",
                description="Please choose 'heads' (h) or 'tails' (t).",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = True

        # Deduct bet from user's balance
        db.update_balance(ctx.author.id, -bet_amount_value, db_field, "$inc")

        # Delete loading message
        await loading_message.delete()

        # Create bet description text
        bet_description = f"**Bet:** {bet_amount_value:.2f} {display_currency}"

        # Initial multiplier
        initial_multiplier = 1.96

        # Create animated coinflip
        try:
            # Create initial embed with rolling animation
            coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
            initial_embed = discord.Embed(
                title="🪙 | Progressive Coinflip",
                description=(
                    f"{bet_description}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Initial Multiplier:** {initial_multiplier}x\n\n"
                    f"{coin_flip_animated} Flipping coin..."
                ),
                color=0x00FFAE
            )
            initial_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

            # Send initial message
            message = await ctx.reply(embed=initial_embed)

            # Wait for dramatic effect
            await asyncio.sleep(2)

            # Start the progressive coinflip game
            await self.continue_progressive_flips(
                ctx, 
                None, 
                message,
                bet_amount_value, 
                display_currency, 
                side, 
                0, 
                1.0
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

        # Animated countdown
        if interaction:
            # If continuing from a previous flip, we need to acknowledge the interaction
            try:
                await interaction.followup.send("Flipping next coin...", ephemeral=True)
            except:
                pass
                
        # Create flipping animation
        coin_flip_animated = "<a:coinflipAnimated:1344971284513030235>"
        flipping_embed = discord.Embed(
            title="🪙 | Progressive Coinflip",
            description=(
                f"**Bet:** {bet_amount:.2f} {currency_used}\n"
                f"**Your Choice:** {side.capitalize()}\n"
                f"**Current Flips:** {current_flips}\n"
                f"**Current Multiplier:** {current_multiplier:.2f}x\n\n"
                f"{coin_flip_animated} Flipping coin..."
            ),
            color=0x00FFAE
        )
        
        if current_flips > 0:
            chosen_emoji = heads_emoji if side == "heads" else tails_emoji
            flipping_embed.add_field(
                name="Your Streak",
                value=f"{chosen_emoji} " * current_flips,
                inline=False
            )
            
        flipping_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Update message with flipping animation
        await message.edit(embed=flipping_embed)
        
        # Wait for dramatic effect
        await asyncio.sleep(2)
        
        # Increment flips counter
        new_flips = current_flips + 1
        
        # Calculate new multiplier (only on win)
        new_multiplier = current_multiplier
        if user_won:
            if current_flips == 0:
                # First flip uses initial multiplier directly
                new_multiplier = 1.96
            else:
                # Each subsequent flip multiplies by 1.96
                new_multiplier = current_multiplier * 1.96
        
        # Format the results
        if user_won:
            max_flips = 15  # Maximum number of flips allowed
            
            # Generate result embed
            result_embed = discord.Embed(
                title="🎉 | Progressive Coinflip - You Won!",
                description=(
                    f"**Result:** {result.capitalize()} {result_emoji}\n"
                    f"**Your Choice:** {side.capitalize()}\n"
                    f"**Current Flips:** {new_flips}\n"
                    f"**Current Multiplier:** {new_multiplier:.2f}x\n\n"
                    f"**Current Potential Winnings:** {bet_amount * new_multiplier:.2f} credits"
                ),
                color=0x00FF00
            )
            
            chosen_emoji = heads_emoji if side == "heads" else tails_emoji
            result_embed.add_field(
                name="Your Streak",
                value=f"{chosen_emoji} " * new_flips,
                inline=False
            )
            
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            
            # Check if we've hit the max flips
            if new_flips >= max_flips:
                # Forced cash out at max flips
                winnings = bet_amount * new_multiplier
                
                # Update database
                db = Users()
                db.update_balance(ctx.author.id, winnings, "credits", "$inc")
                
                # Update user history
                history_entry = {
                    "type": "win",
                    "game": "pcf",
                    "bet": bet_amount,
                    "amount": winnings,
                    "multiplier": new_multiplier,
                    "flips": new_flips,
                    "timestamp": int(time.time())
                }
                
                db.collection.update_one(
                    {"discord_id": ctx.author.id},
                    {
                        "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                        "$inc": {
                            "total_played": 1,
                            "total_won": 1,
                            "total_earned": winnings
                        }
                    }
                )
                
                # Update server history
                server_db = Servers()
                server_data = server_db.fetch_server(ctx.guild.id)
                
                if server_data:
                    server_history_entry = {
                        "type": "win",
                        "game": "pcf",
                        "user_id": ctx.author.id,
                        "user_name": ctx.author.name,
                        "bet": bet_amount,
                        "amount": winnings,
                        "multiplier": new_multiplier,
                        "flips": new_flips,
                        "timestamp": int(time.time())
                    }
                    
                    server_db.collection.update_one(
                        {"server_id": ctx.guild.id},
                        {
                            "$push": {"server_bet_history": {"$each": [server_history_entry], "$slice": -100}},
                            "$inc": {"total_profit": -winnings + bet_amount}
                        }
                    )
                
                # Create max win embed
                max_win_embed = discord.Embed(
                    title="🎉 | Progressive Coinflip - Maximum Win!",
                    description=(
                        f"You've reached the maximum of {max_flips} flips! Automatic cash out.\n\n"
                        f"**Initial Bet:** {bet_amount:.2f} {currency_used}\n"
                        f"**Final Multiplier:** {new_multiplier:.2f}x\n"
                        f"**Winnings:** {winnings:.2f} credits"
                    ),
                    color=0x00FF00
                )
                
                max_win_embed.add_field(
                    name="Your Streak",
                    value=f"{chosen_emoji} " * new_flips,
                    inline=False
                )
                
                max_win_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
                
                # Update message with max win info
                await message.edit(embed=max_win_embed)
                
                # Add play again view
                play_again_view = PlayAgainView(self, ctx, bet_amount, side)
                await message.edit(embed=max_win_embed, view=play_again_view)
                play_again_view.message = message
                
                # Remove ongoing game status
                if ctx.author.id in self.ongoing_games:
                    del self.ongoing_games[ctx.author.id]
            else:
                # Add continue/cash out options
                continue_view = ContinueFlipView(self, ctx, bet_amount, currency_used, side, new_flips, new_multiplier)
                await message.edit(embed=result_embed, view=continue_view)
                continue_view.message = message
        else:
            # User lost
            result_embed = discord.Embed(
                title="❌ | Progressive Coinflip - You Lost!",
                description=(
                    f"**Result:** {result.capitalize()} {result_emoji}\n"
                    f"**Your Choice:** {side.capitalize()}\n\n"
                    f"Better luck next time!"
                ),
                color=0xFF0000
            )
            
            result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
            
            # Update user history for loss
            db = Users()
            history_entry = {
                "type": "loss",
                "game": "pcf",
                "bet": bet_amount,
                "amount": bet_amount,
                "flips": current_flips,
                "timestamp": int(time.time())
            }
            
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {
                        "total_played": 1,
                        "total_lost": 1,
                        "total_spent": bet_amount
                    }
                }
            )
            
            # Update server history for loss
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id)
            
            if server_data:
                server_history_entry = {
                    "type": "loss",
                    "game": "pcf",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "bet": bet_amount,
                    "amount": bet_amount,
                    "flips": current_flips,
                    "timestamp": int(time.time())
                }
                
                server_db.collection.update_one(
                    {"server_id": ctx.guild.id},
                    {
                        "$push": {"server_bet_history": {"$each": [server_history_entry], "$slice": -100}},
                        "$inc": {"total_profit": bet_amount}
                    }
                )
            
            # Add play again button
            play_again_view = PlayAgainView(self, ctx, bet_amount, side)
            await message.edit(embed=result_embed, view=play_again_view)
            play_again_view.message = message
            
            # Remove ongoing game status
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]

def setup(bot):
    bot.add_cog(ProgressiveCoinflipCog(bot))
