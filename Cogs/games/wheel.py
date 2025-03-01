
import discord
import asyncio
import random
import time
from discord.ext import commands
from Cogs.utils.mongo import Users, Servers
from Cogs.utils.emojis import emoji

class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}
        # Define color multipliers
        self.colors = {
            "gray": {"emoji": "⚪", "multiplier": 0, "chance": 15},
            "yellow": {"emoji": "🟡", "multiplier": 1.5, "chance": 30},
            "red": {"emoji": "🔴", "multiplier": 2, "chance": 25},
            "blue": {"emoji": "🔵", "multiplier": 3, "chance": 20},
            "green": {"emoji": "🟢", "multiplier": 5, "chance": 10}
        }
        # Calculate total chance to verify it sums to 100
        self.total_chance = sum(color["chance"] for color in self.colors.values())

    @commands.command(aliases=["w"])
    async def wheel(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play the wheel game - bet on colors with different multipliers!"""
        if not bet_amount:
            embed = discord.Embed(
                title="<a:hersheyparkSpin:1345317103158431805> How to Play Wheel",
                description=(
                    "**Wheel** is a game where you bet and win based on where the wheel lands.\n\n"
                    "**Usage:** `!wheel <amount> [currency_type]`\n"
                    "**Example:** `!wheel 100` or `!wheel 100 tokens`\n\n"
                    "**Colors and Multipliers:**\n"
                    "⚪ **Gray** - 0x (Loss)\n"
                    "🟡 **Yellow** - 1.5x\n"
                    "🔴 **Red** - 2x\n"
                    "🔵 **Blue** - 3x\n"
                    "🟢 **Green** - 5x\n\n"
                    "You can bet using tokens (T) or credits (C):\n"
                    "- Winnings are always paid in credits\n"
                    "- If you have enough tokens, they will be used first\n"
                    "- If you don't have enough tokens, credits will be used"
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
            title=f"{loading_emoji} | Preparing Wheel Game...",
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
                currency_type = "tokens"  # Default to tokens if both are 0 await ctx.reply(embed=embed)

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
        elif currency_type.lower() in ['c', 'credit', 'credits']:
            currency_type = 'credits'
        else:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Currency",
                description="Please use 'tokens' (t) or 'credits' (c).",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)

        # Check if the user has enough balance
        tokens_balance = user_data['tokens']
        credits_balance = user_data['credits']
        
        # Initialize tokens and credits used
        tokens_used = 0
        credits_used = 0
        
        # Determine which currencies to use
        if currency_type == 'tokens':
            if tokens_balance >= bet_amount_value:
                tokens_used = bet_amount_value
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Tokens",
                    description=f"You don't have enough tokens. Your balance: **{tokens_balance:.2f} tokens**\nRequired: **{bet_amount_value:.2f} tokens**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
        else:  # credits
            if credits_balance >= bet_amount_value:
                credits_used = bet_amount_value
            else:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Credits",
                    description=f"You don't have enough credits. Your balance: **{credits_balance:.2f} credits**\nRequired: **{bet_amount_value:.2f} credits**",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)

        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "bet_amount": bet_amount_value,
            "tokens_used": tokens_used,
            "credits_used": credits_used
        }

        # Deduct bet from user's balance
        if tokens_used > 0:
            db.update_balance(ctx.author.id, -tokens_used, "tokens", "$inc")
        if credits_used > 0:
            db.update_balance(ctx.author.id, -credits_used, "credits", "$inc")

        # Delete loading message
        await loading_message.delete()

        # Create initial wheel embed
        wheel_embed = discord.Embed(
            title="<a:hersheyparkSpin:1345317103158431805> Wheel of Fortune",
            description=(
                "The wheel is spinning...\n\n"
                "**Your Bet:** "
            ),
            color=0x00FFAE
        )
        
        # Format bet description
        if tokens_used > 0 and credits_used > 0:
            wheel_embed.description += f"{tokens_used:.2f} tokens + {credits_used:.2f} credits"
        elif tokens_used > 0:
            wheel_embed.description += f"{tokens_used:.2f} tokens"
        else:
            wheel_embed.description += f"{credits_used:.2f} credits"
            
        wheel_embed.add_field(
            name="Possible Outcomes",
            value=(
                "⚪ **Gray** - 0x (Loss)\n"
                "🟡 **Yellow** - 1.5x\n"
                "🔴 **Red** - 2x\n"
                "🔵 **Blue** - 3x\n"
                "🟢 **Green** - 5x"
            ),
            inline=False
        )
        
        wheel_embed.add_field(
            name="Wheel Spinning",
            value="⚙️ " + "⬛" * 10 + " ⚙️",
            inline=False
        )
        
        wheel_embed.set_footer(text="BetSync Casino • Good luck!", icon_url=self.bot.user.avatar.url)
        
        # Send the initial wheel embed
        wheel_message = await ctx.reply(embed=wheel_embed)
        
        # Create spinning animation - reduced to exactly 2 seconds total
        spinning_frames = [
            "⚙️ " + "⬛" * 4 + "🟡" + "⬛" * 5 + " ⚙️",
            "⚙️ " + "⬛" * 5 + "🔴" + "⬛" * 4 + " ⚙️",
            "⚙️ " + "⬛" * 6 + "🔵" + "⬛" * 3 + " ⚙️",
            "⚙️ " + "⬛" * 7 + "🟢" + "⬛" * 2 + " ⚙️",
            "⚙️ " + "⬛" * 8 + "⚪" + "⬛" * 1 + " ⚙️",
            "⚙️ " + "⬛" * 9 + "🟡" + " ⚙️",
            "⚙️ " + "🔴" + "⬛" * 9 + " ⚙️",
            "⚙️ " + "⬛" * 1 + "🔵" + "⬛" * 8 + " ⚙️",
            "⚙️ " + "⬛" * 2 + "🟢" + "⬛" * 7 + " ⚙️",
            "⚙️ " + "⬛" * 3 + "⚪" + "⬛" * 6 + " ⚙️"
        ]
        
        # Animate the wheel spinning - 20 frames × 0.1s = 2 seconds total
        for _ in range(2):  # Reduced to 2 cycles
            for frame in spinning_frames:
                wheel_embed.set_field_at(
                    1,  # Index 1 is the "Wheel Spinning" field
                    name="Wheel Spinning",
                    value=frame,
                    inline=False
                )
                await wheel_message.edit(embed=wheel_embed)
                await asyncio.sleep(0.1)  # Exactly 20 frames × 0.1s = 2 seconds total

        # Calculate result with house edge (3-5%)
        # Implement a small house edge by slightly adjusting the chances
        house_edge = 0.04  # 4% house edge
        
        # Apply house edge to outcome calculation
        if random.random() < house_edge:
            # Force a loss (gray) more often for house edge
            result_color = "gray"
        else:
            # Normal weighted random selection
            random_value = random.randint(1, self.total_chance)
            cumulative = 0
            result_color = None
            
            for color, data in self.colors.items():
                cumulative += data["chance"]
                if random_value <= cumulative:
                    result_color = color
                    break
        
        # Get multiplier for the result
        result_multiplier = self.colors[result_color]["multiplier"]
        result_emoji = self.colors[result_color]["emoji"]
        
        # Calculate winnings (always paid out in credits)
        bet_total = tokens_used + credits_used
        winnings = bet_total * result_multiplier
        
        # Update the wheel embed with the result
        result_frame = "⚙️ " + "⬛" * 5 + result_emoji + "⬛" * 4 + " ⚙️"
        wheel_embed.set_field_at(
            1,
            name="Wheel Result",
            value=result_frame,
            inline=False
        )
        
        # Add result field
        if result_multiplier > 0:
            wheel_embed.add_field(
                name=f"🎉 You Won! ({result_color.capitalize()})",
                value=f"**Multiplier:** {result_multiplier}x\n**Winnings:** {winnings:.2f} credits",
                inline=False
            )
            wheel_embed.color = 0x00FF00  # Green for win
            
            # Update user's balance with winnings
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")
            
            # Add to user history
            history_entry = {
                "type": "win",
                "game": "wheel",
                "bet": bet_total,
                "amount": winnings,
                "multiplier": result_multiplier,
                "timestamp": int(time.time())
            }
            
            # Update user's total won and played count
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_played": 1, "total_won": 1, "total_earned": winnings}
                }
            )
            
            # Add to server bet history
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id)
            
            if server_data:
                server_bet_history_entry = {
                    "type": "win",
                    "game": "wheel",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "bet": bet_total,
                    "amount": winnings,
                    "multiplier": result_multiplier,
                    "timestamp": int(time.time())
                }
                
                # Update server data
                server_db.collection.update_one(
                    {"server_id": ctx.guild.id},
                    {
                        "$push": {"server_bet_history": {"$each": [server_bet_history_entry], "$slice": -100}},
                        "$inc": {"total_profit": bet_total - winnings}  # House profit
                    }
                )
                
        else:
            wheel_embed.add_field(
                name=f"❌ You Lost! ({result_color.capitalize()})",
                value=f"**Multiplier:** {result_multiplier}x\n**Bet Lost:** {bet_total:.2f}",
                inline=False
            )
            wheel_embed.color = 0xFF0000  # Red for loss
            
            # Add to user history
            history_entry = {
                "type": "loss",
                "game": "wheel",
                "bet": bet_total,
                "amount": bet_total,
                "multiplier": result_multiplier,
                "timestamp": int(time.time())
            }
            
            # Update user's total lost and played count
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$push": {"history": {"$each": [history_entry], "$slice": -100}},
                    "$inc": {"total_played": 1, "total_lost": 1, "total_spent": bet_total}
                }
            )
            
            # Add to server bet history
            server_db = Servers()
            server_data = server_db.fetch_server(ctx.guild.id)
            
            if server_data:
                server_bet_history_entry = {
                    "type": "loss",
                    "game": "wheel",
                    "user_id": ctx.author.id,
                    "user_name": ctx.author.name,
                    "bet": bet_total,
                    "amount": bet_total,
                    "multiplier": result_multiplier,
                    "timestamp": int(time.time())
                }
                
                # Update server data
                server_db.collection.update_one(
                    {"server_id": ctx.guild.id},
                    {
                        "$push": {"server_bet_history": {"$each": [server_bet_history_entry], "$slice": -100}},
                        "$inc": {"total_profit": bet_total}  # House profit
                    }
                )
                
        # Update the embed with play again button
        await wheel_message.edit(embed=wheel_embed)
        
        # Create play again view
        view = PlayAgainView(self, ctx, bet_total)
        await wheel_message.edit(view=view)
        view.message = wheel_message
        
        # Remove user from ongoing games
        self.ongoing_games.pop(ctx.author.id, None)


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="play_again")
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
            await self.cog.wheel(self.ctx, str(self.bet_amount), "tokens")
        elif credits_balance >= self.bet_amount:
            # Use credits if not enough tokens
            await self.cog.wheel(self.ctx, str(self.bet_amount), "credits")
        else:
            return await interaction.followup.send(f"You don't have enough balance to play again. You need {self.bet_amount} tokens or credits.", ephemeral=True)

    async def on_timeout(self):
        # Disable the button when the view times out
        for child in self.children:
            child.disabled = True
        
        try:
            await self.message.edit(view=self)
        except:
            pass


def setup(bot):
    bot.add_cog(WheelCog(bot))
