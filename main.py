import os
import discord
from colorama import Fore
from discord.ext import commands
from pymongo import ReturnDocument
from Cogs.utils.mongo import Users
from Cogs.utils.emojis import emoji


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
bot.remove_command("help")

cogs = ["Cogs.guide", "Cogs.fetches", "Cogs.start" , "Cogs.currency"]

#@bot.event
async def on_command_error(ctx, command):
    print(f"{Fore.RED}[-] {Fore.WHITE} Some monkey {Fore.BLACK}{ctx.message.author}{Fore.WHITE} tried to use a non existsent command 💔💔💔")

@bot.event
async def on_command(ctx):
    if ctx.command.is_on_cooldown(ctx):
        return

    db = Users()
    if db.fetch_user(ctx.author.id) != False:
        return

    dump = {"discord_id": ctx.author.id, "tokens": 0, "credits": 0, "history": [], "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost':0}
    db.register_new_user(dump)

    embed = discord.Embed(title=":wave: Welcome to BetSync Casino!", color=0x00FFAE, description="**Type** `!guide` **to get started**")
    embed.set_footer(text="BetSync Casino", icon_url=bot.user.avatar.url)
    await ctx.reply("By using BetSync, agree to our TOS. Type `!tos` to know more.", embed=embed)

# Add default cooldown to all commands
@bot.event 
async def on_command_registration(command):
    if not command.cooldown:
        command.cooldown = commands.Cooldown(1, 3.0, commands.BucketType.user)

@bot.event
async def on_ready():
    os.system("clear")
    print(f"{Fore.GREEN}[+] {Fore.WHITE}{bot.user}\n")
    for i in cogs:
        #try:
        bot.load_extension(i)
        print(f"{Fore.GREEN}[+] {Fore.WHITE}Loaded Cog: {Fore.GREEN}{i}{Fore.WHITE}")
        #except Exception as e:
        #print(f"{Fore.RED}[-] {Fore.WHITE}FIX THIS YOU NIGGER {e}")
            



bot.run(os.environ['TOKEN'])