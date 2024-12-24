__version__ = "v2.0.2"

"""
Made by LucasLiorLE (https://github.com/LucasLiorLE/APEYE)
    - This is just my bot I made for fun, mostly during my free time.
    - Feel free to "steal" or take portions of my code.
    - Has a lot of usefull utilities!
    - /help for more info!

Update Notes:
    - Everything organized into cogs!
    - main.py is now just for functions, and some other stuff. 
    - No more requests, I did not realize some of the older commands had it.
        - Everything should now be used with aiohttp.
    - I think I forgot to mention the AFK command now exists.

Known Bugs:
    - Regular commands (Prefixes) are not working. Currently trying to find a fix, >clean will work with an alternative for now.
    - An error occured when syncing commands. Press Ctrl+C to stop the bot. Error: 400 Bad Request (error code: 50240): You cannot remove this app's Entry Point command in a bulk update operation. Please include the Entry Point command in your update request or delete it separately.
        - It took me like 30 minutes of research to find nothing. It's because the original bot you had cannot change so much slash commands from v1 to v2. 
        - To delete all commands do: 
            @bot.event
            async def on_ready():
                print("Removing all global commands...")

                try:
                    global_commands = await bot.tree.fetch_commands()
                    for command in global_commands:
                        await command.delete()

                        print(f"Deleted global command: {command.name}")
                    print("All global commands have been removed.")
                except Exception as e:
                    print(f"An error occurred while removing global commands: {e}")

        - After deleting commands, you can go back to the original on_ready() function.

Next Patch (Most likely will come):
    - EXP System rework
    - Hopefully fix the regular commands!
    - Add more fun commands

Future updates (Might or might not come, mainly the next update/feature):
    - Fix convert YT command (I think it's just my cookie.txt issue)
        - Try to find a better alternative
    - Try to find an API for converting videos and stuff? Maybe cloudconvert has an API. 
        - Currently found cobalt.tools, will check it out later!
            - This means creating my own instance.
        - /convert youtube is currently gone until an API version is found.

Possible ideas: 
    - GD and OSU connect
        - Not really sure how osu will work yet.
    - OSU profile rework (More info)
    - Finish the alert command
    - New giveaway commands
        - Since the giveaway is forever stored, make it so you can view a certain one.
    - Possibly add comments to explain my code
    - Start working on economy after all that
    - Custom command prefix
    - Json file to store every description. Makes help command easier.
    - Skyblock profile shows user inventory.
        - I know how to decode the data, too much emojis to create. 

This was last updated: 12/14/2024 10:13 AM
"""

import discord
from discord.ext import commands

import json, os, re, sys
import random, time, datetime, math
import asyncio, asyncpraw
import traceback
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path

from aiohttp import ClientSession

from typing import List, Union, Optional, Dict, Any
from ossapi import Ossapi

botAdmins = [721151215010054165]
botMods = []
botTesters = []

class StatusManager:
    def __init__(self, bot):
        self.bot = bot
        self.status_messages = [
            "noob",
            "Glory to the CCP! (我们的)",
            "https://www.nohello.com/",
        ]

    async def change_status(self):
        while True:
            await self.bot.wait_until_ready()
            current_status = random.choice(self.status_messages)

            await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name=current_status))
            await asyncio.sleep(600)

intents = discord.Intents.all()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.dm_messages = True
intents.members = True

bot = commands.Bot(command_prefix=">", intents=intents)


# Global variables for logging
logs = {}
log_id_counter = 1

# Functions for handling files

def open_file(filename: str) -> Dict[str, Any]:
    """
    Opens a JSON file and returns the data.

    Args:
        filename (str): The path to the JSON file.

    Returns:
        dict: The parsed JSON data.
    """
    try:
        with open(filename, "r") as f:
            file_data = json.load(f)
        return file_data
    except FileNotFoundError:
        print(f"Error: The file '{filename}' was not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: The file '{filename}' contains invalid JSON.")
        return {}


def save_file(filename: str, data: Any) -> None:
    """
    Saves data to a JSON file.

    Args:
        filename (str): The path to the JSON file.
        data (Any): The data to be saved.
    """
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)
    except Exception as e:
        raise Exception(f"Error: Could not save data to '{filename}'. {e}") # This ensures error handling occurs, and the user is notifed instead of just a print.

# Functions for handling logs

