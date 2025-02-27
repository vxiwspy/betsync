import discord
import requests
import qrcode
import io
import asyncio

import datetime

import time
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from colorama import Fore
import re


class DepositCancelView(discord.ui.View):
    """
    A View with Cancel and Copy buttons.
    - Cancel: Cancels the pending deposit.
    - Copy: Sends two ephemeral messages containing the deposit address and deposit amount.
    """
    def __init__(self, cog, user_id, deposit_address: str, deposit_amount: float, timeout=600):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_id = user_id
        self.deposit_address = deposit_address
        self.deposit_amount = deposit_amount
        self.loading_msg = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, button, interaction: discord.Interaction):
        # Ensure only the deposit owner can cancel
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You cannot cancel someone else's deposit.", ephemeral=True
            )
        # Get context and remove pending deposit if it exists
        if self.user_id in self.cog.pending_deposits:
            del self.cog.pending_deposits[self.user_id]
            # Reset the cooldown by getting the command and all its cooldowns
            cmd = self.cog.bot.get_command('dep')
            if cmd:
                # Create a minimal dummy context for cooldown reset
                dummy_message = discord.Message(
                    state=interaction.message._state, 
                    channel=interaction.channel, 
                    data={
                        'id': 0,
                        'content': '!dep',
                        'attachments': [],
                        'embeds': [],
                        'mention_everyone': False,
                        'tts': False,
                        'type': 0,
                        'pinned': False,
                        'edited_timestamp': None,
                        'author': {'id': interaction.user.id},
                        'timestamp': '2024-01-01T00:00:00+00:00'
                    }
                )
                dummy_message.author = interaction.user
                ctx = await self.cog.bot.get_context(dummy_message)
                # Reset the cooldown by clearing the cache
                if cmd._buckets._cooldown:
                    bucket = cmd._buckets.get_bucket(ctx.message)
                    if bucket:
                        bucket.reset()

            # Disable buttons and update message
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            # Reset pending deposit
            if self.user_id in self.cog.pending_deposits:
                del self.cog.pending_deposits[self.user_id]

            cancel_embed = discord.Embed(
                title="<:no:1344252518305234987> | DEPOSIT CANCELLED",
                description="Your deposit has been cancelled.\nYou can now use `!dep` to create a new deposit.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=cancel_embed, ephemeral=True)
        else:
            ctx = await self.cog.bot.get_context(interaction.message)
            retry_after = self.cog.dep.get_cooldown_retry_after(ctx)
            if retry_after:
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | DEPOSIT COOLDOWN",
                    description=f"You cannot deposit until {int(retry_after)} seconds have passed or click the cancel button.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                embed = discord.Embed(
                    title="<:no:1344252518305234987> | Cooldown Active",
                    description=f"Please wait {int(retry_after)} seconds before depositing again or click the cancel button.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Copy", style=discord.ButtonStyle.secondary)
    async def copy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Ensure only the deposit owner can use the copy button
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You cannot copy someone else's deposit details.", ephemeral=True
            )
        # Send the deposit address as one ephemeral message
        await interaction.response.send_message(f" {self.deposit_address}", ephemeral=True)
        # Send the deposit amount as a separate ephemeral followup message
        await interaction.followup.send(f" {self.deposit_amount:.6f}", ephemeral=True)

        address_embed = discord.Embed(
            title="Deposit Address",
            description=f"```{self.deposit_address}```",
            color=discord.Color.blue()
        )
        amount_embed = discord.Embed(
            title="Deposit Amount",
            description=f"**{self.deposit_amount:.6f}**",
            color=discord.Color.blue()
        )
        # First, send the address
        await interaction.response.send_message(embed=address_embed, ephemeral=True)
        # Then, send a followup message with the deposit amount.
        await interaction.followup.send(embed=amount_embed, ephemeral=True)


