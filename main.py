import os
import discord
from colorama import Fore
from discord.ext import commands
from discord.ui import Button, View

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
bot.remove_command("help")


cogs = ["Cogs.guide"]

@bot.event
async def on_ready():
    os.system("clear")
    print(f"{Fore.GREEN}[+] {Fore.WHITE}{bot.user}\n")
    for i in cogs:
        try:
            await bot.load_extension(i)
            print(f"{Fore.GREEN}[+] {Fore.WHITE}Loaded Cog: {Fore.GREEN}{i}{Fore.WHITE}")
        except Exception as e:
            print(f"{Fore.RED}[-] {Fore.WHITE}FIX THIS YOU NIGGER {e}")
            



bot.run(os.environ['TOKEN'])