"""
Made by LucasLiorLE (https://github.com/LucasLiorLE/APEYE)
    - This is just my bot I made for fun, mostly during my free time.
    - Feel free to "steal" or take portions of my code.
    - Has a lot of usefull utilities!
    - /help for more info!

Release Notes:
    - Organized main.py
        - Also minor organization to other files.
    - Minor economy update
        - Deleted gambling commands for now.
    - Organized some other files.
    - Userphone command, which allows you to talk to others from across servers!
    - Reminder command group, basic reminder add, list and remove.


This was last updated: 1/19/2025 10:27 PM
"""

import os, random, math, asyncio, asyncpraw
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import commands
from aiohttp import ClientSession # I just don't want to use aiohttp.ClientSession()
from dotenv import load_dotenv # To load secrets.env
from ossapi import Ossapi # Osu API

from bot_utils import (
    open_file,
    save_file,
    get_player_data,
    __version__
)

# config
botAdmins = [721151215010054165]
botMods = []
botTesters = []

# Other stuff 
class InvalidKeyError(Exception): ...

# Bot status management
class StatusManager:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = [
            "https://lucasliorle.github.io",
            "Glory to the CCP! (我们的)",
            "https://www.nohello.com/",
            "https://github.com/LucasLiorLE/APEYE",
            "I really need to sleep...",
            "Do people even read these?"
        ]

    async def change_status(self):
        while True:
            await self.bot.wait_until_ready()
            current_status = random.choice(self.status_messages)
            await self.bot.change_presence(
                status=discord.Status.dnd, 
                activity=discord.Game(name=current_status)
            )
            await asyncio.sleep(600)

# Bot def 
class APEYEBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.dm_messages = True
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(">"),
            intents=intents,
            case_insensitive=True
        )
        self.status_manager = StatusManager(self)

    async def setup_hook(self):
        # import logging
        # logging.basicConfig(level=logging.INFO)
        # logger = logging.getLogger("discord")
        try:
            print("Loading cogs...\n-----------------")
            await load_cogs()
            print("-----------------\nCogs loaded successfully.")
            try:
                # print("Clearing existing commands...")
                # for guild in bot.guilds:
                #     bot.tree.clear_commands(guild=guild)
                print("Syncing commands...")
                await bot.tree.sync()
                print("Commands successfully synced.")
            except Exception as e:
                print(f"An error occurred when syncing commands: {e}")
        except Exception as e:
            print(f"An error occurred when loading cogs: {e}")
        print("Bot is ready.")

# Util functions
async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded {filename}")
            except Exception as e:
                print(f"Failed to load {filename}: {e}")

async def test_hy_key() -> bool:
    async with ClientSession() as session:
        async with session.get(f"https://api.hypixel.net/player?key={hypixel_api}") as response:
            if response.status == 403:
                data = await response.json()
                if data.get("success") == False and data.get("cause") == "Invalid API key":
                    print("Invalid hypixel API key provided. Please check secrets.env")
                    return False
            elif response.status == 400:
                print("Hypixel API key is valid.")
                return True
            else:
                print(f"Request failed with status code: {response.status}")
                return False

async def check_apis():
    if not await test_hy_key():
        return False
    if not await get_player_data(None):
        print("Invalid Clash Royale API key. Please check secrets.env.")
        return False
    
    try:
        osu_api = Ossapi(int(osu_api), osu_secret)
        print("Osu API key is valid.")
    except ValueError:
        print("Invalid Osu API keys")
        return False

    try:
        reddit = asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        ) 
        print("Reddit API is valid.")
    except Exception as e:
        print(f"Reddit API error: {e}")
        return False
    
    return True

# Bot setup and other stuff
bot = APEYEBot()
user_last_message_time = {}

secrets = Path("storage/secrets.env")
load_dotenv(dotenv_path=secrets)

# Load env var
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
user_agent = os.getenv("user_agent")
cr_api = os.getenv("cr_api")
token = os.getenv("token")
osu_api = os.getenv("osu_api")
osu_secret = os.getenv("osu_secret")
hypixel_api = os.getenv("hypixel_api")

# Event handling stuff
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if isinstance(message.channel, discord.DMChannel):
        return

    server_id = str(message.guild.id)
    member_id = str(message.author.id)
    current_time = datetime.now(timezone.utc)

    server_info = open_file("info/server_info.json")
    member_data = open_file("info/member_info.json")

    afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})
    exp_data = server_info.setdefault(server_id, {}).setdefault("exp", {})

    if member_id in afk_data:
        original_name = afk_data[member_id].get("original_name")
        del afk_data[member_id]
        save_file("info/server_info.json", server_info)

        await message.add_reaction("👋")
        await message.channel.send(f"Welcome back, {message.author.mention}! You are no longer AFK.", delete_after=3)
        if original_name and message.author.display_name != original_name:
            try:
                await message.author.edit(nick=original_name)
            except discord.Forbidden:
                pass

    for user in message.mentions:
        user_id = str(user.id)
        if user_id in afk_data:
            afk_reason = afk_data[user_id].get("reason", None)
            afk_time = afk_data[user_id].get("time", datetime.now(timezone.utc).isoformat())
            embed = discord.Embed(
                title=f"{user.display_name} is AFK",
                description=afk_reason,
                timestamp=datetime.fromisoformat(afk_time),
                color=discord.Color.orange(),
            )
            await message.channel.send(embed=embed)

    if member_id not in member_data:
        member_data[member_id] = {"EXP": 0}

    if member_id not in exp_data:
        exp_data[member_id] = {"EXP": 0}

    last_message_time = user_last_message_time.get(member_id)

    if last_message_time is None or current_time - last_message_time >= timedelta(minutes=1):
        message_length = len(message.content)
        exp_gain = min(75, math.floor(message_length / 15)) + (random.randint(5, 15)) 

        member_data[member_id]["EXP"] += exp_gain

        if "exp" not in server_info:
            server_info["exp"] = {}
        if server_id not in server_info["exp"]:
            server_info["exp"][server_id] = {}
        server_info["exp"][server_id][member_id] = server_info["exp"][server_id].get(member_id, 0) + exp_gain

        save_file("info/member_info.json", member_data)
        save_file("info/server_info.json", server_info)

# Main execution thing
async def main():
    print(f"Script loaded. Version: v{__version__}")

    # if not await check_apis():
    #     return

    print("The bot is starting, please give it a minute.")
    try:
        await bot.start(token)
    except discord.errors.LoginFailure:
        print("Incorrect bot token. Please check secrets.env")
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        print("Bot is shutting down.")
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
    except Exception as e:
        print(f"An unexpected error occurred during bot execution: {e}")
