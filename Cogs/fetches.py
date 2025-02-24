
import os
import requests
import discord
from discord.ext import commands
from colorama import Fore

class Fetches(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.command(name="rate")
    async def rate(self, ctx, amount: float = None, currency: str = None):
        bot_icon = self.bot.user.avatar.url

        if amount is None or currency is None:
            embed = discord.Embed(
                title=":bulb: How to Use `!rate`",
                description="Convert tokens/credits to cryptocurrency at real-time rates.\n\n"
                          "**Usage:** `!rate <amount> <currency>`\n"
                          "**Example:** `!rate 100 BTC`\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFFD700
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)
            return await ctx.send(embed=embed)

        currency = currency.upper()
        prices = self.get_crypto_prices()
        
        if not prices:
            embed = discord.Embed(
                title=":x: API Error",
                description="Could not retrieve live crypto prices. Please try again later.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.send(embed=embed)

        conversion_rates = {
            "BTC": prices.get("bitcoin", {}).get("usd"),
            "ETH": prices.get("ethereum", {}).get("usd"),
            "LTC": prices.get("litecoin", {}).get("usd"),
            "SOL": prices.get("solana", {}).get("usd"),
            "DOGE": prices.get("dogecoin", {}).get("usd"),
            "USDT": prices.get("tether", {}).get("usd")
        }

        if currency not in conversion_rates:
            embed = discord.Embed(
                title=":x: Invalid Currency",
                description=f"`{currency}` is not supported.\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFF0000
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.send(embed=embed)

        usd_value = amount * 0.013
        converted_amount = usd_value / conversion_rates[currency]

        embed = discord.Embed(
            title=":currency_exchange: Live Currency Conversion",
            color=0x00FFAE,
            description="ㅤㅤㅤ"
        )

        embed.add_field(
            name=":moneybag: Equivalent USD Value",
            value=f"**${usd_value:,.2f}**",
            inline=False
        )

        embed.add_field(
            name=f":arrows_counterclockwise: {amount:,.2f} Tokens/Credits in {currency}",
            value=f"```ini\n[{converted_amount:.8f} {currency}]\n```",
            inline=False
        )

        embed.set_thumbnail(url=bot_icon)
        embed.set_footer(text="BetSync Casino • Live Exchange Rates", icon_url=bot_icon)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Fetches(bot))
