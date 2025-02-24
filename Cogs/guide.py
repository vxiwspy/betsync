import discord
from discord.ext import commands

class Guide(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def guide(self, ctx):
		embed = discord.Embed(title="ðŸŽ° **Welcome to BetSync Casino!**", color=0x00FFAE, description="**BetSync** is a **Crypto Powered Casino** where you can bet, win, and enjoy a variety of games. We offer **fast deposits**, **fair games**, and **multiple earning methods**! Hereâ€™s everything you need to know to get started:\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤")
		embed.add_field(name="ðŸ'° **Tokens & Credits**", value="â€¢ **Tokens**: Used for **betting and playing games**.Use `!deposit` to get tokens\nâ€¢ **Credits**: Rewarded after **winning a bet**, Used for **withdrawals**`!withdraw <credits` and **Betting**.\nâ€¢ **Conversion Rates**:\n```\n1 Token/Credit = $0.013\n```\nUse `!rate <amount> <currency>` to convert between **Tokens**, **Credits**, and **crypto**.\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸ¥ **Deposits & Withdrawals**", value="â€¢ **Deposit**: Use `!deposit` to select a currency and get a address\nâ€¢ **Minimum Deposit**: Check in `!help`\nâ€¢ **Withdraw**: Use `!withdraw`.\nâ€¢**Minimum Withdrawal**: 20 Credits.\nâ€¢ **Processing**: Deposits are instant after 1 confirmation. Withdrawals take a few minutes.\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸŽ **Earn Free Tokens**", value="â€¢ **Daily Reward**: Use `!daily` to claim **free tokens**.\nâ€¢ **Giveaways**: Look out for **airdrops** hosted \nâ€¢ **Tips**: Other players can **tip you tokens**.\nâ€¢ **Rakeback:** Get **cashback** on bets via `!rakeback` **(based on deposits).**\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸŽ® **Playing Games**", value="â€¢ See All Games: Use `!help` to view available games.\nâ€¢ Multiplayer Games: Use `!multiplayer` to see PvP games.\nâ€¢ :**Popular Games:** Play **Blackjack**,** Keno:**, **Towers:**, **Mines:**, **Coinflip**, and more\n!Each game has a **detailed command:**, e.g., `!blackjack` for rules, bets, and payouts.\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸ›¡ï¸ **Fairness & Security**", value="â€¢ All games use **cryptographically secure random number generation**\nâ€¢ **Provably Fair**: Every bet is `verifiable and unbiased`.\nâ€¢ **98.5% RTP**: Fair odds compared to other casinos\nã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸ“œ **Example Commands**", value="â€¢ `!deposit`          â†’ Choose **currency** to **deposit** in.\nâ€¢ `!withdraw `        â†’ Withdraw **Credits.**\nâ€¢`!rate 100 BTC `     â†’ **Convert** 100 Tokens to BTC & USD.\nâ€¢`!blackjack 10`      â†’ Bet 10 **Tokens** in Blackjack.\nâ€¢`!mines 5 3`         â†’ Bet **5 Tokens** in **Mines with 3 mines.**\nâ€¢ **Use** `!help` to **view** all **commands**\n ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤", inline=False)
		embed.add_field(name="ðŸ“© **Need Help?**", value="â€¢ For support, type `!support` and **submit a request.**\nâ€¢ Got **feedback?** Let us know!", inline=False)
		embed.set_footer(text="BetSync Casino", icon_url=self.bot.user.avatar.url)
		embed.set_thumbnail(url=self.bot.user.avatar.url)
		embed.set_author(name="BetSync Official Guide", icon_url=self.bot.user.avatar.url)

		await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Guide(bot))