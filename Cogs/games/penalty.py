
import discord
import random
import asyncio
import os
import io
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
        self.goal_image_path = "attached_assets/depositphotos_144160027-stock-illustration-soccer-goalkeeper-vector-illustration-of.png"
        
        # Ensure the goal image exists, if not, provide a placeholder
        if not os.path.exists(self.goal_image_path):
            print(f"Warning: Goal image not found at {self.goal_image_path}")
            # We'll handle this in the generate_image method

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
        """Generate an image of the penalty setup"""
        # Create a new image with a light blue background for the sky
        img_width, img_height = 800, 600
        image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
        
        # Draw the field (green)
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
        
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
        
        # Add a goalkeeper in the middle
        try:
            goalkeeper = Image.open(self.goal_image_path).convert('RGBA')
            goalkeeper = goalkeeper.resize((100, 150), Image.LANCZOS)
            
            # Position goalkeeper in the middle of the goal
            goalkeeper_pos = ((img_width - goalkeeper.width) // 2, goal_top + goal_height - goalkeeper.height - 10)
            image.paste(goalkeeper, goalkeeper_pos, goalkeeper)
        except Exception as e:
            print(f"Error loading goalkeeper image: {e}")
            # Draw a simple goalkeeper if image not available
            draw.rectangle([(img_width//2 - 25, goal_top + 50), (img_width//2 + 25, goal_top + 150)], fill=(0, 255, 0))
            draw.ellipse([(img_width//2 - 20, goal_top + 20), (img_width//2 + 20, goal_top + 60)], fill=(255, 200, 150))
        
        # Draw a ball
        ball_radius = 20
        ball_center = (img_width // 2, img_height - 80)
        draw.ellipse([
            (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
            (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
        ], fill=(255, 255, 255))
        
        # Add some details to the ball
        draw.line([
            (ball_center[0] - ball_radius, ball_center[1]),
            (ball_center[0] + ball_radius, ball_center[1])
        ], fill=(0, 0, 0), width=2)
        draw.line([
            (ball_center[0], ball_center[1] - ball_radius),
            (ball_center[0], ball_center[1] + ball_radius)
        ], fill=(0, 0, 0), width=2)
        
        # Add "BETSYNC" watermark
        watermark_font = ImageFont.truetype("roboto.ttf", 60)
        draw.text((img_width // 2, img_height - 30), "BETSYNC", font=watermark_font, fill=(0, 0, 0, 64), anchor="mm")
        
        return image

    def generate_penalty_result_image(self, shot_direction, goalkeeper_direction, goal_scored):
        """Generate an image showing the penalty outcome"""
        # Create a new image with a light blue background for the sky
        img_width, img_height = 800, 600
        image = Image.new('RGBA', (img_width, img_height), (135, 206, 250))
        
        # Draw the field (green)
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0, img_height//2), (img_width, img_height)], fill=(34, 139, 34))
        
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
            "left": (goal_left + 50, goal_top + goal_height - 150 - 10),
            "middle": ((img_width - 100) // 2, goal_top + goal_height - 150 - 10),
            "right": (goal_left + goal_width - 150, goal_top + goal_height - 150 - 10)
        }
        
        # Position mapper for ball
        ball_positions = {
            "left": (goal_left + 100, goal_top + goal_height // 2),
            "middle": (img_width // 2, goal_top + goal_height // 2),
            "right": (goal_left + goal_width - 100, goal_top + goal_height // 2)
        }
        
        # Add the goalkeeper in the chosen position
        try:
            goalkeeper = Image.open(self.goal_image_path).convert('RGBA')
            goalkeeper = goalkeeper.resize((100, 150), Image.LANCZOS)
            
            # Position goalkeeper based on direction
            goalkeeper_pos = goalkeeper_positions[goalkeeper_direction]
            image.paste(goalkeeper, goalkeeper_pos, goalkeeper)
        except Exception as e:
            print(f"Error loading goalkeeper image: {e}")
            # Draw a simple goalkeeper if image not available
            goalkeeper_pos = goalkeeper_positions[goalkeeper_direction]
            draw.rectangle([(goalkeeper_pos[0], goalkeeper_pos[1]), (goalkeeper_pos[0] + 50, goalkeeper_pos[1] + 100)], fill=(0, 255, 0))
            draw.ellipse([(goalkeeper_pos[0] + 5, goalkeeper_pos[1] - 30), (goalkeeper_pos[0] + 45, goalkeeper_pos[1] + 10)], fill=(255, 200, 150))
        
        # Draw the ball at the shot position
        ball_radius = 20
        ball_center = ball_positions[shot_direction]
        draw.ellipse([
            (ball_center[0] - ball_radius, ball_center[1] - ball_radius),
            (ball_center[0] + ball_radius, ball_center[1] + ball_radius)
        ], fill=(255, 255, 255))
        
        # Add some details to the ball
        draw.line([
            (ball_center[0] - ball_radius, ball_center[1]),
            (ball_center[0] + ball_radius, ball_center[1])
        ], fill=(0, 0, 0), width=2)
        draw.line([
            (ball_center[0], ball_center[1] - ball_radius),
            (ball_center[0], ball_center[1] + ball_radius)
        ], fill=(0, 0, 0), width=2)
        
        # Draw the shot path
        draw.line([
            (img_width // 2, img_height - 80),  # Starting position of the ball
            ball_center
        ], fill=(255, 0, 0), width=2)
        
        # Add indicator text
        result_font = ImageFont.truetype("roboto.ttf", 30)
        if goal_scored:
            draw.text(ball_center, "GOAL!", font=result_font, fill=(0, 255, 0), anchor="mm")
        else:
            draw.text(ball_center, "SAVED!", font=result_font, fill=(255, 0, 0), anchor="mm")
        
        # Add "BETSYNC" watermark
        watermark_font = ImageFont.truetype("roboto.ttf", 60)
        draw.text((img_width // 2, img_height - 30), "BETSYNC", font=watermark_font, fill=(0, 0, 0, 64), anchor="mm")
        
        return image


def setup(bot):
    bot.add_cog(PenaltyCog(bot))
