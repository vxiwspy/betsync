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

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        print(f"{Fore.RED}[-] {Fore.WHITE} Some monkey {Fore.BLACK}{ctx.message.author}{Fore.WHITE} tried to use a non existsent command 💔💔💔")

# Global check to handle user registration instantly for any command
@bot.check
async def register_user_if_needed(ctx):
    # Immediate registration for any command
    db = Users()
    
    # Check if user exists, register immediately if not
    if db.fetch_user(ctx.author.id) == False:
        # User not registered, register them immediately
        dump = {"discord_id": ctx.author.id, "tokens": 0, "credits": 0, "history": [], 
                "total_deposit_amount": 0, "total_withdraw_amount": 0, "total_spent": 0, 
                "total_earned": 0, 'total_played': 0, 'total_won': 0, 'total_lost':0}
        db.register_new_user(dump)
        
        # Simple welcome message - only show once after registration
        embed = discord.Embed(title=":wave: Welcome to BetSync Casino!", 
                             color=0x00FFAE, 
                             description="**Type** `!guide` **to get started**")
        embed.set_footer(text="BetSync Casino", icon_url=bot.user.avatar.url)
        
        # Send welcome message immediately, don't wait
        bot.loop.create_task(ctx.reply("By using BetSync, you agree to our TOS. Type `!tos` to know more.", embed=embed))
    
    # Always return True immediately to allow the command to execute without delay
    return True

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