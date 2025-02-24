import discord
from discord.ext import commands

class Guide(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	async def guide(self, ctx):
		embed = discord.Embed(
        title="ðŸŽ° **Welcome to BetSync Casino!**",
        color=0x00FFAE,
        description=(
            "**BetSync** is a **Crypto Powered Casino** where you can bet, win, and enjoy a variety of games. "
            "We offer **fast deposits**, **fair games**, and **multiple earning methods**! Hereâ€™s everything you need to know to get started:\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        )
    )

    # Conversion Rates
		embed.add_field(
        name="ðŸ’° **Tokens & Credits**",
        value=(
            "â€¢ **Tokens**: Used for **betting and playing games**.Use `!deposit` to get tokens\n"
            "â€¢ **Credits**: Rewarded after **winning a bet**, Used for **withdrawals**`!withdraw <credits` and **Betting**.\n"
            "â€¢ **Conversion Rates**:\n"
            "```\n"
            "1 Token/Credit = $0.013\n"
            "```\n"
            "Use `!rate <amount> <currency>` to convert between **Tokens**, **Credits**, and **crypto**.\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        ),
        inline=False
    )


    # Depositing & Withdrawing
		embed.add_field(
        name="ðŸ“¥ **Deposits & Withdrawals**",
        value=(
            "â€¢ **Deposit**: Use `!deposit` to select a currency and get a address\n"
            "â€¢ **Minimum Deposit**: Check in `!help`\n"
            "â€¢ **Withdraw**: Use `!withdraw`.\n"
            "â€¢**Minimum Withdrawal**: 20 Credits.\n"
            "â€¢ **Processing**: Deposits are instant after 1 confirmation. Withdrawals take a few minutes.\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        ),
        inline=False
    )


    # How to Earn Free Tokens
		embed.add_field(
        name="ðŸŽ **Earn Free Tokens**",
        value=(
            "â€¢ **Daily Reward**: Use `!daily` to claim **free tokens**.\n"
            "â€¢ **Giveaways**: Look out for **airdrops** hosted \n"
            "â€¢ **Tips**: Other players can **tip you tokens**.\n"
            "â€¢ **Rakeback:** Get **cashback** on bets via `!rakeback` **(based on deposits).**\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        ),
        inline=False
    )


    # Playing Games
		embed.add_field(
        name="ðŸŽ® **Playing Games**",
        value=(
            "â€¢ See All Games: Use `!help` to view available games.\n"
            "â€¢ Multiplayer Games: Use `!multiplayer` to see PvP games.\n"
            "â€¢ :**Popular Games:** Play **Blackjack**,** Keno:**, **Towers:**, **Mines:**, **Coinflip**, and more\n!"
            "Each game has a **detailed command:**, e.g., `!blackjack` for rules, bets, and payouts.\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"

        ),
        inline=False
    )

    # Fairness & Security
		embed.add_field(
        name="ðŸ›¡ï¸ **Fairness & Security**",
        value=(
    "â€¢ All games use **cryptographically secure random number generation**\n"
            "â€¢ **Provably Fair**: Every bet is `verifiable and unbiased`.\n"
            "â€¢ **98.5% RTP**: Fair odds compared to other casinos\n"
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        ),
        inline=False
    )



    # Example Commands
		embed.add_field(
        name="ðŸ“œ **Example Commands**",
        value=(

            "â€¢ `!deposit`          â†’ Choose **currency** to **deposit** in.\n"
            "â€¢ `!withdraw `        â†’ Withdraw **Credits.**\n"
            "â€¢`!rate 100 BTC `     â†’ **Convert** 100 Tokens to BTC & USD.\n"
            "â€¢`!blackjack 10`      â†’ Bet 10 **Tokens** in Blackjack.\n"
            "â€¢`!mines 5 3`         â†’ Bet **5 Tokens** in **Mines with 3 mines.**\n"
            "â€¢ **Use** `!help` to **view** all **commands**\n "
            "ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤ã…¤"
        ),
        inline=False
    )



    # Need Help?
		embed.add_field(
        name="ðŸ“© **Need Help?**",
        value=(
            "â€¢ For support, type `!support` and **submit a request.**\n"
            "â€¢ Got **feedback?** Let us know!"
        ),
        inline=False
    )

    # Footer with bot icon and BetSync text
		embed.set_footer(
        text="BetSync Casino",
        icon_url=self.bot.user.avatar.url
    )

    # Thumbnail and author
		embed.set_thumbnail(url=self.bot.user.avatar.url)
		embed.set_author(
        name="BetSync Official Guide",
        icon_url=self.bot.user.avatar.url
    )

		await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Guide(bot))