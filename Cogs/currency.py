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
        self.target_currency = "usdc"  # Target currency for deposits (changed from usdcalgo to usdc)
        self.api_key = "d676247c-fbc2-4490-9fbf-e0e60a4e2066"  # SimpleSwap API key
        self.supported_currencies = {
            "BTC": "btc",
            "LTC": "ltc",
            "SOL": "sol",
            "ETH": "eth",
            "USDT": "usdt"
        }
        self.pending_deposits = {}
        self.deposit_timeout = 600  # 10 minutes
        
        # Test the API connection on initialization
        print("[INIT] Testing SimpleSwap API connection on startup")
        self.test_api_connection()

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

    def test_api_connection(self):
        """
        Test the SimpleSwap API connection with a minimal request to diagnose issues.
        """
        print(f"[DEBUG-TEST] Testing SimpleSwap API connection...")
        test_url = f"https://api.simpleswap.io/v1/get_all_currencies?api_key={self.api_key}"
        
        try:
            response = requests.get(test_url, timeout=10)
            print(f"[DEBUG-TEST] Test API status code: {response.status_code}")
            
            if response.status_code == 200:
                print(f"[DEBUG-TEST] API connection successful")
                try:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        print(f"[DEBUG-TEST] API returned a list of {len(data)} currencies")
                        # Verify our target currency is in the list
                        if self.target_currency in data:
                            print(f"[DEBUG-TEST] Target currency '{self.target_currency}' is supported")
                        else:
                            print(f"[ERROR-TEST] Target currency '{self.target_currency}' is NOT in the supported currencies list!")
                            # Try to find some alternative stable coins
                            stablecoins = [c for c in data if 'usd' in c.lower()][:5]
                            if stablecoins:
                                print(f"[DEBUG-TEST] Available stablecoins: {stablecoins}")
                    else:
                        print(f"[DEBUG-TEST] API returned unexpected data format: {data}")
                except Exception as e:
                    print(f"[DEBUG-TEST] Cannot parse API response: {str(e)}")
            else:
                print(f"[ERROR-TEST] API test failed with status code {response.status_code}: {response.text}")
                
            # Check if our supported currencies are valid
            print(f"[DEBUG-TEST] Checking supported currencies...")
            for currency_code in self.supported_currencies.values():
                currency_check_url = f"https://api.simpleswap.io/v1/get_pairs?api_key={self.api_key}&fixed=false&currency_from={currency_code}"
                try:
                    currency_response = requests.get(currency_check_url, timeout=10)
                    if currency_response.status_code == 200:
                        pairs = currency_response.json()
                        if self.target_currency in pairs:
                            print(f"[DEBUG-TEST] '{currency_code}' to '{self.target_currency}' exchange is supported")
                        else:
                            print(f"[ERROR-TEST] '{currency_code}' to '{self.target_currency}' exchange is NOT supported")
                            if len(pairs) > 0:
                                print(f"[DEBUG-TEST] Sample available pairs for {currency_code}: {pairs[:3]}")
                    else:
                        print(f"[ERROR-TEST] Could not check pairs for {currency_code}: {currency_response.status_code}")
                except Exception as e:
                    print(f"[ERROR-TEST] Error checking pairs for {currency_code}: {str(e)}")
            
        except Exception as e:
            print(f"[ERROR-TEST] API test failed with exception: {str(e)}")

    def get_deposit_data(self, currency, amount):
        """
        Create a SimpleSwap exchange transaction and return the full JSON response.
        """
        import time
        import traceback
        start_time = time.time()
        
        print(f"\n[DEBUG-DEPOSIT] === STARTING DEPOSIT PROCESS ===")
        print(f"[DEBUG-DEPOSIT] Currency: {currency}, Amount: {amount}")
        
        # Using USDC ERC20 wallet address (make sure to update this with your actual USDC address)
        personal_address = "0xE67B10f7e5D3F3875B1E82c3CA53a5B96ef27cA6"
        url = f"https://api.simpleswap.io/v1/create_exchange?api_key={self.api_key}"
        payload = {
            "currency_from": currency,
            "currency_to": self.target_currency,
            "amount": amount,
            "address_to": personal_address,
            "fixed": False
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"[DEBUG-DEPOSIT] API Key (first 4 chars): {self.api_key[:4]}***")
        print(f"[DEBUG-DEPOSIT] Sending request to: {url}")
        print(f"[DEBUG-DEPOSIT] Payload: {payload}")
        print(f"[DEBUG-DEPOSIT] Headers: {headers}")
        
        try:
            print(f"[DEBUG-DEPOSIT] Making API request...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            print(f"[DEBUG-DEPOSIT] Status code: {response.status_code}")
            print(f"[DEBUG-DEPOSIT] Response headers: {response.headers}")
            print(f"[DEBUG-DEPOSIT] Raw response: {response.text[:500]}")  # Print first 500 chars to avoid flooding logs
            
            if response.status_code != 200:
                print(f"[ERROR-DEPOSIT] API returned status code {response.status_code}: {response.text}")
                return None
                
            try:
                print(f"[DEBUG-DEPOSIT] Parsing JSON response...")
                data = response.json()
                print(f"[DEBUG-DEPOSIT] Parsed JSON: {data}")
                
                if isinstance(data, dict) and "address_from" in data:
                    print(f"[SUCCESS-DEPOSIT] Address generated: {data['address_from']}")
                    return data
                elif isinstance(data, dict) and "message" in data:
                    print(f"[ERROR-DEPOSIT] API error message: {data['message']}")
                    return None
                else:
                    print(f"[ERROR-DEPOSIT] Missing 'address_from' in response: {data}")
                    # Try testing the API with a minimal test call
                    self.test_api_connection()
                    return None
            except requests.exceptions.JSONDecodeError as json_err:
                print(f"[ERROR-DEPOSIT] Non-JSON response: {response.text}")
                print(f"[ERROR-DEPOSIT] JSON decode error: {str(json_err)}")
                return None
        except requests.exceptions.Timeout:
            print(f"[ERROR-DEPOSIT] Request timeout - API server may be slow or unresponsive")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[ERROR-DEPOSIT] Connection error - Check your internet connection")
            return None
        except Exception as e:
            print(f"[ERROR-DEPOSIT] Unexpected exception: {str(e)}")
            print(f"[ERROR-DEPOSIT] Traceback: {traceback.format_exc()}")
            return None
        finally:
            end_time = time.time()
            print(f"[TIMING-DEPOSIT] SimpleSwap API request took {end_time - start_time:.2f} seconds")
            print(f"[DEBUG-DEPOSIT] === DEPOSIT PROCESS COMPLETED ===\n")

    # Cooldown is now handled directly in the command
    # This listener is no longer needed as we apply cooldown manually

    @commands.command(aliases=["depo", "deposit"])
    async def dep(self, ctx, currency: str = None, amount: float = None):
        """
        Deposit command: !dep <currency> <amount in USD>
        Example: !dep BTC 50
        """
        # Test API connection before continuing
        print(f"[DEBUG] Testing API connection before generating deposit")
        self.test_api_connection()
        
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
            usage_embed = discord.Embed(
                title=":bulb: How to Use `!dep`",
                description="**Usage:** `!dep <currency> <amount in USD>`\n**Example:** `!dep BTC 50`",
                color=0xFFD700
            )
            usage_embed.add_field(
                name=":pushpin: Supported Currencies",
                value="BTC, LTC, SOL, ETH, USDT (ERC20)"
            )
            # Do not trigger cooldown if user is just checking usage
            await loading_message.delete()
            return await ctx.reply(embed=usage_embed)
            
        # Apply cooldown only when actually starting a deposit
        self.dep._buckets.get_bucket(ctx).update_rate_limit()

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
        print(f"[DEBUG-CMD] Attempting to get deposit data for {currency} (code: {self.supported_currencies[currency]}) - Amount: {amount}")
        try:
            # Set a shorter timeout for the API call
            deposit_data = self.get_deposit_data(self.supported_currencies[currency], amount)
            
            # Debug check - print what we received
            print(f"[DEBUG-DEPOSIT-RESPONSE] Received response: {deposit_data}")
            
            if not deposit_data:
                # Test the API connection before giving up
                print(f"[DEBUG-CMD] Deposit data fetch failed. Testing API connection...")
                self.test_api_connection()
                
                # Try again with a different API endpoint format
                print(f"[DEBUG-CMD] Trying alternative API endpoint format...")
                # Update target currency to properly formatted version
                alt_target = "usdcalgo" 
                alt_url = f"https://api.simpleswap.io/v1/create_exchange?api_key={self.api_key}"
                alt_payload = {
                    "currency_from": self.supported_currencies[currency],
                    "currency_to": alt_target,
                    "amount": amount,
                    "address_to": "GRTDJ7BFUWZYL5344ZD4KUWVALVKSBR4LNY62PRCL5E4664QHM4C4YLNFQ",
                    "fixed": False
                }
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                
                print(f"[DEBUG-FALLBACK] Making fallback API request to {alt_url}")
                print(f"[DEBUG-FALLBACK] Payload: {alt_payload}")
                
                response = requests.post(alt_url, json=alt_payload, headers=headers, timeout=30)
                print(f"[DEBUG-FALLBACK] Status code: {response.status_code}")
                print(f"[DEBUG-FALLBACK] Response text: {response.text}")
                
                if response.status_code == 200:
                    try:
                        deposit_data = response.json()
                        print(f"[DEBUG-FALLBACK] Successfully got data: {deposit_data}")
                    except Exception as e:
                        print(f"[DEBUG-FALLBACK] JSON parsing error: {str(e)}")
                
            if not deposit_data:
                await loading_message.delete()
                error_embed = discord.Embed(
                    title="<:no:1344252518305234987> | Deposit Error",
                    description="Failed to fetch deposit address. This could be due to:\n\n" +
                               "• API service might be down\n" +
                               "• Network connectivity issues\n" +
                               "• Minimum deposit amount may have changed\n\n" +
                               "Please try again later or contact support.",
                    color=0xFF0000
                )
                error_embed.set_footer(text="Error details have been logged for the administrator")
                return await ctx.reply(embed=error_embed)
        except Exception as e:
            print(f"[ERROR-CRITICAL] Exception during deposit data fetch: {str(e)}")
            await loading_message.delete()
            error_embed = discord.Embed(
                title="<:no:1344252518305234987> | Deposit Error",
                description=f"An error occurred while processing your deposit request:\n```{str(e)}```\nPlease try again later or contact support.",
                color=0xFF0000
            )
            error_embed.set_footer(text="Error details have been logged for the administrator")
            return await ctx.reply(embed=error_embed)
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
        try:
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
            print(f"[DEBUG] Successfully generated QR code for address: {deposit_address}")
        except Exception as e:
            print(f"[ERROR] Failed to generate QR code: {str(e)}")
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title="<:no:1344252518305234987> | QR Generation Error",
                    description="Failed to generate QR code. Please try again.",
                    color=0xFF0000
                )
            )

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
        try:
            title_font = ImageFont.truetype("roboto.ttf", 36)
            detail_font = ImageFont.truetype("roboto.ttf", 24)
        except Exception as e:
            print(f"[WARNING] Could not load Roboto font: {str(e)}. Using default font.")
            # Use default font as fallback
            title_font = ImageFont.load_default()
            detail_font = ImageFont.load_default()

        # Add text elements with adjusted spacing
        draw.text((250, 50), f"{ctx.author.name}'s Deposit QR", font=title_font, anchor="mm", fill="black")
        draw.text((250, qr_y + qr_img.height + 20), f"Amount: {converted_amount:.6f} {currency}", font=detail_font, anchor="mm", fill="black")
        draw.text((250, qr_y + qr_img.height + 50), "Scan to get address", font=detail_font, anchor="mm", fill="black")

        # Add semi-transparent watermark
        try:
            watermark = "BETSYNC"
            try:
                watermark_font = ImageFont.truetype("roboto.ttf", 60)  # Smaller font
            except Exception as e:
                print(f"[WARNING] Could not load Roboto font for watermark: {str(e)}. Using default.")
                watermark_font = ImageFont.load_default()
                
            watermark_bbox = draw.textbbox((0, 0), watermark, font=watermark_font)
            watermark_width = watermark_bbox[2] - watermark_bbox[0]
            watermark_x = (background.width - watermark_width) // 2
            watermark_y = 520  # Adjusted position

            # Draw watermark with transparency
            draw.text((watermark_x, watermark_y), watermark, font=watermark_font, fill=(0, 0, 0, 64))
        except Exception as e:
            print(f"[WARNING] Could not draw watermark: {str(e)}")
            # Continue without watermark if there's an error

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
            print(f"[DEBUG] Attempting to create DM channel for user {ctx.author.id}")
            dm_channel = ctx.author.dm_channel or await ctx.author.create_dm()
            
            print(f"[DEBUG] Sending deposit details to user via DM")
            dm_message = await dm_channel.send(embed=deposit_embed, file=file, view=view)
            print(f"[DEBUG] Successfully sent DM with message ID: {dm_message.id}")
            
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
            print(f"[ERROR] Cannot send DM to user {ctx.author.id} - DMs are disabled")
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":warning: DMs Disabled",
                    description="Please enable DMs to receive deposit instructions.\n\nTo enable DMs:\n1. Right-click on the server name\n2. Select 'Privacy Settings'\n3. Enable 'Direct Messages'",
                    color=0xFFA500
                )
            )
        except Exception as e:
            print(f"[ERROR] Failed to send deposit information via DM: {str(e)}")
            
            # If we can't DM, send it in the channel instead (with warning)
            await loading_message.delete()
            warning_embed = discord.Embed(
                title=":warning: Could Not Send DM",
                description="I couldn't send you a DM with the deposit details. Here they are instead:",
                color=0xFFA500
            )
            await ctx.reply(embed=warning_embed)
            
            # Create a simpler embed without the file attachment for fallback in channel
            fallback_embed = discord.Embed(
                title="💎 Deposit Information",
                description="**Please copy this information carefully:**",
                color=0x2B2D31
            )
            fallback_embed.add_field(
                name="Deposit Amount",
                value=f"Send **{converted_amount:.6f} {currency}**",
                inline=False
            )
            fallback_embed.add_field(
                name="Deposit Address",
                value=f"```{deposit_address}```",
                inline=False
            )
            fallback_embed.add_field(
                name="Tokens to be Received",
                value=f"**{tokens_to_be_received:.2f} tokens**",
                inline=False
            )
            fallback_embed.set_footer(text="BetSync Casino • Secure Transactions")
            
            # Send fallback embed in channel
            await ctx.reply(embed=fallback_embed, view=view)

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