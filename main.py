"""
Made by LucasLiorLE

Some notes I might forget in the github:
    - Moderation rework (Again), hopefully it works better!
        - Clean command rework (I actually read the docs instead of working on it at 2 am, although it is 2 am...)
        - Purge commands rework as well
    - Blackjack is hurting my brain
    - Status API


Future updates:
    - Economy update (Mainly bj game for now)
    - GD and OSU connect functions
        - More GD and OSU commands as well!

    - Also includes more BTD6 commands
    - A /badges command, which just checks badges for a game without the ingame name like /cgloves

    - API commands
        - Chess.com: https://www.chess.com/news/view/published-data-api
        - Lichess: https://lichess.org/api
        - Clash of clans: https://developer.clashofclans.com/
        - Hypixel (Epically failed like 3 years prior but I have more API knowledge): https://api.hypixel.net/ 

This was last updated: 12/1/24 at 1:55 AM
"""

import json, os, io, re
import random, time, datetime, math
import aiohttp, requests, asyncio, asyncpraw
import yt_dlp, tempfile, traceback
from datetime import datetime, timedelta, timezone

from aiohttp import ClientError
from io import BytesIO
from petpetgif import petpet 
from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageSequence
from moviepy.editor import VideoFileClip, AudioFileClip

from ossapi import Ossapi, UserLookupKey, GameMode, RankingType

import discord
from discord import app_commands
from discord.ext import commands, tasks

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

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.dm_messages = True
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)

logs = {}
log_id_counter = 1

def store_log(log_type: str, message: str) -> int:
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


async def handle_logs(interaction: discord.Interaction, error: Exception, log_type: str = "error"):
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

def parse_duration(duration_str):
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
    return interaction.user.id == original_user.id

class RestrictedView(discord.ui.View):
    def __init__(self, original_user: discord.User):
        super().__init__()
        self.original_user = original_user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_user.id:
            await interaction.response.send_message("You can't interact with this.", ephemeral=True)
            return False
        return True

def open_file(filename):
    with open(filename, "r") as f:
        file_data = json.load(f)
    return file_data

def save_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)

secrets = open_file("storage/secrets.json")

client_id = secrets.get("client_id")
client_secret = secrets.get("client_secret")
user_agent = secrets.get("user_agent")
cr_API = secrets.get("cr_API")
token = secrets.get("token")

osu_id = secrets.get("osu_id")
osu_secret = secrets.get("osu_secret")

hypixel_api = secrets.get("hypixel_api")

osu_api = Ossapi(osu_id, osu_secret)

reddit = asyncpraw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
) 

class ReplyModal(discord.ui.Modal):
    def __init__(self, user, message_id, reply_author):
        super().__init__(title="Reply to User")
        self.user = user
        self.message_id = message_id
        self.reply_author = reply_author
        self.add_item(
            discord.ui.TextInput(
                label="Your reply",
                placeholder="Type your reply here...",
            )
        )

    async def callback(self, interaction: discord.Interaction):
        reply_content = self.children[0].value
        try:
            await self.user.send(
                f"**Reply from {self.reply_author.display_name}:**\n{reply_content}"
            )
            await interaction.response.send_message(
                f"Replied to {self.user.mention}: {reply_content}", ephemeral=True
            )
            reply_log_channel = bot.get_channel(1291626347713790033)
            if reply_log_channel:
                embed = discord.Embed(
                    title="Reply Sent",
                    description=f"**Replied to:** {self.user.mention}\n"
                    f"**Replied by:** {self.reply_author.mention}\n"
                    f"**Original Message ID:** {self.message_id}\n"
                    f"**Reply Content:** {reply_content}",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                )
                await reply_log_channel.send(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed to send the reply. The user may have DMs disabled.", ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Failed to send the DM or log the reply.", ephemeral=True
            )

class ReplyButton(discord.ui.Button):
    def __init__(self, user, message_id):
        super().__init__(label="Reply", style=discord.ButtonStyle.primary)
        self.user = user
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        modal = ReplyModal(self.user, self.message_id, interaction.user)
        await interaction.response.send_modal(modal)

user_last_message_time = {}
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
        for guild in bot.guilds:
            member = guild.get_member(message.author.id)
            if member:
                server_info = open_file("info/server_info.json")
                guild_id = str(guild.id)

                if guild_id in server_info["preferences"] and "dmLogs" in server_info["preferences"][guild_id]:
                    dm_log_channel = bot.get_channel(server_info["preferences"][guild_id]["dmLogs"])
                    if dm_log_channel:
                        embed = discord.Embed(
                            title="Direct Message Received",
                            description=f"**User:** {message.author.mention}\n"
                                        f"**Message:** {message.content or '[No text content]'}\n"
                                        f"**Message ID:** {message.id}",
                            color=discord.Color.blue(),
                            timestamp=message.created_at,
                        )

                        if message.attachments:
                            for attachment in message.attachments:
                                embed.add_field(
                                    name="Attachment",
                                    value=attachment.url,
                                    inline=False,
                                )

                        reply_button = ReplyButton(user=message.author, message_id=message.id)
                        view = discord.ui.View()
                        view.add_item(reply_button)

                        await dm_log_channel.send(embed=embed, view=view)

    if not isinstance(message.channel, discord.DMChannel):
        member_id = str(message.author.id)
        current_time = datetime.now()

        member_data = open_file("info/member_info.json")

        if member_id not in member_data:
            member_data[member_id] = {"EXP": 0}

        last_message_time = user_last_message_time.get(member_id)

        if last_message_time is None or current_time - last_message_time >= timedelta(minutes=1):
            message_length = len(message.content)
            exp_gain = math.floor(message_length / 15)

            member_data[member_id]["EXP"] += exp_gain
            user_last_message_time[member_id] = current_time

            save_file("info/member_info.json", member_data)

        await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.tree.sync()
    status_manager = StatusManager(bot)
    bot.loop.create_task(status_manager.change_status())


"""
GEOMETRY DASH COMMANDS
"""

class GeometryDashCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="gd", description="Geometry Dash related commands")

    @app_commands.command(name="profile", description="Fetch a Geometry Dash profile's data.")
    @app_commands.describe(username="The Geometry Dash username to fetch.")
    async def gdprofile(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://gdbrowser.com/api/profile/{username}") as response:
                    if response.status == 200:
                        data = await response.json()

                        if "username" not in data:
                            await interaction.followup.send(f"User {username} not found.", ephemeral=True)
                            return
                        
                        embed = discord.Embed(title="Geometry Dash Profile",description=f"Profile information for **{data['username']}**",color=discord.Color.blue())
                        
                        embed.add_field(name="Username",value=f"{data['username']} (Account ID: {data['accountID']})",inline=False)
                        
                        embed.add_field(
                            name="Stats",
                            value=(
                                f"<:Stars:1299321915411791922> **Stars**: {data['stars']}\n"
                                f"<:Moons:1299321898169274378> **Moons**: {data['moons']}\n"
                                f"<:Coins:1299321945954713670> **Coins**: {data['coins']}\n"
                                f"<:UserCoins:1299321964867092510> **User Coins**: {data['userCoins']}"
                            ),
                            inline=False
                        )
                        
                        embed.add_field(
                            name="Demons",
                            value=(
                                f"**Total Beaten**: {data['demons']}\n"
                                f"**Classic Demons**:\n"
                                f"<:EasyDemon:1299319586197471253> Easy: {data['classicDemonsCompleted']['easy']}\n"
                                f"<:MediumDemon:1299319602936942635> Medium: {data['classicDemonsCompleted']['medium']}\n"
                                f"<:HardDemon:1299319619571552318> Hard: {data['classicDemonsCompleted']['hard']}\n"
                                f"<:InsaneDemon:1299319639959928872> Insane: {data['classicDemonsCompleted']['insane']}\n"
                                f"<:ExtremeDemon:1299319662995046420> Extreme: {data['classicDemonsCompleted']['extreme']}\n"
                                f"<:WeeklyDemon:1299320499146330152> Weekly: {data['classicDemonsCompleted']['weekly']}\n"
                                f"<:Gauntlet:1299320799458627626> Gauntlet: {data['classicDemonsCompleted']['gauntlet']}\n\n"
                                f"**Platformer Demons**:\n"
                                f"<:EasyDemon:1299319586197471253> Easy: {data['platformerDemonsCompleted']['easy']}\n"
                                f"<:MediumDemon:1299319602936942635> Medium: {data['platformerDemonsCompleted']['medium']}\n"
                                f"<:HardDemon:1299319619571552318> Hard: {data['platformerDemonsCompleted']['hard']}\n"
                                f"<:ExtremeDemon:1299319662995046420> Insane: {data['platformerDemonsCompleted']['insane']}\n"
                                f"<:ExtremeDemon:1299319662995046420> Extreme: {data['platformerDemonsCompleted']['extreme']}"
                            ),
                            inline=False
                        )

                        social_links = ""
                        if data.get("youtube"):
                            social_links += f"[YouTube](https://www.youtube.com/channel/{data['youtube']})\n"
                        if data.get("twitter"):
                            social_links += f"[Twitter](https://twitter.com/{data['twitter']})\n"
                        if data.get("twitch"):
                            social_links += f"[Twitch](https://www.twitch.tv/{data['twitch']})\n"

                        if social_links:
                            embed.add_field(name="Social", value=social_links, inline=False)

                        embed.set_footer(text=f"Rank: {"Leaderboard banned" if data["rank"] == 0 else f"Rank: {data['rank']}"} | Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

                        await interaction.followup.send(embed=embed)
                    else: 
                        await interaction.followup.send(f"Failed to retrieve profile for {username}.", ephemeral=True)
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(GeometryDashCommandGroup())

"""
BTD6 COMMANDS
"""

class BloonsTD6CommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="btd6", description="Bloons Tower Defense 6 related commands")

    @app_commands.command(name="connect", description="Connect your BTD6 account!")
    async def btd6connect(self, interaction: discord.Interaction, oak_key: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if not oak_key:
                embed = discord.Embed(
                    title="How to obtain your Open Access Key (OAK)",
                    description="1. Go in game\n"
                                "2. Go to settings\n"
                                "3. At the bottom, click \"Open Data API\"\n"
                                "4. Generate a new API and click copy\n\n"
                                "[Click this for more information](https://support.ninjakiwi.com/hc/en-us/articles/13438499873937-Open-Data-API)",
                    color=discord.Color.dark_gold)
                embed.set_footer("Please keep in mind you need to renew this once every 90 days.")

                await interaction.followup.send(embed=embed)

            if oak_key:
                member_info = open_file("info/member_info.json")
                discord_user_id = str(interaction.user.id)

                if discord_user_id not in member_info:
                    member_info[discord_user_id] = {}

                member_info[discord_user_id]["btd6oakkey"] = oak_key
                save_file("info/member_info.json", member_info)
                
                await interaction.followup.send("Success! Your BTD6 (Maybe someone else's) was successfully linked.")
        except Exception as error:
            await handle_logs(interaction, error)

        
    @app_commands.command(name="racedata", description="Get race data for a specific BT6 race ID.")
    @app_commands.describe(race_id="ID of the race you want to view the data for.")
    async def btd6racedata(self, interaction: discord.Interaction, race_id: str):
        await interaction.response.defer()
        try:
            url = f"https://data.ninjakiwi.com/btd6/races/{race_id}/leaderboard"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("success"):
                            race_info = data["body"]

                            embed = discord.Embed(
                                title=f"<:btd6Race:1312989026147631154> BTD6 Race: {race_info['name']}",
                                description=f"Map: {race_info['map']}\nMode: {race_info['mode']}\nDifficulty: {race_info['difficulty']}",
                                color=discord.Color.red()
                            )
                            embed.set_thumbnail(url=race_info['mapURL'])
                            embed.add_field(name="Starting Cash", value=f"${race_info['startingCash']}", inline=False)
                            embed.add_field(name="Lives", value=f"{race_info['lives']} / {race_info['maxLives']}", inline=False)
                            embed.add_field(name="Rounds", value=f"Start: {race_info['startRound']} - End: {race_info['endRound']}", inline=False)
                            embed.add_field(name="Power Restrictions", value=f"Powers Disabled: {race_info['disablePowers']}", inline=False)

                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send("Failed to retrieve race data. Please check the race ID and try again.", ephemeral=True)
                    else:
                        await interaction.followup.send("Error occurred while fetching the race data. Please try again later.", ephemeral=True)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="racelb", description="Displays the leaderboard for a specific BTD6 race")
    @app_commands.describe(race_id="ID of the race you want to view the leaderboard for.")
    async def btd6racelb(self, interaction: discord.Interaction, race_id: str):
        await interaction.response.defer()
        try:
            emoji_data = open_file("storage/emoji_data.json")

            url = f"https://data.ninjakiwi.com/btd6/races/{race_id}/leaderboard"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                if 'body' in data:
                    leaderboard = data['body']
                    embed = discord.Embed(
                        title=f"<:btd6Race:1312989026147631154> BTD6 Race Leaderboard: {race_id}",
                        color=discord.Color.orange(),
                    )

                    for i, player in enumerate(leaderboard[:9]):
                        display_name = player['displayName']
                        score = f"{player['score']:,}"
                        profile_url = player['profile']

                        emoji_key = f"btd6Race{['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth', 'Ninth'][i]}"
                        emoji_id = emoji_data.get(emoji_key, "")
                        emoji = f"<:{emoji_key}:{emoji_id}>"

                        embed.add_field(
                            name=f"{emoji} {i + 1}. {display_name}",
                            value=f"<:btd6Trophy:1312993305038032966> **Score**: {score}\n[Profile]({profile_url})",
                            inline=False
                        )

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Unexpected response structure.")
            else:
                await interaction.followup.send("Failed to fetch data. Please try again later.")
        except Exception as error:
            await handle_logs(interaction, error)


    @app_commands.command(name="races", description="Displays the latest BTD6 race events.")
    async def btd6races(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            url = "https://data.ninjakiwi.com/btd6/races"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                if 'body' in data:
                    body = data['body']
                    embed = discord.Embed(
                        title="BTD6 Race Events",
                        color=discord.Color.blue(),
                    )

                    for _, race in enumerate(body):
                        race_name = race['name']
                        race_id = race['id']
                        race_start = f"<t:{int(race['start'] / 1000)}:F>"
                        race_end = f"<t:{int(race['end'] / 1000)}:F>"
                        total_scores = f"{race['totalScores']:,}"

                        embed.add_field(
                            name=f"<:btd6Race:1312989026147631154> Race: {race_name} (ID: {race_id})",
                            value=(
                                f"**Start Time**: {race_start}\n"
                                f"**End Time**: {race_end}\n"
                                f"<:btd6Trophy:1312993305038032966> **Total Scores Submitted**: {total_scores}\n"
                            ),
                            inline=False
                        )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Unexpected response structure.")
            else:
                await interaction.followup.send("Failed to fetch data. Please try again later.")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="profile", description="Displays info about a BTD6 player!")
    @app_commands.describe(oak_key="https://support.ninjakiwi.com/hc/en-us/articles/13438499873937-Open-Data-API")
    async def btd6profile(self, interaction: discord.Interaction, oak_key: str = None):
        await interaction.response.defer()
        try:
            member_info = open_file("info/member_info.json")
            discord_user_id = str(interaction.user.id)
            if (discord_user_id not in member_info or "btd6oakkey" not in member_info[discord_user_id]):
                await interaction.followup.send("You do not have a linked BTD6 account.")
                return
            else:
                oak_key = member_info[discord_user_id]["btd6oakkey"]

            url = f"https://data.ninjakiwi.com/btd6/users/{oak_key}"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                if 'body' in data:
                    body = data['body']

                    display_name = body.get("displayName", "N/A")
                    rank = body.get("rank", "N/A")
                    veteran_rank = body.get("veteranRank", "N/A")
                    achievements = body.get("achievements", "N/A")
                    most_experienced_monkey = body.get("mostExperiencedMonkey", "N/A")
                    avatar_url = body.get("avatarURL", "https://example.com/default-avatar.png")
                    followers = body.get("followers", "N/A")

                    embed = discord.Embed(
                        title=f"{display_name}'s Profile",
                        color=discord.Color.green()
                    )
                    embed.set_thumbnail(url=avatar_url)
                    embed.add_field(name="Rank", value=str(rank), inline=True)
                    if int(rank) > 155:
                        embed.add_field(name="Veteran Rank", value=str(veteran_rank), inline=True)
                    embed.add_field(name="Achievements", value=f"{str(achievements)}/150", inline=True)
                    embed.add_field(name="Most Experienced Monkey", value=most_experienced_monkey, inline=True)
                    embed.add_field(name="Followers", value=str(followers), inline=True)

                    gameplay = body.get("gameplay", {})
                    total_cash_earned = gameplay.get("cashEarned", "N/A")
                    highest_round = gameplay.get("highestRound", "N/A")
                    total_games_won = gameplay.get("gamesWon", "N/A")
                    total_games_played = gameplay.get("gameCount", "N/A")
                    total_monkeys_placed = gameplay.get("monkeysPlaced", "N/A")

                    def format_number(num):
                        if isinstance(num, int):
                            return f"{num:,}"
                        return num

                    embed.add_field(name="Total Cash Earned", value=f"${format_number(total_cash_earned)}", inline=True)
                    embed.add_field(name="Highest Round", value=str(highest_round), inline=True)
                    embed.add_field(name="Total Games Won", value=f"{str(total_games_won)}/{str(total_games_played)}", inline=True)
                    embed.add_field(name="Total Monkeys Placed", value=format_number(total_monkeys_placed), inline=True)

                    towers_placed = body.get("towersPlaced", {})
                    tower_lines = ""
                    if total_monkeys_placed != "N/A" and isinstance(total_monkeys_placed, int):
                        for tower, count in towers_placed.items():
                            if isinstance(count, int):
                                percentage = (count / total_monkeys_placed) * 100
                                tower_lines += f"{re.sub(r'([A-Z])', r' \1', tower).strip().title()}: {format_number(count)} ({percentage:.2f}%)\n"

                    embed.add_field(name="Monkeys Placed by Type", value=tower_lines if tower_lines else "N/A", inline=False)

                    bloons_popped = body.get("bloonsPopped", {})
                    bloon_lines = "\n".join([f"{re.sub(r'([A-Z])', r' \1', bloon_type.replace('Popped', '').replace('Leaked', ' Leaks')).strip().title()}: {format_number(count)}" for bloon_type, count in bloons_popped.items()])
                    embed.add_field(name="Bloons Popped Stats", value=bloon_lines if bloon_lines else "N/A", inline=False)

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Unexpected response structure.")
            else:
                await interaction.followup.send("Failed to fetch data. Please check the user ID or try again later.")
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(BloonsTD6CommandGroup())

"""
OSU COMMANDS
"""

class OsuCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="osu", description="Osu related commands")

    @app_commands.command(name="profile", description="Get osu! profile information")
    @app_commands.describe(username="Username to get data from")
    async def osuprofile(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            user = osu_api.user(username, key=UserLookupKey.USERNAME)
            
            embed = discord.Embed(
                title=f"osu! Profile: {user.username}",
                url=f"https://osu.ppy.sh/users/{user.id}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(name="Username", value=user.username or "N/A", inline=True)
            embed.add_field(name="ID", value=str(user.id) if user.id is not None else "N/A", inline=True)
            
            pp = f"{user.statistics.pp:,}pp" if user.statistics.pp is not None else "N/A"
            rank = f"#{user.statistics.global_rank:,}" if user.statistics.global_rank is not None else "N/A"

            embed.add_field(name="PP", value=pp, inline=True)
            embed.add_field(name="Rank", value=rank, inline=True)
            embed.add_field(name="Country", value=user.country.name or "N/A", inline=True)
            embed.add_field(name="Playcount", value=f"{user.statistics.play_count:,}" if user.statistics.play_count is not None else "N/A", inline=True)
            embed.add_field(
                name="Hit Accuracy",
                value=f"{user.statistics.hit_accuracy:.2f}%" if user.statistics.hit_accuracy is not None else "N/A",
                inline=True,
            )
            embed.add_field(
                name="Total Play Time",
                value=f"{user.statistics.play_time // 3600:,} hours" if user.statistics.play_time is not None else "N/A",
                inline=True,
            )
            embed.set_footer(text="osu! profile data fetched using ossapi")
            
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(OsuCommandGroup())
"""
CLASH ROYALE COMMANDS
"""

async def get_player_data(tag: str):
    api_url = f"https://api.clashroyale.com/v1/players/{tag}"  
    headers = {"Authorization": f"Bearer {cr_API}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            response_json = await response.json()

            if response.status == 200:
                return response_json

async def get_clan_data(clan_tag: str):
    api_url = f"https://api.clashroyale.com/v1/clans/{clan_tag}"
    headers = {"Authorization": f"Bearer {cr_API}"}

    async with aiohttp.ClientSession() as session:
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

class ProfileView(discord.ui.View):
    def __init__(self, player_data, current_page="main"):
        super().__init__(timeout=None)
        self.player_data = player_data
        self.current_page = current_page
        self.main_button = discord.ui.Button(label="Main", style=discord.ButtonStyle.primary)
        self.main_button.callback = self.show_main_page
        self.add_item(self.main_button)
        self.deck_button = discord.ui.Button(label="Deck", style=discord.ButtonStyle.secondary)
        self.deck_button.callback = self.show_deck_page
        self.add_item(self.deck_button)
        self.update_buttons()
        self.emoji_data = self.load_emoji_data()

    def load_emoji_data(self):
        with open("storage/emoji_data.json", "r") as f:
            return json.load(f)

    def update_buttons(self):
        self.main_button.disabled = self.current_page == "main"
        self.deck_button.disabled = self.current_page == "deck"

    async def show_main_page(self, interaction: discord.Interaction):
        self.current_page = "main"
        self.update_buttons()

        embed = self.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def show_deck_page(self, interaction: discord.Interaction):
        self.current_page = "deck"
        self.update_buttons()

        embed = self.create_deck_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_main_embed(self):
        name = self.player_data.get("name", "Unknown")
        user_id = self.player_data.get("tag", "Unknown")
        wins = self.player_data.get("wins", 0)
        losses = self.player_data.get("losses", 0)
        trophies = self.player_data.get("trophies", "Unknown")
        max_trophies = self.player_data.get("bestTrophies", "Unknown")
        arena = self.player_data.get("arena", {}).get("name", "Unknown")
        goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("trophies", "Unknown")
        max_goblin_trophies = self.player_data.get("progress", {}).get("goblin-road", {}).get("bestTrophies", "Unknown")
        goblin_arena = self.player_data.get("progress", {}).get("goblin-road", {}).get("arena", {}).get("name", "Unknown")
        clan_name = self.player_data.get("clan", {}).get("name", "No Clan")
        clan_tag = self.player_data.get("clan", {}).get("tag", "N/A")
        winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

        embed = discord.Embed(title=f"{name}'s Clash Royale Profile", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{name} ({user_id})", inline=False)
        embed.add_field(name="Wins/Losses", value=f"{wins}/{losses} ({winrate:.2f}%)", inline=False)
        embed.add_field(name="<:Trophy:1299093384882950245> Trophy Road", value=f"{trophies}/{max_trophies} ({arena})", inline=False)
        embed.add_field(name="<:Goblin_Trophy:1299093585274343508> Goblin Queen's Journey", value=f"{goblin_trophies}/{max_goblin_trophies} ({goblin_arena})", inline=False)
        embed.add_field(name="<:Trophy:1299093384882950245> Trophy Road", value=f"{trophies}/{max_trophies} ({arena})", inline=False)
        embed.add_field(name="<:Goblin_Trophy:1299093585274343508> Goblin Queen's Journey", value=f"{goblin_trophies}/{max_goblin_trophies} ({goblin_arena})", inline=False)
        embed.add_field(name="Clan", value=f"{clan_name} ({clan_tag})", inline=False)
        return embed

    def create_deck_embed(self):
        embed = discord.Embed(title="Deck Information", color=discord.Color.green())

        current_deck = self.player_data.get("currentDeck", [])
        card_ids = []  

        for index, card in enumerate(current_deck):
                name = card.get("name", "Unknown")
                level = card.get("level", "Unknown")
                star_level = card.get("starLevel", "0")
                emoji = self.get_card_emoji(name)

                card_id = card.get("id")
                if card_id:
                        card_ids.append(str(card_id))

                field_value = f"{emoji} | Level: {level} | Star Level: {star_level}"
                embed.add_field(name=f"Card {index + 1}: {name}", value=field_value, inline=False)

        embed.description=f"[Click here to copy the deck](https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={'%3B'.join(card_ids)}&l=Royals)"

        return embed

    def get_card_emoji(self, card_name):
        formatted_name = ''.join(re.findall(r'[A-Za-z]', card_name))
        emoji_id = self.emoji_data.get(formatted_name)
        if emoji_id:
            return f"<:{formatted_name}:{emoji_id}>"
        return "❓" 

class ClashRoyaleCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="cr", description="Clash Royale related commands")
            
    @app_commands.command(name="connect", description="Connect your Clash Royale profile.")
    @app_commands.describe(tag="Your player tag")
    async def crconnect(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer()
        try:
            if not tag.startswith("#"):
                tag = f"#{tag}"

            player_data = await get_player_data(tag.replace("#", "%23"))
            if not player_data:
                await interaction.followup.send("Failed to retrieve data for the provided player tag.", ephemeral=True)
                return

            random_deck = random.sample(["Giant", "Mini P.E.K.K.A", "Fireball", "Archers", "Minions", "Knight", "Musketeer", "Arrows"], k=8)
            random_deck_str = " ".join(f"`{card}`" for card in random_deck)
            await interaction.followup.send(
                f"Please use the following deck: {random_deck_str}\nYou have 15 minutes to make it, which will be checked per minute.\n"
                "Note that the Clash Royale API can be slow, so response times may vary."
            )

            end_time = datetime.now() + timedelta(minutes=15)
            while datetime.now() < end_time:
                player_data = await get_player_data(tag.replace("#", "%23"))
                current_deck = player_data.get("currentDeck", [])
                player_deck_names = [card.get("name", "Unknown") for card in current_deck]

                if sorted(player_deck_names) == sorted(random_deck):
                    member_info = open_file("info/member_info.json")
                    discord_user_id = str(interaction.user.id)

                    if discord_user_id not in member_info:
                        member_info[discord_user_id] = {}

                    member_info[discord_user_id]["cr_id"] = tag
                    save_file("info/member_info.json", member_info)

                    await interaction.followup.send("Deck matched! Your Clash Royale ID has been successfully linked.")
                    return

                await asyncio.sleep(60)

            await interaction.followup.send("Deck did not match within 15 minutes. Please try again.")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="profile", description="Get Clash Royale player profile data")
    @app_commands.describe(tag="The user's tag (The one with the #, optional)", user="The user ID of the member (optional)")
    async def crprofile(self, interaction: discord.Interaction, tag: str = None, user: str = None):
        await interaction.response.defer()
        try:
            member_info = open_file("info/member_info.json")

            if tag is None:
                user_id = str(interaction.user.id)
                cr_id = member_info.get(user_id, {}).get("cr_id")

                if cr_id:
                    tag = cr_id
                else:
                    await interaction.followup.send("No linked Clash Royale account found.")
                    return
            else:
                if not tag.startswith("#"):
                    tag = "#" + tag.strip()


            player_data = await get_player_data(tag.replace("#", "%23"))

            if player_data:
                view = ProfileView(player_data)
                embed = view.create_main_embed()
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.followup.send(f"Player data not found for tag: {tag}")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="clan", description="Get data about a Clash Royale clan")
    @app_commands.describe(clantag="The clan's tag (the one with the #)")
    async def crclan(self, interaction: discord.Interaction, clantag: str):
        await interaction.response.defer()
        try:
            if not clantag.startswith("#"):
                clantag = "#" + clantag.strip()

            clan_data = await get_clan_data(clantag.replace("#", "%23"))

            if clan_data:
                embed = discord.Embed(title=f"Clan Data for {clan_data['name']}", color=discord.Color.blue())

                embed.add_field(name="<:Clan:1300957220422549514> Name", value=f"{clan_data['name']} ({clan_data['tag']})")
                embed.add_field(name="<:Trophy:1299093384882950245> Clan Score", value=clan_data['clanScore'])
                embed.add_field(name="<:ClanTrophies:1300956037272309850> Clan Trophies", value=clan_data['clanWarTrophies'])
                embed.add_field(name="<:Trophy:1299093384882950245> Required Trophies", value=clan_data['requiredTrophies'])
                embed.add_field(name="<:Cards:1300955092534558850> Weekly Donations", value=clan_data['donationsPerWeek'])
                embed.add_field(name="<:Members:1300956053588152373> Members", value=clan_data['members'])
                embed.add_field(name="<:Clan:1300957220422549514> Description", value=clan_data['description'])
                embed.set_footer(text=f"The clan is currently {clan_data['type']} | Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"Clan data not found for tag: {clantag}")
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(ClashRoyaleCommandGroup())

"""
ROBLOX COMMANDS
"""

async def fetch_roblox_bio(roblox_user_id):
    async with aiohttp.ClientSession() as session:
        url = f"https://users.roblox.com/v1/users/{roblox_user_id}"
        async with session.get(url) as response:
            data = await response.json()
            return data.get("description", "")

async def GetRobloxID(roblox_username):
    async with aiohttp.ClientSession() as session:
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

class RobloxGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="roblox", description="Roblox account-related commands")

    @app_commands.command(name="connect", description="Connect with your Roblox account")
    @app_commands.describe(username="The username to connect to")
    @app_commands.checks.cooldown(1, 60)
    async def rbxconnect(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            color_sequence = " ".join(
                random.choices(
                    ["orange", "strawberry", "pear", "apple", "banana", "watermelon"], k=10
                )
            )
            await interaction.followup.send(
                f"Please update your Roblox bio with this sequence:\n**{color_sequence}**\nYou have 1 minute to complete it."
            )

            await asyncio.sleep(60)

            roblox_user_id = await GetRobloxID(username)
            if roblox_user_id is None:
                await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                return

            bio = await fetch_roblox_bio(roblox_user_id)

            if color_sequence in bio:
                member_info = open_file("info/member_info.json")
                discord_user_id = str(interaction.user.id)

                if discord_user_id not in member_info:
                    member_info[discord_user_id] = {}

                member_info[discord_user_id]["roblox_username"] = username
                member_info[discord_user_id]["roblox_id"] = roblox_user_id
                save_file("info/member_info.json", member_info)

                await interaction.followup.send(f"Success! Your Roblox account is now linked.")

            else:
                await interaction.followup.send("Failed! Your Roblox bio did not match the given sequence.")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="description", description="Provides the description of a Roblox account.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).")
    async def rbxdescription(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None):
        await interaction.response.defer()
        try:
            discord_user_id = str(member.id) or str(interaction.user.id)
            member_info = open_file("info/member_info.json")

            if (discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]):
                await interaction.response.send_message("The specified account (Or yours) is not linked.")
                return

            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.response.send_message(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                roblox_user_id = member_info[discord_user_id]["roblox_id"]

            bio = await fetch_roblox_bio(roblox_user_id)
            embed = discord.Embed(title=f"User Description for {roblox_user_id}", description=bio, color=0x808080)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="info", description="Provides info about your linked Roblox account.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).")
    async def rbxinfo(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None):
        await interaction.response.defer()
        try:
            discord_user_id = str(member.id) or str(interaction.user.id)
            member_info = open_file("info/member_info.json")

            if (discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]):
                await interaction.response.send_message("The specified account (Or yours) is not linked.")
                return

            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                roblox_user_id = member_info[discord_user_id]["roblox_id"]

            async with aiohttp.ClientSession() as session:
                async def fetch_count(roblox_user_id: int, type: str):
                    async with session.get(f"https://friends.roblox.com/v1/users/{roblox_user_id}/{type}/count") as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("count", 0)

                async def fetch_user_presence(roblox_user_id: int):
                    async with session.post("https://presence.roblox.com/v1/presence/users", json={"userIds": [roblox_user_id]}) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data["userPresences"][0]

                async def fetch_user_info(roblox_user_id: int):
                    async with session.get(f"https://users.roblox.com/v1/users/{roblox_user_id}") as response:
                        if response.status == 200:
                            return await response.json()


                async def check_premium(roblox_user_id: int):
                    headers = {'accept': 'application/json'}
                    url = f"https://premiumfeatures.roblox.com/v1/users/{roblox_user_id}/validate-membership"

                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()

                is_premium = await check_premium(roblox_user_id)
                friends_count = await fetch_count(roblox_user_id, "friends")
                followers_count = await fetch_count(roblox_user_id, "followers")
                following_count = await fetch_count(roblox_user_id, "followings")
                presence_data = await fetch_user_presence(roblox_user_id)
                user_info = await fetch_user_info(roblox_user_id)

            embed = discord.Embed(title=f"{'<:Premium:1298832636805910589> ' if is_premium else ''}Roblox Account Info", color=0x808080)
            display_name = user_info.get("displayName", "N/A")
            username = user_info.get("name", "N/A")
            embed.add_field(name="Username", value=f"{display_name} (@{username})", inline=False)
            embed.add_field(name="Friends/Followers/Following", value=f"Friends: {friends_count}\nFollowers: {followers_count}\nFollowing: {following_count}", inline=False)

            status = "Offline" if presence_data["userPresenceType"] == 0 else "Ingame" if presence_data["userPresenceType"] == 1 else "Online"
            last_online = datetime.strptime(presence_data["lastOnline"][:-1], "%Y-%m-%dT%H:%M:%S.%f")
            last_online_str = last_online.strftime("%m-%d-%Y")  
            embed.add_field(name="Status", value=f"{status} | Last online: {last_online_str}", inline=False)
            creation_date = datetime.strptime(user_info["created"][:-1], "%Y-%m-%dT%H:%M:%S.%f")
            creation_date_str = creation_date.strftime("%m-%d-%Y")  
            embed.set_footer(text=f"Account created: {creation_date_str} | Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="avatar", description="Provides a Roblox account's avatar.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).", items="Whether or not to display the list of currently worn items (default: False).")
    async def rbxavatar(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None, items: bool = False):
        await interaction.response.defer()
        try:
            discord_user_id = str(member.id) or str(interaction.user.id)
            member_info = open_file("info/member_info.json")

            if (discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]):
                await interaction.response.send_message("The specified account (Or yours) is not linked.")
                return

            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                roblox_user_id = member_info[discord_user_id]["roblox_id"]

            async with aiohttp.ClientSession() as session:
                async def get_avatar_items(session, roblox_user_id: int):
                    url = f"https://avatar.roblox.com/v1/users/{roblox_user_id}/currently-wearing"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if not data['assetIds']:  
                                return None  
                            return data['assetIds']
                        else:
                            return None

                async def get_avatar_thumbnail(session, roblox_user_id: int):
                    url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={roblox_user_id}&size=720x720&format=Png&isCircular=false"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and data['data'][0]['state'] == 'Completed':
                                return data['data'][0]['imageUrl']
                            else:
                                return None
                        else:
                            return None

                avatar_thumbnail_url = await get_avatar_thumbnail(session, roblox_user_id)

                if items:
                    asset_ids = await get_avatar_items(session, roblox_user_id)
                else:
                    asset_ids = None

                embed = discord.Embed(title="Roblox Avatar View",color=discord.Color.blue())
                embed.set_image(url=avatar_thumbnail_url)  
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

                if items:
                    if asset_ids:
                        urls = [f"https://www.roblox.com/catalog/{asset_id}" for asset_id in asset_ids]
                        url_list = '\n'.join(urls)
                        embed.description = url_list  
                    else:
                        embed.description = "This user has no currently worn items."  

                await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(RobloxGroup())