def store_log(log_type: str, message: str) -> int:
    """
    Stores a log entry and returns its ID.

    Args:
        log_type (str): The type of log (e.g., "error").
        message (str): The message to store in the log.

    Returns:
        int: The log entry ID.
    """
    global log_id_counter

    log_type = log_type.title()

    if log_type not in logs:
        logs[log_type] = []

    if not isinstance(message, str):
        raise ValueError("Message must be a string.")

    log_entry = {
        "Message": message,
        "ID": log_id_counter,
        "Time": int(time.time()),
    }

    logs[log_type].append(log_entry)
    print(f"[{log_type}] {message}")

    current_id = log_id_counter
    log_id_counter += 1

    return current_id

async def handle_logs(interaction: discord.Interaction, error: Exception, log_type: str = "error") -> None:
    """
    Handles logging of errors or other types of logs, including sending embeds to Discord.

    Args:
        interaction (discord.Interaction): The interaction that triggered the log.
        error (Exception): The error or message to log.
        log_type (str): The type of log (default is "error").
    """
    global log_id_counter
    log_type = log_type.title()

    if log_type == "Error" and isinstance(error, Exception):
        embed = discord.Embed(title="An error occurred", color=discord.Color.red())
        embed.add_field(name="Error", value=str(error), inline=False)
        embed.add_field(name="ID", value=log_id_counter)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

        full_error = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        log_id = store_log(log_type, full_error)
        print(f"Logged error with ID: {log_id}")
    else:
        log_id = store_log(log_type, str(error))
        print(f"Logged '{log_type}' with ID: {log_id}")

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parses a duration string in the format 'XdYhZmWs' into a timedelta object.

    Parameters:
    - duration_str (str): The duration string to parse, where:
      - 'd' represents days,
      - 'h' represents hours,
      - 'm' represents minutes,
      - 's' represents seconds.

    Returns:
    - Optional[timedelta]: A `timedelta` object representing the total duration if the format is valid, otherwise `None`.

    Example:
    - Input: "1d2h30m15s"
    - Output: timedelta(days=1, hours=2, minutes=30, seconds=15)
    """
    duration_regex = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = duration_regex.match(duration_str)

    if not match:
        return None

    days, hours, minutes, seconds = match.groups()
    total_duration = timedelta()

    if days:
        total_duration += timedelta(days=int(days))
    if hours:
        total_duration += timedelta(hours=int(hours))
    if minutes:
        total_duration += timedelta(minutes=int(minutes))
    if seconds:
        total_duration += timedelta(seconds=int(seconds))

    return total_duration

def check_user(interaction: discord.Interaction, original_user: discord.User) -> bool:
    """
    Checks if the interaction is performed by the original user.

    Parameters:
    - interaction (discord.Interaction): The interaction object triggered by the user.
    - original_user (discord.User): The user who is allowed to interact.

    Returns:
    - bool: True if the interaction user matches the original user, otherwise False.
    """
    return interaction.user.id == original_user.id

class RestrictedView(discord.ui.View):
    """
    A custom Discord UI View that restricts interactions to a specific user.

    Attributes:
    - original_user (discord.User): The user who is allowed to interact with the view.
    """
    def __init__(self, original_user: discord.User):
        """
        Initializes the RestrictedView.

        Parameters:
        - original_user (discord.User): The user who is allowed to interact with the view.
        """
        super().__init__()
        self.original_user = original_user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Validates whether the interaction is initiated by the original user.

        Parameters:
        - interaction (discord.Interaction): The interaction object triggered by the user.

        Returns:
        - bool: True if the interaction user matches the original user, otherwise False.

        Behavior:
        - Sends an ephemeral message if the interaction is not from the original user.
        """
        if not check_user(interaction, self.original_user):
            await interaction.response.send_message(
                "You can't interact with this.", ephemeral=True
            )
            return False
        return True

secrets = Path('storage/secrets.env')
load_dotenv(dotenv_path=secrets)

client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
user_agent = os.getenv("user_agent")
cr_api = os.getenv("cr_api")
token = os.getenv("token")
osu_api = os.getenv("osu_api")
osu_secret = os.getenv("osu_secret")
hypixel_api = os.getenv("hypixel_api")

# https://sky.shiiyu.moe/api/v2/profile/ also works as a skyblock profile command.

async def test_hy_key() -> bool:
    async with ClientSession() as session:
        async with session.get(f"https://api.hypixel.net/player?key={hypixel_api}") as response:
            if response.status == 403:
                data = await response.json()
                if data.get("success") == False and data.get("cause") == "Invalid API key": 
                    print("Invalid hypixel API key provided. Please check secrets.env.")
                    return False
            elif response.status == 400: # UUID is not provided, therefore it would return 400
                print("Hypixel API key is valid.")
                return True
            else:
                print(f"Request failed with status code: {response.status}")
                return False
