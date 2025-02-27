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

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.green)
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

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["cr"])
    async def crash(self, ctx, bet_amount: str = None):
        """Play the crash game - bet before the graph crashes!"""
        if not bet_amount:
            embed = discord.Embed(
                title=":bulb: How to Play Crash",
                description=(
                    "**Crash** is a multiplier game where you place a bet and cash out before the graph crashes.\n\n"
                    "**Usage:** `!crash <amount>`\n"
                    "**Example:** `!crash 100`\n\n"
                    "- Watch as the multiplier increases in real-time\n"
                    "- Click **Cash Out** before it crashes to win\n"
                    "- If it crashes before you cash out, you lose your bet\n"
                    "- The longer you wait, the higher the potential reward!"
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
            
        # Validate bet amount
        try:
            # Handle 'all' or 'max' bet
            if bet_amount.lower() in ['all', 'max']:
                tokens = user_data['tokens']
            else:
                # Check if bet has 'k' or 'm' suffix
                if bet_amount.lower().endswith('k'):
                    tokens = float(bet_amount[:-1]) * 1000
                elif bet_amount.lower().endswith('m'):
                    tokens = float(bet_amount[:-1]) * 1000000
                else:
                    tokens = float(bet_amount)
                    
            tokens = int(tokens)  # Convert to integer
            
            if tokens <= 0:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Amount",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
                
            if tokens > user_data['tokens']:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Funds",
                    description=f"You don't have enough tokens. Your balance: **{user_data['tokens']} tokens**",
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
            
        # Deduct tokens from user balance
        db.update_balance(ctx.author.id, tokens, "tokens", "$inc", -1)
        
        # Record game stats
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$inc": {"total_played": 1, "total_spent": tokens}}
        )
        
        # Create view with Cash Out button
        view = CrashView(self, ctx, tokens, ctx.author.id)
        
        # Generate crash point - typically follows a Pareto distribution
        # This gives rare but very high crash points, with most being lower values
        crash_point = math.floor(100 * random.paretovariate(2)) / 100
        if crash_point < 1.0:
            crash_point = 1.0  # Minimum crash point is 1.0x
        
        # We don't want unrealistically high crash points
        crash_point = min(crash_point, 20.0)  # Cap at 20x
        
        # Create initial graph
        initial_embed, initial_file = self.generate_crash_graph(1.0, False)
        initial_embed.title = "🚀 | Crash Game Started"
        initial_embed.description = (
            f"**Bet Amount:** {tokens} tokens\n"
            f"**Current Multiplier:** 1.00x\n\n"
            "Click **Cash Out** before it crashes to win!"
        )
        
        # Delete loading message and send initial game message
        await loading_message.delete()
        message = await ctx.reply(embed=initial_embed, file=initial_file, view=view)
        
        # Mark the game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "message": message,
            "view": view
        }
        
        # Start the game
        await self.run_crash_game(ctx, message, view, crash_point, tokens)
        
    async def run_crash_game(self, ctx, message, view, crash_point, bet_amount):
        """Run the crash game animation and handle the result"""
        try:
            multiplier = 1.0
            growth_rate = 0.05  # Controls how fast the multiplier increases
            
            # Continue incrementing the multiplier until crash or cash out
            while multiplier < crash_point and not view.cashed_out:
                # Wait a bit between updates (faster at the start, slower as multiplier increases)
                delay = 1.0 / (1 + multiplier * 0.5)
                delay = max(0.5, min(delay, 1.0))  # Keep delay between 0.5 and 1.0 seconds
                await asyncio.sleep(delay)
                
                # Increase multiplier with a bit of randomness
                multiplier += growth_rate * (1 + random.uniform(-0.2, 0.2))
                view.current_multiplier = multiplier
                
                # Generate updated graph and embed
                embed, file = self.generate_crash_graph(multiplier, False)
                embed.title = "🚀 | Crash Game In Progress"
                embed.description = (
                    f"**Bet Amount:** {bet_amount} tokens\n"
                    f"**Current Multiplier:** {multiplier:.2f}x\n\n"
                    "Click **Cash Out** before it crashes to win!"
                )
                
                # Update the message
                await message.edit(embed=embed, attachments=[file], view=view)
                
            # Game ended - either crashed or cashed out
            view.crashed = True
            
            # Disable the cash out button
            for item in view.children:
                item.disabled = True
                
            # Handle crash
            if not view.cashed_out:
                # Generate crash graph
                embed, file = self.generate_crash_graph(multiplier, True)
                embed.title = "💥 | CRASHED!"
                embed.description = (
                    f"**Bet Amount:** {bet_amount} tokens\n"
                    f"**Crashed At:** {multiplier:.2f}x\n\n"
                    f"**Result:** You lost {bet_amount} tokens!"
                )
                embed.color = 0xFF0000
                
                # Add to history
                db = Users()
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
                
            else:
                # User cashed out successfully
                cash_out_multiplier = view.cash_out_multiplier
                winnings = int(bet_amount * cash_out_multiplier)
                profit = winnings - bet_amount
                
                # Generate success graph
                embed, file = self.generate_crash_graph(cash_out_multiplier, False, cash_out=True)
                embed.title = "💰 | CASHED OUT!"
                embed.description = (
                    f"**Bet Amount:** {bet_amount} tokens\n"
                    f"**Cashed Out At:** {cash_out_multiplier:.2f}x\n"
                    f"**Winnings:** {winnings} tokens\n"
                    f"**Profit:** {profit} tokens"
                )
                embed.color = 0x00FF00
                
                # Add credits to user balance
                db = Users()
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
            
            # Update the final message
            await message.edit(embed=embed, attachments=[file], view=view)
            
        except Exception as e:
            print(f"Error in crash game: {e}")
        finally:
            # Remove the game from ongoing games
            if ctx.author.id in self.ongoing_games:
                del self.ongoing_games[ctx.author.id]
                
    def generate_crash_graph(self, current_multiplier, crashed=False, cash_out=False):
        """Generate a crash game graph"""
        # Clear previous plot
        plt.clf()
        plt.figure(figsize=(10, 6))
        
        # Set background color
        plt.gca().set_facecolor('#2B2D31')
        plt.gcf().set_facecolor('#2B2D31')
        
        # Generate x and y coordinates
        x = np.linspace(0, current_multiplier, 100)
        y = np.exp(x) - 1
        
        # Scale y values to match the current multiplier
        y = y * (current_multiplier / (np.exp(current_multiplier) - 1))
        
        # Plot the line
        line_color = 'red' if crashed else 'green' if cash_out else '#00FFAE'
        plt.plot(x, y, color=line_color, linewidth=3)
        
        # Add crash point if crashed
        if crashed:
            plt.scatter([current_multiplier], [current_multiplier], color='red', s=100, zorder=5)
            plt.text(current_multiplier, current_multiplier, f"CRASH: {current_multiplier:.2f}x", 
                     color='white', fontweight='bold', ha='right', va='bottom')
        
        # Add cash out point if cashed out
        if cash_out:
            plt.scatter([current_multiplier], [current_multiplier], color='green', s=100, zorder=5)
            plt.text(current_multiplier, current_multiplier, f"CASH OUT: {current_multiplier:.2f}x", 
                     color='white', fontweight='bold', ha='right', va='bottom')
        
        # Set axes properties
        plt.grid(True, linestyle='--', alpha=0.3)
        plt.xlim(0, max(2, current_multiplier * 1.1))
        plt.ylim(0, max(2, current_multiplier * 1.1))
        
        # Add labels with white text
        plt.xlabel('Time', color='white')
        plt.ylabel('Multiplier', color='white')
        plt.title('BetSync Crash Game', color='white', fontsize=16, fontweight='bold')
        
        # Style the ticks
        plt.tick_params(colors='white', which='both')
        
        # Save plot to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # Create discord File object
        file = discord.File(buf, filename="crash_graph.png")
        
        # Create embed with the graph
        embed = discord.Embed(color=0x2B2D31)
        embed.set_image(url="attachment://crash_graph.png")
        
        return embed, file

def setup(bot):
    bot.add_cog(Games(bot))