class GloveView(discord.ui.View):
    def __init__(
        self,
        badge_embed,
        glove_embed,
        full_glove_data,
        obtained_gloves,
        roblox_id,
        owned_gamepasses,
        not_owned_gamepasses,
    ):
        super().__init__(timeout=None)
        self.badge_embed = badge_embed
        self.glove_embed = glove_embed
        self.full_glove_data = full_glove_data
        self.obtained_gloves = obtained_gloves
        self.roblox_id = roblox_id
        self.owned_gamepasses = owned_gamepasses
        self.not_owned_gamepasses = not_owned_gamepasses
        self.current_page = "glove_data"
        self.update_buttons()

    def update_buttons(self):
        self.glove_data_button.disabled = self.current_page == "glove_data"
        self.full_glove_data_button.disabled = self.current_page == "full_glove_data"
        self.additional_badges_button.disabled = (self.current_page == "additional_badges")
        self.gamepass_data_button.disabled = self.current_page == "gamepass_data"

    @discord.ui.button(label="Glove Data", style=discord.ButtonStyle.secondary)
    async def glove_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        
        self.current_page = "glove_data"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.glove_embed], view=self)

    @discord.ui.button(label="Full Glove Data", style=discord.ButtonStyle.secondary)
    async def full_glove_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return

        self.current_page = "full_glove_data"
        self.update_buttons()

        full_glove_description = "\n".join(
            [
                f"{glove} - <t:{int(datetime.strptime(obtain_date[:19], '%Y-%m-%dT%H:%M:%S').timestamp())}:F>"
                for glove, obtain_date in self.obtained_gloves.items()
            ]
        )

        full_glove_embed = discord.Embed(
            title=f"Full Glove Data for {interaction.user.name}",
            description=full_glove_description
            if full_glove_description
            else "No gloves obtained.",
            color=0xFF0000,
        )

        await interaction.response.edit_message(embeds=[full_glove_embed], view=self)

    @discord.ui.button(label="Additional Badges", style=discord.ButtonStyle.secondary)
    async def additional_badges_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "additional_badges"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.badge_embed], view=self)

    @discord.ui.button(label="Gamepass Data", style=discord.ButtonStyle.secondary)
    async def gamepass_data_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "gamepass_data"
        self.update_buttons()

        gamepass_embed = discord.Embed(title=f"Gamepass Data for {interaction.user.name}", color=0xFF0000)
        gamepass_embed.add_field(name="Owned", value=", ".join(self.owned_gamepasses) if self.owned_gamepasses else "None", inline=False)
        gamepass_embed.add_field(name="Not Owned", value=", ".join(self.not_owned_gamepasses) if self.not_owned_gamepasses else "None", inline=False)

        await interaction.response.edit_message(embed=gamepass_embed, view=self)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="cgloves", description="Check all the user's gloves in slap battles.")
@app_commands.describe(username="The user to check gloves for (leave empty to check your own)", ephemeral="If the message is hidden (Useful if no perms)")
async def cgloves(interaction: discord.Interaction, username: str = None, member: discord.Member = None, ephemeral: bool = True):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        discord_user_id = str(member.id) or str(interaction.user.id)

        if username is None:
            member_info = open_file("info/member_info.json")
            if (discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]):
                await interaction.response.send_message("The specified account (Or yours) is not linked.")
                return
            roblox_id = member_info[discord_user_id]["roblox_id"]
        else:
            roblox_id = await GetRobloxID(username)
            if roblox_id is None:
                await interaction.followup.send(f"No data found for the username: {username}")
                return

        gloves = open_file("storage/gloves.json")
        all_badge_ids = [badge_id for badge_ids in gloves.values() for badge_id in badge_ids]
        url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, all_badge_ids))}"

        async with aiohttp.ClientSession() as session:
            response = await session.get(url)

            if response.status == 200:
                data = await response.json()
                if not data["data"]:
                    await interaction.followup.send(f"No badges found for the user: {username if username else interaction.user.name}")
                    return

                owned = [
                    glove
                    for glove, badge_ids in gloves.items()
                    if all(
                        any(badge.get("badgeId") == badge_id for badge in data["data"])
                        for badge_id in badge_ids
                    )
                ]
                not_owned = [glove for glove in gloves.keys() if glove not in owned]

                total_gloves = len(gloves)
                owned_gloves = len(owned)
                glove_percentage = (owned_gloves / total_gloves) * 100
                glove_percentage_str = f"{glove_percentage:.1f}"

                glove_embed = discord.Embed(
                    title=f"SB Gloves Data for {username if username else interaction.user.name} ({roblox_id}):",
                    description=f"Badge gloves:\n{owned_gloves}/{total_gloves} badge gloves owned ({glove_percentage_str}%)",
                    color=0xFF0000,
                )
                glove_embed.add_field(
                    name="OWNED", 
                    value=", ".join(owned) if owned else "None", 
                    inline=False
                )
                glove_embed.add_field(
                    name="NOT OWNED",
                    value=", ".join(not_owned) if not_owned else "None",
                    inline=False,
                )

                obtained_gloves = {
                    glove: badge["awardedDate"]
                    for glove, badge_ids in gloves.items()
                    for badge_id in badge_ids
                    for badge in data["data"]
                    if badge.get("badgeId") == badge_id
                }

                additional_badges = {
                    "Welcome": 2124743766,
                    "You met the owner": 2124760252,
                    "you met snow": 2124760875,
                    "[REDACTED]": 2124760911,
                    "Divine Punishment": 2124760917,
                    "really?": 2124760923,
                    "barzil": 2124775097,
                    "The one": 2124807750,
                    "Ascend": 2124807752,
                    "1 0 0": 2124836270,
                    'The "Reverse" Incident': 2124912059,
                    "Clipped Wings": 2147535393,
                    "Apostle of Judgement": 4414399146292319,
                    "court evidence": 2124760907,
                    "duck": 2124760916,
                    "The Lone Orange": 2128220957,
                    "The Hunt Event": 1195935784919838,
                    "The Backrooms": 2124929812,
                    "pog": 2124760877,
                }

                badge_ids = ",".join(map(str, additional_badges.values()))
                url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={badge_ids}"

                async with aiohttp.ClientSession() as session:
                    response = await session.get(url)
                    if response.status == 200:
                        data = await response.json()

                        badge_embed = discord.Embed(
                            title=f"Additional Badges for {username if username else interaction.user.name} ({roblox_id}):",
                            color=0xFF0000,
                        )

                        obtained_badges = {badge["badgeId"]: badge["awardedDate"] for badge in data["data"]}

                        for badge_name, badge_id in additional_badges.items():
                            if badge_id in obtained_badges:
                                awarded_date = obtained_badges[badge_id]
                                date, time, fraction = awarded_date.replace("Z", "+0000").partition(".")
                                fraction = fraction[: fraction.index("+")][:6] + "+0000"
                                awarded_date = f"{date}.{fraction}"
                                awarded_date = datetime.strptime(awarded_date, "%Y-%m-%dT%H:%M:%S.%f%z")
                                epoch_time = int(awarded_date.timestamp())
                                badge_embed.add_field(
                                    name=f"<:check:1292269189536682004> | {badge_name}",
                                    value=f"Obtained on <t:{epoch_time}:F>",
                                    inline=False,
                                )
                            else:
                                badge_embed.add_field(
                                    name=f"❌ | {badge_name}",
                                    value="Not obtained",
                                    inline=False,
                                )

                        gamepass_items = {
                            "2x Slaps": 15037108,
                            "5x Slaps": 15037147,
                            "Radio": 16067226,
                            "nothing": 16127797,
                            "OVERKILL": 16361133,
                            "Spectator": 19150776,
                            "Custom death audio": 21651535,
                            "CUSTOM GLOVE": 33742082,
                            "Animation Pack": 37665008,
                            "Vampire": 45176930,
                            "Ultra Instinct": 85895851,
                            "Cannoneer": 174818129,
                        }

                        owned_gamepasses = []
                        not_owned_gamepasses = []

                        async with aiohttp.ClientSession() as session:
                            for item_name, item_id in gamepass_items.items():
                                url = f"https://inventory.roblox.com/v1/users/{roblox_id}/items/1/{item_id}/is-owned"
                                async with session.get(url) as item_response:
                                    if item_response.status == 200:
                                        item_data = await item_response.json()
                                        if item_data:
                                            owned_gamepasses.append(item_name)
                                        else:
                                            not_owned_gamepasses.append(item_name)

                        view = GloveView(
                            badge_embed,
                            glove_embed,
                            full_glove_data=obtained_gloves,
                            obtained_gloves=obtained_gloves,
                            roblox_id=roblox_id,
                            owned_gamepasses=owned_gamepasses,
                            not_owned_gamepasses=not_owned_gamepasses,
                        )

                        await interaction.followup.send(embeds=[glove_embed], view=view)

                    else:
                        await interaction.followup.send("An error occurred while fetching the user's badges.")
            else:
                await interaction.followup.send("An error occurred while fetching the user's gloves.")

    except Exception as error:
        await handle_logs(interaction, error)

"""
MINECRAFT COMMANDS
"""

async def getUUID(interaction: discord.Interaction, username: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as response:
            if response.status == 200:
                return (await response.json())["id"]
            else:
                await interaction.followup.send(f"The usename is incorrect or the minecraft API is down. Exiting with status: {response.status}")
                return False

@bot.tree.command(name="uuid", description="Get a Minecraft UUID based on a username")
@app_commands.describe(username="A Minecraft username")
async def uuid(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    uuid_result = await getUUID(interaction, username)
    if uuid_result:
        await interaction.followup.send(f"The UUID for {username} is {uuid_result}")

"""
HYPIXEL COMMANDS
"""
class SkyblockCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="sb", description="Hypixel skyblock commands")


bot.tree.add_command(SkyblockCommandsGroup())
"""
FUN COMMANDS
"""

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="ccp", description="Ping a user and send a message.")
@app_commands.describe(choice="Select whether to increase or decrease the Social Credit Score", user_id="The ID of the user to mention",)
@app_commands.choices(
    choice=[
        app_commands.Choice(name="Increase", value="increase"),
        app_commands.Choice(name="Decrease", value="decrease"),
    ]
)
async def ccp(interaction: discord.Interaction, choice: str, user_id: str):
    await interaction.response.defer()
    try:
        if choice == "increase":
            message = f"<@{user_id}> (我们的) Good work citizen, and glory to the CCP! Remember to redeem your food units after 12:00 P.M."
        elif choice == "decrease":
            message = (
                f"<@{user_id}> (我们的) :arrow_double_down: Your Social Credit Score has decreased "
                ":arrow_double_down:. Please refrain from making more of these comments or we will have "
                "to send a Reeducation Squad to your location. Thank you! Glory to the CCP! :flag_cn: (我们的)"
            )

        await interaction.followup.send(message)
    except Exception as error:
        await handle_logs(interaction, error)

class MemeifyGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="memeify", description="Generate memes!")

    @app_commands.command(name="spongebob", description="Generates a Spongebob meme")
    @app_commands.describe(text="The text you want to show on the paper")
    async def spongebob(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://memeado.vercel.app/api/spongebob?text={text}") as response:
                    if response.status == 200:
                        meme_url = str(response.url)
                        await interaction.followup.send(content=meme_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="drakelikehate", description="Generates a Drake Like Hate meme")
    @app_commands.describe(text1="The text for the 'Like' part", text2="The text for the 'Hate' part")
    async def drakelikehate(self, interaction: discord.Interaction, text1: str, text2: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://memeado.vercel.app/api/drakelikehate?text1={text1}&text2={text2}"
                async with session.get(url) as response:
                    if response.status == 200:
                        meme_url = str(response.url)
                        await interaction.followup.send(content=meme_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as error:
            await handle_logs(interaction, error)
            
    @app_commands.command(name="petpet", description="Creates a pet-pet gif from a user's avatar, emoji, custom image URL, or uploaded file")
    @app_commands.describe(
        member="Use a member's avatar",
        url="URL to an image to create a pet-pet gif (optional)",
        attachment="File attachment to use for the pet-pet gif (optional)"
    )
    async def petpet(self, interaction: discord.Interaction, member: discord.Member = None, url: str = None, attachment: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if attachment:
                image_data = await attachment.read()

            elif url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            await interaction.followup.send("Failed to retrieve the image from the URL.")
                            return
                        image_data = await response.read()

            elif isinstance(member, discord.Member):
                image_data = await member.display_avatar.read()
            else:
                image_data = await interaction.member.display_avatar.read()

            source = BytesIO(image_data)
            dest = BytesIO()
            petpet.make(source, dest)
            dest.seek(0)

            await interaction.followup.send(file=discord.File(dest, filename="petpet.gif"))
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(MemeifyGroup())

@bot.tree.command(name="say", description="Say a message in a channel")
@app_commands.describe(
    channel="The user to talk in",
    message="The message to send",
    attachment="An optional attachment to include",
    message_id="An optional message to reply to",
    ephemeral="Whether the message will be ephemeral for others or not"
)
@commands.has_permissions(manage_messages=True)
async def say(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str = None,
    attachment: discord.Attachment = None,
    message_id: str = None,
    ephemeral: bool = False
):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        reference_message = None

        if message_id:
            try:
                reference_message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                await interaction.followup.send(f"Message with ID {message_id} not found in {channel.mention}.")
                return
            except discord.HTTPException as e:
                await interaction.followup.send(f"An error occurred while fetching the message: {e}")
                return
            
        # Testing if file=None will return an error or not.
        await channel.send(content=message, file=await attachment.to_file(), reference=reference_message)

        '''
        if attachment:
            await channel.send(content=message, file=await attachment.to_file(), reference=reference_message)
        else:
            await channel.send(content=message, reference=reference_message)
        '''

        await interaction.followup.send(f"Sent '{message}' to {channel.mention}")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="dm", description="Directly message a person.")
@app_commands.describe(
    user="The user to DM",
    message="The message to send to them",
    attachment="An optional attachment to include",
)
async def dm(
    interaction: discord.Interaction,
    member: discord.Member,
    message: str = None,
    attachment: discord.Attachment = None,
):
    await interaction.response.defer()
    try:
        await member.send(content=message, file=await attachment.to_file())
        await interaction.followup.send(f"Sent '{message}' to {member}")              
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="fact", description="Fetches a random fact.")
async def fact(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        url = "https://uselessfacts.jsph.pl/random.json?language=en"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            embed = discord.Embed(title="Random Fact 🤓", description=data["text"], color=0x9370DB)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the fact.")
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="joke", description="Fetches a random joke.")
async def joke(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        url = "https://official-joke-api.appspot.com/jokes/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            if "setup" in data and "punchline" in data:
                joke_setup = data["setup"]
                joke_punchline = data["punchline"]
                await interaction.followup.send(content=f"**{joke_setup}**\n\n*||{joke_punchline}||*")
            else:
                await interaction.followup.send(content="Sorry, I couldn't fetch a joke right now. Try again later!")
        else:
            await interaction.followup.send(content="An error occurred while fetching the joke.")
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="cat", description="Fetches a cute cat picture.")
async def cat(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        url = "https://api.thecatapi.com/v1/images/search"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            cat_image_url = data[0]["url"]

            embed = discord.Embed(title="Here's a cute cat for you!", color=0xFFA07A)
            embed.set_image(url=cat_image_url)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the cat picture.")
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="dog", description="Fetches an adorable dog picture.")
async def dog(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        url = "https://dog.ceo/api/breeds/image/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            dog_image_url = data["message"]

            embed = discord.Embed(title="Here's a cute dog for you!", color=0xADD8E6)
            embed.set_image(url=dog_image_url)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the dog picture.")
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="quote", description="Fetches an inspirational quote.")
async def quote(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        url = "https://zenquotes.io/api/random"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()[0]

            embed = discord.Embed(title=data["q"], description=f"-{data['a']}", color=0x66CDAA)
            await interaction.followup.send(content=None, embed=embed)
        else:
            await interaction.followup.send(content="An error occurred while fetching the quote.")
    except Exception as error:
        await handle_logs(interaction, error)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
@bot.tree.command(name="meme", description="Fetches a funny meme!")
async def meme(interaction: discord.Interaction, ephemeral: bool = False):
    await interaction.response.defer(ephemeral=ephemeral)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://meme-api.com/gimme") as response:
                if response.status == 200:  
                    data = await response.json()
                    meme_data = data[0]

                    embed = discord.Embed(title=f"({meme_data['title']})[{meme_data['postLink']}]", color=0x66CDAA)
                    embed.set_image(url=meme_data["url"])
                    embed.set_footer(text=f"{meme_data['ups']} Upvotes | By: {meme_data['author']} | Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("An error occurred when trying to fetch the meme")
    except Exception as error:
        await handle_logs(interaction, error)

"""
INFORMATIVE COMMANDS
"""
@bot.tree.command(name="help", description="Get details about a specific command.")
@app_commands.describe(command="The command you'd like to learn about.")
async def help_command(interaction: discord.Interaction, command: str):
    commands_data = open_file("info/commands.json")
    
    for group, group_commands in commands_data.items():
        for cmd_name, cmd_details in group_commands.items():
            if cmd_name.lower() == command.lower():
                arguments = cmd_details.get("arguments", {})
                required_args = [f"[{arg}]" for arg, details in arguments.items() if details.get("required", False)]
                optional_args = [f"({arg})" for arg, details in arguments.items() if not details.get("required", False)]
                arg_list = " ".join(required_args + optional_args)

                embed = discord.Embed(
                    title=f"/{cmd_name.lower()} {arg_list}",
                    description=cmd_details.get("description", "No description provided."),
                    color=discord.Color.blue()
                )
                
                if "example" in cmd_details:
                    embed.add_field(name="Example", value=cmd_details["example"], inline=False)

                for arg_name, arg_details in arguments.items():
                    arg_info = (
                        f"**Required**: {arg_details.get('required', False)}\n"
                        f"**Default**: {arg_details.get('default', 'None')}\n"
                        f"**Type**: {arg_details.get('type', 'Unknown')}\n"
                        f"**Description**: {arg_details.get('description', 'No description provided.')}")
                    embed.add_field(name=arg_name.title(), value=arg_info, inline=False)

                embed.set_footer(text="[Required Arguments] (Optional Arguments)")

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

    await interaction.response.send_message(f"Command `{command}` not found. Please check your input and try again.", ephemeral=True)


@bot.tree.command(name="mlevel", description="Calculate mee6 levels and how long it will take you to achieve them.")
@app_commands.describe( 
    current_level="Your current level",
    current_exp="Your current EXP in that level",
    target_level="The level you want to achieve",
    hours_per_day="Hours you will chat everyday"
)
async def mlevel(interaction: discord.Interaction, current_level: int, current_exp: int, target_level: int, hours_per_day: int):
    await interaction.response.defer()
    try:
        def exp_required(level):
            total_exp = 0
            for l in range(1, level + 1):
                total_exp += 5 * (l ** 2) + 50 * l + 100
            return total_exp

        required_exp = exp_required(target_level) - (exp_required(current_level) + current_exp)

        embed = discord.Embed(
            title="Mee6 Level Calculator",
            description=f"Estimated based off you chat {hours_per_day} hours per day and gain {hours_per_day * 1200} EXP.\n**Other Info**\nCurrent Level: {current_level}\nCurrent EXP: {current_exp}\nTarget Level: {target_level}\nTotal EXP: {exp_required(current_level)}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Required EXP", value=f"{required_exp:,}")
        embed.add_field(name="Estimated Messages", value=f"{round((required_exp / 20) * 1.5):,}")
        embed.add_field(name="Estimated Days", value=f"{round(required_exp / (hours_per_day * 1200)):,}")
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="error", description="Allows you to view a certain error.")
async def view_error(interaction: discord.Interaction, error_id: int):
    await interaction.response.defer()

    if interaction.user.id not in botTesters:
        await interaction.followup.send("You do not have permission to use this command.")
        return

    for log_type, log_entries in logs.items():
        for entry in log_entries:
            if entry["ID"] == error_id:
                timestamp = entry["Time"]
                error_message = entry.get("Message", "No error message available.")
                
                embed = discord.Embed(
                    title=f"Error ID: {error_id}",
                    color=discord.Color.red()
                )
                embed.add_field(name="Type", value=log_type.capitalize(), inline=False)
                embed.timestamp = datetime.utcfromtimestamp(time.time())
                
                chunks = [error_message[i:i + 1024] for i in range(0, len(error_message), 1024)]
                for idx, chunk in enumerate(chunks):
                    embed.add_field(
                        name=f"Error (Part {idx + 1})" if len(chunks) > 1 else "Error",
                        value=chunk,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                return

    await interaction.followup.send(f"No error found with ID {error_id}", ephemeral=True)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="ping", description="Shows your latency and the bot's latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        start_time = time.time()
        processing_start_time = time.time()
        await asyncio.sleep(0.1)
        processing_time = (time.time() - processing_start_time) * 1000
        end_time = time.time()
        round_trip_latency = round((end_time - start_time) * 1000)
        bot_latency = round(bot.latency * 1000)
        color = (0x00FF00 if bot_latency < 81 else 0xFFFF00 if bot_latency < 201 else 0xFF0000)
        embed = discord.Embed(
            title="Pong! 🏓",
            description=(
                f"Your approximate latency: {round_trip_latency}ms\n"
                f"Bot's latency: {bot_latency}ms\n"
                f"Processing Time: {processing_time:.2f}ms\n"
                f"Response Time: {round_trip_latency + processing_time:.2f}ms"
            ),
            color=color,
        )
        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="info", description="Displays information about the bot.")
async def info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        embed = discord.Embed(title="Bot Info", description="This bot is developed by LucasLiorLE.", color=0x808080)
        embed.add_field(name="Version", value="v1.1.21")
        embed.add_field(name="Server Count", value=len(bot.guilds))
        embed.add_field(name="Library", value="Discord.py")
        embed.add_field(name="Other", value="made by lucasliorle\nEstimated time: 90 hours+")
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

        button = discord.ui.Button(label="Visit Website", url="https://lucasliorle.github.io")
        view = discord.ui.View()
        view.add_item(button)

        await interaction.followup.send(embed=embed, view=view)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="serverinfo", description="Shows information about the server.")
async def serverinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        guild = interaction.guild

        embed = discord.Embed(title="Server Info", color=0x808080)
        embed.add_field(name="Owner", value=guild.owner.mention)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Roles", value=len([role.name for role in guild.roles]))
        embed.add_field(name="Category Channels", value=len(guild.categories))
        embed.add_field(name="Text Channels", value=len([channel for channel in guild.text_channels]))
        embed.add_field(name="Voice Channels", value=len([channel for channel in guild.voice_channels]))
        embed.add_field(name="Role List", value=", ".join([role.name for role in guild.roles]), inline=False)
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Server Created", value=f"{guild.created_at.strftime("%m/%d/%Y %I:%M %p")}")
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="roleinfo", description="Provides information for a role.")
@app_commands.describe(role="The role to get the info for")
async def roleinfo(interaction: discord.Interaction, role: discord.Role):
    await interaction.response.defer()
    try:
        permissions = role.permissions
        permissions_list = [perm for perm, value in permissions if value]

        embed = discord.Embed(title=f"Role info for {role.name}", color=role.color)
        embed.add_field(name="Role ID", value=role.id)
        embed.add_field(name="Color", value=str(role.color))
        embed.add_field(name="Mentionable", value=str(role.mentionable))
        embed.add_field(name="Hoist", value=str(role.hoist))
        embed.add_field(name="Position",value=f"{role.position}/{len(interaction.guild.roles)}",)
        embed.add_field(name="Permissions",value=", ".join(permissions_list) if permissions_list else "No permissions")
        embed.add_field(name="Member Count", value=len(role.members))
        embed.add_field(name="Role Created On",value=f"{role.created_at.strftime("%m/%d/%Y %H:%M")} ({(datetime.now(timezone.utc) - role.created_at).days} days ago)")

        if role.icon:
            embed.set_thumbnail(url=role.icon.url)

        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="userinfo", description="Provides information about a user.")
@app_commands.describe(user="The member to get the info for",)
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer(ephemeral=True)
    try:
        member = member or interaction.user
        embed = discord.Embed(title="User Info", color=0x808080)
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="Username", value=member.display_name)
        embed.add_field(name="User ID", value=member.id)
        embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"))
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"))
        embed.add_field(name="Roles", value=", ".join([role.name for role in member.roles]))
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

class AvatarGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="avatar", description="Avatar-related commands")

    @app_commands.command(name="get", description="Displays a user's global avatar.")
    @app_commands.describe(user="The member to get the avatar for")
    async def get(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x808080)
            embed.set_image(url=member.avatar.url)
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="server", description="Displays a user's server-specific avatar if available.",)
    @app_commands.describe(user="The member to get the server-specific avatar for")
    async def server(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Server Avatar", color=0x808080)
            embed.set_image(url=member.display_avatar.url)  
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(AvatarGroup())

@bot.tree.command(name="status", description="Check the status of a website.")
@app_commands.describe(website="Link to the website.")
async def status(interaction: discord.Interaction, website: str):
    await interaction.response.defer()

    if not website.startswith(("http://", "https://")):
        website = "http://" + website

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(website, timeout=5) as response:
                status_code = response.status
                if 200 <= status_code < 300:
                    message = f"<:check:1292269189536682004> The website `{website}` is **up**! Status Code: `{status_code}`."
                else:
                    message = f"⚠️ The website `{website}` returned a **problematic** status. Status Code: `{status_code}`."
        except ClientError as e:
            message = f"❌ The website `{website}` is **down** or unreachable. Error: `{e}`"
        except asyncio.TimeoutError:
            message = f"❌ The request to `{website}` timed out after 5 seconds."

    await interaction.followup.send(message)

@bot.tree.command(name="define", description="Define a word")
@app_commands.describe(word="The word you want to define")
async def define(interaction: discord.Interaction, word: str):
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as response:
                if response.status != 200:
                    await interaction.followup.send("Could not find the definition.")
                    return
                
                data = await response.json()
        
        entry = data[0]
        phonetic = entry.get('phonetics', [{}])[0].get('text', 'N/A')
        origin = entry.get('origin', 'N/A')
        meanings = entry.get('meanings', [])
        
        embed = discord.Embed(title=f"Definition for **{word}** ({phonetic})", color=discord.Color.blue())

        if origin != "N/A":
            embed.add_field(name="Origin", value=origin, inline=False)

        for meaning in meanings:
            part_of_speech = meaning.get("partOfSpeech", "N/A")
            definitions = meaning.get("definitions", [])

            for definition in definitions:
                field_value = f"**Definition**: {definition.get('definition', '') or 'Nothing'}\n"
                field_value += f"**Example**: {definition.get('example', 'Nothing')}\n"

                synonyms = definition.get("synonyms", [])
                antonyms = definition.get("antonyms", [])
                if synonyms:
                    field_value += f"**Synonyms**: {', '.join(synonyms)}\n"
                if antonyms:
                    field_value += f"**Antonyms**: {', '.join(antonyms)}\n"

                embed.add_field(name=part_of_speech.capitalize(), value=field_value, inline=False)

        audio_urls = [phonetic.get("audio", "") for phonetic in entry.get("phonetics", []) if phonetic.get("audio")]

        if audio_urls:
            audio_url = audio_urls[0].lstrip("//")
            audio_file_name = f"{word}_pronunciation.mp3"

            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url) as audio_response:
                    if audio_response.status == 200:
                        with open(audio_file_name, 'wb') as f:
                            f.write(await audio_response.read())
            
            await interaction.followup.send(embed=embed, file=discord.File(audio_file_name))
            os.remove(audio_file_name)
        else:
            await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

