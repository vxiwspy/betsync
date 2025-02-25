import discord
import requests
import qrcode
import io
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.supported_currencies = {"BTC": "bitcoin", "LTC": "litecoin", "SOL": "solana", "ETH": "ethereum", "USDT": "tether"}
        self.target_currency = "usdcalgo"
        self.api_key = "d676247c-fbc2-4490-9fbf-e0e60a4e2066" #good job gng thanks <3

    def get_minimum_deposit(self, currency):
        url = f"https://api.simpleswap.io/v1/get_ranges?api_key={self.api_key}&currency_from={currency}&currency_to={self.target_currency}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("min", None)
        return None

    @commands.command(aliases=["depo"])
    async def dep(self, ctx, currency: str = None, amount: float = None):
        if not currency or not amount:
            embed = discord.Embed(title=":bulb: How to Use `!dep`", description="**Usage:** `!dep <currency> <amount in USD>`\n**Example:** `!dep BTC 50`", color=0xFFD700)
            embed.add_field(name=":pushpin: Supported Currencies", value="BTC, LTC, SOL, ETH, USDT (ERC20)")
            return await ctx.reply(embed=embed)

        currency = currency.upper()
        if currency not in self.supported_currencies:
            return await ctx.reply(embed=discord.Embed(title=":x: Invalid Currency", description=f"`{currency}` is not supported. Use BTC, LTC, SOL, ETH, USDT.", color=0xFF0000))

        min_deposit = self.get_minimum_deposit(self.supported_currencies[currency])
        if not min_deposit:
            return await ctx.reply(embed=discord.Embed(title=":x: API Error", description="Could not retrieve minimum deposit amount. Try again later.", color=0xFF0000))

        if amount < min_deposit:
            return await ctx.reply(embed=discord.Embed(title=":warning: Amount Too Low", description=f"Minimum deposit for {currency} is **{min_deposit} USD**.", color=0xFFA500))

        user = Users().fetch_user(ctx.author.id)
        if not user:
            return await ctx.reply(embed=discord.Embed(title=":x: Not Registered", description="Use `!signup` to register first!", color=0xFF0000))

        deposit_address = "GENERATED_CRYPTO_ADDRESS"
        qr = qrcode.make(deposit_address)
        img_buf = io.BytesIO()
        qr.save(img_buf, format='PNG')
        img_buf.seek(0)

        embed = discord.Embed(title=":money_with_wings: Deposit Details", description=f"Send **{amount} {currency}** to the address below.", color=0x00FFAE)
        embed.add_field(name=":bank: Address", value=f"```{deposit_address}```", inline=False)
        embed.set_footer(text="BetSync Casino • Secure Transactions")

        try:
            await ctx.author.send(embed=embed, file=discord.File(img_buf, filename="qrcode.png"))
            await ctx.reply(embed=discord.Embed(title=":white_check_mark: Check Your DMs!", description="Deposit details have been sent to you.", color=0x00FF00))
        except discord.Forbidden:
            await ctx.reply(embed=discord.Embed(title=":warning: DMs Disabled", description="Enable DMs to receive deposit instructions.", color=0xFFA500))

    def process_deposit(self, user_id, amount):
        Users().update_balance(user_id, amount, "tokens")

        user = self.bot.get_user(user_id)
        if user:
            embed = discord.Embed(title=":moneybag: Deposit Successful!", description=f"You have received **{amount} tokens** in your balance.", color=0x00FF00)
            return user.send(embed=embed)

def setup(bot):
    bot.add_cog(Currency(bot))
