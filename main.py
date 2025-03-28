# Made by LucasLiorLE (https://github.com/LucasLiorLE/AstralV) (https://lucasliorle.github.io)
#    - This is just my bot I made for fun, mostly during my free time.
#    - Feel free to "steal" or take portions of my code.
#    - Has a lot of usefull utilities!
#    - /help for more info! (Ok tbh rn it doesn't do crap :sob:)
# 
# Release notes:
#    - Tried to fix "AttributeError: 'NoneType' object has no attribute 'sequence'" error
#    - Economy update
#    - Stored moderation and economy in packets to make it easier for me to see stuff
#    - Hypixel command update
#    - Some moderation fixes
#    - Minor commands (Useless feature: poll!)
#    - String commands
#    - Roblox friendswish command testing, might make faster later on and is buggy!
#    - Role command group
#
# Other notes:
#    - Attempt to fix status upon disconnect
#    - Fixed some bugs with the moderation commands
#    - Discovered how to use hybrid_commands 
#         - Was too use to bridge_commands from pycord
# 
# TODO/FIX:
#    - Make auto mute a server set function. (2.4.0)
#    - Make a more efficient storage system using sql and json (2.6.0)
#
# This was last updated: 3/26/2025 2:06 AM

import os, random, math, asyncio
# import asyncpraw
from datetime import datetime, timezone

import discord
from discord.ext import commands
from aiohttp import ClientSession
from ossapi import Ossapi

from bot_utils import (
    open_file,
    save_file,
    cr_fetchPlayerData,
    get_member_cooldown,
    # debug,
    error,
    warn,

    token,
    # client_id,
    # client_secret,
    # userAgent,
    # crAPI,
    # osuAPI,
    osuSecret,
    hypixelAPI,
    __version__,
)

# config
botAdmins = [721151215010054165]
botMods = [721151215010054165]
botTesters = [721151215010054165, 776139231583010846]