class Convert(app_commands.Group):
    def __init__(self):
        super().__init__(name="convert", description="Image conversion commands")

    @app_commands.command(name="image", description="Convert an uploaded image to a specified format")
    @app_commands.describe(
        image="The image file you want to convert.", 
        format="The format you want to convert the image to.",
        ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="JPEG", value="jpeg"),
            app_commands.Choice(name="PNG", value="png"),
            app_commands.Choice(name="WEBP", value="webp"),
            app_commands.Choice(name="GIF", value="gif"),
            app_commands.Choice(name="BMP", value="bmp"),
            app_commands.Choice(name="TIFF", value="tiff"),
        ]
    )
    async def convert_image(self, interaction: discord.Interaction, image: discord.Attachment, format: str, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if not image.content_type.startswith("image/"):
                await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
                return

            img_data = await image.read()
            image_pil = Image.open(io.BytesIO(img_data))

            if format.value == "jpeg" and image_pil.mode == "RGBA":
                image_pil = image_pil.convert("RGB")

            output_buffer = io.BytesIO()
            
            if format.value == "gif" and image_pil.is_animated:
                frames = []
                for frame in ImageSequence.Iterator(image_pil):
                    frame = frame.convert("RGBA")
                    frames.append(frame)

                frames[0].save(output_buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0)
            else:
                output_filename = f"{image.filename.rsplit('.', 1)[0]}.{format.value.lower()}"
                image_pil.save(output_buffer, format=format.value.upper())

            output_buffer.seek(0)
            
            await interaction.followup.send(
                content=f"Here is your converted image in {format.value.upper()} format:",
                file=discord.File(fp=output_buffer, filename=f"{output_filename}.{format.value.lower()}")
            )

            os.remove(output_filename)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="video", description="Convert an uploaded video to a specified format")
    @app_commands.describe(
        video="The uploaded video file you want to convert.", 
        format="The format you want to convert the video to.",
        ephemeral="If you want the message ephemeral or not.")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="MP4", value="mp4"),
            app_commands.Choice(name="MP3", value="mp3"),
            app_commands.Choice(name="WMV", value="wmv"),
            app_commands.Choice(name="MOV", value="mov"),
            app_commands.Choice(name="MKV", value="mkv"),
            app_commands.Choice(name="AVI", value="avi"),
            app_commands.Choice(name="GIF", value="gif")
        ]
    )
    async def convert_video(self, interaction: discord.Interaction, video: discord.Attachment, format: str, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            video_data = await video.read()
            output_filename = await asyncio.to_thread(self.process_video, video_data, video.filename, format.value)

            await interaction.followup.send(
                content=f"Here is your converted file in {format.value.upper()} format:",
                file=discord.File(fp=output_filename, filename=output_filename.split('/')[-1])
            )

            def process_video(self, video_data, original_filename, target_format):
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{original_filename.split('.')[-1]}") as temp_input:
                    temp_input.write(video_data)
                    temp_input_path = temp_input.name

                output_filename = f"{tempfile.gettempdir()}/{original_filename.rsplit('.', 1)[0]}.{target_format.lower()}"

                if target_format.lower() == "mp3":
                    input_audio = AudioFileClip(temp_input_path)
                    input_audio.write_audiofile(output_filename)
                else:
                    input_video = VideoFileClip(temp_input_path)
                    input_video.write_videofile(output_filename, codec="libx264", audio_codec="aac", remove_temp=True)

                return output_filename
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="youtube", description="Convert a YouTube video into an MP4 or MP3 file!")
    @app_commands.describe(
        link="The YouTube video link",
        resolution="The resolution of the video",
        format="The output format of the video",
        ephemeral="If you want the message ephemeral or not."
    )
    @app_commands.choices(
        resolution=[
            app_commands.Choice(name="144p (SD)", value="144p"),
            app_commands.Choice(name="240p (SD)", value="240p"),
            app_commands.Choice(name="360p (SD)", value="360p"),
            app_commands.Choice(name="480p (SD)", value="480p"),
            app_commands.Choice(name="720p (HD)", value="720p"),
            app_commands.Choice(name="1080p (FHD)", value="1080p"),
            app_commands.Choice(name="1440p (2K)", value="1440p"),
            app_commands.Choice(name="2160p (4K)", value="2160p"),
            app_commands.Choice(name="4320p (8K)", value="4320p"),
        ],
        format=[
            app_commands.Choice(name="MP4", value="mp4"),
            app_commands.Choice(name="MP3", value="mp3"),
        ]
    )
    async def convert_youtube(self, interaction: discord.Interaction, link: str, resolution: str, format: str, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if not link.startswith(("https://youtube.com", "https://www.youtube.com", "https://youtu.be", "https://www.youtu.be")):
                await interaction.followup.send("Please provide a valid YouTube link.", ephemeral=True)
                return

            def download_and_convert(link, resolution, format):
                ydl_opts = {
                    'format': f'bestvideo[height<={resolution[:-1]}]+bestaudio/best',
                    'outtmpl': '%(title)s.%(ext)s',
                    'postprocessors': [{
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': format,
                    }],
                    'cookiefile': 'storage/cookies.txt',
                    'noplaylist': True,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(link, download=True)
                    video_title = re.sub(r'[<>:"/\\|?*]', '', (info_dict.get('title', 'video')))
                    output_path = f"{video_title}.{format}"

                return output_path

            output_path = await asyncio.to_thread(download_and_convert, link, resolution, format)

            await interaction.followup.send(file=discord.File(output_path))
            os.remove(output_path)
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(Convert())

@bot.tree.command(name="filedata", description="Display metadata for an uploaded file") 
@app_commands.describe(file="The uploaded file to analyze.")
async def filedata(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer()
    try:
        file_data = await file.read()
        file_type = file.content_type
        file_size = len(file_data) / (1024 * 1024)

        file_info = f"**File Name:** {file.filename}\n**File Type:** {file_type}\n**File Size:** {file_size:.2f} MB\n"

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as temp_input:
            temp_input.write(file_data)
            temp_input_path = temp_input.name

        if "video" in file_type:
            clip = VideoFileClip(temp_input_path)
            frame_rate = clip.fps
            duration = clip.duration
            bitrate = (file_size * 8) / duration if duration > 0 else "Unknown"
            resolution = f"{clip.w}x{clip.h} pixels"
            file_info += (
                f"**Duration:** {duration:.2f} seconds\n"
                f"**Frame Rate:** {frame_rate:.2f} fps\n"
                f"**Bitrate:** {bitrate:.2f} kbps\n"
                f"**Resolution:** {resolution}"
            )
            clip.close()

        elif "audio" in file_type:
            clip = AudioFileClip(temp_input_path)
            duration = clip.duration
            bitrate = (file_size * 8) / duration if duration > 0 else "Unknown"
            file_info += (
                f"**Duration:** {duration:.2f} seconds\n"
                f"**Bitrate:** {bitrate:.2f} kbps"
            )
            clip.close()

        elif "text" in file_type:
            with open(temp_input_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            file_info += (
                f"**Encoding:** UTF-8\n"
                f"**Line Count:** {len(lines)}"
            )

        else:
            file_info += "No additional metadata available for this file type."

        await interaction.followup.send(content=file_info)

        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)
    except Exception as error:
        await handle_logs(interaction, error)

"""
MODERATION COMMANDS
"""

async def store_modlog(
        type, 
        server_id, 
        moderator: discord.User, 
        user: discord.User = None, 
        channel: discord.TextChannel = None, 
        role: discord.Role = None, 
        reason: str = "No reason provided.", 
        arguments: str = None
        ):

    server_info = open_file("info/server_info.json")
    server_info.setdefault("preferences", {})
    server_info.setdefault("modlogs", {})
    server_info.setdefault("modstats", {})
    server_info.setdefault("warnings", {})

    server_info["modlogs"].setdefault(str(server_id), {})
    server_info["modstats"].setdefault(str(server_id), {})
    server_info["warnings"].setdefault(str(server_id), {})

    channel_id = server_info["preferences"].get(str(server_id), {}).get("modLogs")
    channel = bot.get_channel(channel_id) if channel_id else None

    embed = discord.Embed(title="Moderation Log", color=discord.Color.red())
    embed.add_field(name="Type", value=type, inline=False)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Moderator", value=moderator.mention, inline=False)
    if role is not None:
        embed.add_field(name="Role affected", value=role.mention, inline=False)
    if user is not None:
        embed.add_field(name="User affected", value=user.mention, inline=False)
    if channel is not None:
        embed.add_field(name="Channel affected", value=channel.mention, inline=False)
    if arguments is not None:
        embed.add_field(name="Extra arguments", value=arguments, inline=False)
    embed.timestamp = datetime.utcnow()

    if user is not None:
        user_id = str(user.id)

        server_info["modlogs"][str(server_id)].setdefault(user_id, {})
        last_case_number = max(map(int, server_info["modlogs"][str(server_id)][user_id].keys()), default=0)
        new_case_number = last_case_number + 1

        server_info["modlogs"][str(server_id)][user_id][str(new_case_number)] = {
            "Type": type,
            "User": str(user),
            "Moderator": str(moderator),
            "Reason": reason,
            "Time": int(time.time()),
        }

        moderator_id = str(moderator.id)
        server_info["modstats"][str(server_id)].setdefault(moderator_id, {})

        if type.title() in ["Kick", "Mute", "Ban", "Warn"]:
            server_info["modstats"][str(server_id)][moderator_id][str(new_case_number)] = {
                "type": type.title(),
                "timestamp": int(time.time()),
            }

            if type.title() == "Warn":
                server_info["warnings"][str(server_id)].setdefault(user_id, {})
                user_last_case_number = max(map(int, server_info["warnings"][str(server_id)][user_id].keys()), default=0)
                new_warning_case_number = user_last_case_number + 1

                server_info["warnings"][str(server_id)][user_id][str(new_warning_case_number)] = {
                    "reason": reason,
                    "moderator": str(moderator),
                    "time": int(time.time())
                }

    if channel is not None:
        await channel.send(embed=embed)

    save_file("info/server_info.json", server_info)

async def dmbed(interaction, user, action, reason, duration=None):
    embed = discord.Embed(title=f"Member {action}.", color=discord.Color.orange())
    embed.add_field(name="Action", value=action.title())
    embed.add_field(name="Reason", value=reason)
    if duration:
        embed.add_field(name="Duration", value=duration)

    try:
        MemberEmbed = discord.Embed(title=f"You have been {action} in {interaction.guild.name}.", color=discord.Color.orange())
        MemberEmbed.add_field(name="Moderator", value=interaction.user.mention)
        MemberEmbed.add_field(name="Reason", value=reason)
        if duration:
            MemberEmbed.add_field(name="Duration", value=duration)
        MemberEmbed.set_footer(text="If you think this is a mistake, please contact a staff user.")
        await user.send(embed=MemberEmbed)
    except discord.Forbidden:
        embed.set_footer(text="I could not DM them.")

    await interaction.followup.send(embed=embed)

async def check_mod(interaction: discord.Interaction, permission_name: str):
    server_info = open_file("info/server_info.json")
    guild_id = str(interaction.guild_id)

    if "preferences" not in server_info:
        server_info["preferences"] = {}
    if "modlogs" not in server_info:
        server_info["modlogs"] = {}
    if "modstats" not in server_info:
        server_info["modstats"] = {}
    if "warnings" not in server_info:
        server_info["warnings"] = {}
    if "notes" not in server_info:
        server_info["notes"] = {}

    server_info["preferences"].setdefault(guild_id, {})
    server_info["modlogs"].setdefault(guild_id, {})
    server_info["modstats"].setdefault(guild_id, {})
    server_info["warnings"].setdefault(guild_id, {})
    server_info["notes"].setdefault(guild_id, {})

    save_file("info/server_info.json", server_info)

    mod_role_id = server_info["preferences"][guild_id].get("moderator")
    has_permission = getattr(interaction.user.guild_permissions, permission_name, False)
    has_role = mod_role_id and discord.utils.get(interaction.user.roles, id=int(mod_role_id))

    if not (has_permission or has_role):
        await interaction.followup.send(
            f"You need the '{permission_name.replace('_', ' ').title()}' permission or the Moderator role to use this command.",
            ephemeral=True
        )
        return False
    return True

@bot.tree.command(name="setlogs", description="Changes the log channels of your server")
@app_commands.describe(option="Choose the type of log (Message Logs, DM Logs, Mod Logs)", channel="The channel to send logs to")
@app_commands.choices(
    option=[
        app_commands.Choice(name="Message Logs", value="messageLogs"),
        app_commands.Choice(name="DM Logs", value="dmLogs"),
        app_commands.Choice(name="Mod Logs", value="modLogs"),
    ]
)
async def setlogs(interaction: discord.Interaction, option: app_commands.Choice[str], channel: discord.TextChannel):
    await interaction.response.defer()
    try:
        server_info = open_file("info/server_info.json")
        guild_id = str(interaction.guild_id)

        if not await check_mod(interaction, "administrator"):
            return

        if guild_id not in server_info["preferences"]:
            server_info["preferences"][guild_id] = {}

        server_info["preferences"][guild_id][option.value] = channel.id
        save_file("info/server_info.json", server_info)

        await interaction.followup.send(f"{option.name} will be set to: {channel.mention}")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="setroles", description="Allows you to set the server roles")
@app_commands.describe(option="Choose the role to set", role="The role to set for members")
@app_commands.choices(
    option=[
        app_commands.Choice(name="Member", value="member"),
        app_commands.Choice(name="Moderator", value="moderator"),
        app_commands.Choice(name="Manager", value="manager")
    ]
)
async def setroles(interaction: discord.Interaction, option: str, role: discord.Role):
    await interaction.response.defer()
    try:
        server_info = open_file("info/server_info.json")
        guild_id = str(interaction.guild_id)

        if not await check_mod(interaction, "administrator"):
            return

        if guild_id not in server_info["preferences"]:
            server_info["preferences"][guild_id] = {}

        server_info["preferences"][guild_id][option] = role.id
        save_file("info/server_info.json", server_info)

        await interaction.followup.send(f"The role '{role.name}' has been set for members.")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def cpurge(ctx, amount: int, member: discord.Member = None):
    if amount <= 0:
        await ctx.send("The amount must be greater than zero.", delete_after=5)
        return

    messages_to_delete = []
    
    if member is None:
        deleted_messages = await ctx.channel.purge(limit=amount)
        messages_to_delete = deleted_messages
    else:
        async for message in ctx.channel.history(limit=1000):
            if len(messages_to_delete) >= amount:
                break
            if message.author.id == member.id:
                messages_to_delete.append(message)

        await ctx.channel.delete_messages(messages_to_delete)

    reason = f"Deleted {len(messages_to_delete)} message(s)"
    await store_modlog("Purge", ctx.guild.id, ctx.author, reason)

class MessageCheck:
    """
    I need to read the docs more bro I never knew delete_messages was a thing and I spent like an hour with a headache researching
    Suprisingly didn't find anything on stackoverflow that said you can do this as well
    """

    @staticmethod
    def cleanCommand(message: discord.Message) -> bool:
        """Check if the message is from the bot or starts with '?'."""
        is_bot_message = message.author == message.guild.me
        starts_with_question = message.content.startswith('?')  
        return is_bot_message or starts_with_question

    @staticmethod
    def is_text_only(message: discord.Message) -> bool:
        """Check if a message contains only text (no embeds or attachments)."""
        has_embeds = bool(message.embeds)
        has_attachments = bool(message.attachments)
        return not has_embeds and not has_attachments and bool(message.content.strip())

    @staticmethod
    def is_from_user(message: discord.Message, user: discord.User) -> bool:
        """Check if the message is from a specific user."""
        return message.author == user

    @staticmethod
    def has_embeds(message: discord.Message) -> bool:
        """Check if the message contains embeds."""
        return bool(message.embeds)

    @staticmethod
    def has_attachments(message: discord.Message) -> bool:
        """Check if the message contains attachments."""
        return bool(message.attachments)

    @staticmethod
    async def purge_messages(channel: discord.TextChannel, amount: int, check_func, interaction: discord.Interaction = None, reason: str = None) -> list:
        """Purge messages based on a given check function and return the deleted messages."""
        messages_to_delete = []
        async for message in channel.history(limit=1000):
            if len(messages_to_delete) >= amount:
                break
            if check_func(message):
                messages_to_delete.append(message)
        
        if messages_to_delete:
            if len(messages_to_delete) > 1:
                try:
                    await channel.delete_messages(messages_to_delete, reason=reason)
                    await interaction.followup.send(f"Succesfully deleted {len(messages_to_delete)} messages")
                    return messages_to_delete
                except discord.HTTPException as e:
                    print(f"Error deleting messages: {e}")
                    return []
            else:
                try:
                    await messages_to_delete[0].delete()
                    return [messages_to_delete[0]]
                except discord.HTTPException as e:
                    print(f"Error deleting message: {e}")
                    return []

        return []


class PurgeCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="purge", description="Purge commands for messages")

    @app_commands.command(name="any", description="Purges any type of message")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await interaction.channel.purge(limit=amount, reason=reason)
            await store_modlog(f"Purged {amount} messages", interaction.guild.id, interaction.user, reason=reason)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="user", description="Purges messages from a specific user.")
    @app_commands.describe(user="The user to purge the messages for", amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def upurge(self, interaction: discord.Interaction, user: discord.User, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, lambda msg: MessageCheck.is_from_user(msg, user), interaction, reason)
            await store_modlog(f"Purged {amount} messages from {user}", interaction.guild.id, interaction.user, reason=reason)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="embeds", description="Purges messages containing embeds.")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def epurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_embeds, interaction, reason)
            await store_modlog(f"Purged {amount} embed messages", interaction.guild.id, interaction.user, reason=reason)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="attachments", description="Purges messages containing attachments.")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_attachments, interaction, reason)
            await store_modlog(f"Purged {amount} messages with attachments", interaction.guild.id, interaction.user, reason=reason)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="text", description="Purges messages based on criteria (Default: 10)")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def tpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.is_text_only, interaction, reason)

            text = f"Deleted {amount} text messages."
            await store_modlog(text, interaction.guild.id, interaction.user, reason=reason)
        except Exception as error:
            await handle_logs(interaction, error)


