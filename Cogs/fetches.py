
import os
import requests
import discord
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users, Servers
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
            return await ctx.message.reply(embed=embed)

        currency = currency.upper()
        prices = self.get_crypto_prices()
        
        if not prices:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | API Error",
                description="Could not retrieve live crypto prices. Please try again later.",
                color=0xFF0000
            )
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

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
                title="<:no:1344252518305234987> | Invalid Currency",
                description=f"`{currency}` is not supported.\n\n"
                          ":pushpin: **Supported Currencies:**\n"
                          "`BTC, ETH, LTC, SOL, DOGE, USDT`",
                color=0xFF0000
            )
            embed.set_thumbnail(url=bot_icon)
            embed.set_footer(text="BetSync Casino", icon_url=bot_icon)
            return await ctx.message.reply(embed=embed)

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

        await ctx.message.reply(embed=embed)

    @commands.command()
    async def stats(self, ctx, user: discord.Member = None):
        user = ctx.author
        user_id = user.id
        db = Users()
        info = db.fetch_user(user_id)
        if info == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Registered", description="wait for autoregister to take place then use this command again", color=0xFF0000)
            embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar)
            return await ctx.message.reply(embed=embed)
        else:
            deposits = info["total_deposit_amount"]
            withdrawals = info["total_withdraw_amount"]
            games_played = info["total_played"]
            profit = info["total_earned"]
            games_won = info["total_won"]
            games_lost = info["total_lost"]
            spent = info["total_spent"]
            
            
            
            
        moneybag = emoji()["money"]
        statsemoji = emoji()["stats"]
        # Create embed
        embed = discord.Embed(title=f":star: | Stats for {user.name}", color=discord.Color.blue())
        embed.add_field(name=f"{moneybag} **Deposits:**", value=f"```{deposits} Tokens```", inline=False)
        embed.add_field(name=":outbox_tray: **Withdrawals:**", value=f"```{withdrawals} Credits```", inline=False)
        #embed.add_field(
            #name=":gift: Tips:",
            #value=f"Sent: **{tokens_tipped}** tokens, **{credits_tipped}** credits\n Received: **{tokens_received}** tokens, **{credits_received}** credits",
        #inline=False
    #)
        embed.add_field(name=":money_bag: Wagered", value=f"```{spent} Tokens```")
        embed.add_field(name=":money_with_wings: Won", value=f"```{profit} Credits```")
        #embed.add_field(
            #name=f"{statsemoji} Games:",
            #value=f":video_game: **Played: {games_played} games**\n:trophy: **Games Won: {games_won} games**\n",
            #inline=False
        #)
        #embed.add_field(name=":medal: Badges:", value=badge_text, inline=False)
        embed.set_footer(text="BetSync User Stats", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url)


        await ctx.reply(embed=embed)

    @commands.command(aliases=["bal"])
    async def balance(self, ctx, user:discord.Member = None):
        if user is None:
            user = ctx.author
        else:
            db = Users()
            if db.fetch_user(user.id) == False: 
                await ctx.reply("**User Does Not Have An Account.**")
                return
            else:
                pass
            pass
            
        token_value = 0.0212
        db = Users()
        info = db.fetch_user(user.id)
        tokens = info["tokens"]
        credits = info["credits"]
        money = emoji()["money"]
        embed = discord.Embed(title=f"{money} | {user.name}\'s Balance", color=discord.Color.blue(), thumbnail=user.avatar.url)
        embed.add_field(name=":moneybag: Tokens", value=f"```{round(tokens, 2)} Tokens (~${round((tokens * token_value),2)})```")
        embed.add_field(name=":money_with_wings: Credits", value=f"```{round(credits, 2)} Credits (~${round((credits * token_value), 2)})```")
        embed.set_footer(text="Betsync Casino", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)
    
    @commands.command(aliases=["lb", "top"])
    async def leaderboard(self, ctx, scope: str = None, currency_type: str = None):
        """View the leaderboard for tokens or credits
        
        Usage: !leaderboard [global/server] [tokens/credits]
        Default: !leaderboard global credits
        """
        # Set default values if not provided
        if scope is None or scope.lower() not in ["global", "server"]:
            if currency_type is None:
                # If neither argument is provided, use defaults
                scope = "global"
                currency_type = "credits"
            else:
                # If only one argument is provided, check if it's a currency type
                if currency_type.lower() in ["tokens", "credits"]:
                    scope = "global"
                else:
                    # If it's not a valid currency, it might be the scope
                    if scope.lower() in ["global", "server"]:
                        currency_type = "credits"
                    else:
                        # Show usage if arguments are invalid
                        return await self.show_leaderboard_usage(ctx)
        
        if currency_type is None or currency_type.lower() not in ["tokens", "credits"]:
            currency_type = "credits"
        
        # Normalize arguments
        scope = scope.lower()
        currency_type = currency_type.lower()
        
        # Get the leaderboard data
        if scope == "global":
            await self.show_global_leaderboard(ctx, currency_type)
        else:  # scope == "server"
            if ctx.guild is None:
                return await ctx.reply("Server leaderboard can only be viewed in a server.")
            await self.show_server_leaderboard(ctx, currency_type)
    
    async def show_leaderboard_usage(self, ctx):
        """Show usage information for leaderboard command"""
        embed = discord.Embed(
            title=":trophy: Leaderboard - Usage",
            description=(
                "View the top users by tokens or credits.\n\n"
                "**Usage:** `!leaderboard [scope] [currency]`\n"
                "**Example:** `!leaderboard global credits`\n\n"
                "**Available Scopes:**\n"
                "`global` - Show leaderboard across all servers\n"
                "`server` - Show leaderboard for the current server\n\n"
                "**Available Currencies:**\n"
                "`tokens` - Show leaderboard by token balance\n"
                "`credits` - Show leaderboard by credit balance"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        return await ctx.reply(embed=embed)
    
    async def show_global_leaderboard(self, ctx, currency_type):
        """Show global leaderboard for tokens or credits"""
        db = Users()
        # Get top 10 users sorted by the specified currency
        users = list(db.collection.find().sort([(currency_type, -1)]).limit(10))
        
        if not users:
            return await ctx.reply("No users found in the leaderboard.")
        
        # Create embed
        currency_symbol = ":moneybag:" if currency_type == "tokens" else ":money_with_wings:"
        embed = discord.Embed(
            title=f":trophy: Global {currency_type.capitalize()} Leaderboard",
            description=f"Top users ranked by {currency_type} balance",
            color=0x00FFAE
        )
        
        # Add leaderboard entries
        for i, user_data in enumerate(users):
            try:
                user = await self.bot.fetch_user(user_data["discord_id"])
                user_name = user.name if user else f"User {user_data['discord_id']}"
                
                # Add medal emoji for top 3
                if i == 0:
                    medal = ":first_place:"
                elif i == 1:
                    medal = ":second_place:"
                elif i == 2:
                    medal = ":third_place:"
                else:
                    medal = f"`{i+1}.`"
                
                # Format the amount with commas
                balance = f"{user_data[currency_type]:,.2f}"
                
                embed.add_field(
                    name=f"{medal} {user_name}",
                    value=f"{currency_symbol} **{balance}** {currency_type}",
                    inline=False
                )
            except Exception as e:
                print(f"Error getting user: {e}")
                continue
        
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)
    
    async def show_server_leaderboard(self, ctx, currency_type):
        """Show server leaderboard for tokens or credits"""
        db = Users()
        server_users = []
        
        # First get all users in the database
        all_users = list(db.collection.find())
        
        # Get all members in the server
        server_members = ctx.guild.members
        server_member_ids = [member.id for member in server_members]
        
        # Filter users who are in this server
        for user_data in all_users:
            if user_data["discord_id"] in server_member_ids:
                server_users.append(user_data)
        
        # Sort the filtered users by the specified currency
        server_users.sort(key=lambda x: x[currency_type], reverse=True)
        
        # Take top 10
        server_users = server_users[:10]
        
        if not server_users:
            return await ctx.reply("No users found in the server leaderboard.")
        
        # Create embed
        currency_symbol = ":moneybag:" if currency_type == "tokens" else ":money_with_wings:"
        embed = discord.Embed(
            title=f":trophy: {ctx.guild.name} {currency_type.capitalize()} Leaderboard",
            description=f"Top users in this server ranked by {currency_type} balance",
            color=0x00FFAE
        )
        
        # Add leaderboard entries
        for i, user_data in enumerate(server_users):
            try:
                user = await self.bot.fetch_user(user_data["discord_id"])
                user_name = user.name if user else f"User {user_data['discord_id']}"
                
                # Add medal emoji for top 3
                if i == 0:
                    medal = ":first_place:"
                elif i == 1:
                    medal = ":second_place:"
                elif i == 2:
                    medal = ":third_place:"
                else:
                    medal = f"`{i+1}.`"
                
                # Format the amount with commas
                balance = f"{user_data[currency_type]:,.2f}"
                
                embed.add_field(
                    name=f"{medal} {user_name}",
                    value=f"{currency_symbol} **{balance}** {currency_type}",
                    inline=False
                )
            except Exception as e:
                print(f"Error getting user: {e}")
                continue
        
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Fetches(bot))