class Deposit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_currency = "usdcalgo"
        self.api_key = "d676247c-fbc2-4490-9fbf-e0e60a4e2066"
        self.supported_currencies = {
            "BTC": "btc",
            "LTC": "ltc",
            "SOL": "sol",
            "ETH": "eth",
            "USDT": "usdt"
        }
        self.pending_deposits = {}
        self.deposit_timeout = 600  # 10 minutes

    def get_crypto_prices(self):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,litecoin,solana",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"{Fore.RED}[-] {Fore.WHITE}Failed to fetch crypto prices. Status Code: {Fore.RED}{response.status_code}{Fore.WHITE}")
            return None

    def get_conversion_rate(self, currency, amount):
        url = (
            f"https://api.simpleswap.io/v1/get_estimated?"
            f"api_key={self.api_key}&currency_from={self.target_currency}"
            f"&currency_to={currency}&amount={amount}&fixed=false"
        )
        response = requests.get(url)
        try:
            data = response.json()
            if isinstance(data, (float, int, str)):
                return float(data)
            elif isinstance(data, dict) and data.get("code") == 422:
                # Parse the minimum value from the description string
                desc = data.get("description", "")
                match = re.search(r"Min:\s*([\d.]+)", desc)
                if match:
                    min_deposit_crypto = float(match.group(1))
                    return {"error": "amount_too_low", "min": min_deposit_crypto}
                else:
                    print(f"[ERROR] Could not parse minimum deposit from: {desc}")
                    return None
            else:
                print(f"[ERROR] Unexpected conversion response: {data}")
                return None
        except requests.exceptions.JSONDecodeError:
            print(f"[ERROR] Non-JSON response: {response.text}")
            return None

    def get_usdcalgo_to_usd(self, amount):
        """
        Converts a given amount of USDC (Algo) to USD using CoinGecko.
        Since USDC is pegged to USD, this should normally return a 1:1 conversion.
        """
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "usd-coin",
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params)
        try:
            data = response.json()
            rate = data.get("usd-coin", {}).get("usd")
            if rate is None:
                print("[ERROR] Could not fetch USD conversion rate for USDC from CoinGecko.")
                return None
            return float(rate) * float(amount)
        except Exception as e:
            print(f"[ERROR] Exception in get_usdcalgo_to_usd: {e}")
            return None

    def get_minimum_deposit(self, currency):
        """
        Fetch the minimum deposit amount (in USD) for the given currency.
        """
        url = (
            f"https://api.simpleswap.io/v1/get_ranges?"
            f"api_key={self.api_key}&currency_from={currency}&currency_to={self.target_currency}&fixed=false"
        )
        response = requests.get(url)
        try:
            data = response.json()
            min_amount = data.get("min")
            if min_amount is not None:
                return float(min_amount)
            return None
        except Exception as e:
            print(f"[ERROR] Unable to fetch minimum deposit: {e}")
            return None

    def get_deposit_data(self, currency, amount):
        """
        Create a SimpleSwap exchange transaction and return the full JSON response.
        """
        personal_address = "GRTDJ7BFUWZYL5344ZD4KUWVALVKSBR4LNY62PRCL5E4664QHM4C4YLNFQ"
        url = f"https://api.simpleswap.io/v1/create_exchange?api_key={self.api_key}"
        payload = {
            "currency_from": currency,
            "currency_to": self.target_currency,
            "amount": amount,
            "address_to": personal_address,
            "fixed": False
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers)
        try:
            data = response.json()
            print(f"[DEBUG] create_exchange response: {data}")
            if "address_from" in data:
                return data
            else:
                print(f"[ERROR] Missing 'address_from': {data}")
                return None
        except requests.exceptions.JSONDecodeError:
            print(f"[ERROR] Non-JSON response: {response.text}")
            return None

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown) and ctx.command.name in ['dep', 'depo']:
            retry_after = int(error.retry_after)
            current_time = int(time.time())
            embed = discord.Embed(
                title="<:no:1344252518305234987> | DEPOSIT COOLDOWN",
                description=f"You're on cooldown!\nPlease wait **{retry_after}** seconds.\nTry again <t:{current_time + retry_after}:R>",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.command(aliases=["depo"])
    @commands.cooldown(1, 600, commands.BucketType.user)  # 10 minute cooldown
    async def dep(self, ctx, currency: str = None, amount: float = None):
        """
        Deposit command: !dep <currency> <amount in USD>
        Example: !dep BTC 50
        """
        # Immediately send loading embed
        loading_embed = discord.Embed(
            title="<a:loading:1344611780638412811> | Generating Deposit...",
            description="Please wait while we fetch your deposit details.",
            color=discord.Color.gold()
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Check for active deposit
        if ctx.author.id in self.pending_deposits:
            # Get remaining cooldown
            retry_after = self.dep.get_cooldown_retry_after(ctx)
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Active Deposit",
                description=f"Please wait {int(retry_after)} seconds before depositing again or cancel manually via the cancel button.",
                color=discord.Color.red()
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)

        # Prevent duplicate deposits
        if ctx.author.id in self.pending_deposits:
            await loading_message.delete()
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Active Deposit",
                description="You have a pending deposit. Please wait for it to expire or cancel it.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed)

        # Validate input
        if not currency or not amount:
            await loading_message.delete()
            usage_embed = discord.Embed(
                title=":bulb: How to Use `!dep`",
                description="**Usage:** `!dep <currency> <amount in USD>`\n**Example:** `!dep BTC 50`",
                color=0xFFD700
            )
            usage_embed.add_field(
                name=":pushpin: Supported Currencies",
                value="BTC, LTC, SOL, ETH, USDT (ERC20)"
            )
            await ctx.reply(embed=usage_embed)
            return await self.dep.reset_cooldown(ctx)

        currency = currency.upper()
        if currency not in self.supported_currencies:
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Invalid Currency",
                    description=f"`{currency}` is not supported. Use BTC, LTC, SOL, ETH, USDT.",
                    color=0xFF0000
                )
            )


        # Get conversion rate from USD -> Crypto for the user's deposit amount
        converted_amount = self.get_conversion_rate(self.supported_currencies[currency], amount)

        # Check if the API returned an error dict indicating the amount is too low
        if isinstance(converted_amount, dict) and converted_amount.get("error") == "amount_too_low":
            # The API error returns the minimum deposit in usdcalgo
            min_deposit_usdcalgo = converted_amount["min"]
            # Convert 1 usdcalgo to USD. This gives you the live USD value of one usdcalgo.
            usd_value = self.get_usdcalgo_to_usd(1)
            if usd_value:
                min_deposit_usd = min_deposit_usdcalgo * usd_value
            else:
                min_deposit_usd = min_deposit_usdcalgo  # Fallback if conversion fails
            # Round to 8 decimal places
            min_deposit_usd = round(min_deposit_usd, 8)
            await loading_message.delete()
            return await ctx.reply(embed=discord.Embed(
                title=":warning: Amount Too Low",
                description=(
                    f"The minimum deposit for **{currency}** is **{min_deposit_usd:.8f} USD**.\n"
                    "Please increase your deposit amount and try again."
                ),
                color=discord.Color.orange()
            ))

        # Create exchange and get deposit info
        deposit_data = self.get_deposit_data(self.supported_currencies[currency], amount)
        if not deposit_data:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Error",
                    description="Failed to fetch deposit address. Try again later.",
                    color=0xFF0000
                )
            )
        deposit_address = deposit_data.get("address_from")
        order_id = deposit_data.get("id")  # Capture the order ID from SimpleSwap
        if not deposit_address or not order_id:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Error",
                    description="No deposit address or order ID received. Contact support.",
                    color=0xFF0000
                )
            )

        # Generate QR Code with optimized settings
        qr_data = f"Amount: {converted_amount:.6f} {currency}\nAddress: {deposit_address}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=8,
            border=1
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Create a new background with gradient
        background = Image.new('RGBA', (500, 600), 'white')  # Reduced height
        gradient = Image.new('RGBA', background.size, (0,0,0,0))
        draw_gradient = ImageDraw.Draw(gradient)
        for y in range(background.height):
            alpha = int(255 * (1 - y/background.height))
            draw_gradient.line([(0,y), (background.width,y)], fill=(240,240,255,alpha))
        background = Image.alpha_composite(background.convert('RGBA'), gradient)

        # Resize and optimize QR code
        qr_img = qr_img.resize((280, 280), Image.Resampling.LANCZOS)  # Slightly smaller QR

        # Calculate position to center QR code
        qr_x = (background.width - qr_img.width) // 2
        qr_y = 120  # Moved up
        background.paste(qr_img, (qr_x, qr_y))

        # Add text with better fonts
        draw = ImageDraw.Draw(background)
        title_font = ImageFont.truetype("roboto.ttf", 36)
        detail_font = ImageFont.truetype("roboto.ttf", 24)

        # Add text elements with adjusted spacing
        draw.text((250, 50), f"{ctx.author.name}'s Deposit QR", font=title_font, anchor="mm", fill="black")
        draw.text((250, qr_y + qr_img.height + 20), f"Amount: {converted_amount:.6f} {currency}", font=detail_font, anchor="mm", fill="black")
        draw.text((250, qr_y + qr_img.height + 50), "Scan to get address", font=detail_font, anchor="mm", fill="black")

        # Add semi-transparent watermark
        watermark = "BETSYNC"
        watermark_font = ImageFont.truetype("roboto.ttf", 60)  # Smaller font
        watermark_bbox = draw.textbbox((0, 0), watermark, font=watermark_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_x = (background.width - watermark_width) // 2
        watermark_y = 520  # Adjusted position

        # Draw watermark with transparency
        draw.text((watermark_x, watermark_y), watermark, font=watermark_font, fill=(0, 0, 0, 64))

        # Save to bytes
        img_buf = io.BytesIO()
        background.save(img_buf, format='PNG')
        img_buf.seek(0)
        file = discord.File(img_buf, filename="qrcode.png")

        # Calculate tokens to be received based on the deposit USD amount
        # (1 token = 0.0212 USD)
        tokens_to_be_received = amount / 0.0212

        # Build the deposit embed to be sent via DM
        expiration_timestamp = int(time.time() + self.deposit_timeout)
        deposit_embed = discord.Embed(
            title="💎 Secure Deposit Gateway",
            description=(
                "**Follow these steps to complete your deposit:**\n"
                "1. Send the exact amount shown below\n"
                "2. Wait for confirmation (2-3 minutes)\n"
                "3. Your balance will update automatically"
            ),
            color=0x2B2D31
        )
        deposit_embed.add_field(
            name="Deposit Amount",
            value=f"Send **{converted_amount:.6f} {currency}**",
            inline=False
        )
        deposit_embed.add_field(
            name="Deposit Address",
            value=f"```{deposit_address}```",
            inline=False
        )
        deposit_embed.add_field(
            name="Tokens to be Received",
            value=f"**{tokens_to_be_received:.2f} tokens**",
            inline=False
        )
        deposit_embed.add_field(
            name="Expires",
            value=f"<t:{expiration_timestamp}:R>",
            inline=True
        )
        deposit_embed.add_field(
            name="Instructions",
            value="After sending, please wait 2-3 minutes. Your balance will update automatically.",
            inline=True
        )
        deposit_embed.add_field(
            name="Important",
            value=(
                ":warning: **Note:** Minimum deposit requirements may change at any time. "
                "If you send less than the updated minimum, you may need to contact support using `!support` to get your funds returned. "
                "To avoid issues, we recommend sending a few cents more than the displayed minimum."
            ),
            inline=False
        )
        deposit_embed.set_image(url="attachment://qrcode.png")
        deposit_embed.set_footer(text="BetSync Casino • Secure Transactions")

        # Create a view with Cancel and Copy buttons
        view = DepositCancelView(self, ctx.author.id, deposit_address, converted_amount, timeout=self.deposit_timeout)

        # DM the deposit embed to the user
        try:
            dm_channel = ctx.author.dm_channel or await ctx.author.create_dm()
            await dm_channel.send(embed=deposit_embed, file=file, view=view)
            await loading_message.delete()
            # Send success message
            success_embed = discord.Embed(
                title="<:checkmark:1344252974188335206> | Deposit Details Sent!",
                description="Check your DMs for the deposit details.",
                color=discord.Color.green()
            )
            await ctx.reply(embed=success_embed, delete_after=10)

            # Start tracking the payment
            self.bot.loop.create_task(
                self.track_payment(ctx, order_id, converted_amount, currency, amount)
            )
        except discord.Forbidden:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":warning: DMs Disabled",
                    description="Please enable DMs to receive deposit instructions.",
                    color=0xFFA500
                )
            )

        # Mark the deposit as pending (store order_id and original USD amount)
        self.pending_deposits[ctx.author.id] = {
            "address": deposit_address,
            "amount": converted_amount,
            "currency": currency,
            "order_id": order_id,
            "usd_amount": amount,           # Original deposit amount in USD
            "tokens": tokens_to_be_received  # Tokens to be credited
        }

        # Launch the background task for live payment tracking
        # Pass the original USD amount for token calculation
        self.bot.loop.create_task(
            self.track_payment(ctx, order_id, converted_amount, currency, amount)
        )

    def process_deposit(self, user_id, tokens_amount):
        """Updates the user's balance when a deposit is successful."""
        db = Users()
        # Update balance
        resp = db.update_balance(user_id, tokens_amount, "tokens", "$inc")
        
        # Add to history
        history_entry = {
            "type": "deposit",
            "amount": tokens_amount,
            "timestamp": int(datetime.datetime.now().timestamp())
        }
        db.collection.update_one(
            {"discord_id": user_id},
            {"$push": {"history": {"$each": [history_entry], "$slice": -100}}}  # Keep last 100 entries
        )
        
        # Update total deposit amount
        db.collection.update_one(
            {"discord_id": user_id},
            {"$inc": {"total_deposit_amount": tokens_amount}}
        )
        
        user = self.bot.get_user(user_id)
        if user:
            embed = discord.Embed(
                title=":moneybag: Deposit Successful!",
                description=f"You have received **{tokens_amount:.2f} tokens** in your balance.",
                color=0x00FF00
            )
            return user.send(embed=embed)

    async def track_payment(self, ctx, order_id, expected_amount, currency, usd_amount):
        """
        Monitors the deposit payment.
        - expected_amount: The crypto amount expected.
        - usd_amount: The original deposit amount in USD.
        """
        start_time = time.time()
        poll_interval = 15  # seconds between each check

        while time.time() - start_time < self.deposit_timeout:
            payment_status = self.check_payment(order_id)
            if payment_status["received"]:
                received_amount = payment_status["amount"]
                if received_amount >= expected_amount:
                    try:
                        # Calculate tokens based on the original deposit USD amount
                        tokens_to_be_received = usd_amount / 0.0212
                        await ctx.author.send(
                            f"<:checkmark:1344252974188335206> | Full payment of **{received_amount:.6f} {currency}** received! "
                            f"Processing your deposit... You will receive **{tokens_to_be_received:.2f} tokens**."
                        )
                        self.process_deposit(ctx.author.id, tokens_to_be_received)
                        self.pending_deposits.pop(ctx.author.id, None)
                        return
                    except Exception as e:
                        print(f"[ERROR] Processing deposit: {e}")
                        await ctx.author.send("There was an error processing your deposit. Please contact support.")
                        return
                else:
                    # Optionally re-fetch the current minimum deposit for this currency
                    current_minimum = self.get_minimum_deposit(currency)
                    message = f":warning: Partial payment detected. You sent **{received_amount:.6f} {currency}** but **{expected_amount:.6f} {currency}** is required."
                    if current_minimum and current_minimum > expected_amount:
                        message += f" The minimum has increased to **{current_minimum:.6f} {currency}** during your payment."
                    message += " Please send the remaining amount to complete your deposit or contact support for a refund."
                    await ctx.author.send(message)
            await asyncio.sleep(poll_interval)

        if ctx.author.id in self.pending_deposits:
            cancel_embed = discord.Embed(
                title="<:no:1344252518305234987> | DEPOSIT CANCELLED",
                description=(
                    "The deposit timer has expired and no full transaction was detected.\n"
                    "If you'd like to try again, use `!dep <currency> <amount>`."
                ),
                color=discord.Color.red()
            )
            try:
                await ctx.author.send(embed=cancel_embed)
            except discord.Forbidden:
                pass
            self.pending_deposits.pop(ctx.author.id, None)

    def check_payment(self, order_id):
        """
        Check the payment status for the given SimpleSwap order ID.
        Returns a dict: {"received": bool, "amount": float}
        """
        url = f"https://api.simpleswap.io/v1/get_status?api_key={self.api_key}&id={order_id}"
        try:
            response = requests.get(url)
            data = response.json()
            # Example: SimpleSwap might return a status like "completed" or "partial"
            if data.get("status") in ["completed", "partial"]:
                received_amount = float(data.get("received_amount", 0))
                return {"received": True, "amount": received_amount}
            else:
                return {"received": False, "amount": 0.0}
        except Exception as e:
            print(f"[ERROR] Checking payment status: {e}")
            return {"received": False, "amount": 0.0}

    @dep.before_invoke
    async def before(self, ctx):
        loading_emoji = emoji()["loading"]
        db = Users()
        if db.fetch_user(ctx.author.id) != False:
            pass
        else:
            print(f"{Fore.YELLOW}[~] {Fore.WHITE}New User Detected... {Fore.BLACK}{ctx.author.id}{Fore.WHITE} {Fore.YELLOW}")
            dump = {"discord_id": ctx.author.id, "tokens": 0, "credits": 0, "history": [], "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost':0}
            db.register_new_user(dump)

def setup(bot):
    bot.add_cog(Deposit(bot))