bot.tree.add_command(PurgeCommandGroup())

@bot.command("test")
async def test(ctx):
    for i in range(10):
        await ctx.channel.send(i)
        await asyncio.sleep(0.5)

@bot.command(name="clean")
async def cclean(ctx, amount: int = 10):
    if ctx.author.guild_permissions.manage_messages:
        try:
            await MessageCheck.purge_messages(ctx.channel, amount, MessageCheck.cleanCommand)
            await ctx.send(f"{amount} messages have been deleted.", delete_after=2)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have the required permission to run this command.")

@bot.tree.command(name="clean", description="Clean the bot's messages")
@app_commands.describe(amount="Amount to delete (Default: 10)")
async def clean(interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided"):
    try:
        if not await check_mod(interaction, "manage_messages"):
            await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
            return

        await MessageCheck.purge_clean_command(interaction.channel, amount)
        await store_modlog(f"Clean ({amount} messages)", interaction.guild.id, interaction.user, reason=reason)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="role", description="Toggle a role for a member")
@app_commands.describe(user="Member to manage roles for", role="Role to manage", reason="Reason for management")
async def role(interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided."):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_roles"):
            return
    
        if role in member.roles:
            await member.remove_roles(role)
            task = "removed"
        else:
            await member.add_roles(role)
            task = "added"

        embed = discord.Embed(
                title=f"Role {task}.",
                description=f"{role.mention} was successfully {task} to {member.mention}",
                color=discord.Color.orange
            )
        await interaction.followup.send(embed=embed)

        await store_modlog(f"Role {task}", interaction.guild.id, interaction.user, member, reason=reason)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="lock", description="Lock a channel.")
@app_commands.describe(
    channel="The channel to lock (default is the current channel)",
    role="The role to lock the channel for (default is 'Member')",
    reason="The reason for locking the channel (default is 'No reason provided')",
)
async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
    await interaction.response.defer()
    try:
        channel = channel or interaction.channel
        server_info = open_file("info/server_info.json")
        guild_id = str(interaction.guild_id)
        
        if not await check_mod(interaction, "manage_messages"):
            return
        
        if role is None:
            role_id = server_info["preferences"].get(guild_id, {}).get("member")
            role = interaction.guild.get_role(role_id) if role_id else None

        if role is None:
            await interaction.followup.send("No role found to lock the channel for.")
            return

        if role not in channel.overwrites:
            overwrites = {role: discord.PermissionOverwrite(send_messages=False)}
            await channel.edit(overwrites=overwrites)
        else:
            await channel.set_permissions(role, send_messages=False)

        reason_with_role = f"{reason}. Role: {role.name}"

        await store_modlog("Lock", interaction.guild.id, interaction.user, role=role, channel=channel, reason=reason)
        await interaction.followup.send(f"{channel.mention} has been locked for {role.name}.\nReason: {reason}")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="unlock", description="Unlock a channel.")
@app_commands.describe(
    channel="The channel to unlock (default is the current channel)",
    role="The role to unlock the channel for (default is 'Member')",
    reason="The reason for unlocking the channel (default is 'No reason provided')",
)
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
    await interaction.response.defer()
    try:
        channel = channel or interaction.channel
        server_info = open_file("info/server_info.json")
        guild_id = str(interaction.guild_id)
        
        if not await check_mod(interaction, "manage_messages"):
            return
        
        if role is None:
            role_id = server_info["preferences"].get(guild_id, {}).get("member")
            role = interaction.guild.get_role(role_id) if role_id else None

        if role is None:
            await interaction.followup.send("No role found to unlock the channel for.")
            return

        if role in channel.overwrites:
            await channel.set_permissions(role, send_messages=True)

        reason_with_role = f"{reason}. Role: {role.name}"

        await store_modlog("Unlock", interaction.guild.id, interaction.user, role=role, channel=channel, reason=reason)
        await interaction.followup.send(f"{channel.mention} has been unlocked for {role.name}.\nReason: {reason}")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="slowmode", description="Sets or removes the slowmode delay for the channel.")
@app_commands.describe(delay="Slowmode in seconds (max of 21600, omit for no slowmode)")
@app_commands.checks.has_permissions(manage_messages=True)
async def slowmode(interaction: discord.Interaction, channel: discord.TextChannel = None, delay: int = None):
    await interaction.response.defer()
    try:
        channel = channel or interaction.channel
        if not await check_mod(interaction, "manage_messages"):
            return
        if delay is None:
            await channel.edit(slowmode_delay=0)
            reason = f"Slowmode removed in #{channel.name}."
            await interaction.followup.send(embed=discord.Embed(title="Slowmode", description="Slowmode has been removed.", color=0x00FF00))
        elif 0 <= delay <= 21600:
            await channel.edit(slowmode_delay=delay)
            reason = f"Slowmode set to {delay} seconds in #{channel.name}."
            await interaction.followup.send(embed=discord.Embed(title="Slowmode", description=f"Slowmode set to {delay} seconds.", color=0x00FF00))
        else:
            await interaction.followup.send(embed=discord.Embed(title="Slowmode Error", description="Please provide a delay between 0 and 21600 seconds.", color=0xFF0000))
            return

        await store_modlog("Slowmode", interaction.guild.id, interaction.user, channel=channel, arguments=f"Slowmode of {'0' if delay == None else delay} seconds")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="nick", description="Changes a member's nickname.")
@app_commands.describe(member="The member to manage nicknames for", new_nick="The new nickname of the member")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def nick(interaction: discord.Interaction, member: discord.Member, new_nick: str):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return
        old_nick = member.display_name
        await member.edit(nick=new_nick)

        arguments = f"Changed {member.name}'s nickname from {old_nick} to {new_nick} for {member.display_name}"
        await interaction.followup.send(embed=discord.Embed(title="Nickname Changed", description=arguments, color=0x32A852))

        await store_modlog("Nickname", interaction.guild.id, interaction.user, member, arguments=arguments)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="mute", description="Mutes a member for a specified duration")
@app_commands.describe(
    member="Member to mute",
    duration="Duration of the mute",
    reason="Reason for the mute"
)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "timeout_members"):
            return
        duration = parse_duration(duration)

        if not duration:
            await interaction.followup.send("Invalid time format. Please use formats like `1h10m15s` or `15s1h10m`.")
            return

        until = discord.utils.utcnow() + duration
        await member.timeout(until, reason=reason)

        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        human_readable_time = (f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)")
        await dmbed(interaction, member, "muted", reason, human_readable_time)

        await store_modlog("Mute", interaction.guild.id, interaction.user, member, reason=reason, arguments=f"{reason}\nMuted for {human_readable_time}")
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="unmute", description="Unmutes a user.")
@commands.has_permissions(kick_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "timeout_members"):
            return
        await member.timeout(None, reason=reason)
        await dmbed(interaction, member, "unmuted", reason)

        await store_modlog("Unmute", interaction.guild.id, interaction.user, member, reason=reason)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="kick", description="Kick a member out of the guild.")
@commands.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No Reason Provided."):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "kick_members"):
            return
        await member.kick(reason=reason)
        await dmbed(interaction, member, "kicked", reason)

        await store_modlog("Kick", interaction.guild.id, interaction.user, member, reason=reason)
    except Exception as error:
        await handle_logs(interaction, error)

class DelLog(discord.ui.Select):
    def __init__(
        self,
        log_type,
        member: discord.Member,
        embed: discord.Embed,
        interaction: discord.Interaction,
        *args,
        **kwargs,
    ):
        placeholder = f"Delete a {log_type}"
        super().__init__(placeholder=placeholder, *args, **kwargs)

        self.log_type = log_type
        self.member = member
        self.embed = embed
        self.interaction = interaction

        server_info = open_file("info/server_info.json")
        
        if self.log_type == "warn":
            self.logs = server_info.get("warnings", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})
        elif self.log_type == "note":
            self.logs = server_info.get("notes", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})

        self.options = [
            discord.SelectOption(
                label=f"{self.log_type.capitalize()} Case #{case_number}",
                description=log["reason"] if "reason" in log else "No reason provided",
                value=str(case_number)
            )
            for case_number, log in self.logs.items()
        ]

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_index = self.values[0]

            if selected_index in self.logs:
                log_entry = self.logs[selected_index]
                del self.logs[selected_index]

                if not self.logs:
                    if self.log_type == "warn":
                        server_info = open_file("info/server_info.json")
                        server_info["warnings"].get(str(interaction.guild.id), {}).pop(str(self.user.id), None)
                    elif self.log_type == "note":
                        server_info = open_file("info/server_info.json")
                        server_info["notes"].get(str(interaction.guild.id), {}).pop(str(self.user.id), None)

                save_file("info/server_info.json", server_info)

                self.embed.clear_fields()
                updated_logs = self.logs.get(str(self.user.id), {})

                if updated_logs:
                    for index, log in sorted(updated_logs.items(), key=lambda x: int(x[0])):
                        time_str = f"<t:{log['time']}:R>"
                        moderator = self.interaction.guild.get_member(int(log["moderator"]))
                        moderator_name = moderator.display_name if moderator else "Unknown"
                        self.embed.add_field(
                            name=f"Case #{index} - {self.log_type.capitalize()} by {moderator_name}",
                            value=f"Reason: {log['reason']}\nTime: {time_str}",
                            inline=False
                        )

                    self.options = [
                        discord.SelectOption(
                            label=f"{self.log_type.capitalize()} Case #{index}",
                            description=log["reason"],
                            value=str(index)
                        )
                        for index, log in sorted(updated_logs.items(), key=lambda x: int(x[0]))
                    ]
                else:
                    self.embed.description = f"No {self.log_type} left for {self.user.display_name}."

                await interaction.response.edit_message(embed=self.embed, view=self.view)
                await interaction.followup.send(f"Deleted {self.log_type.capitalize()} Case #{selected_index} for {self.user.display_name}.", ephemeral=True)
            else:
                await interaction.response.send_message("Invalid selection. Please choose a valid log to delete.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid selection. Please try again.", ephemeral=True)
        except Exception as error:
            await handle_logs(interaction, error)


@bot.tree.command(name="warn", description="Warns a user.")
@app_commands.describe(user="The member to warn.", reason="Reason for the warn.")
@app_commands.choices(
    reason=[
        app_commands.Choice(name="Spamming", value="spamming"),
        app_commands.Choice(name="Flood", value="flood"),
        app_commands.Choice(name="Bot Commands", value="bot commands"),
        app_commands.Choice(name="Soft NSFW", value="soft nsfw"),
        app_commands.Choice(name="Hard NSFW", value="hard nsfw"),
        app_commands.Choice(name="Advertising", value="advertising"),
        app_commands.Choice(name="Tragic Event Joke", value="tragic event joke"),
        app_commands.Choice(name="Fatherless Joke", value="fatherless joke"),
        app_commands.Choice(name="KYS Joke", value="kys joke"),
    ]
)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer()

    try:
        if not await check_mod(interaction, "manage_messages"):
            return

        server_info = open_file("info/server_info.json")
        server_id = str(interaction.guild.id)

        server_info.setdefault("warnings", {})
        server_info["warnings"].setdefault(server_id, {})
        server_info["warnings"][server_id].setdefault(str(member.id), {})

        member_warnings = server_info["warnings"][server_id][str(member.id)]

        if member_warnings:
            try:
                highest_case_number = max(map(int, member_warnings.keys()), default=0)
                last_warning_time = member_warnings.get(str(highest_case_number), {}).get("time", 0)

                if int(time.time()) - last_warning_time < 60:
                    await interaction.followup.send(embed=discord.Embed(
                        title="Warning Error",
                        description=f"{member.mention} has been warned recently and cannot be warned again yet.",
                        color=0xFF0000
                    ))
                    return
            except ValueError as e:
                print("Error finding highest case number:", e)

        await dmbed(interaction, member, "warn", reason)
        await store_modlog("Warn", interaction.guild.id, interaction.user, member, reason=reason)

        punishment_durations = {
            "spamming": 1 * 60 * 60,
            "flood": 1 * 60 * 60,
            "bot commands": 0.5 * 60 * 60,
            "soft nsfw": 2 * 60 * 60,
            "hard nsfw": 24 * 60 * 60,
            "advertising": 6 * 60 * 60,
            "tragic event joke": 12 * 60 * 60,
            "fatherless joke": 3 * 60 * 60,
            "kys joke": 6 * 60 * 60,
        }

        mute_duration = punishment_durations.get(reason.lower(), 0)
        if len(member_warnings) > 2:
            mute_duration += (len(member_warnings) - 2) * 60 * 60

        if mute_duration > 0:
            try:
                await user.timeout(timedelta(seconds=mute_duration))
                await interaction.followup.send(embed=discord.Embed(
                    title="Member Muted",
                    description=f"{user.mention} has been automatically muted for {mute_duration // 60} minutes due to {len(member_warnings) + 1} warnings.",
                    color=0xFF0000
                ))
            except discord.Forbidden:
                await interaction.followup.send(embed=discord.Embed(
                    title="Mute Failed",
                    description=f"Failed to mute {member.mention} due to insufficient permissions.",
                    color=0xFF0000
                ))
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="warns", description="Displays the warnings for a user.")
@app_commands.describe(user="The member whose warnings you want to view.")
async def warns(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return
        
        member = member or interaction.user
        server_info = open_file("info/server_info.json")
        server_id = str(interaction.guild.id)
        
        member_warnings = server_info["warnings"].get(server_id, {}).get(str(member.id), {})
        embed = discord.Embed(title=f"Warnings for {member.display_name}", color=0xFFA500)

        if member_warnings:
            for case_number, warning_data in sorted(member_warnings.items(), key=lambda x: int(x[0])):
                time_str = f"<t:{warning_data['time']}:R>"
                moderator_name = warning_data.get("moderator")
                embed.add_field(
                    name=f"Case #{case_number} - Warned by {moderator_name}",
                    value=f"Reason: {warning_data['reason']}\nTime: {time_str}",
                    inline=False
                )

            view = discord.ui.View()
            del_log_dropdown = DelLog("warn", member, embed, interaction)
            view.add_item(del_log_dropdown)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"No warnings found for {member.display_name}.", ephemeral=True)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="note", description="Gives a note to a user.")