'''     
reddit = asyncpraw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
) 
'''
user_last_message_time = {}

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        return

    server_id = str(message.guild.id)
    member_id = str(message.author.id)
    current_time = datetime.now(timezone.utc)

    server_info = open_file("info/server_info.json")
    member_data = open_file("info/member_info.json")

    afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})

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
            afk_reason = afk_data[user_id].get("reason", "No reason provided")
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

    last_message_time = user_last_message_time.get(member_id)

    if last_message_time is None or current_time - last_message_time >= timedelta(minutes=1):
        message_length = len(message.content)
        exp_gain = math.floor(message_length / 15)

        member_data[member_id]["EXP"] += exp_gain
        user_last_message_time[member_id] = current_time

        save_file("info/member_info.json", member_data)
      
@bot.event
async def on_ready():
    # import logging
    # logging.basicConfig(level=logging.INFO)
    # logger = logging.getLogger('discord')
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

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded {filename}")
            except Exception as e:
                print(f"Failed to load {filename}: {e}")

"""
MODERATION COMMANDS
"""

async def dmbed(
        interaction: discord.Interaction, 
        user: discord.User, 
        action: str, 
        reason: str, 
        duration: str = None
    ) -> None:

    embed = discord.Embed(title=f"Member {action}.", color=discord.Color.orange())
    embed.add_field(name="Action", value=action.title())
    embed.add_field(name="Reason", value=reason)
    if duration:
        embed.add_field(name="Duration", value=duration)

    try:
        MemberEmbed = discord.Embed(
            title=f"You have been {action} in {interaction.guild.name}.", 
            color=discord.Color.orange()
        )
        MemberEmbed.add_field(name="Moderator", value=interaction.user.mention)
        MemberEmbed.add_field(name="Reason", value=reason)
        if duration:
            MemberEmbed.add_field(name="Duration", value=duration)
        MemberEmbed.set_footer(text="If you think this is a mistake, please contact a staff user.")
        await user.send(embed=MemberEmbed)
    except discord.Forbidden:
        embed.set_footer(text="I could not DM them.")

    await interaction.followup.send(embed=embed)

async def check_mod(
        interaction: discord.Interaction, 
        permission_name: str
    ) -> bool:
    server_info = open_file("info/server_info.json")
    guild_id = str(interaction.guild_id)

    server_info.setdefault("preferences", {})
    server_info.setdefault("modlogs", {})
    server_info.setdefault("modstats", {})
    server_info.setdefault("warnings", {})
    server_info.setdefault("notes", {})

    server_info["preferences"].setdefault(guild_id, {})
    server_info["modlogs"].setdefault(guild_id, {})
    server_info["modstats"].setdefault(guild_id, {})
    server_info["warnings"].setdefault(guild_id, {})
    server_info["notes"].setdefault(guild_id, {})

    save_file("info/server_info.json", server_info)

    mod_role_id: Optional[int] = server_info["preferences"][guild_id].get("moderator")
    has_permission: bool = getattr(interaction.user.guild_permissions, permission_name, False)
    has_role: bool = mod_role_id and discord.utils.get(interaction.user.roles, id=int(mod_role_id))

    if not (has_permission or has_role):
        await interaction.followup.send(
            f"You need the '{permission_name.replace('_', ' ').title()}' permission or the Moderator role to use this command.",
            ephemeral=True
        )
        return False

    return True

