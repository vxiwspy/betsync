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

class CrashView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, user_id):
        super().__init__(timeout=None)
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

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.green, emoji="💰")
    async def cash_out(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
            
        if self.crashed:
            return await interaction.response.send_message("Game already crashed!", ephemeral=True)
            
        self.cashed_out = True
        self.cash_out_multiplier = self.current_multiplier
        button.disabled = True
        button.label = f"Cashed Out at {self.cash_out_multiplier:.2f}x"
        await interaction.response.edit_message(view=self)
        
        # Send immediate feedback to player
        winnings = int(self.bet_amount * self.cash_out_multiplier)
        feedback_embed = discord.Embed(
            title="✅ Cash Out Successful!",
            description=f"You cashed out at **{self.cash_out_multiplier:.2f}x**\nWinnings: **{winnings} credits**",
            color=0x00FF00
        )
        await interaction.followup.send(embed=feedback_embed, ephemeral=True)

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

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
                    "- Click **Cash Out** before it crashes to win\n"
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
                    
            bet_amount_value = int(bet_amount_value)  # Convert to integer
            
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
        
        # Create view with Cash Out button
        view = CrashView(self, ctx, total_bet, ctx.author.id)
        
        # Generate crash point - typically follows a Pareto distribution
        # This gives rare but very high crash points, with most being lower values
        try:
            crash_point = math.floor(100 * random.paretovariate(2)) / 100
            if crash_point < 1.0:
                crash_point = 1.0  # Minimum crash point is 1.0x
            
            # We don't want unrealistically high crash points
            crash_point = min(crash_point, 20.0)  # Cap at 20x
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
                "Click **Cash Out** before it crashes to win!"
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
            message = await ctx.reply(embed=initial_embed, file=initial_file, view=view)
        else:
            message = await ctx.reply(embed=initial_embed, view=view)
        
        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "message": message,
            "view": view,
            "tokens_used": tokens_used,
            "credits_used": credits_used
        }
        
        # Track the currency used for winning calculation
        view.tokens_used = tokens_used
        view.credits_used = credits_used
        
        # Start the game
        await self.run_crash_game(ctx, message, view, crash_point, total_bet)
        
    async def run_crash_game(self, ctx, message, view, crash_point, bet_amount):
        """Run the crash game animation and handle the result"""
        try:
            multiplier = 1.0
            growth_rate = 0.05  # Controls how fast the multiplier increases
            
            # Format bet amount description based on tokens and credits used
            if hasattr(view, 'tokens_used') and hasattr(view, 'credits_used'):
                tokens_used = view.tokens_used
                credits_used = view.credits_used
                
                if tokens_used > 0 and credits_used > 0:
                    bet_description = f"**Bet Amount:** {tokens_used} tokens + {credits_used} credits"
                elif tokens_used > 0:
                    bet_description = f"**Bet Amount:** {tokens_used} tokens"
                else:
                    bet_description = f"**Bet Amount:** {credits_used} credits"
            else:
                bet_description = f"**Bet Amount:** {bet_amount}"
            
            # Continue incrementing the multiplier until crash or cash out
            while multiplier < crash_point and not view.cashed_out:
                # Wait a bit between updates (faster at the start, slower as multiplier increases)
                delay = 1.0 / (1 + multiplier * 0.5)
                delay = max(0.3, min(delay, 0.8))  # Keep delay between 0.3 and 0.8 seconds
                await asyncio.sleep(delay)
                
                # Increase multiplier with a bit of randomness
                multiplier += growth_rate * (1 + random.uniform(-0.2, 0.2))
                view.current_multiplier = multiplier
                
                try:
                    # Generate updated graph and embed
                    embed, file = self.generate_crash_graph(multiplier, False)
                    embed.title = "🚀 | Crash Game In Progress"
                    embed.description = (
                        f"{bet_description}\n"
                        f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                        "Click **Cash Out** before it crashes to win!"
                    )
                    
                    # Update the message with new graph
                    await message.edit(embed=embed, attachments=[file], view=view)
                except Exception as graph_error:
                    print(f"Error updating graph: {graph_error}")
                    # Simple fallback in case graph generation fails
                    try:
                        embed = discord.Embed(
                            title="🚀 | Crash Game In Progress", 
                            description=(
                                f"{bet_description}\n"
                                f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                                "Click **Cash Out** before it crashes to win!"
                            ),
                            color=0x00FFAE
                        )
                        await message.edit(embed=embed, view=view)
                    except Exception as fallback_error:
                        print(f"Error updating fallback message: {fallback_error}")
                
            # Game ended - either crashed or cashed out
            view.crashed = True
            
            # Disable the cash out button
            for item in view.children:
                item.disabled = True
            
            # Get database connection
            db = Users()
                
            # Handle crash
            if not view.cashed_out:
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
                        "type": "game_loss",
                        "game": "crash",
                        "bet": bet_amount,
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
                    
                    # Update message with crash result
                    await message.edit(embed=embed, attachments=[file], view=view)
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
                        await message.edit(embed=embed, view=view)
                    except Exception as fallback_error:
                        print(f"Error updating fallback crash message: {fallback_error}")
                
            else:
                try:
                    # User cashed out successfully
                    cash_out_multiplier = view.cash_out_multiplier
                    winnings = int(bet_amount * cash_out_multiplier)
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
                        "type": "game_win",
                        "game": "crash",
                        "bet": bet_amount,
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
                    
                    # Update message with win result
                    await message.edit(embed=embed, attachments=[file], view=view)
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
                        await message.edit(embed=embed, view=view)
                        
                        # Make sure winnings are credited even if graph fails
                        db.update_balance(ctx.author.id, winnings, "credits", "$inc")
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
                if hasattr(view, 'tokens_used') and view.tokens_used > 0:
                    current_tokens = db.fetch_user(ctx.author.id)['tokens']
                    db.update_balance(ctx.author.id, current_tokens + view.tokens_used, "tokens")
                
                if hasattr(view, 'credits_used') and view.credits_used > 0:
                    current_credits = db.fetch_user(ctx.author.id)['credits']
                    db.update_balance(ctx.author.id, current_credits + view.credits_used, "credits")
            except Exception as refund_error:
                print(f"Error refunding bet: {refund_error}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]
                
    def generate_crash_graph(self, current_multiplier, crashed=False, cash_out=False):
        """Generate a crash game graph with improved visuals"""
        try:
            # Clear previous plot and create new figure
            plt.clf()
            plt.figure(figsize=(10, 6), dpi=100)
            
            # Set background color with a darker theme
            bg_color = '#1E1F22'
            plt.gca().set_facecolor(bg_color)
            plt.gcf().set_facecolor(bg_color)
            
            # Generate x and y coordinates with more points for smoother curve
            x = np.linspace(0, current_multiplier, 150)
            
            # Create a more dynamic curve that starts slower and grows faster
            if current_multiplier <= 1.5:
                # For small multipliers, use simple exponential
                y = np.exp(x) - 1
            else:
                # For larger multipliers, use a combination for more dramatic curve
                y = np.power(1.5, x) - 0.5
                
            # Scale y values to match the current multiplier
            y = y * (current_multiplier / y[-1])
            
            # Add subtle gradient background
            gradient = np.linspace(0, 1, 100).reshape(-1, 1)
            gradient_colors = plt.cm.viridis(gradient)
            gradient_colors[:, 3] = 0.1  # Set alpha for transparency
            plt.imshow(gradient, extent=[0, max(2, current_multiplier * 1.1), 0, max(2, current_multiplier * 1.1)], 
                      aspect='auto', cmap='viridis', alpha=0.1)
            
            # Determine line color and style based on game state
            if crashed:
                line_color = '#FF5555'  # Bright red for crash
                line_style = '-'
                line_width = 4
            elif cash_out:
                line_color = '#55FF55'  # Bright green for cashout
                line_style = '-'
                line_width = 4
            else:
                # Create a gradient line that changes from cyan to yellow to orange as multiplier increases
                line_color = '#00FFAE'  # Teal/cyan color
                if current_multiplier > 2:
                    line_color = '#FFDD00'  # Yellow
                if current_multiplier > 5:
                    line_color = '#FF8800'  # Orange
                line_style = '-'
                line_width = 3.5
            
            # Plot the main line
            plt.plot(x, y, color=line_color, linewidth=line_width, linestyle=line_style, path_effects=[
                plt.matplotlib.patheffects.withStroke(linewidth=5, foreground='black', alpha=0.3)
            ])
            
            # Add points along the curve for visual effect
            if not crashed and not cash_out and current_multiplier > 1.2:
                point_indices = np.linspace(0, len(x)-1, min(int(current_multiplier * 3), 30), dtype=int)
                plt.scatter(x[point_indices], y[point_indices], color='white', s=15, alpha=0.5, zorder=4)
            
            # Add special markers and text for crash or cash out points
            if crashed:
                # Add explosion effect for crash
                plt.scatter([current_multiplier], [current_multiplier], color='red', s=150, marker='*', zorder=5)
                # Add shadow/glow effect
                plt.scatter([current_multiplier], [current_multiplier], color='darkred', s=200, marker='*', alpha=0.3, zorder=4)
                
                # Add crash text with shadow effect
                plt.text(current_multiplier, current_multiplier + 0.2, f"CRASHED AT {current_multiplier:.2f}x", 
                         color='white', fontweight='bold', fontsize=12, ha='right', va='bottom',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor='red', alpha=0.7, edgecolor='darkred'))
            
            elif cash_out:
                # Add diamond symbol for cash out
                plt.scatter([current_multiplier], [current_multiplier], color='lime', s=130, marker='D', zorder=5)
                # Add shadow/glow effect
                plt.scatter([current_multiplier], [current_multiplier], color='green', s=180, marker='D', alpha=0.3, zorder=4)
                
                # Add cash out text with shadow effect
                plt.text(current_multiplier, current_multiplier + 0.2, f"CASHED OUT AT {current_multiplier:.2f}x", 
                         color='white', fontweight='bold', fontsize=12, ha='right', va='bottom',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor='green', alpha=0.7, edgecolor='darkgreen'))
            
            # Add current multiplier in the top-right corner
            if not crashed and not cash_out:
                plt.text(0.95, 0.95, f"{current_multiplier:.2f}x", 
                         transform=plt.gca().transAxes, color='white', fontsize=20, fontweight='bold', ha='right', va='top',
                         bbox=dict(boxstyle="round,pad=0.3", facecolor=line_color, alpha=0.7))
            
            # Set axes properties with grid and better styling
            plt.grid(True, linestyle='--', alpha=0.2, color='gray')
            plt.xlim(0, max(2, current_multiplier * 1.1))
            plt.ylim(0, max(2, current_multiplier * 1.1))
            
            # Remove axis numbers, keep only the graph
            plt.xticks([])
            plt.yticks([])
            
            # Remove spines (borders)
            for spine in plt.gca().spines.values():
                spine.set_visible(False)
            
            # Add subtle BetSync watermark/branding
            plt.text(0.5, 0.03, "BetSync Casino", transform=plt.gca().transAxes,
                    color='white', alpha=0.3, fontsize=14, fontweight='bold', ha='center')
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', transparent=False)
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