@app_commands.describe(user="The member to add a note to", note="Whatever you want to say")
async def note(interaction: discord.Interaction, member: discord.Member, note: str):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return
        
        server_info = open_file("info/server_info.json")
        member_notes = server_info["notes"].setdefault(str(interaction.guild.id), {}).setdefault(str(member.id), {})
        case_number = str(max(map(int, member_notes.keys()), default=0) + 1)
        member_notes[case_number] = {
            "reason": note,
            "moderator": str(interaction.user.id),
            "time": int(time.time())
        }
        save_file("info/server_info.json", server_info)
        await interaction.followup.send(embed=discord.Embed(
            title="Note Added",
            description=f"Added note to: {member.mention}\nCase #{case_number}\n{note}",
            color=0xFFA500
        ))
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="notes", description="Displays the notes for a member")
@app_commands.describe(user="The member whose notes you want to view.")
async def notes(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return
        
        member = member or interaction.user
        server_info = open_file("info/server_info.json")
        member_notes = server_info["notes"].get(str(interaction.guild.id), {}).get(str(member.id), {})
        embed = discord.Embed(title=f"Notes for {member.display_name}", color=0xFFA500)

        if member_notes:
            for case_number, note in sorted(member_notes.items(), key=lambda x: int(x[0])):
                time_str = f"<t:{note['time']}:R>"
                moderator = interaction.guild.get_member(int(note["moderator"]))
                moderator_name = moderator.display_name if moderator else "Unknown"
                embed.add_field(
                    name=f"Case #{case_number} by {moderator_name}",
                    value=f"Note: {note['reason']}\nTime: {time_str}",
                    inline=False
                )

            view = discord.ui.View()
            del_log_dropdown = DelLog("note", member, embed, interaction)
            view.add_item(del_log_dropdown)

            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(f"No notes found for {member.display_name}.", ephemeral=True)
    except Exception as error:
        await handle_logs(interaction, error)

async def send_modlog_embed(interaction: discord.Interaction, user: discord.User, page: int):
    server_info = open_file("info/server_info.json")
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

class LogSelect(discord.ui.Select):
    def __init__(self, options, interaction, user, current_page):
        super().__init__(
            placeholder=f"Current page: {current_page}",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.interaction = interaction
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return

        await interaction.response.defer()
        selected_page = int(self.values[0])
        embed, total_logs, total_pages = await send_modlog_embed(self.interaction, self.user, selected_page)
        await interaction.message.edit(embed=embed)
        self.placeholder = f"Current page: {selected_page}"
        await interaction.message.edit(view=self.view)

@bot.tree.command(name="modlogs", description="View moderation logs for a user.")
async def modlogs(interaction: discord.Interaction, member: discord.Member, page: int = 1):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return
        embed, total_logs, total_pages = await send_modlog_embed(interaction, member, page)

        if embed is None:
            return

        options = [discord.SelectOption(label=f"Page {i + 1}", value=str(i + 1)) for i in range(total_pages)]

        select_menu = LogSelect(options, interaction, member, page)
        view = discord.ui.View()
        view.add_item(select_menu)

        await interaction.followup.send(embed=embed, view=view)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="modstats", description="Check the moderation statistics of a moderator")
@commands.has_permissions(kick_members=True)
async def modstats(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        if not await check_mod(interaction, "manage_messages"):
            return

        member = member or interaction.user
        server_info = open_file("info/server_info.json")

        stats = {
            "warn": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
            "kick": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
            "mute": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
            "ban": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
        }

        totals = {"last 7 days": 0, "last 30 days": 0, "all time": 0}
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        for server_id, moderators in server_info["modstats"].items():
            user_stats = moderators.get(str(member.id), {})

            for case_number, action in user_stats.items():
                action_type = action["type"].lower()
                action_time = datetime.fromtimestamp(action["timestamp"], timezone.utc)

                if action_type in stats:
                    if action_time > seven_days_ago:
                        stats[action_type]["last 7 days"] += 1
                        totals["last 7 days"] += 1
                    if action_time > thirty_days_ago:
                        stats[action_type]["last 30 days"] += 1
                        totals["last 30 days"] += 1
                    stats[action_type]["all time"] += 1
                    totals["all time"] += 1

        embed = discord.Embed(title=f"Moderation Statistics for {member.display_name}", color=0xFFA500)
        embed.add_field(name="\u200b", value="**Last 7 days**")
        embed.add_field(name="\u200b", value="**Last 30 days**")
        embed.add_field(name="\u200b", value="**All Time**")

        for action_type in stats.keys():
            embed.add_field(name=f"**{action_type.capitalize()}**", value=str(stats[action_type]["last 7 days"]))
            embed.add_field(name="\u200b", value=str(stats[action_type]["last 30 days"]))
            embed.add_field(name="\u200b", value=str(stats[action_type]["all time"]))

        embed.add_field(name="**Total**", value=str(totals["last 7 days"]))
        embed.add_field(name="\u200b", value=str(totals["last 30 days"]))
        embed.add_field(name="\u200b", value=str(totals["all time"]))

        await interaction.followup.send(embed=embed)
    except Exception as error:
        await handle_logs(interaction, error)

"""
ECONOMY COMMANDS
"""

# Eco data

items = open_file("storage/economy/items.json")
eco_path = "storage/economy/economy.json"

# Hourly shop system

SHOP = []

@tasks.loop(hours=1)
async def handle_eco_shop():
    global SHOP
    SHOP = []
    shop_items = random.sample(list(items.items()), min(10, len(items)))
    for name, data in shop_items:
        if "appearInShop" in data:
            appear_data = data["appearInShop"]
            SHOP.append({
                "item": name,
                "price": appear_data.get("buyPrice", 0),
                "amount": appear_data.get("amount", 0),
                "description": appear_data.get("description", "No description yet...")
            })
    
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

@bot.tree.command(name="balance", description="Check a user's purse and bank balance!")
@app_commands.describe(user="The user whose balance you want to check.")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()
    try:
        user = user or interaction.user
        user_id = str(user.id)

        eco = open_file(eco_path)

        if user_id not in eco:
            if user_id == str(interaction.user.id):
                create_account(user_id)
            else:
                await interaction.followup.send("The user does not have an account.")
                return
            
            eco = open_file(eco_path)

        player_data = eco[user_id]
        purse_balance = int(player_data["balance"]["purse"])
        bank_balance = int(player_data["balance"]["bank"])
        max_bank = int(player_data["balance"]["maxBank"])

        embed = discord.Embed(
            title=f"{user.display_name}'s Balance",
            description=(
                f"**Wallet:** {purse_balance}\n"
                f"**Bank:** {bank_balance} / {max_bank} ({(bank_balance / max_bank) * 100:.2f}%)"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        async def update_embed():
            updated_embed = discord.Embed(
                title=f"{user.display_name}'s Balance",
                description=(
                    f"**Wallet:** {eco[user_id]['balance']['purse']}\n"
                    f"**Bank:** {eco[user_id]['balance']['bank']} / {eco[user_id]['balance']['maxBank']} "
                    f"({(eco[user_id]['balance']['bank'] / eco[user_id]['balance']['maxBank']) * 100:.2f}%)"
                ),
                color=discord.Color.green()
            )
            updated_embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            return updated_embed

        view = RestrictedView(interaction.user)

        withdraw_button = discord.ui.Button(label="Withdraw", style=discord.ButtonStyle.red)
        async def withdraw_callback(interaction: discord.Interaction):
            if interaction.user.id != user.id:
                return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

            modal = discord.ui.Modal(title="Withdraw")
            amount_input = discord.ui.TextInput(label="Amount to withdraw")
            modal.add_item(amount_input)

            async def modal_callback(modal_interaction: discord.Interaction):
                amount = int(amount_input.value)
                success, transaction_result = await process_transaction(modal_interaction.user.id, "withdraw", amount)
                if success:
                    eco[user_id]['balance']['purse'] += amount
                    eco[user_id]['balance']['bank'] -= amount
                    save_file(eco_path, eco)

                    updated_embed = await update_embed()
                    await interaction.message.edit(embed=updated_embed, view=view)
                await modal_interaction.response.send_message(transaction_result, ephemeral=True)

            modal.on_submit = modal_callback
            await interaction.response.send_modal(modal)
        withdraw_button.callback = withdraw_callback
        view.add_item(withdraw_button)

        deposit_button = discord.ui.Button(label="Deposit", style=discord.ButtonStyle.green)
        async def deposit_callback(interaction: discord.Interaction):
            if interaction.user.id != user.id:
                return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

            modal = discord.ui.Modal(title="Deposit")
            amount_input = discord.ui.TextInput(label="Amount to deposit")
            modal.add_item(amount_input)

            async def modal_callback(modal_interaction: discord.Interaction):
                amount = int(amount_input.value)
                success, transaction_result = await process_transaction(modal_interaction.user.id, "deposit", amount)
                if success:
                    eco[user_id]['balance']['purse'] -= amount
                    eco[user_id]['balance']['bank'] += amount
                    save_file(eco_path, eco)

                    updated_embed = await update_embed()
                    await interaction.message.edit(embed=updated_embed, view=view)
                await modal_interaction.response.send_message(transaction_result, ephemeral=True)

            modal.on_submit = modal_callback
            await interaction.response.send_modal(modal)
        deposit_button.callback = deposit_callback
        view.add_item(deposit_button)

        await interaction.followup.send(embed=embed, view=view)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="withdraw", description="Withdraw money from the bank.")
async def withdraw(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()
    try:
        user_id = str(interaction.user.id)
        result = await process_transaction(user_id, "withdraw", amount)
        
        if result[0] == True:
            await interaction.followup.send(result[1], ephemeral=True)
        else:
            await interaction.followup.send(result[1], ephemeral=True)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="deposit", description="Deposit money to the bank.")
async def deposit(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()
    try:
        user_id = str(interaction.user.id)
        result = await process_transaction(user_id, "deposit", amount)
        
        if result[0] == True:
            await interaction.followup.send(result[1], ephemeral=True)
        else:
            await interaction.followup.send(result[1], ephemeral=True)
    except Exception as error:
        await handle_logs(interaction, error)

@bot.tree.command(name="pay", description="Pay other user coins.")
async def pay(interaction: discord.Interaction):
    pass

# Basic ways to get money
@bot.tree.command(name="beg", description="Beg for money on the streets.")
async def beg(interaction: discord.Interaction):
    pass

@bot.tree.command(name="fish", description="Not coming soon.")
async def fish(interaction: discord.Interaction):
    pass
@bot.tree.command(name="hunt", description="Not coming soon.")
async def hunt(interaction: discord.Interaction):
    pass
@bot.tree.command(name="dig", description="Not coming soon.")
async def dig(interaction: discord.Interaction):
    pass
@bot.tree.command(name="search", description="Not coming soon.")
async def search(interaction: discord.Interaction):
    pass
@bot.tree.command(name="crime", description="Not coming soon.")
async def crime(interaction: discord.Interaction):
    pass

# Other ways to get money
@bot.tree.command(name="daily", description="Not coming soon.")
async def daily(interaction: discord.Interaction):
    pass
@bot.tree.command(name="weekly", description="Not coming soon.")
async def weekly(interaction: discord.Interaction):
    pass
@bot.tree.command(name="monthly", description="Not coming soon.")
async def monthly(interaction: discord.Interaction):
    pass

"""
GAME COMMANDS (PART OF ECO)
"""
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

@bot.tree.command(name="coinflip", description="50% chance to double or lose everything.")
@app_commands.describe(guess="Heads or tails?", amount="Optional amount if you want to bet!")
@app_commands.choices(
    guess=[
        app_commands.Choice(name="Heads", value="Heads"),
        app_commands.Choice(name="Tails", value="Tails"),
    ]
)
async def coinflip(interaction: discord.Interaction, guess: str = None, amount: str = None):
    await interaction.response.defer()

    try:
        coin = random.choice(["Heads", "Tails"])
        won = coin == guess

        if amount and not guess:
            await interaction.followup.send("You need to guess heads or tails to bet an amount!")
            return

        if amount and guess:
            try:
                amount = convert_number(amount)
            except ValueError:
                await interaction.followup.send("Invalid amount format. Use formats like 10k, 50m, etc.")
                return

            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)

            eco = open_file(eco_path)
            player_data = eco[user_id]
            purse_balance = int(player_data["balance"]["purse"])

            if amount > purse_balance:
                await interaction.followup.send("You don't have enough coins in your purse!")
                return

            if won:
                purse_balance += amount
                message = f"The coin landed on {coin.upper()}! You won {amount} coins!"
            else:
                purse_balance -= amount
                message = f"The coin landed on {coin.lower()}... You lost {amount} coins."

            player_data["balance"]["purse"] = purse_balance
            save_file(eco_path, eco)

            await interaction.followup.send(message)
            return

        if guess:
            if won:
                await interaction.followup.send(f"Congrats! The coin landed on {coin.upper()}!")
            else:
                await interaction.followup.send(f"Bad luck! The coin landed on {coin.lower()}.")
            return

        await interaction.followup.send(f"The coin landed on {coin.lower()}!")

    except Exception as error:
        await handle_logs(interaction, error)

class BlackjackView(discord.ui.View):
    def __init__(self, player, deck, player_hand, dealer_hand, bot, amount=0):
        super().__init__(timeout=30 if not bot else None)
        self.player = player
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.bot = bot
        self.result = None
        self.amount = amount

    def get_game_state(self):
        embed = discord.Embed(title="Blackjack Game")
        embed.add_field(name="Your Hand", value=f"{self.player_hand} (Total: {sum(self.player_hand)})")
        
        if self.result is None:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand[0]}, ?")
        else:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand} (Total: {sum(self.dealer_hand)})")
            embed.add_field(name="Result", value=self.result, inline=False)
        
        return embed

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit(self, interaction, button):
        if interaction.user != self.player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        self.player_hand.append(self.deck.pop())
        if sum(self.player_hand) > 21:
            self.result = "You busted! Dealer wins."
            update_stats(str(self.player.id), "blackjack", "loss", self.amount)
            await interaction.response.edit_message(embed=self.get_game_state(), view=None)
            self.stop()
            return

        await interaction.response.edit_message(embed=self.get_game_state())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand(self, interaction, button):
        if interaction.user != self.player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        while sum(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        dealer_total = sum(self.dealer_hand)
        player_total = sum(self.player_hand)

        if dealer_total > 21 or player_total > dealer_total:
            self.result = "You win!"
            update_stats(str(self.player.id), "blackjack", "win", self.amount)
        elif player_total < dealer_total:
            self.result = "Dealer wins!"
            update_stats(str(self.player.id), "blackjack", "loss", self.amount)
        else:
            self.result = "It's a tie!"
            update_stats(str(self.player.id), "blackjack", "draw")

        await interaction.response.edit_message(embed=self.get_game_state(), view=None)
        self.stop()

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, amount):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.response = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction, button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("You are not the challenged user!", ephemeral=True)
            return

        self.response = True
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction, button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("You are not the challenged user!", ephemeral=True)
            return

        self.response = False
        self.stop()

    async def on_timeout(self):
        self.response = False

class BlackjackGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="blackjack", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a blackjack game")
    @app_commands.describe(amount="The amount you want to wager", user="User you want to wager against (Or bot if none)")
    async def bjwager(self, interaction: discord.Interaction, amount: int, user: discord.User = None):
        try:
            if user == interaction.user:
                await interaction.response.send_message("You can't go against yourself!", ephemeral=True)
                return
            if user is None:
                await self.start_game(interaction, amount, bot=True)
            else:
                await self.challenge_user(interaction, amount, user=user)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="casual", description="Play a casual game of blackjack")
    @app_commands.describe(user="The user you want to play against")
    async def bjcasual(self, interaction: discord.Interaction, user: discord.User = None):
        try:
            if user == interaction.user:
                await interaction.response.send_message("You can't go against yourself!!", ephemeral=True)
                return
            if user is None:
                await self.start_game(interaction, amount=0, bot=True)
            else:
                await self.challenge_user(interaction, amount=0, user=user)
        except Exception as error:
            await handle_logs(interaction, error)

    async def challenge_user(self, interaction, amount, user):
        view = ChallengeView(interaction.user, user, amount)
        await interaction.response.send_message(
            f"{user.mention}, you have been challenged by {interaction.user.mention} to a blackjack game! Do you accept?",
            view=view
        )
        await view.wait()
        if view.response is None:  
            await interaction.followup.send("The challenge timed out!", ephemeral=True)
        elif view.response:  
            await self.start_game(interaction, amount=amount, bot=False)
        else:  
            await interaction.followup.send(f"{user.mention} declined the challenge.", ephemeral=True)

    async def start_game(self, interaction, amount, bot):
        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(deck)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        view = BlackjackView(interaction.user, deck, player_hand, dealer_hand, bot, amount)
        await interaction.followup.send(
            embed=view.get_game_state(),
            view=view
        )
        
    @app_commands.command(name="stats", description="View a user's stats for blackjack")
    @app_commands.describe(user="The user you want to view the stats for.")
    async def bjstats(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        stats = gambling_stats(str(user.id), "blackjack")

        embed = discord.Embed(title=f"{user.name}'s Blackjack Stats")
        embed.add_field(name="Wins", value=stats["wins"])
        embed.add_field(name="Losses", value=stats["losses"])
        embed.add_field(name="Draws", value=stats["draws"])
        embed.add_field(name="Coins Won", value=stats["coinsWon"])
        embed.add_field(name="Coins Lost", value=stats["coinsLost"])

        await interaction.response.send_message(embed=embed)
class TicTacToeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tictactoe", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a tic tac toe game")
    @app_commands.describe(amount="The amount you want to wager")
    async def tttwager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="casual", description="Play a casual gane of tic tac toe")
    async def tttcasual(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="stats", description="View a user's stats for tic tac toe")
    @app_commands.describe(user="The user you want to view the stats for.")

    async def tttstats(self, interaction: discord.Interaction, user: str = None):
        pass


