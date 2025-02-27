import discord
import os
from discord.ext import commands
from Cogs.utils.mongo import Servers, Users
from Cogs.utils.emojis import emoji


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


def setup(bot):
    bot.add_cog(ServersCog(bot))