async def store_modlog(
        modlog_type: str,
        server_id: int,
        moderator: discord.User,
        user: discord.User = None,
        channel: discord.TextChannel = None,
        role: discord.Role = None,
        reason: str = "No reason provided.",
        arguments: str = None,
        bot = None
    ) -> None:
    """
    Store moderation logs and send embed messages to designated channel.
    
    Args:
        modlog_type: Type of moderation action
        server_id: Discord server ID
        moderator: Moderator who performed the action
        user: Affected user (optional)
        channel: Affected channel (optional)
        role: Affected role (optional)
        reason: Reason for moderation action
        arguments: Additional arguments
        bot: Discord bot instance
    """
    server_info = open_file("info/server_info.json")
    for key in ["preferences", "modlogs", "modstats", "warnings"]:
        server_info.setdefault(key, {})
        if key in ["modlogs", "modstats", "warnings"]:
            server_info[key].setdefault(str(server_id), {})

    modlog_channel = None
    channel_id = server_info["preferences"].get(str(server_id), {}).get("modLogs")
    
    if channel_id and bot:
        try:
            modlog_channel = bot.get_channel(int(channel_id))
            if not modlog_channel:
                raise discord.NotFound(f"Could not find channel with ID {channel_id}")
        except ValueError:
            raise ValueError(f"Invalid channel ID format: {channel_id}")
        except Exception as e:
            raise Exception(f"Error retrieving modlog channel: {str(e)}")

    embed = discord.Embed(
        title="Moderation Log",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
    )
    
    embed_fields = {
        "Type": modlog_type,
        "Reason": reason,
        "Moderator": moderator.mention,
    }
    
    if role:
        embed_fields["Role affected"] = role.mention
    if user:
        embed_fields["User affected"] = user.mention
    if channel:
        embed_fields["Channel affected"] = channel.mention
    if arguments:
        embed_fields["Extra arguments"] = arguments

    for name, value in embed_fields.items():
        embed.add_field(name=name, value=value, inline=False)

    if user:
        user_id = str(user.id)
        moderator_id = str(moderator.id)
        
        server_info["modlogs"][str(server_id)].setdefault(user_id, {})
        
        last_case_number = max(map(int, server_info["modlogs"][str(server_id)][user_id].keys()), default=0)
        new_case_number = last_case_number + 1
        
        modlog_entry = {
            "Type": modlog_type,
            "User": str(user),
            "Moderator": str(moderator),
            "Reason": reason,
            "Time": int(time.time()),
        }
        
        server_info["modlogs"][str(server_id)][user_id][str(new_case_number)] = modlog_entry

        if modlog_type.title() in ["Kick", "Mute", "Ban", "Warn"]:
            server_info["modstats"][str(server_id)].setdefault(moderator_id, {})
            server_info["modstats"][str(server_id)][moderator_id][str(new_case_number)] = {
                "type": modlog_type.title(),
                "timestamp": int(time.time()),
            }

            if modlog_type.title() == "Warn":
                server_info["warnings"][str(server_id)].setdefault(user_id, {})
                warning_case_number = max(map(int, server_info["warnings"][str(server_id)][user_id].keys()), default=0) + 1
                
                server_info["warnings"][str(server_id)][user_id][str(warning_case_number)] = {
                    "reason": reason,
                    "moderator": str(moderator),
                    "time": int(time.time())
                }

    if modlog_channel:
        try:
            await modlog_channel.send(embed=embed)
        except discord.Forbidden:
            raise discord.Forbidden(f"Missing permissions to send messages in modlog channel {modlog_channel.id}")
        except discord.HTTPException as e:
            raise discord.HTTPException(f"Failed to send modlog message: {e}")

    save_file("info/server_info.json", server_info)

async def send_modlog_embed(interaction: discord.Interaction, user: discord.User, page: int):
    server_info = open_file("info/server_info.json")
    print(server_info)
    server_id = str(interaction.guild.id)
    user_id = str(user.id)

    user_logs = server_info["modlogs"].get(server_id, {}).get(user_id, {})
    total_logs = len(user_logs)

    if total_logs == 0:
        await interaction.followup.send(f"No logs found for {user}.", ephemeral=True)
        return None, total_logs, 0

    logs_per_page = 10
    total_pages = (total_logs // logs_per_page) + (1 if total_logs % logs_per_page > 0 else 0)

    if page < 1 or page > total_pages:
        await interaction.followup.send(f"Invalid page number. Please provide a page between 1 and {total_pages}.", ephemeral=True)
        return None, total_logs, total_pages

    embed = discord.Embed(title=f"Modlogs for {user}", color=discord.Color.blue())
    start_index = (page - 1) * logs_per_page
    end_index = start_index + logs_per_page
    logs_to_display = list(user_logs.items())[start_index:end_index]

    for case_number, log in logs_to_display:
        embed.add_field(
            name=f"Case #{case_number}",
            value=(
                f"Type: {log['Type']}\n"
                f"User: {log['User']}\n"
                f"Moderator: {log['Moderator']}\n"
                f"Reason: {log['Reason']}\n"
                f"Time: <t:{log['Time']}:F>"
            ),
            inline=False
        )

    embed.set_footer(text=f"{total_logs} total logs | Page {page} of {total_pages}", icon_url=user.avatar.url)

    return embed, total_logs, total_pages

"""
CLASH ROYALE COMMANDS
"""

async def get_player_data(tag: str):
    api_url = f"https://api.clashroyale.com/v1/players/{tag}"  
    headers = {"Authorization": f"Bearer {cr_api}"}

    async with ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            response_json = await response.json()

            if response.status == 200:
                return response_json
            if response.status == 400:
                return True

async def get_clan_data(clan_tag: str):
    api_url = f"https://api.clashroyale.com/v1/clans/{clan_tag}"
    headers = {"Authorization": f"Bearer {cr_api}"}

    async with ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status == 200:
                clan_data = await response.json()
                return {
                    "name": clan_data.get("name", "N/A"),
                    "tag": clan_data.get("tag", "N/A"),
                    "clanScore": clan_data.get("clanScore", 0),
                    "clanWarTrophies": clan_data.get("clanWarTrophies", 0),
                    "requiredTrophies": clan_data.get("requiredTrophies", 0),
                    "donationsPerWeek": clan_data.get("donationsPerWeek", 0),
                    "members": clan_data.get("members", 0),
                    "description": clan_data.get("description", "No description available."),
                    "type": clan_data.get("type", "N/A"),
                }
            else:
                return None


"""
ROBLOX COMMANDS
"""

async def fetch_roblox_bio(roblox_user_id):
    async with ClientSession() as session:
        url = f"https://users.roblox.com/v1/users/{roblox_user_id}"
        async with session.get(url) as response:
            data = await response.json()
            return data.get("description", "")

async def GetRobloxID(roblox_username):
    async with ClientSession() as session:
        response = await session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [roblox_username], "excludeBannedUsers": True},
        )
        if response.status != 200:
            return None
        data = await response.json()
        if not data["data"]:
            return None
        return data["data"][0]["id"]



