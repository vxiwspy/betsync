import discord
import json
from discord.ext import commands
from Cogs.utils.emojis import emoji

class Guide(commands.Cog):
	def __init__(self, bot):

		self.emojis = emoji()
		self.required = [self.emojis["money"]]	
		self.bot = bot

	@commands.command()
	async def guide(self, ctx):
		embed = discord.Embed(title=":slot_machine: **Welcome to BetSync Casino!**", color=0x00FFAE, description="**BetSync** is a **Crypto Powered Casino** where you can bet, win, and enjoy a variety of games. We offer **fast deposits**, **fair games**, and **multiple earning methods**! Here\'s everything you need to know to get started:\n")
		embed.add_field(name=f"{self.required[0]} **Tokens & Credits**", value="- **Tokens**: Used for **betting and playing games**.Use `!deposit` to get tokens\n- **Credits**: Rewarded after **winning a bet**, Used for **withdrawals**`!withdraw <credits` and **Betting**.\n- **Conversion Rates**:\n```\n1 Token/Credit = $0.0212\n```\nUse `!rate <amount> <currency>` to convert between **Tokens**, **Credits**, and **crypto**.\n", inline=False)
		embed.add_field(name=":inbox_tray: **Deposits & Withdrawals**", value="- **Deposit**: Use `!deposit` to select a currency and get a address\n- **Minimum Deposit**: Check in `!help`\n- **Withdraw**: Use `!withdraw`.\n- **Minimum Withdrawal**: 20 Credits.\n- **Processing**: Deposits are instant after 1 confirmation. Withdrawals take a few minutes.\n", inline=False)
		embed.add_field(name=":gift: **Earn Free Tokens**", value="- **Daily Reward**: Use `!daily` to claim **free tokens**.\n- **Giveaways**: Look out for **airdrops** hosted \n- **Tips**: Other players can **tip you tokens**.\n- **Rakeback:** Get **cashback** on bets via `!rakeback` **(based on deposits).**\n", inline=False)
		embed.add_field(name=":video_game: **Playing Games**", value="- **See All Games:** Use `!help` to view available games.\n- **Multiplayer Games:** Use `!multiplayer` to see PvP games.\n - **Popular Games:** Play **Blackjack**,** Keno:**, **Towers:**, **Mines:**, **Coinflip**, and more!\n Each game has a **detailed command:**, e.g., `!blackjack` for rules, bets, and payouts.\n", inline=False)
		embed.add_field(name=":shield: **Fairness & Security**", value="- All games use **cryptographically secure random number generation**\n- **Provably Fair**: Every bet is `verifiable and unbiased`.\n- **98.5% RTP**: Fair odds compared to other casinos\n", inline=False)
		embed.add_field(name=":scroll: **Example Commands**", value="- `!deposit:` **Deposit** \n - `!withdraw:` **Withdraw** \n - `!rate 100 BTC:` **Convert** \n - `!blackjack 10:` **Bet** \n - `!mines 5 3:` **Play Mines** \n - `!help:` **All Commands**", inline=False)
		embed.add_field(name=":question_mark: **Need Help?**", value="- For support, type `!support` and **submit a request.**\n- Got **feedback?** Let us know!", inline=False)
		embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
		embed.set_thumbnail(url=self.bot.user.avatar.url)
		embed.set_author(name="BetSync Official Guide", icon_url=self.bot.user.avatar.url)

		await ctx.message.reply(embed=embed)

def setup(bot):
    bot.add_cog(Guide(bot))