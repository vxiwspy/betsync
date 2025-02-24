
import discord
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users

class Start(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    class MainView(discord.ui.View):
        @discord.ui.button(label="Sign Up", style=discord.ButtonStyle.green)
        async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
            money = emoji()["money"]
            user_id = interaction.user.id
            dump = {"discord_id": user_id, "tokens": 0, "credits": 0, "history": []}

            response = Users().register_new_user(dump)
            if response == False:
                embed = discord.Embed(title=":x: **User Already Has An Account.**", color=0xFF0000, description="- **You Are Already Registered In Our Database.**", icon_url=self.bot.user.avatar.url)
                embed.set_footer(text="BetSync Casino • Best Casino", icon_url=self.bot.user.avatar.url)
            else:
                embed = discord.Embed(title="**Registerd New User**", description=f"**Your discord account has been successfully registered in our database with the following details:**\n```Tokens: 0\nCredits: 0```", color=0x00FFAE, icon_url=self.bot.user.avatar.url)
                embed.add_field(name=f"{money} Get Started", value="- **Type !help or !guide to start betting!**", inline=False)
                embed.set_footer(text="BetSync Casino • Best Casino", icon_url=self.bot.user.avatar.url)

            await interaction.response.send_message(embed=embed)

    @commands.command(name="signup")
    async def signup(self, ctx):
        embed = discord.Embed(title=":wave: **Welcom to BetSync Casino**", description="Press The Button Below To Sign Up If You're A New User!", color=0x00FFAE)
        await ctx.reply(embed=embed, view=self.MainView())

def setup(bot):
    bot.add_cog(Start(bot))