"""
MINECRAFT COMMANDS
"""

async def getUUID(interaction: discord.Interaction, username: str):
    async with ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as response:
            if response.status == 200:
                return (await response.json())["id"]
            else:
                await interaction.followup.send(f"The usename is incorrect or the minecraft API is down. Exiting with status: {response.status}")
                return False

"""
INFORMATIVE COMMANDS
"""

def get_next_report_id(reports_data):
    if reports_data:
        return max(map(int, reports_data.keys())) + 1
    return 1

def blacklist_user(user_id):
    member_info = open_file("info/member_info.json")
    if str(user_id) not in member_info:
        member_info[str(user_id)] = {"TicketBlacklist": True}
    else:
        member_info[str(user_id)]["TicketBlacklist"] = True
    save_file("info/member_info.json", member_info)

def is_user_blacklisted(user_id):
    member_info = open_file("info/member_info.json")
    return member_info.get(str(user_id), {}).get("TicketBlacklist", False)


items = open_file("storage/economy/items.json")
eco_path = "storage/economy/economy.json"

def create_account(id):
    players = open_file(eco_path)

    try:
        lastPlayerData = next(reversed(players.values()))
        playerID = lastPlayerData["playerID"] + 1
    except (StopIteration, KeyError):
        playerID = 1

    players[id] = {
        "playerID": playerID,
        "joinTimestamp": int(time.time()),
        "levels": {
            "EXP": 0,
            "retire": 0,
            "prestige": 0,
            "rebirth": 0,
            "evolve": 0,
            # More coming later ig
        },
        "balance": {
            "bank": 5000,
            "purse": 0,
            "maxBank": 25000
        },
        "inventory": {},

        # Advanced later stuff
        "pets": {},
        "gear": {
            "helmet": None,
            "chestplate": None,
            "leggings": None,
            "boots": None,
            "rune": None,
            "ring": None,
            "weapon": None,
        },
        "boosts": {
            "coins": 100,
            "exp": 100,
        },
        "points": {
            "health": 0,
            "damage": 0,
            "speed": 0,
            "extra": 0
        }
    }

    save_file(eco_path, players)

def check_user_stat(
    root: List[str], 
    user: int, 
    value_type: Optional[Union[type, None]] = None
) -> bool:
    ''' 
    For newer versions of the bot auto updating data without needing to add them manually.

    Args:
        root (List[str]): A list representing the path to the nested dictionary keys (e.g., ['balance', 'purse']).
        user (int): The user ID to check data for.
        value_type (Optional[Union[type, None]]): The type of value to set if the key does not exist. 
                                                 None for a dictionary (default), int for 0, str for an empty string.

    Returns: 
        bool: Whether or not the data existed or was initialized during this call.
    '''
    players: Dict[str, Any] = open_file(eco_path)
    user_str: str = str(user)
    
    if user_str not in players:
        create_account(user_str)
    
    players = open_file(eco_path)
    
    current = players[user_str]
    for key in root[:-1]:
        current = current.setdefault(key, {})
    
    final_key = root[-1]
    if final_key not in current:
        if value_type is None:
            current[final_key] = {}
        elif value_type == int:
            current[final_key] = 0
        elif value_type == str:
            current[final_key] = ""
        save_file(eco_path, players)
        return False

    return True


