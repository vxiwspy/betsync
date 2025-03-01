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

    # Leaderboard Pagination View
    class LeaderboardView(discord.ui.View):
        def __init__(self, author_id, all_data, page_size=10, timeout=60):
            super().__init__(timeout=timeout)
            self.author_id = author_id
            self.all_data = all_data
            self.page_size = page_size
            self.current_page = 0
            self.total_pages = max(1, (len(all_data["users"]) + page_size - 1) // page_size)
            self.message = None
            self.scope = all_data.get("scope", "global")
            self.leaderboard_type = all_data.get("type", "stats")
            self.stat_type = all_data.get("stat_type", "wins")

            # Disable buttons if not needed
            self.update_buttons()

        def update_buttons(self):
            # Disable/enable prev/next buttons based on current page
            self.first_page_button.disabled = self.current_page == 0
            self.prev_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= self.total_pages - 1
            self.last_page_button.disabled = self.current_page >= self.total_pages - 1

        @discord.ui.button(label="<<", style=discord.ButtonStyle.gray, custom_id="first_page")
        async def first_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = 0
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label="<", style=discord.ButtonStyle.gray, custom_id="prev_page")
        async def prev_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = max(0, self.current_page - 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">", style=discord.ButtonStyle.gray, custom_id="next_page")
        async def next_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = min(self.total_pages - 1, self.current_page + 1)
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        @discord.ui.button(label=">>", style=discord.ButtonStyle.gray, custom_id="last_page")
        async def last_page_button(self, button, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("This is not your leaderboard!", ephemeral=True)

            self.current_page = self.total_pages - 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_current_page_embed(), view=self)

        def get_current_page_embed(self):
            # Get data for current page
            start_idx = self.current_page * self.page_size
            end_idx = min(start_idx + self.page_size, len(self.all_data["users"]))
            current_page_data = self.all_data["users"][start_idx:end_idx]

            # Create embed based on leaderboard type
            if self.leaderboard_type == "stats":
                return self.create_stats_embed(current_page_data, start_idx)
            elif self.leaderboard_type == "wagered":
                return self.create_wagered_embed(current_page_data, start_idx)

            # Default to stats embed
            return self.create_stats_embed(current_page_data, start_idx)

        def create_stats_embed(self, users_data, start_idx):
            stat_type = self.stat_type
            scope_text = self.scope.capitalize()
            stat_icon = "🏆" if stat_type == "wins" else "❌"

            title_text = "Wins" if stat_type == "wins" else "Losses"
            
            # Find user's position in the full leaderboard
            user_id = self.all_data.get("author_id")
            user_position = None
            for i, user in enumerate(self.all_data["users"]):
                if user["id"] == user_id:
                    user_position = i + 1
                    break
            
            description = f"Top users ranked by total {stat_type}"
            if user_position:
                user_amount = next((user["amount"] for user in self.all_data["users"] if user["id"] == user_id), 0)
                description += f"\n\n**Your Rank: #{user_position}** with **{user_amount:,.0f}** {stat_type}"
            
            embed = discord.Embed(
                title=f"{stat_icon} {scope_text} {title_text} Leaderboard",
                description=description,
                color=0x00FFAE if stat_type == "wins" else 0xFF5500
            )

            for i, user_data in enumerate(users_data):
                # Calculate actual position on leaderboard
                position = start_idx + i + 1

                # Format the amount with commas
                stat_value = f"{user_data['amount']:,.0f}"

                embed.add_field(
                    name=f"#{position}. {user_data['name']}",
                    value=f"{stat_icon} **{stat_value}** {stat_type}",
                    inline=False
                )

            # Add pagination details to footer
            footer_text = f"BetSync Casino • Page {self.current_page + 1} of {self.total_pages}"
            embed.set_footer(text=footer_text, icon_url=self.all_data.get("bot_avatar", ""))
            return embed

        def create_wagered_embed(self, users_data, start_idx):
            scope_text = self.scope.capitalize()
            
            # Find user's position in the full leaderboard
            user_id = self.all_data.get("author_id")
            user_position = None
            for i, user in enumerate(self.all_data["users"]):
                if user["id"] == user_id:
                    user_position = i + 1
                    break
            
            description = f"Top users ranked by total amount wagered"
            if user_position:
                user_amount = next((user["amount"] for user in self.all_data["users"] if user["id"] == user_id), 0)
                description += f"\n\n**Your Rank: #{user_position}** with **{user_amount:,.2f}** wagered"
            
            embed = discord.Embed(
                title=f"🔥 {scope_text} Wagering Leaderboard",
                description=description,
                color=0xFF5500
            )

            for i, user_data in enumerate(users_data):
                # Calculate actual position on leaderboard
                position = start_idx + i + 1

                # Format the amount with commas
                wagered = f"{user_data['amount']:,.2f}"

                embed.add_field(
                    name=f"#{position}. {user_data['name']}",
                    value=f"💸 **{wagered}** wagered",
                    inline=False
                )

            # Add pagination details to footer
            footer_text = f"BetSync Casino • Page {self.current_page + 1} of {self.total_pages}"
            embed.set_footer(text=footer_text, icon_url=self.all_data.get("bot_avatar", ""))
            return embed

        async def on_timeout(self):
            # Disable all buttons when the view times out
            for child in self.children:
                child.disabled = True

            if self.message:
                try:
                    await self.message.edit(view=self)
                except:
                    pass

    @commands.command(aliases=["lb", "top"])
    async def leaderboard(self, ctx, arg1: str = None, arg2: str = None):
        """View the leaderboard for wins, losses, or wagered amount

        Usage: !leaderboard [scope] [type] 
        Examples: 
        - !leaderboard global wins
        - !leaderboard server losses
        - !leaderboard wagered
        - !leaderboard server wagered
        """
        # If no arguments are provided, show usage information
        if arg1 is None and arg2 is None:
            return await self.show_leaderboard_usage(ctx)

        # Default values
        scope = "global"
        leaderboard_type = "stats"
        stat_type = "wins"

        # Parse arguments (flexible order)
        args = [a.lower() for a in [arg1, arg2] if a]

        # Check for scope
        if "global" in args:
            scope = "global"
            args.remove("global")
        elif "server" in args:
            scope = "server"
            args.remove("server")

        # Check for type
        if "wagered" in args:
            leaderboard_type = "wagered"
            args.remove("wagered")

        # Remaining arg should be stat type (if stats type)
        if args and leaderboard_type == "stats":
            if args[0] in ["wins", "losses"]:
                stat_type = args[0]
            else:
                return await self.show_leaderboard_usage(ctx)

        # If in DM and requesting server leaderboard
        if scope == "server" and ctx.guild is None:
            return await ctx.reply("Server leaderboard can only be viewed in a server.")

        # Get the leaderboard data
        if leaderboard_type == "stats":
            if scope == "global":
                await self.show_global_stats_leaderboard(ctx, stat_type)
            else:  # scope == "server"
                await self.show_server_stats_leaderboard(ctx, stat_type)
        else:  # leaderboard_type == "wagered"
            if scope == "global":
                await self.show_global_wagered_leaderboard(ctx)
            else:  # scope == "server"
                await self.show_server_wagered_leaderboard(ctx)

    async def show_leaderboard_usage(self, ctx):
        """Show usage information for leaderboard command"""
        embed = discord.Embed(
            title=":trophy: Leaderboard - Usage",
            description=(
                "View the top users by wins, losses, or wagered amount.\n\n"
                "**Usage:** `!leaderboard [scope] [type]`\n\n"
                "**Examples:**\n"
                "`!leaderboard global wins` - Global wins leaderboard\n"
                "`!leaderboard server losses` - Server losses leaderboard\n"
                "`!leaderboard wagered` - Global wagering leaderboard\n"
                "`!leaderboard server wagered` - Server wagering leaderboard\n\n"
                "**Available Scopes:**\n"
                "`global` - Show leaderboard across all servers\n"
                "`server` - Show leaderboard for the current server\n\n"
                "**Available Types:**\n"
                "`wins` - Show leaderboard by total wins\n"
                "`losses` - Show leaderboard by total losses\n"
                "`wagered` - Show leaderboard by total amount wagered"
            ),
            color=0x00FFAE
        )
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
        return await ctx.reply(embed=embed)

    async def show_global_stats_leaderboard(self, ctx, stat_type):
        """Show global leaderboard for wins or losses with pagination"""
        db = Users()

        # Get all users sorted by the specified stat
        field_name = "total_won" if stat_type == "wins" else "total_lost"
        users = list(db.collection.find().sort([(field_name, -1)]))

        if not users:
            return await ctx.reply("No users found in the leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in users:
            if user_data.get(field_name, 0) > 0: # Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get(field_name, 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "global",
            "type": "stats",
            "stat_type": stat_type,
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_server_stats_leaderboard(self, ctx, stat_type):
        """Show server leaderboard for wins or losses with pagination"""
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

        # Sort the filtered users by the specified stat
        field_name = "total_won" if stat_type == "wins" else "total_lost"
        server_users.sort(key=lambda x: x.get(field_name, 0), reverse=True)

        if not server_users:
            return await ctx.reply("No users found in the server leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in server_users:
            if user_data.get(field_name, 0) > 0: # Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get(field_name, 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "server",
            "type": "stats",
            "stat_type": stat_type,
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_global_wagered_leaderboard(self, ctx):
        """Show global leaderboard for amount wagered with pagination"""
        db = Users()
        # Get all users, we'll sort by total_spent
        users = list(db.collection.find().sort([("total_spent", -1)]))

        if not users:
            return await ctx.reply("No users found in the leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in users:
            if user_data.get("total_spent", 0) > 0: #Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get("total_spent", 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "global",
            "type": "wagered",
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message

    async def show_server_wagered_leaderboard(self, ctx):
        """Show server leaderboard for amount wagered with pagination"""
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

        # Sort the filtered users by total_spent
        server_users.sort(key=lambda x: x.get("total_spent", 0), reverse=True)

        if not server_users:
            return await ctx.reply("No users found in the server leaderboard.")

        # Prepare data for pagination
        formatted_users = []
        for user_data in server_users:
            if user_data.get("total_spent", 0) > 0: #Filter out users with 0 value
                try:
                    user = await self.bot.fetch_user(user_data["discord_id"])
                    user_name = user.name if user else f"User {user_data['discord_id']}"

                    formatted_users.append({
                        "name": user_name,
                        "amount": user_data.get("total_spent", 0),
                        "id": user_data["discord_id"]
                    })
                except Exception as e:
                    print(f"Error getting user: {e}")
                    continue

        # Create the data structure for the paginated view
        leaderboard_data = {
            "users": formatted_users,
            "scope": "server",
            "type": "wagered",
            "bot_avatar": self.bot.user.avatar.url,
            "author_id": ctx.author.id
        }

        # Create and send the paginated view
        view = self.LeaderboardView(ctx.author.id, leaderboard_data)
        message = await ctx.reply(embed=view.get_current_page_embed(), view=view)
        view.message = message


def setup(bot):
    bot.add_cog(Fetches(bot))