class connect4Group(app_commands.Group):
    def __init__(self):
        super().__init__(name="connect4", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a connect 4 game")
    @app_commands.describe(amount="The amount you want to wager")
    async def c4wager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="casual", description="Play a casual gane of connect 4")
    async def c4casual(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="stats", description="View a user's stats for connect 4")
    @app_commands.describe(user="The user you want to view the stats for.")

    async def c4stats(self, interaction: discord.Interaction, user: str = None):
        pass

class slotsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="slots", description="Not coming soon")

    @app_commands.command(name="wager", description="Gamble in slots")
    @app_commands.describe(amount="The amount you want to wager")
    async def slotwager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="stats", description="View a user's stats for slots")
    @app_commands.describe(user="The user you want to view the stats for.")

    async def slotstats(self, interaction: discord.Interaction, user: str = None):
        pass


bot.tree.add_command(BlackjackGroup())
bot.tree.add_command(TicTacToeGroup())
bot.tree.add_command(connect4Group())
bot.tree.add_command(slotsGroup())

# Currency system
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Not coming soon.")

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop commands.")

    @app_commands.command(name="show", description="View the shop.")
    async def show(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()

            embed = discord.Embed(title="Shop Items", color=discord.Color.blue())
            for item in SHOP:
                amount = "Infinity" if item["amount"] == -1 else item["amount"]
                embed.add_field(
                    name=f"{item['item']}",
                    value=f"**Price**: {item['price']}\n**Amount Left**: {amount}\n**Description**: {item['description']}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as error:
            handle_logs(interaction, error)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    async def buy(self, interaction: discord.Interaction, item_name: str, quantity: int):
        for item in SHOP:
            if item["item"].lower() == item_name.lower():
                if item["amount"] == -1 or item["amount"] >= quantity:
                    item["amount"] = item["amount"] - quantity if item["amount"] != -1 else -1
                    await interaction.response.send_message(f"You bought {quantity}x {item_name} for {item['price'] * quantity} coins.")
                    return
                else:
                    await interaction.response.send_message(f"Not enough {item_name} in stock.", ephemeral=True)
                    return

        await interaction.response.send_message(f"Item {item_name} not found in the shop.", ephemeral=True)

class AuctionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="auction", description="Not coming soon.")

bot.tree.add_command(MarketGroup())
bot.tree.add_command(ShopGroup())
bot.tree.add_command(AuctionGroup())

"""F
MISC COMMANDS
"""
@bot.tree.command(name="error_test", description="Demonstrates intentional error generation")
async def error_test(interaction: discord.Interaction):
    error_list = []
    try:
        print(error_list[0]) 
    except Exception as error:
        log_id = store_log("error", ''.join(traceback.format_exception(type(error), error, error.__traceback__)))
        await handle_logs(interaction, error)
        
class AlertGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="alert", description="Used for updates, and allows you to follow along!")

    @app_commands.command(name="follow", description="Subscribe or unsubscribe from updates")
    async def alert_follow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            member_info = open_file("info/member_info.json")
            user = interaction.user.id

            if user not in member_info:
                member_info[user] = {
                    "subscribed": 0
                }
            
            if member_info[user]["subscribed"] == 0:
                member_info[user]["subscribed"] = 1
                await interaction.followup.send("You are now subscribed to updates!")
            else:
                member_info[user]["subscribed"] = 0
                await interaction.followup.send("You are now unsubscribed from updates!")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="send", description="Sends an update to all subscribed users")
    @app_commands.describe(
        type="The type of alert",
        description="Provide a brief description of what's going on",
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Alert", value="alert"),
            app_commands.Choice(name="Update", value="update"),
            app_commands.Choice(name="Warning", value="warning")
        ]
    )
    async def alert_send(self, interaction: discord.Interaction, type: str, description: str):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                await interaction.followup.send("You do not have permission to use this command.")
                return


            alertIDs = []
            member_info = open_file("info/member_info.json")
            for member in member_info:
                if member_info[member]["subscribed"] == 1:
                    alertIDs.append(member)


            embed=discord.Embed(
                title="New update!" if type.value == "alert" else "ALERT" if type.value == "alert" else "WARNING",
                description=description
            )
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(AlertGroup())

async def end_giveaway(interaction: discord.Interaction, giveaway_id: str, server_id: str):
    try:
        server_info = open_file("info/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            await interaction.followup.send("The specified giveaway could not be found.", ephemeral=True)
            return

        duration = giveaway['endTime'] - giveaway['startTime']
        await asyncio.sleep(duration)

        server_info = open_file("info/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            return

        participants = giveaway.get("participants", [])
        winners_count = giveaway.get("winners", 1)

        if participants:
            winner_list = random.sample(participants, k=min(winners_count, len(participants)))
            formatted_winners = ', '.join(f'<@{winner}>' for winner in winner_list)
        else:
            formatted_winners = "No participants."

        embed = discord.Embed(
            title=f"🎉 Giveaway Ended: {giveaway['prize']} 🎉",
            description=f"**Winners:** {formatted_winners}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"ID: {giveaway_id}")

        channel_id = giveaway.get("channel_id")
        message_id = giveaway.get("message_id")
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            await interaction.followup.send("Giveaway channel could not be found.", ephemeral=True)
            return

        message = await channel.fetch_message(message_id)
        if not message:
            await interaction.followup.send("Giveaway message could not be found.", ephemeral=True)
            return

        await message.reply(embed=embed)

    except Exception as error:
        await handle_logs(interaction, error)

class GiveawayButtonView(discord.ui.View):
    def __init__(self, giveaway_id: str, server_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.server_id = server_id

    async def disable_buttons(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Enter/Leave Giveaway", style=discord.ButtonStyle.blurple)
    async def enter_leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            server_info = open_file("info/server_info.json")
            server_info.setdefault(self.server_id, {}).setdefault("giveaways", {})

            if self.giveaway_id not in server_info[self.server_id]["giveaways"]:
                raise KeyError(f"Giveaway ID {self.giveaway_id} not found in server {self.server_id}.")

            giveaway = server_info[self.server_id]["giveaways"][self.giveaway_id]
            participants = giveaway["participants"]

            if interaction.user.id in participants:
                participants.remove(interaction.user.id)
                message = "You have left the giveaway."
            else:
                participants.append(interaction.user.id)
                message = "You have joined the giveaway."

            embed = interaction.message.embeds[0]
            description_lines = embed.description.split("\n")
            for i, line in enumerate(description_lines):
                if line.startswith("**Participants:**"):
                    description_lines[i] = f"**Participants:** {len(participants)}"
                    break
            else:
                description_lines.append(f"**Participants:** {len(participants)}")
            
            embed.description = "\n".join(description_lines)

            save_file("info/server_info.json", server_info)

            await interaction.message.edit(embed=embed, view=self)

            await interaction.response.send_message(content=message, ephemeral=True)

        except KeyError as ke:
            await interaction.response.send_message("An error occurred: Giveaway not found.", ephemeral=True)
        except Exception as error:
            await handle_logs(interaction, error)


class GiveawayGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="giveaway", description="Giveaway related commands")

    @app_commands.command(name="reroll", description="Rerolls a giveaway's winner/s")
    @app_commands.describe(id="ID of the giveaway", winners="Number of winners to reroll")
    async def greroll(self, interaction: discord.Interaction, id: str, winners: int):
        await interaction.response.defer()
        try:
            server_id = str(interaction.guild_id)
            server_info = open_file("info/server_info.json")
            
            if server_id not in server_info or "giveaways" not in server_info[server_id]:
                return await interaction.followup.send("No giveaways found for this server.", ephemeral=True)

            giveaways = server_info[server_id]["giveaways"]
            if id not in giveaways:
                return await interaction.followup.send(f"Giveaway with ID `{id}` not found.", ephemeral=True)

            giveaway = giveaways[id]

            participants = giveaway.get("participants", [])
            if len(participants) < winners:
                return await interaction.followup.send(
                    "Not enough participants to reroll the specified number of winners.", ephemeral=True
                )

            rerolled_winners = random.sample(participants, winners)
            formatted_winners = ", ".join([f"<@{user}>" for user in rerolled_winners])

            embed = discord.Embed(
                title=f"🎉 Giveaway Rerolled: {giveaway['prize']} 🎉",
                description=f"**New Winners:** {formatted_winners}",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"ID: {id}")

            await interaction.followup.send(embed=embed)

        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="create", description="Creates a giveaway")
    @app_commands.describe(
        prize="The prize of the giveaway",
        duration="Duration of the giveaway. Ex. 1d6h30m15s",
        description="An optional description to add",
        requirement="A role required to join the giveaway",
        winners="The number of people who will win the giveaway"
    )
    async def ggiveaway(self, interaction: discord.Interaction, prize: str, duration: str, description: str = None, requirement: discord.Role = None, winners: int = 1):
        await interaction.response.defer()
        try:
            server_info = open_file("info/server_info.json")
            duration_timedelta = parse_duration(duration)
            if duration_timedelta is None or duration_timedelta.total_seconds() <= 0:
                raise ValueError("Duration must be greater than 0.")

            start_time = int(time.time())
            end_time = start_time + int(duration_timedelta.total_seconds())

            giveaway_id = str(int(time.time()))

            server_id = str(interaction.guild.id)
            if server_id not in server_info:
                server_info[server_id] = {}

            if "giveaways" not in server_info[server_id]:
                server_info[server_id]["giveaways"] = {}

            server_info[server_id]["giveaways"][giveaway_id] = {
                "host": interaction.user.id,
                "prize": prize,
                "startTime": start_time,
                "endTime": end_time,
                "description": description or "No description provided.",
                "requirement": requirement.id if requirement else None,
                "winners": winners,
                "participants": [],
            }
            save_file("info/server_info.json", server_info)

            embed = discord.Embed(
                title=f"🎉 {prize} 🎉",
                description=(f"{description}\n\n" if description else "") +
                f"**Ends at**: <t:{end_time}:T> (<t:{end_time}:R>)\n" +
                (f"**Requirement**: {requirement.mention}\n" if requirement else "")
            )
            embed.set_footer(text=f"{winners} Winner(s)")
            embed.set_author(name=f"ID: {giveaway_id} | Hosted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            view = GiveawayButtonView(giveaway_id, server_id)

            message = await interaction.followup.send(embed=embed, view=view)
            server_info[server_id]["giveaways"][giveaway_id]["channel_id"] = interaction.channel_id
            server_info[server_id]["giveaways"][giveaway_id]["message_id"] = message.id
            save_file("info/server_info.json", server_info)

            asyncio.create_task(end_giveaway(interaction, giveaway_id, server_id))
            
        except Exception as error:
            await handle_logs(interaction, error)

bot.tree.add_command(GiveawayGroup())

"""
OTHER COMMANDS
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

class ReportButtons(discord.ui.View):
    def __init__(self, report_id, reports_data, message):
        super().__init__(timeout=None)
        self.report_id = str(report_id)
        self.reports_data = reports_data
        self.message = message

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.",ephemeral=True,)
            return

        report["Status"] = "Accepted"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been accepted!")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Accepted\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been accepted.", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defe
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.", ephemeral=True)
            return

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been declined.", ephemeral=True)

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary)
    async def blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        blacklist_user(interaction.user.id)

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)
        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.\nYou are now ticket blacklisted.")

        await interaction.followup.send(f"The report has been declined and the reported is now blacklisted.", ephemeral=True)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} has been declined and you have been blacklisted.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined (Blacklisted)\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.greyple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="report", description="Report an in game rule breaker")
@app_commands.choices(
    type=[
        app_commands.Choice(name="Auto Win", value="Auto Win"),
        app_commands.Choice(name="Ability Spam", value="Ability Spam"),
        app_commands.Choice(name="Alchemist Auto Brew", value="Alchemist Auto Brew"),
        app_commands.Choice(name="Bob Auto Farm", value="Bob Auto Farm"),
        app_commands.Choice(name="Bypassing", value="Bypassing"),
        app_commands.Choice(name="False Votekick", value="False Votekick"),
        app_commands.Choice(name="Flight", value="Flight"),
        app_commands.Choice(name="Framing Exploit", value="Framing Exploit"),
        app_commands.Choice(name="Item Vacuum", value="Item Vacuum"),
        app_commands.Choice(name="Kick Exploit", value="Kick Exploit"),
        app_commands.Choice(name="Godmode", value="Godmode"),
        app_commands.Choice(name="NSFW", value="NSFW"),
        app_commands.Choice(name="Reach", value="Reach"),
        app_commands.Choice(name="Rhythm Ability Spam", value="Rhythm Ability Spam"),
        app_commands.Choice(name="Slap Aura", value="Slap Aura"),
        app_commands.Choice(name="Slap Auto Farm", value="Slap Auto Farm"),
        app_commands.Choice(name="Slapple Farm", value="Slapple Farm"),
        app_commands.Choice(name="Teleport", value="Teleport"),
        app_commands.Choice(name="Toxicity", value="Toxicity"),
        app_commands.Choice(name="Trap Auto Farm", value="Trap Auto Farm"),
        app_commands.Choice(name="Anti Acid/Lava", value="Anti Acid/Lava"),
        app_commands.Choice(name="Anti Ragdoll", value="Anti Ragdoll"),
        app_commands.Choice(name="Anti Void", value="Anti Void"),
        app_commands.Choice(name="Other", value="Other"),
    ]
)
@app_commands.describe(
    type="The type of exploit they used",
    proof="Use medal or youtube and post the link",
    user="The user to report",
    other="Any other information needed)",
)
async def report(interaction: discord.Interaction, type: str, proof: str, user: str, other: str):
    await interaction.response.defer(ephemeral=True)
    try:
        member_info = open_file("info/member_info.json")
        reporter_id = str(interaction.user.id)

        if member_info.get(reporter_id, {}).get("TicketBlacklist"):
            await interaction.followup.send("You are blacklisted from submitting reports.", ephemeral=True)
            return

        reports_data = open_file("info/reports.json")
        report_id = get_next_report_id(reports_data)

        timestamp = datetime.now().isoformat()
        new_report = {
            "Status": "Open",
            "Reporter": reporter_id,
            "User": user,
            "Proof": proof,
            "Type": type,
            "Other": other,
            "Timestamp": timestamp,
        }

        reports_data[str(report_id)] = new_report
        save_file("reports.json", reports_data)

        report_embed = discord.Embed(
            title=f"Report ID: {report_id}",
            description=f"**Type:** {type}\n**Proof:** {proof}\n**Reported User:** {user}\n**Other:** {other}",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )

        report_embed.set_footer(text=f"Reported by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

        guild = interaction.client.get_guild(1279160584662679673)
        report_channel = guild.get_channel(1292649491203096646)
        if report_channel:
            message = await report_channel.send(embed=report_embed, view=None)
            await message.edit(view=ReportButtons(report_id, reports_data, message))
            await interaction.followup.send(f"Your report has been submitted for {user}.")
        else:
            await interaction.followup.send("Report channel not found.", ephemeral=True)
    except Exception as error:
        await handle_logs(interaction, error)

bot.run(token)