'''

Maybe I'll use this, not sure yet

def get_player_data(id, data):
    players = open_file(eco_path)
    if id not in players:
        create_account(id)
    
    player_data = players[id]
    if data == "balance":
        return player_data["balance"]["bank"], player_data["balance"]["purse"], player_data["balance"]["maxBank"]
'''
# Base currency system setup

async def process_transaction(user_id, transaction_type, amount):
    eco = open_file(eco_path)

    if user_id not in eco:
        create_account(user_id)

    player_data = eco[str(user_id)]
    purse_balance = int(player_data["balance"]["purse"])
    bank_balance = int(player_data["balance"]["bank"])
    max_bank = int(player_data["balance"]["maxBank"])

    if int(amount) <= 0:
        return "The amount must be a positive number."

    if transaction_type == "deposit":
        if purse_balance < int(amount):
            return False, "Insufficient funds in purse."
        if bank_balance + int(amount) > max_bank:
            return False, "This exceeds your bank capacity."
        player_data["balance"]["purse"] -= int(amount)
        player_data["balance"]["bank"] += int(amount)
    elif transaction_type == "withdraw":
        if bank_balance < int(amount):
            return False, "Insufficient funds in bank."
        player_data["balance"]["purse"] += int(amount)
        player_data["balance"]["bank"] -= int(amount)
    else:
        return False, "Invalid transaction type."

    save_file(eco_path, eco)
    
    return True, f"{transaction_type.capitalize()} of {amount} Coins has been processed."

def gambling_stats(user_id, game):
    eco = open_file(eco_path)
    if user_id not in eco:
        create_account(user_id)
    eco = open_file(eco_path)

    user_info = eco[user_id]

    if game not in user_info:
        user_info[game] = {
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "coinsWon": 0,
            "coinsLost": 0
        }

        save_file(eco_path, eco)
    return user_info[game]

def update_stats(user_id, game, result, amount=0):
    eco = open_file(eco_path)
    stats = gambling_stats(user_id, game)
    eco = open_file(eco_path)

    if result == "win":
        stats["wins"] += 1
        stats["coinsWon"] += amount
    elif result == "loss":
        stats["losses"] += 1
        stats["coinsLost"] += amount
    elif result == "draw":
        stats["draws"] += 1

    eco[user_id][game] = stats
    save_file(eco_path, eco)

def convert_number(number: str) -> int:
    """
    Converts shorthand notations like 50m, 1b, 10k to full numbers.
    Ex. 
    50m -> 50000000
    1b -> 1000000000
    10k -> 10000

    Args:
        number (str): The shorthand number as a string.

    Returns:
        int: The full numeric value.
    """
    suffixes = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000, 't': 1_000_000_000_000}
    if not number:
        raise ValueError("No number provided.")

    number = number.lower().strip()
    if number[-1] in suffixes:
        multiplier = suffixes[number[-1]]
        return int(float(number[:-1]) * multiplier)
    return int(number)


async def main():
    try:
        if not await test_hy_key():
            await bot.close()
        print("Hypixel API key is valid.")
        if not await get_player_data(None):
            print("Invalid Clash Royale API key. Please check secrets.env.")
            print("If your key is there, consider checking if your IP is authorized.")
            await bot.close()
        else:
            print("The bot is starting, please give it a minute.")
            await bot.start(token)
    except discord.errors.LoginFailure:
        print("Incorrect bot token has been passed. Please check secrets.env")
    except KeyboardInterrupt: # Ctrl + C
        print("Shutting down the bot...")
        await bot.close()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Bot is shutting down. If an error occurs, you can ignore it.")

if __name__ == "__main__":
    try:
        print("Script loaded.")
        print(f"Current Version: {__version__}")

        try:
            osu_api = Ossapi(int(osu_api), osu_secret)
            print("Osu API key is valid.")
        except ValueError:
            print("Invalid API keys; Are you sure you entered your osu api correctly?")
            print("Automatically exiting, rerun the script to try again.")
            sys.exit()

        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"An unexpected error occurred during bot execution: {e}")
