
import discord
import random
import asyncio
import os
import io
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji


class PlayAgainView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=15):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
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

        credits_balance = user_data['credits']
        
        if credits_balance < self.bet_amount:
            return await interaction.followup.send(f"You don't have enough credits to play again. You need {self.bet_amount} credits.", ephemeral=True)

        # Create a new penalty game with the same bet amount
        await self.cog.penalty(self.ctx, str(self.bet_amount), "credits")

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class PenaltyButtonView(discord.ui.View):
    def __init__(self, cog, ctx, bet_amount, timeout=30):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.bet_amount = bet_amount
        self.message = None
    
    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="⬅️")
    async def left_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "left", self.bet_amount)
    
    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="⬆️")
    async def middle_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "middle", self.bet_amount)
    
    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="➡️")
    async def right_button(self, button, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)
        
        # Disable all buttons to prevent multiple clicks
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Process the shot
        await self.cog.process_penalty_shot(self.ctx, interaction, "right", self.bet_amount)
    
    async def on_timeout(self):
        # Disable all buttons when the view times out
        for child in self.children:
            child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
                await self.ctx.send(f"{self.ctx.author.mention}, your penalty game has timed out!")
                
                # Remove from ongoing games
                if self.ctx.author.id in self.cog.ongoing_games:
                    del self.cog.ongoing_games[self.ctx.author.id]
            except:
                pass


class PenaltyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    @commands.command(aliases=["pen", "pk"])
    async def penalty(self, ctx, bet_amount: str = None, currency_type: str = None):
        """Play penalty shootout - aim your shot and try to score!"""
        if not bet_amount:
            embed = discord.Embed(
                title="⚽ How to Play Penalty",
                description=(
                    "**Penalty** is a game where you take a penalty kick against a goalkeeper!\n\n"
                    "**Usage:** `!penalty <amount> [currency_type]`\n"
                    "**Example:** `!penalty 100` or `!penalty 100 credits`\n\n"
                    "- **Choose to shoot left, middle, or right**\n"
                    "- **If the goalkeeper dives in a different direction, you score and win 1.5x your bet!**\n"
                    "- **If the goalkeeper saves your shot, you lose your bet**\n"
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
            title=f"{loading_emoji} | Preparing Penalty Game...",
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

        # Parse bet amount and currency
        try:
            # Check if bet amount is "all" or "max"
            if bet_amount.lower() in ["all", "max"]:
                # Default to credits if not specified
                if not currency_type or currency_type.lower() != "tokens":
                    bet_amount = user_data["credits"]
                    currency_type = "credits"
                else:
                    bet_amount = user_data["tokens"]
                    currency_type = "tokens"
            else:
                # Convert bet amount to float
                bet_amount = float(bet_amount)
                
                # Default to credits if not specified
                if not currency_type:
                    currency_type = "credits"
                
                # Ensure currency is either "tokens" or "credits"
                if currency_type.lower() not in ["tokens", "credits"]:
                    await loading_message.delete()
                    embed = discord.Embed(
                        title="<:no:1344252518305234987> | Invalid Currency",
                        description="Currency must be either 'tokens' or 'credits'.",
                        color=0xFF0000
                    )
                    return await ctx.reply(embed=embed)

            # Force currency to be credits for penalty game
            if currency_type.lower() == "tokens":
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Currency",
                    description="Penalty game can only be played with credits.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            currency_type = "credits"
            
            # Check if bet amount is valid
            if bet_amount <= 0:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Bet",
                    description="Bet amount must be greater than 0.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
            # Check if user has enough balance
            if bet_amount > user_data[currency_type]:
                await loading_message.delete()
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Insufficient Balance",
                    description=f"You don't have enough {currency_type}. You need {bet_amount} but only have {user_data[currency_type]}.",
                    color=0xFF0000
                )
                return await ctx.reply(embed=embed)
            
        except ValueError:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Invalid Bet",
                description="Bet amount must be a number.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Mark game as ongoing
        self.ongoing_games[ctx.author.id] = {
            "currency_type": currency_type,
            "bet_amount": bet_amount
        }
        
        # Deduct bet from user's balance
        db.update_balance(ctx.author.id, -bet_amount, currency_type, "$inc")
        
        # Generate initial penalty image (no shot taken yet)
        initial_image = self.generate_penalty_image()
        
        # Convert image to bytes for Discord
        img_buffer = io.BytesIO()
        initial_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        file = discord.File(img_buffer, filename="penalty_setup.png")
        
        # Create start embed
        embed = discord.Embed(
            title="⚽ Penalty Kick",
            description=(
                f"**Bet:** {bet_amount:,.2f} {currency_type}\n\n"
                "Choose where to shoot:"
            ),
            color=0x00FFAE
        )
        embed.set_image(url="attachment://penalty_setup.png")
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Delete loading message
        await loading_message.delete()
        
        # Create view with buttons
        view = PenaltyButtonView(self, ctx, bet_amount)
        view.message = await ctx.reply(embed=embed, file=file, view=view)

    async def process_penalty_shot(self, ctx, interaction, shot_direction, bet_amount):
        """Process the penalty shot and determine the outcome"""
        # Remove from ongoing games
        if ctx.author.id in self.ongoing_games:
            del self.ongoing_games[ctx.author.id]
        
        # Goalkeeper picks a random direction
        goalkeeper_directions = ["left", "middle", "right"]
        goalkeeper_direction = random.choice(goalkeeper_directions)
        
        # Determine the outcome
        goal_scored = shot_direction != goalkeeper_direction
        
        # Calculate winnings
        multiplier = 1.5
        winnings = bet_amount * multiplier if goal_scored else 0
        
        # Generate the result image
        result_image = self.generate_penalty_result_image(shot_direction, goalkeeper_direction, goal_scored)
        
        # Convert image to bytes for Discord
        img_buffer = io.BytesIO()
        result_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        file = discord.File(img_buffer, filename="penalty_result.png")
        
        # Create result embed
        if goal_scored:
            title = "🎉 GOAL! You scored!"
            description = f"You shot **{shot_direction}**, the goalkeeper dove **{goalkeeper_direction}**.\n\n**You won {winnings:,.2f} credits!**"
            color = 0x00FF00  # Green for win
        else:
            title = "❌ SAVED! The goalkeeper stopped your shot!"
            description = f"You shot **{shot_direction}**, the goalkeeper dove **{goalkeeper_direction}**.\n\n**You lost {bet_amount:,.2f} credits.**"
            color = 0xFF0000  # Red for loss
        
        result_embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        result_embed.set_image(url="attachment://penalty_result.png")
        result_embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        
        # Create Play Again view
        play_again_view = PlayAgainView(self, ctx, bet_amount)
        
        # Send result message
        play_again_view.message = await interaction.followup.send(embed=result_embed, file=file, view=play_again_view)
        
        # Update user's balance and history
        db = Users()
        
        if goal_scored:
            # Update balance with winnings
            db.update_balance(ctx.author.id, winnings, "credits", "$inc")
            
            # Update history for win
            history_entry = {
                "type": "win",
                "game": "penalty",
                "amount": winnings,
                "bet": bet_amount,
                "timestamp": int(datetime.now().timestamp())
            }
            
            # Update total stats
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$inc": {
                        "total_won": 1,
                        "total_played": 1,
                        "total_earned": winnings
                    }
                }
            )
        else:
            # Update history for loss
            history_entry = {
                "type": "loss",
                "game": "penalty",
                "amount": bet_amount,
                "timestamp": int(datetime.now().timestamp())
            }
            
            # Update total stats
            db.collection.update_one(
                {"discord_id": ctx.author.id},
                {
                    "$inc": {
                        "total_lost": 1,
                        "total_played": 1,
                        "total_spent": bet_amount
                    }
                }
            )
        
        # Add to history
        db.collection.update_one(
            {"discord_id": ctx.author.id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}  # Keep last 100 entries
        )

    def generate_penalty_image(self):
        """Generate an image of the penalty setup with a simple shape for goalkeeper"""
        try:
            # Create a new image with a light blue background for the sky
            img_width, img_height = 800, 600
            image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
            
            # Draw the field (green)
            draw = ImageDraw.Draw(image)
            draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
            
            # Add stadium in background
            # Draw stands
            draw.rectangle([(0, img_height//3), (img_width, img_height//2)], fill=(100, 100, 150))
            
            # Draw crowd (small circles representing people)
            for i in range(0, img_width, 15):
                for j in range(img_height//3, img_height//2, 10):
                    if random.random() > 0.3:  # Random gaps in crowd
                        color = (
                            random.randint(150, 255),
                            random.randint(150, 255),
                            random.randint(150, 255)
                        )
                        draw.ellipse([(i, j), (i+8, j+8)], fill=color)
            
            # Draw the goal
            goal_width, goal_height = 500, 200
            goal_left = (img_width - goal_width) // 2
            goal_top = img_height//2 - 50
            
            # Goal posts (white rectangles)
            draw.rectangle([(goal_left, goal_top), (goal_left + 10, goal_top + goal_height)], fill=(255, 255, 255))  # Left post
            draw.rectangle([(goal_left + goal_width - 10, goal_top), (goal_left + goal_width, goal_top + goal_height)], fill=(255, 255, 255))  # Right post
            draw.rectangle([(goal_left, goal_top), (goal_left + goal_width, goal_top + 10)], fill=(255, 255, 255))  # Crossbar
            
            # Draw goal net
            # Vertical lines
            for x in range(goal_left + 20, goal_left + goal_width - 10, 30):
                draw.line([(x, goal_top + 10), (x, goal_top + goal_height)], fill=(200, 200, 200), width=2)
            
            # Horizontal lines
            for y in range(goal_top + 30, goal_top + goal_height, 30):
                draw.line([(goal_left + 10, y), (goal_left + goal_width - 10, y)], fill=(200, 200, 200), width=2)
            
            # Draw a simple shape for goalkeeper in the middle
            goalkeeper_x = (img_width - 80) // 2
            goalkeeper_y = goal_top + goal_height - 150
            
            # Draw goalkeeper as a single green rectangle with extended arms
            gk_width, gk_height = 80, 120
            
            # Main body rectangle
            draw.rectangle([
                (goalkeeper_x, goalkeeper_y), 
                (goalkeeper_x + gk_width, goalkeeper_y + gk_height)
            ], fill=(0, 180, 0), outline=(0, 100, 0), width=2)
            
            # Arms (horizontal rectangles extending from body)
            arm_height = 20
            # Left arm
            draw.rectangle([
                (goalkeeper_x - 40, goalkeeper_y + 40),
                (goalkeeper_x, goalkeeper_y + 40 + arm_height)
            ], fill=(0, 180, 0), outline=(0, 100, 0), width=2)
            
            # Right arm
            draw.rectangle([
                (goalkeeper_x + gk_width, goalkeeper_y + 40),
                (goalkeeper_x + gk_width + 40, goalkeeper_y + 40 + arm_height)
            ], fill=(0, 180, 0), outline=(0, 100, 0), width=2)
            
            # Add "GK" text to identify goalkeeper
            gk_font = ImageFont.truetype("roboto.ttf", 36)
            draw.text(
                (goalkeeper_x + gk_width // 2, goalkeeper_y + gk_height // 2), 
                "GK", 
                font=gk_font, 
                fill=(255, 255, 255),
                anchor="mm"
            )
            
            # Draw a more realistic ball
            ball_radius = 20
            ball_center = (img_width // 2, img_height - 80)
            
            # White base of the ball
            draw.ellipse([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], fill=(255, 255, 255), outline=(220, 220, 220), width=1)
            
            # Draw the classic soccer ball pattern
            # Hexagons and pentagons
            pentagon_points = []
            hexagon_points = []
            
            # Create pattern of alternating pentagons and hexagons
            for i in range(8):
                angle = i * (2 * math.pi / 8)
                radius_factor = 0.7 if i % 2 == 0 else 0.85
                x = ball_center[0] + ball_radius * radius_factor * math.cos(angle)
                y = ball_center[1] + ball_radius * radius_factor * math.sin(angle)
                
                if i % 2 == 0:
                    # Pentagon (black)
                    try:
                        draw.regular_polygon((x, y, 5), 5, rotation=0, fill=(0, 0, 0))
                    except AttributeError:
                        # Fallback if regular_polygon not available
                        draw.ellipse([(x-4, y-4), (x+4, y+4)], fill=(0, 0, 0))
                else:
                    # Hexagon (using small black circles as approximation)
                    draw.ellipse([(x-3, y-3), (x+3, y+3)], fill=(0, 0, 0))
            
            # Add seam lines to make it look more like a soccer ball
            # Horizontal seam
            draw.arc([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], 0, 180, fill=(0, 0, 0), width=1)
            
            # Vertical seam
            draw.arc([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], 270, 90, fill=(0, 0, 0), width=1)
            
            # Diagonal seams
            draw.line([
                (ball_center[0] - ball_radius * 0.7, ball_center[1] - ball_radius * 0.7),
                (ball_center[0] + ball_radius * 0.7, ball_center[1] + ball_radius * 0.7)
            ], fill=(0, 0, 0), width=1)
            
            draw.line([
                (ball_center[0] - ball_radius * 0.7, ball_center[1] + ball_radius * 0.7),
                (ball_center[0] + ball_radius * 0.7, ball_center[1] - ball_radius * 0.7)
            ], fill=(0, 0, 0), width=1)
            
            # Add highlight to make the ball look 3D
            highlight_radius = ball_radius * 0.3
            highlight_offset = ball_radius * 0.4
            draw.ellipse([
                (ball_center[0] - highlight_radius - highlight_offset, 
                 ball_center[1] - highlight_radius - highlight_offset),
                (ball_center[0] + highlight_radius - highlight_offset, 
                 ball_center[1] + highlight_radius - highlight_offset)
            ], fill=(255, 255, 255, 180))
            
            # Draw penalty spot
            draw.ellipse([
                (ball_center[0] - 5, ball_center[1] + ball_radius + 5),
                (ball_center[0] + 5, ball_center[1] + ball_radius + 15)
            ], fill=(255, 255, 255), outline=(255, 255, 255), width=2)
            
            # Add "BETSYNC" watermark at the top with transparency
            watermark_font = ImageFont.truetype("roboto.ttf", 50)
            draw.text(
                (img_width // 2, 40), 
                "BETSYNC", 
                font=watermark_font, 
                fill=(0, 0, 0, 64),  # More transparent
                anchor="mm"
            )
            
            return image
        except Exception as e:
            # If any error occurs, create a simple fallback image
            img_width, img_height = 800, 600
            fallback_image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
            draw = ImageDraw.Draw(fallback_image)
            
            # Basic field
            draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
            
            # Simple goal
            goal_width, goal_height = 500, 200
            goal_left = (img_width - goal_width) // 2
            goal_top = img_height//2 - 50
            
            # Goal outline
            draw.rectangle([(goal_left, goal_top), (goal_left + goal_width, goal_top + goal_height)], outline=(255, 255, 255), width=5)
            
            # Simple goalkeeper
            goalkeeper_center = (img_width // 2, goal_top + goal_height - 100)
            draw.rectangle([(goalkeeper_center[0] - 30, goalkeeper_center[1] - 60), 
                           (goalkeeper_center[0] + 30, goalkeeper_center[1] + 60)], fill=(0, 180, 0))
            
            # Simple ball
            ball_center = (img_width // 2, img_height - 80)
            draw.ellipse([(ball_center[0] - 20, ball_center[1] - 20), 
                         (ball_center[0] + 20, ball_center[1] + 20)], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
            
            # Add watermark
            draw.text((img_width // 2, img_height - 30), "BETSYNC", font=ImageFont.truetype("roboto.ttf", 60), 
                      fill=(0, 0, 0, 64), anchor="mm")
            
            # Add error message
            font = ImageFont.truetype("roboto.ttf", 20)
            draw.text((img_width // 2, 30), f"Image rendering issue: {str(e)}", font=font, fill=(255, 0, 0), anchor="mm")
            
            return fallback_image

    def generate_penalty_result_image(self, shot_direction, goalkeeper_direction, goal_scored):
        """Generate an image showing the penalty outcome with simplified goalkeeper"""
        try:
            # Create a new image with a light blue background for the sky
            img_width, img_height = 800, 600
            image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
            
            # Draw the field (green)
            draw = ImageDraw.Draw(image)
            draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
            
            # Add stadium in background
            # Draw stands
            draw.rectangle([(0, img_height//3), (img_width, img_height//2)], fill=(100, 100, 150))
            
            # Draw crowd (small circles representing people)
            for i in range(0, img_width, 15):
                for j in range(img_height//3, img_height//2, 10):
                    if random.random() > 0.3:  # Random gaps in crowd
                        # If goal scored, more people stand up (excited)
                        y_variation = random.randint(-5, 5) if goal_scored else 0
                        color = (
                            random.randint(150, 255),
                            random.randint(150, 255),
                            random.randint(150, 255)
                        )
                        draw.ellipse([(i, j + y_variation), (i+8, j+8 + y_variation)], fill=color)
            
            # Draw the goal
            goal_width, goal_height = 500, 200
            goal_left = (img_width - goal_width) // 2
            goal_top = img_height//2 - 50
            
            # Goal posts (white rectangles)
            draw.rectangle([(goal_left, goal_top), (goal_left + 10, goal_top + goal_height)], fill=(255, 255, 255))  # Left post
            draw.rectangle([(goal_left + goal_width - 10, goal_top), (goal_left + goal_width, goal_top + goal_height)], fill=(255, 255, 255))  # Right post
            draw.rectangle([(goal_left, goal_top), (goal_left + goal_width, goal_top + 10)], fill=(255, 255, 255))  # Crossbar
            
            # Draw goal net
            # Vertical lines
            for x in range(goal_left + 20, goal_left + goal_width - 10, 30):
                draw.line([(x, goal_top + 10), (x, goal_top + goal_height)], fill=(200, 200, 200), width=2)
            
            # Horizontal lines
            for y in range(goal_top + 30, goal_top + goal_height, 30):
                draw.line([(goal_left + 10, y), (goal_left + goal_width - 10, y)], fill=(200, 200, 200), width=2)
            
            # Position mapper for goalkeeper
            goalkeeper_positions = {
                "left": (goal_left + 80, goal_top + goal_height - 150),
                "middle": ((img_width - 80) // 2, goal_top + goal_height - 150),
                "right": (goal_left + goal_width - 160, goal_top + goal_height - 150)
            }
            
            # Position mapper for ball
            ball_positions = {
                "left": (goal_left + 100, goal_top + goal_height // 2),
                "middle": (img_width // 2, goal_top + goal_height // 2),
                "right": (goal_left + goal_width - 100, goal_top + goal_height // 2)
            }
            
            # Get goalkeeper position
            goalkeeper_x = goalkeeper_positions[goalkeeper_direction][0]
            goalkeeper_y = goalkeeper_positions[goalkeeper_direction][1]
            
            # Draw goalkeeper as a single shape based on direction
            gk_width, gk_height = 80, 120
            
            # Draw the goalkeeper in different positions based on direction
            if goalkeeper_direction == "left":
                # Goalkeeper diving to the left
                # Main rectangle body rotated/stretched to left
                points = [
                    (goalkeeper_x, goalkeeper_y + 30),  # Top left
                    (goalkeeper_x + gk_width * 0.8, goalkeeper_y),  # Top right
                    (goalkeeper_x + gk_width, goalkeeper_y + gk_height * 0.8),  # Bottom right
                    (goalkeeper_x - 40, goalkeeper_y + gk_height)   # Bottom left (extended for dive)
                ]
                draw.polygon(points, fill=(0, 180, 0), outline=(0, 100, 0), width=2)
                
                # Add motion lines to show diving
                for i in range(3):
                    offset = i * 10
                    draw.line([
                        (goalkeeper_x + gk_width + offset, goalkeeper_y + 30), 
                        (goalkeeper_x + gk_width + 20 + offset, goalkeeper_y + 30)
                    ], fill=(50, 50, 50, 150), width=2)
                
            elif goalkeeper_direction == "right":
                # Goalkeeper diving to the right
                # Main rectangle body rotated/stretched to right
                points = [
                    (goalkeeper_x + gk_width * 0.2, goalkeeper_y),  # Top left
                    (goalkeeper_x + gk_width, goalkeeper_y + 30),  # Top right
                    (goalkeeper_x + gk_width + 40, goalkeeper_y + gk_height),  # Bottom right (extended for dive)
                    (goalkeeper_x, goalkeeper_y + gk_height * 0.8)   # Bottom left
                ]
                draw.polygon(points, fill=(0, 180, 0), outline=(0, 100, 0), width=2)
                
                # Add motion lines to show diving
                for i in range(3):
                    offset = i * 10
                    draw.line([
                        (goalkeeper_x - offset, goalkeeper_y + 30), 
                        (goalkeeper_x - 20 - offset, goalkeeper_y + 30)
                    ], fill=(50, 50, 50, 150), width=2)
                
            else:  # middle
                # Goalkeeper jumping up for middle save
                # Main rectangle body
                points = [
                    (goalkeeper_x, goalkeeper_y - 20),  # Top left (higher for jump)
                    (goalkeeper_x + gk_width, goalkeeper_y - 20),  # Top right (higher for jump)
                    (goalkeeper_x + gk_width, goalkeeper_y + gk_height - 20),  # Bottom right
                    (goalkeeper_x, goalkeeper_y + gk_height - 20)   # Bottom left
                ]
                draw.polygon(points, fill=(0, 180, 0), outline=(0, 100, 0), width=2)
                
                # Add arms extended upward
                draw.rectangle([
                    (goalkeeper_x - 30, goalkeeper_y - 30),
                    (goalkeeper_x, goalkeeper_y)
                ], fill=(0, 180, 0), outline=(0, 100, 0), width=2)
                
                draw.rectangle([
                    (goalkeeper_x + gk_width, goalkeeper_y - 30),
                    (goalkeeper_x + gk_width + 30, goalkeeper_y)
                ], fill=(0, 180, 0), outline=(0, 100, 0), width=2)
                
                # Add motion lines for jump
                for i in range(3):
                    offset = i * 10
                    draw.line([
                        (goalkeeper_x + gk_width//2, goalkeeper_y + gk_height + offset), 
                        (goalkeeper_x + gk_width//2, goalkeeper_y + gk_height + 20 + offset)
                    ], fill=(50, 50, 50, 150), width=2)
            
            # Add "GK" text
            gk_font = ImageFont.truetype("roboto.ttf", 36)
            gk_text_x = goalkeeper_x + gk_width // 2
            gk_text_y = goalkeeper_y + gk_height // 2
            
            # Adjust text position based on dive direction
            if goalkeeper_direction == "left":
                gk_text_x -= 20
            elif goalkeeper_direction == "right":
                gk_text_x += 20
            elif goalkeeper_direction == "middle":
                gk_text_y -= 10
                
            draw.text(
                (gk_text_x, gk_text_y), 
                "GK", 
                font=gk_font, 
                fill=(255, 255, 255),
                anchor="mm"
            )
            
            # Draw the ball at the shot position
            ball_radius = 20
            ball_center = ball_positions[shot_direction]
            
            # If saved, show the ball slightly deflected
            if not goal_scored:
                # Move ball slightly away from the goal based on the direction
                if shot_direction == "left":
                    ball_center = (ball_center[0] - 20, ball_center[1] + 40)
                elif shot_direction == "right":
                    ball_center = (ball_center[0] + 20, ball_center[1] + 40)
                else:
                    ball_center = (ball_center[0], ball_center[1] + 40)
            
            # Draw the white base of the ball
            draw.ellipse([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], fill=(255, 255, 255), outline=(220, 220, 220), width=1)
            
            # Draw the classic soccer ball pattern
            # Hexagons and pentagons
            for i in range(8):
                angle = i * (2 * math.pi / 8)
                radius_factor = 0.7 if i % 2 == 0 else 0.85
                x = ball_center[0] + ball_radius * radius_factor * math.cos(angle)
                y = ball_center[1] + ball_radius * radius_factor * math.sin(angle)
                
                if i % 2 == 0:
                    # Pentagon (black)
                    try:
                        draw.regular_polygon((x, y, 5), 5, rotation=0, fill=(0, 0, 0))
                    except AttributeError:
                        # Fallback if regular_polygon not available
                        draw.ellipse([(x-4, y-4), (x+4, y+4)], fill=(0, 0, 0))
                else:
                    # Hexagon (using small black circles as approximation)
                    draw.ellipse([(x-3, y-3), (x+3, y+3)], fill=(0, 0, 0))
            
            # Add seam lines to make it look more like a soccer ball
            # Horizontal seam
            draw.arc([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], 0, 180, fill=(0, 0, 0), width=1)
            
            # Vertical seam
            draw.arc([
                (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
                (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
            ], 270, 90, fill=(0, 0, 0), width=1)
            
            # Diagonal seams
            draw.line([
                (ball_center[0] - ball_radius * 0.7, ball_center[1] - ball_radius * 0.7),
                (ball_center[0] + ball_radius * 0.7, ball_center[1] + ball_radius * 0.7)
            ], fill=(0, 0, 0), width=1)
            
            draw.line([
                (ball_center[0] - ball_radius * 0.7, ball_center[1] + ball_radius * 0.7),
                (ball_center[0] + ball_radius * 0.7, ball_center[1] - ball_radius * 0.7)
            ], fill=(0, 0, 0), width=1)
            
            # Add highlight to make the ball look 3D
            highlight_radius = ball_radius * 0.3
            highlight_offset = ball_radius * 0.4
            draw.ellipse([
                (ball_center[0] - highlight_radius - highlight_offset, 
                 ball_center[1] - highlight_radius - highlight_offset),
                (ball_center[0] + highlight_radius - highlight_offset, 
                 ball_center[1] + highlight_radius - highlight_offset)
            ], fill=(255, 255, 255, 180))
            
            # If the shot was saved, add a small motion blur effect
            if not goal_scored:
                for i in range(3):
                    offset = i * 5
                    opacity = 100 - (i * 30)  # Decreasing opacity
                    if shot_direction == "left":
                        draw.ellipse([
                            (ball_center[0] + offset - ball_radius * 0.7, ball_center[1] - ball_radius * 0.7),
                            (ball_center[0] + offset + ball_radius * 0.7, ball_center[1] + ball_radius * 0.7)
                        ], fill=(255, 255, 255, opacity), outline=None)
                    elif shot_direction == "right":
                        draw.ellipse([
                            (ball_center[0] - offset - ball_radius * 0.7, ball_center[1] - ball_radius * 0.7),
                            (ball_center[0] - offset + ball_radius * 0.7, ball_center[1] + ball_radius * 0.7)
                        ], fill=(255, 255, 255, opacity), outline=None)
                    else:
                        draw.ellipse([
                            (ball_center[0] - ball_radius * 0.7, ball_center[1] - offset - ball_radius * 0.7),
                            (ball_center[0] + ball_radius * 0.7, ball_center[1] - offset + ball_radius * 0.7)
                        ], fill=(255, 255, 255, opacity), outline=None)
            
            # Draw the shot path with arrow
            start_point = (img_width // 2, img_height - 80)
            end_point = ball_center
            
            # Draw line
            draw.line([start_point, end_point], fill=(255, 0, 0), width=3)
            
            # Calculate angle for arrow
            try:
                angle = math.atan2(end_point[1] - start_point[1], end_point[0] - start_point[0])
                
                # Draw arrowhead
                arrow_size = 15
                arrow_point1 = (
                    end_point[0] - arrow_size * math.cos(angle - math.pi/6),
                    end_point[1] - arrow_size * math.sin(angle - math.pi/6)
                )
                arrow_point2 = (
                    end_point[0] - arrow_size * math.cos(angle + math.pi/6),
                    end_point[1] - arrow_size * math.sin(angle + math.pi/6)
                )
                
                draw.polygon([end_point, arrow_point1, arrow_point2], fill=(255, 0, 0))
            except:
                # Just add a small circle if math fails
                draw.ellipse([
                    (end_point[0] - 5, end_point[1] - 5),
                    (end_point[0] + 5, end_point[1] + 5)
                ], fill=(255, 0, 0))
            
            # Add shot direction indicator
            direction_text = f"Shot: {shot_direction.upper()}"
            draw.text((img_width // 2, img_height - 50), direction_text, 
                     font=ImageFont.truetype("roboto.ttf", 25), fill=(0, 0, 0), anchor="mm")
            
            # Add result indicator
            result_font = ImageFont.truetype("roboto.ttf", 40)
            if goal_scored:
                result_text = "GOAL!"
                text_color = (0, 255, 0)
                # Add celebratory effects
                for _ in range(20):
                    x = random.randint(0, img_width)
                    y = random.randint(0, img_height // 3)
                    size = random.randint(5, 15)
                    color = (
                        random.randint(200, 255),
                        random.randint(200, 255),
                        random.randint(100, 200)
                    )
                    draw.ellipse([(x, y), (x + size, y + size)], fill=color)
            else:
                result_text = "SAVED!"
                text_color = (255, 0, 0)
            
            # Create highlight behind text
            try:
                text_width, text_height = result_font.getbbox(result_text)[2:]
                text_pos = (img_width // 2, 50)
                draw.rectangle([
                    (text_pos[0] - text_width//2 - 10, text_pos[1] - text_height//2 - 5),
                    (text_pos[0] + text_width//2 + 10, text_pos[1] + text_height//2 + 5)
                ], fill=(255, 255, 255, 180))
                
                draw.text(text_pos, result_text, font=result_font, fill=text_color, anchor="mm")
            except:
                # Fallback if getbbox fails
                draw.rectangle([
                    (img_width//2 - 100, 30),
                    (img_width//2 + 100, 70)
                ], fill=(255, 255, 255, 180))
                
                draw.text((img_width//2, 50), result_text, font=result_font, fill=text_color, anchor="mm")
            
            # Add "BETSYNC" watermark at the top with transparency
            watermark_font = ImageFont.truetype("roboto.ttf", 50)
            draw.text(
                (img_width // 2, 40), 
                "BETSYNC", 
                font=watermark_font, 
                fill=(0, 0, 0, 64),  # More transparent
                anchor="mm"
            )
            
            return image
            
        except Exception as e:
            # If any error occurs, create a simple fallback image
            img_width, img_height = 800, 600
            fallback_image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
            draw = ImageDraw.Draw(fallback_image)
            
            # Basic field
            draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
            
            # Simple goal
            goal_width, goal_height = 500, 200
            goal_left = (img_width - goal_width) // 2
            goal_top = img_height//2 - 50
            
            # Goal outline
            draw.rectangle([(goal_left, goal_top), (goal_left + goal_width, goal_top + goal_height)], outline=(255, 255, 255), width=5)
            
            # Simple goalkeeper
            goalkeeper_center = (img_width // 2, goal_top + goal_height - 100)
            if goalkeeper_direction == "left":
                goalkeeper_center = (goal_left + 100, goalkeeper_center[1])
            elif goalkeeper_direction == "right":
                goalkeeper_center = (goal_left + goal_width - 100, goalkeeper_center[1])
                
            draw.rectangle([(goalkeeper_center[0] - 30, goalkeeper_center[1] - 60), 
                           (goalkeeper_center[0] + 30, goalkeeper_center[1] + 60)], fill=(0, 180, 0))
            
            # Simple ball
            ball_center = (img_width // 2, goal_top + goal_height // 2)
            if shot_direction == "left":
                ball_center = (goal_left + 100, ball_center[1])
            elif shot_direction == "right":
                ball_center = (goal_left + goal_width - 100, ball_center[1])
                
            draw.ellipse([(ball_center[0] - 20, ball_center[1] - 20), 
                         (ball_center[0] + 20, ball_center[1] + 20)], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
            
            # Draw shot path
            draw.line([(img_width // 2, img_height - 80), ball_center], fill=(255, 0, 0), width=3)
            
            # Add result text
            result_text = "GOAL!" if goal_scored else "SAVED!"
            text_color = (0, 255, 0) if goal_scored else (255, 0, 0)
            
            font = ImageFont.truetype("roboto.ttf", 40)
            draw.text((img_width // 2, 50), result_text, font=font, fill=text_color, anchor="mm")
            
            # Add direction text
            draw.text((img_width // 2, img_height - 50), f"Shot: {shot_direction.upper()}", 
                     font=ImageFont.truetype("roboto.ttf", 25), fill=(0, 0, 0), anchor="mm")
            
            # Add watermark
            draw.text((img_width // 2, img_height - 30), "BETSYNC", font=ImageFont.truetype("roboto.ttf", 60), 
                      fill=(0, 0, 0, 64), anchor="mm")
            
            return fallback_image


def setup(bot):
    bot.add_cog(PenaltyCog(bot))
