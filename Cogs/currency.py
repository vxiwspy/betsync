import discord
import requests
import qrcode
import io
import asyncio
from discord.ext import commands
from Cogs.utils.mongo import Users

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

    def get_conversion_rate(self, currency, amount):
        url = f"https://api.simpleswap.io/v1/get_estimated?api_key={self.api_key}&currency_from={self.target_currency}&currency_to={currency}&amount={amount}&fixed=false"
        response = requests.get(url)

        try:
            data = response.json()
            if isinstance(data, (float, int, str)):
                return float(data)
            else:
                print(f"Error: Unexpected API response format: {data}")
                return None
        except requests.exceptions.JSONDecodeError:
            print(f"Error: API returned non-JSON response: {response.text}")
            return None

    def get_deposit_address(self, currency, amount):
        """Generates a SimpleSwap transaction and returns the deposit address."""

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
# Debug: Print response

        try:
            data = response.json()
            if "address_from" in data:
                return data
            else:
                print(f"[ERROR] Failed to fetch deposit address: {data}")
                return None
        except requests.exceptions.JSONDecodeError:
            print(f"[ERROR] Non-JSON API response: {response.text}")
            return None




    @commands.command(aliases=["depo"])
    async def dep(self, ctx, currency: str = None, amount: float = None):
        if not currency or not amount:
            embed = discord.Embed(title=":bulb: How to Use `!dep`",
                                  description="**Usage:** `!dep <currency> <amount in USD>`\n**Example:** `!dep BTC 50`",
                                  color=0xFFD700)
            embed.add_field(name=":pushpin: Supported Currencies", value="BTC, LTC, SOL, ETH, USDT (ERC20)")
            return await ctx.reply(embed=embed)

        currency = currency.upper()
        if currency not in self.supported_currencies:
            return await ctx.reply(embed=discord.Embed(title=":x: Invalid Currency",
                                                       description=f"`{currency}` is not supported. Use BTC, LTC, SOL, ETH, USDT.",
                                                       color=0xFF0000))

        converted_amount = self.get_conversion_rate(self.supported_currencies[currency], amount)
        if converted_amount is None:
            return await ctx.reply(embed=discord.Embed(title=":x: Conversion Error",
                                                       description="Failed to fetch conversion rate. Try again later.",
                                                       color=0xFF0000))

        deposit_data = self.get_deposit_address(self.supported_currencies[currency], amount)

        if not deposit_data:
            return await ctx.reply(embed=discord.Embed(
                title=":x: Deposit Error",
                description="Failed to fetch deposit address. Try again later.",
                color=0xFF0000
            ))

        # Extract the deposit address from the API response
        deposit_address = deposit_data.get("address_from")

        if not deposit_address:
            return await ctx.reply(embed=discord.Embed(
                title=":x: Deposit Error",
                description="No deposit address received. Contact support.",
                color=0xFF0000
            ))

        # Send deposit address to the user
        await ctx.reply(embed=discord.Embed(
            title=":bank: Deposit Address",
            description=f"Send **{amount} BTC** to the address below:\n```{deposit_address}```",
            color=0x00FF00
        ))

        # Generate QR Code
        qr = qrcode.make(deposit_address)
        img_buf = io.BytesIO()
        qr.save(img_buf, format='PNG')
        img_buf.seek(0)
        file = discord.File(img_buf, filename="qrcode.png")

        # Create embed
        embed = discord.Embed(title=":money_with_wings: Deposit Details",
                              description=f"Send **{converted_amount} {currency}** to the address below.\n\n"
                                          f"⏳ **Expires in 10 minutes**",
                              color=0x00FFAE)
        embed.add_field(name=":bank: Address", value=f"```{deposit_address}```", inline=False)
        embed.set_footer(text="BetSync Casino • Secure Transactions")
        embed.set_image(url="attachment://qrcode.png")

        try:
            await ctx.author.send(embed=embed, file=file)
            await ctx.reply(embed=discord.Embed(title=":white_check_mark: Check Your DMs!",
                                                description="Deposit details have been sent to you.",
                                                color=0x00FF00))
        except discord.Forbidden:
            await ctx.reply(embed=discord.Embed(title=":warning: DMs Disabled",
                                                description="Enable DMs to receive deposit instructions.",
                                                color=0xFFA500))

        # Track deposit expiration
        self.pending_deposits[ctx.author.id] = {
            "address": deposit_address,
            "amount": converted_amount,
            "currency": currency
        }

        await asyncio.sleep(600)  # Wait 10 minutes
        if ctx.author.id in self.pending_deposits:  # If still in pending, it expired
            await ctx.author.send(embed=discord.Embed(title=":x: Payment Expired",
                                                      description="Your deposit request has expired. Please create a new one using `!dep`.",
                                                      color=0xFF0000))
            del self.pending_deposits[ctx.author.id]

    def process_deposit(self, user_id, amount):
        """Updates the user's balance when a deposit is successful."""
        Users().update_balance(user_id, amount, "tokens")

        user = self.bot.get_user(user_id)
        if user:
            embed = discord.Embed(title=":moneybag: Deposit Successful!",
                                  description=f"You have received **{amount} tokens** in your balance.",
                                  color=0x00FF00)
            return user.send(embed=embed)

def setup(bot):
    bot.add_cog(Deposit(bot))
