import discord
from discord.ext import commands
from Cogs.utils.emojis import emoji
from Cogs.utils.mongo import Users

class MainView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__()
        self.bot = bot
        self.user = user

    @discord.ui.button(label="Sign Up", style=discord.ButtonStyle.green)
    async def signup(self,button, interaction: discord.Interaction):
        dump = {"discord_id": self.user.id, "tokens": 0, "credits": 0, "history": []}
        money = emoji()["money"]
        response = Users().register_new_user(dump)

        if response is False:
            embed = discord.Embed(
                title=":x: **User Already Has An Account.**",
                color=0xFF0000,
                description="- **You Are Already Registered In Our Database.**"
            )
        else:
            embed = discord.Embed(
                title="**Registered New User**",
                description="**Your discord account has been successfully registered in our database with the following details:**\n```Tokens: 0\nCredits: 0```",
                color=0x00FFAE
            )
            embed.add_field(name=f"{money} Get Started", value="- **Type !help or !guide to start betting!**", inline=False)

        embed.set_footer(text="BetSync Casino • Best Casino", icon_url=self.user.avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Start(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="signup")
    async def signup(self, ctx):
        embed = discord.Embed(
            title=":wave: **Welcome to BetSync Casino**",
            description="Press The Button Below To Sign Up If You're A New User!",
            color=0x00FFAE
        )
        await ctx.reply(embed=embed, view=MainView(self.bot, ctx.author))

def setup(bot):
    bot.add_cog(Start(bot))
    