import discord
import requests
import qrcode
import io
import asyncio
import time
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
from colorama import Fore

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
        # Remove pending deposit if it exists
        if self.user_id in self.cog.pending_deposits:
            del self.cog.pending_deposits[self.user_id]
        # Disable all buttons in the view
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        cancel_embed = discord.Embed(
            title="❌ DEPOSIT CANCELLED",
            description="Your deposit has been cancelled as per your request.\n\nIf you'd like to try again, use `!dep`.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=cancel_embed, ephemeral=True)

    @discord.ui.button(label="Copy", style=discord.ButtonStyle.secondary)
    async def copy_button(self, button: discord.ui.Button, interaction: discord.Interaction):
            # Ensure only the deposit owner can use the copy button
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                    "You cannot copy someone else's deposit details.", ephemeral=True
                )
            # Send plain text messages (not embeds) so mobile users can easily copy the info.
        await interaction.response.send_message(f"Deposit Address: {self.deposit_address}", ephemeral=True)
        #await interaction.followup.send_message(f"Deposit Amount: {self.deposit_amount:.6f}", ephemeral=True)
        # Send two ephemeral messages: one for the deposit address and one for the deposit amount.
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
            else:
                print(f"[ERROR] Unexpected conversion response: {data}")
                return None
        except requests.exceptions.JSONDecodeError:
            print(f"[ERROR] Non-JSON response: {response.text}")
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


    @commands.command(aliases=["depo"])
    async def dep(self, ctx, currency: str = None, amount: float = None):
        """
        Deposit command: !dep <currency> <amount in USD>
        Example: !dep BTC 50
        """
        # Prevent duplicate deposits
        if ctx.author.id in self.pending_deposits:
            embed = discord.Embed(
                title="❌ Pending Deposit",
                description="You already have a pending deposit. Please wait for it to expire or cancel it before starting a new one.",
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
            return await ctx.reply(embed=usage_embed)

        currency = currency.upper()
        if currency not in self.supported_currencies:
            return await ctx.reply(
                embed=discord.Embed(
                    title=":x: Invalid Currency",
                    description=f"`{currency}` is not supported. Use BTC, LTC, SOL, ETH, USDT.",
                    color=0xFF0000
                )
            )

        # Check minimum deposit requirement
        min_deposit = self.get_minimum_deposit(self.supported_currencies[currency])
        if min_deposit is None:
            return await ctx.reply(
                embed=discord.Embed(
                    title=":x: Minimum Check Error",
                    description="Could not fetch minimum deposit amount. Please try again later.",
                    color=discord.Color.red()
                )
            )
        elif amount < min_deposit:
            min_deposit_info = "\n".join([
                f"**{cur}**: {self.get_minimum_deposit(self.supported_currencies[cur]):.2f} USD" 
                for cur in self.supported_currencies
            ])

            min_embed = discord.Embed(
                title=":warning: Amount Too Low",
                description=(
                    f"The minimum deposit for **{currency}** is **{min_deposit:.2f} USD**.\n"
                    "Please increase your deposit amount and try again.\n\n"
                    "**Minimum Deposit Requirements:**\n" + min_deposit_info
                ),
                color=discord.Color.orange()
            )

            return await ctx.reply(embed=min_embed)  


        # Send loading embed in channel
        loading_embed = discord.Embed(
            title="Generating Deposit...",
            description="Please wait while we fetch your deposit details.",
            color=discord.Color.gold()
        )
        loading_message = await ctx.reply(embed=loading_embed)

        # Get conversion rate from USD -> Crypto
        converted_amount = self.get_conversion_rate(self.supported_currencies[currency], amount)
        if converted_amount is None:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":x: Conversion Error",
                    description="Failed to fetch conversion rate. Try again later.",
                    color=0xFF0000
                )
            )

        # Create exchange and get deposit info
        deposit_data = self.get_deposit_data(self.supported_currencies[currency], amount)
        if not deposit_data:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":x: Deposit Error",
                    description="Failed to fetch deposit address. Try again later.",
                    color=0xFF0000
                )
            )
        deposit_address = deposit_data.get("address_from")
        if not deposit_address:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":x: Deposit Error",
                    description="No deposit address received. Contact support.",
                    color=0xFF0000
                )
            )

        # Generate QR Code for the deposit address
        qr = qrcode.make(deposit_address)
        img_buf = io.BytesIO()
        qr.save(img_buf, format='PNG')
        img_buf.seek(0)
        image = Image.open(img_buf)
        #image = image.resize((1024, 1024))
        font = ImageFont.truetype("roboto.ttf", 22)
        font2 = ImageFont.truetype(font="roboto.ttf", size=18)
        draw = ImageDraw.Draw(image)
        draw.text((256, 12), "BetSync", font=font)
        draw.text((90, 335), f"{ctx.author.name}\'s wallet address", font=font)
        with io.BytesIO() as image_binary:
            image.save(image_binary, 'PNG')
            image_binary.seek(0)
            file = discord.File(image_binary, filename="qrcode.png")

        # Build the deposit embed to be sent via DM
        expiration_timestamp = int(time.time() + self.deposit_timeout)
        deposit_embed = discord.Embed(
            title=":moneybag: DEPOSIT",
            description=(
                f"**Send {converted_amount:.6f} {currency}** to the address below:\n"
                f"```{deposit_address}```"
            ),
            color=0x00FF00
        )
        deposit_embed.add_field(
            name="Expires",
            value=f"<t:{expiration_timestamp}:R>",
            inline=False
        )
        deposit_embed.add_field(
            name="Instructions",
            value="Please wait 2-3 minutes after sending. Your balance will update automatically.",
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
            success_embed = discord.Embed(
                title=":white_check_mark: Deposit Details Sent!",
                description="Check your DMs for the deposit details.",
                color=discord.Color.green()
            )
            await ctx.reply(embed=success_embed, delete_after=10)
        except discord.Forbidden:
            await loading_message.delete()
            return await ctx.reply(
                embed=discord.Embed(
                    title=":warning: DMs Disabled",
                    description="Please enable DMs to receive deposit instructions.",
                    color=0xFFA500
                )
            )

        # Mark the deposit as pending
        #await self.loading_msg.delete()
        self.pending_deposits[ctx.author.id] = {
            "address": deposit_address,
            "amount": converted_amount,
            "currency": currency
        }

        # Wait for the deposit timeout; if still pending, auto-cancel
        await asyncio.sleep(self.deposit_timeout)
        if ctx.author.id in self.pending_deposits:
            cancel_embed = discord.Embed(
                title="❌ DEPOSIT CANCELLED",
                description=(
                    "The deposit timer has expired and no transaction was detected.\n"
                    "If you'd like to try again, use `!dep <currency> <amount>`."
                ),
                color=discord.Color.red()
            )
            try:
                await ctx.author.send(embed=cancel_embed)
            except discord.Forbidden:
                pass
            del self.pending_deposits[ctx.author.id]

    def process_deposit(self, user_id, amount):
        """Updates the user's balance when a deposit is successful."""
        Users().update_balance(user_id, amount, "tokens")
        user = self.bot.get_user(user_id)
        if user:
            embed = discord.Embed(
                title=":moneybag: Deposit Successful!",
                description=f"You have received **{amount} tokens** in your balance.",
                color=0x00FF00
            )
            return user.send(embed=embed)

    @dep.before_invoke
    async def before(self, ctx):
        loading_emoji = emoji()["loading"]
        #self.loading_msg = await ctx.reply(embed=discord.Embed(title=f"{loading_emoji} Running Your Command", description="`Please be paitient while we validate your credentials...`", color=discord.Color.green()))
        db = Users()
        if db.fetch_user(ctx.author.id) != False:
        #await loading_msg.delete()
            pass
        else:
            print(f"{Fore.YELLOW}[~] {Fore.WHITE}New User Detected... {Fore.BLACK}{ctx.author.id}{Fore.WHITE} {Fore.YELLOW}")
            dump = {"discord_id": ctx.author.id, "tokens": 0, "credits": 0, "history": [], "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost':0}
            db.register_new_user(dump)

def setup(bot):
    bot.add_cog(Deposit(bot))