# Bot status management
class StatusManager:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = [
            "https://lucasliorle.github.io",
            "Glory to the CCP! (我们的)",
            "https://www.nohello.com/",
            "https://github.com/LucasLiorLE/AstralV",
            "I really need to sleep...",
            "Do people even read these?"
        ]
        self.running = False
        self.current_status = None

    async def change_status(self):
        self.running = True
        while self.running:
            try:
                await self.bot.wait_until_ready()
                self.current_status = random.choice(self.status_messages)
                await self.bot.change_presence(
                    status=discord.Status.dnd, 
                    activity=discord.Game(
                        name=self.current_status,
                    )
                )
                await asyncio.sleep(600)
            except Exception as e:
                print(f"Status update error: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self.running = False

# Bot def 
class botMain(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.dm_messages = True
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("."),
            intents=intents,
            case_insensitive=True
        )
        self.status_manager = StatusManager(self)

    async def setup_hook(self):
        self.loop.create_task(self.status_manager.change_status())
        
        # import logging
        # logging.basicConfig(level=logging.INFO)
        # logger = logging.getLogger("discord")
        try:
            print("Loading cogs...\n-----------------")
            await load_cogs()
            print("-----------------\nCogs loaded successfully.")
            try:
                # for guild in bot.guilds:
                #     await bot.tree.clear_commands(guild=guild)
                print("Syncing commands...")
                await bot.tree.sync()
                print("Commands successfully synced.")
            except Exception as e:
                error(f"An error occurred when syncing commands: {e}")
        except Exception as e:
            error(f"An error occurred when loading cogs: {e}")
        print("Bot is ready.")

# Util functions
async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "utils.py":
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded {filename}")
            except Exception as e:
                error(f"Failed to load {filename}: {e}")

    for folder in os.listdir("./cogs"):
        if os.path.isdir(f"./cogs/{folder}"):
            for filename in os.listdir(f"./cogs/{folder}"):
                if filename.endswith(".py") and filename != "utils.py":
                    try:
                        await bot.load_extension(f"cogs.{folder}.{filename[:-3]}")
                    except Exception as e:
                        error(f"Failed to load {folder}/{filename}: {e}")

            print(f"Loaded {folder}")

async def test_hy_key() -> bool:
    async with ClientSession() as session:
        async with session.get(f"https://api.hypixel.net/player?key={hypixelAPI}") as response:
            if response.status == 403:
                data = await response.json()
                if data.get("success") == False and data.get("cause") == "Invalid API key":
                    print("Invalid hypixel API key provided. Please check secrets.env")
                    return False
            elif response.status == 400:
                print("Hypixel API key is valid.")
                return True
            else:
                error(f"Request failed with status code: {response.status}")
                return False

async def check_apis() -> bool:
    if not await test_hy_key():
        return False
    if not await cr_fetchPlayerData(None):
        error("Invalid Clash Royale API key. Please check secrets.env.")
        return False
    
    try:
        osu_api = Ossapi(int(osu_api), osuSecret)
        print("Osu API key is valid.")
    except ValueError:
        error("Invalid Osu API keys")
        return False

    # try:
    #     reddit = asyncpraw.Reddit(
    #         client_id=client_id,
    #         client_secret=client_secret,
    #         user_agent=user_agent,
    #     ) 
    #     print("Reddit API is valid.")
    # except Exception as e:
    #     print(f"Reddit API error: {e}")
    #     return False
    
    return True

# Bot setup and other stuff
bot = botMain()

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

    server_info = open_file("storage/server_info.json")
    member_data = open_file("storage/member_info.json")

    afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})

    if member_id in afk_data:
        original_name = afk_data[member_id].get("original_name")
        del afk_data[member_id]
        save_file("storage/server_info.json", server_info)

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

    cooldown = get_member_cooldown(member_id, exp=True)
    if cooldown >= 60:
        message_length = len(message.content)
        exp_gain = min(75, math.floor(message_length / 15)) + (random.randint(5, 15))

        if member_id not in member_data:
            member_data[member_id] = {"EXP": {"total": 0, "cooldown": 0}}
        
        member_data[member_id]["EXP"]["total"] = member_data[member_id].get("EXP", {}).get("total", 0) + exp_gain
        member_data[member_id]["EXP"]["cooldown"] = int(datetime.now(timezone.utc).timestamp())

        if "exp" not in server_info:
            server_info["exp"] = {}
        if server_id not in server_info["exp"]:
            server_info["exp"][server_id] = {}
        if member_id not in server_info["exp"][server_id]:
            server_info["exp"][server_id][member_id] = 0
        server_info["exp"][server_id][member_id] += exp_gain

        save_file("storage/member_info.json", member_data)
        save_file("storage/server_info.json", server_info)

@bot.event
async def on_connect():
    if not bot.status_manager.running:
        bot.loop.create_task(bot.status_manager.change_status())

@bot.event
async def on_resumed():
    if bot.status_manager.current_status:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name=bot.status_manager.current_status)
        )

# Main execution thing

async def main():
    print(f"Script loaded. Version: v{__version__}")

    # Checking for APIs not required but it will be required
    # if you want to use some commands later.
    # Recommended to uncomment this if you want to use it for that.
    # I have it commented because I'm too lazy to refresh all 
    # of my APIs, so you can do that too I guess.

    # if not await check_apis():
    #     return

    print("The bot is starting, please give it a minute.")
    retry = 0
    while True:
        try:
            await bot.start(token)
        except discord.errors.LoginFailure:
            warn("Incorrect bot token. Please check secrets.env")
            break 
        except KeyboardInterrupt:
            print("Shutting down gracefully...")
            break
        except Exception as e:
            import traceback
            print(traceback.format_exc()) if retry > 5 else error(f"Unexpected error: {e}")
            print(f"Retrying in {min(2 ** retry, 60)} seconds.")
            await asyncio.sleep(min(2 ** retry, 60))
            retry += 1
        finally:
            print("Bot is shutting down.")
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Shutting down...")
    except Exception as e:
        error(f"An unexpected error occurred during bot execution: {e}")