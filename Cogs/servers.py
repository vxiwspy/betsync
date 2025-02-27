
import discord
import os
import time
from discord.ext import commands
from Cogs.utils.mongo import Servers, Users
from Cogs.utils.emojis import emoji

class ServerBetHistoryView(discord.ui.View):
    def __init__(self, bot, server_data, author_id, category="all", page=0):
        super().__init__(timeout=120)
        self.bot = bot
        self.server_data = server_data
        self.server_bet_history = server_data.get("server_bet_history", [])
        self.author_id = author_id
        self.category = category
        self.page = page
        self.per_page = 10
        self.max_pages = 0
        self.message = None

        # Calculate the initial max pages
        self._calculate_max_pages()

        # Add the buttons to the view
        self._update_buttons()

    def _calculate_max_pages(self):
        """Calculate the maximum number of pages for the current category"""
        filtered = self._get_filtered_history(full=True)
        self.max_pages = max(1, (len(filtered) + self.per_page - 1) // self.per_page)

    def _update_buttons(self):
        """Update all buttons in the view based on current state"""
        self.clear_items()

        # Add category buttons
        self.add_item(discord.ui.Button(label="All", style=discord.ButtonStyle.primary if self.category == "all" else discord.ButtonStyle.secondary, custom_id="all"))
        self.add_item(discord.ui.Button(label="Wins", style=discord.ButtonStyle.primary if self.category == "win" else discord.ButtonStyle.secondary, custom_id="win"))
        self.add_item(discord.ui.Button(label="Losses", style=discord.ButtonStyle.primary if self.category == "loss" else discord.ButtonStyle.secondary, custom_id="loss"))

        # Add pagination buttons
        self.add_item(discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=self.page == 0))
        self.add_item(discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next", disabled=self.page >= self.max_pages - 1))

    def _get_filtered_history(self, full=False):
        """Get filtered history based on the selected category

        Args:
            full: If True, return all items in category, otherwise return just current page items
        """
        if self.category == "all":
            filtered = self.server_bet_history
        else:
            filtered = [item for item in self.server_bet_history if item.get("type") == self.category]

        # Sort by timestamp (most recent first)
        filtered.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        # Limit to items per page if not requesting full list
        if not full:
            # Get items for current page
            start_idx = self.page * self.per_page
            end_idx = min(start_idx + self.per_page, len(filtered))
            return filtered[start_idx:end_idx]

        return filtered

    def create_embed(self):
        """Create the server bet history embed with the filtered data"""
        filtered_data = self._get_filtered_history()
        server_name = self.server_data.get("server_name", "Unknown Server")

        # Prepare embed
        embed = discord.Embed(
            title=f":chart_with_upwards_trend: Server Bet History | {self.category.capitalize()}",
            description=f"Showing bet history for **{server_name}**.",
            color=0x00FFAE
        )

        if not filtered_data:
            embed.add_field(name="No History", value="No bets found for this category.", inline=False)
        else:
            for item in filtered_data:
                timestamp = item.get("timestamp", "Unknown")
                if isinstance(timestamp, (int, float)):
                    # Convert timestamp to readable date
                    date_str = f"<t:{int(timestamp)}:R>"
                else:
                    date_str = timestamp

                user_id = item.get("user_id", "Unknown")
                user_name = item.get("user_name", "Unknown User")
                
                # Format field name and value based on transaction type
                if item.get("type") == "win":
                    field_name = f"🏆 Win • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Bet: **{item.get('bet', 0):,.2f}**\n"
                    field_value += f"Won: **{item.get('amount', 0):,.2f} credits**\n"
                    field_value += f"Multiplier: **{item.get('multiplier', 1.0):,.2f}x**"
                elif item.get("type") == "loss":
                    field_name = f"❌ Loss • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Lost: **{item.get('amount', 0):,.2f}**\n"
                    if "multiplier" in item:
                        field_value += f"Multiplier: **{item.get('multiplier', 1.0):,.2f}x**"
                else:
                    field_name = f"🎮 Game • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"User: **{user_name}** (<@{user_id}>)\n"
                    field_value += f"Amount: **{item.get('amount', 0):,.2f}**"

                embed.add_field(name=field_name, value=field_value, inline=False)

        # Add page info
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • BetSync Casino", icon_url=self.bot.user.avatar.url)

        return embed

    async def interaction_check(self, interaction):
        """Check if the person clicking is the same as the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your command. You can use `!serverbets` to view the server history.", ephemeral=True)
            return False

        # Handle the button click
        await self.button_callback(interaction)
        return False  # Return False to prevent the default handling

    async def button_callback(self, interaction):
        """Handle button interactions"""
        custom_id = interaction.data.get("custom_id")

        if custom_id == "all":
            self.category = "all"
            self.page = 0
        elif custom_id == "win":
            self.category = "win"
            self.page = 0
        elif custom_id == "loss":
            self.category = "loss"
            self.page = 0
        elif custom_id == "prev":
            if self.page > 0:
                self.page -= 1
        elif custom_id == "next":
            if self.page < self.max_pages - 1:
                self.page += 1

        # Recalculate max pages
        self._calculate_max_pages()

        # Update buttons
        self._update_buttons()

        # Update the message
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for child in self.children:
            child.disabled = True

        # Try to update the message with disabled buttons
        try:
            await self.message.edit(view=self)
        except:
            pass


class ServersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["ss"])
    async def serverstats(self, ctx):
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        total_profit = server_data["total_profit"]
        server_admins = server_data["server_admins"]
        giveaway_channel = server_data["giveaway_channel"]

        #if count(server_admins) == 0: server_admins = None

        #if giveaway_channel == None: giveaway_channel = "Not Set"

        embed = discord.Embed(title=f":stars: Server Stats for {ctx.guild.name}", color=0x00FFAE)
        money = emoji()["money"]
        embed.add_field(name=f"{money} Total Profit", value=f"```{round(total_profit, 2)} Tokens (~{round((total_profit * 0.0212), 2)} $)```")
        embed.add_field(name=f"{money} Server's Cut Of The Profits", value=f"```{round((total_profit * (32/100)), 2)} Tokens (~{round((total_profit * 0.0212) * (25/100), 2)} $)```")
        embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)

        await ctx.reply(embed=embed)
        
    @commands.command(aliases=["serverbets", "serverhistory", "sbets"])
    async def serverbethistory(self, ctx):
        """View server's bet history with filtering by category and pagination"""
        # Send loading embed first
        loading_emoji = emoji()["loading"]
        loading_embed = discord.Embed(
            title=f"{loading_emoji} | Loading Server Bet History...",
            description="Please wait while we fetch the server's bet history.",
            color=0x00FFAE
        )
        loading_message = await ctx.reply(embed=loading_embed)
        
        # Get server data
        db = Servers()
        server_data = db.fetch_server(ctx.guild.id)

        if server_data == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | Server Not Found",
                description="This server isn't registered in our database. Please contact an administrator.",
                color=0xFF0000
            )
            await loading_message.delete()
            return await ctx.reply(embed=embed)

        # Create view with buttons
        view = ServerBetHistoryView(self.bot, server_data, ctx.author.id)

        # Send initial embed
        embed = view.create_embed()
        
        # Delete the loading message
        await loading_message.delete()
        
        message = await ctx.reply(embed=embed, view=view)

        # Store the message for later reference in the view
        view.message = message


def setup(bot):
    bot.add_cog(ServersCog(bot))
