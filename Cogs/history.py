
import discord
from discord.ext import commands
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji
import datetime

class HistoryView(discord.ui.View):
    def __init__(self, bot, user, history_data, author_id, category="all", page=0):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.history_data = history_data
        self.author_id = author_id
        self.category = category
        self.page = page
        self.per_page = 10
        self.max_pages = 0
        
        # Add the category buttons
        self.add_category_buttons()
        # Add pagination buttons
        self.add_pagination_buttons()
    
    def add_category_buttons(self):
        # Add category selection buttons
        self.add_item(discord.ui.Button(label="All", style=discord.ButtonStyle.primary if self.category == "all" else discord.ButtonStyle.secondary, custom_id="all"))
        self.add_item(discord.ui.Button(label="Deposits", style=discord.ButtonStyle.primary if self.category == "deposit" else discord.ButtonStyle.secondary, custom_id="deposit"))
        self.add_item(discord.ui.Button(label="Withdrawals", style=discord.ButtonStyle.primary if self.category == "withdraw" else discord.ButtonStyle.secondary, custom_id="withdraw"))
        self.add_item(discord.ui.Button(label="Wins", style=discord.ButtonStyle.primary if self.category == "win" else discord.ButtonStyle.secondary, custom_id="win"))
        self.add_item(discord.ui.Button(label="Losses", style=discord.ButtonStyle.primary if self.category == "loss" else discord.ButtonStyle.secondary, custom_id="loss"))
    
    def add_pagination_buttons(self):
        # Add previous and next buttons for pagination
        self.add_item(discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev", disabled=self.page == 0))
        self.add_item(discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next", disabled=self.page >= self.max_pages - 1))
    
    def filter_history(self):
        """Filter history based on the selected category"""
        filtered = []
        if self.category == "all":
            filtered = self.history_data[:20]  # Get recent 20 items
        else:
            # Filter by type and get at most 20 recent items
            filtered = [item for item in self.history_data if item.get("type") == self.category][:20]
        
        # Calculate max pages
        self.max_pages = max(1, (len(filtered) + self.per_page - 1) // self.per_page)
        
        # Get items for current page
        start_idx = self.page * self.per_page
        end_idx = min(start_idx + self.per_page, len(filtered))
        
        return filtered[start_idx:end_idx]
    
    def create_embed(self):
        """Create the history embed with the filtered data"""
        filtered_data = self.filter_history()
        
        # Prepare embed
        embed = discord.Embed(
            title=f":scroll: Transaction History | {self.category.capitalize()}",
            description=f"Showing {self.user.name}'s transaction history.",
            color=0x00FFAE
        )
        
        if not filtered_data:
            embed.add_field(name="No History", value="No transactions found for this category.", inline=False)
        else:
            for item in filtered_data:
                timestamp = item.get("timestamp", "Unknown")
                if isinstance(timestamp, (int, float)):
                    # Convert timestamp to readable date
                    date_str = f"<t:{int(timestamp)}:R>"
                else:
                    date_str = timestamp
                
                # Format field name and value based on transaction type
                if item.get("type") == "deposit":
                    field_name = f"🔼 Deposit • {date_str}"
                    field_value = f"Received **{item.get('amount', 0):,.2f} tokens**"
                elif item.get("type") == "withdraw":
                    field_name = f"🔽 Withdrawal • {date_str}"
                    field_value = f"Sent **{item.get('amount', 0):,.2f} credits**"
                elif item.get("type") == "win":
                    field_name = f"🏆 Win • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"Won **{item.get('amount', 0):,.2f} credits**"
                elif item.get("type") == "loss":
                    field_name = f"❌ Loss • {item.get('game', 'Game')} • {date_str}"
                    field_value = f"Lost **{item.get('amount', 0):,.2f} tokens**"
                else:
                    field_name = f"🔄 Transaction • {date_str}"
                    field_value = f"Amount: **{item.get('amount', 0):,.2f}**"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
        
        # Add page info
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • BetSync Casino", icon_url=self.bot.user.avatar.url)
        embed.set_thumbnail(url=self.user.avatar.url)
        
        return embed
    
    async def interaction_check(self, interaction):
        """Check if the person clicking is the same as the command author"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your command. Type `!history` to view your own history.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for child in self.children:
            child.disabled = True
        
        # Try to update the message with disabled buttons
        try:
            message = self.message
            await message.edit(view=self)
        except:
            pass
    
    @discord.ui.button(label="", style=discord.ButtonStyle.primary, custom_id="all")
    async def all_button_callback(self, button, interaction):
        self.category = "all"
        self.page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.primary, custom_id="deposit")
    async def deposit_button_callback(self, button, interaction):
        self.category = "deposit"
        self.page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.primary, custom_id="withdraw")
    async def withdraw_button_callback(self, button, interaction):
        self.category = "withdraw"
        self.page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.primary, custom_id="win")
    async def win_button_callback(self, button, interaction):
        self.category = "win"
        self.page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.primary, custom_id="loss")
    async def loss_button_callback(self, button, interaction):
        self.category = "loss"
        self.page = 0
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button_callback(self, button, interaction):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button_callback(self, button, interaction):
        if self.page < self.max_pages - 1:
            self.page += 1
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class History(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(aliases=["transactions", "logs"])
    async def history(self, ctx, user: discord.Member = None):
        """View your transaction history with filtering by category and pagination"""
        if user is None:
            user = ctx.author
        
        db = Users()
        user_data = db.fetch_user(user.id)
        
        if user_data == False:
            embed = discord.Embed(
                title="<:no:1344252518305234987> | User Not Found",
                description="This user doesn't have an account. Please wait for auto-registration or use `!signup`.",
                color=0xFF0000
            )
            return await ctx.reply(embed=embed)
        
        # Get history from user data
        history_data = user_data.get("history", [])
        
        # Create view with buttons
        view = HistoryView(self.bot, user, history_data, ctx.author.id)
        
        # Send initial embed
        embed = view.create_embed()
        message = await ctx.reply(embed=embed, view=view)
        
        # Store the message for later reference in the view
        view.message = message


def setup(bot):
    bot.add_cog(History(bot))
