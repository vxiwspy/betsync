",
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
        embed.add_field(name=":money_with_wings: Credits", value=f"```{round(credits, 2)} Credits (~${round((credits * token_value), 2)})