from bot_utils import (
    open_file,
    save_file,
    load_commands,
    handle_logs
)

import discord
from discord.ext import commands
from discord import app_commands

import re
from aiohttp import ClientSession

class BloonsTD6CommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="btd6", description="Bloons Tower Defense 6 related commands")
        load_commands(self.commands, "btd6")

    @app_commands.command(name="connect")
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
                member_info = open_file("storage/member_info.json")
                discord_user_id = str(interaction.user.id)

                if (discord_user_id not in member_info):
                    member_info[discord_user_id] = {}

                member_info[discord_user_id]["btd6oakkey"] = oak_key
                save_file("storage/member_info.json", member_info)
                
                await interaction.followup.send("Success! Your BTD6 (Maybe someone else's) was successfully linked.")
        except Exception as e:
            await handle_logs(interaction, e)

        
    @app_commands.command(name="racedata")
    @app_commands.describe(race_id="ID or name of the race you want to view the data for.")
    async def btd6racedata(self, interaction: discord.Interaction, race_id: str):
        await interaction.response.defer()
        try:
            async with ClientSession() as session:
                async with session.get("https://data.ninjakiwi.com/btd6/races") as response:
                    if response.status == 200:
                        races_data = await response.json()
                        
                        if (races_data.get("success") and races_data.get("body")):
                            found_race = None
                            for race in races_data["body"]:
                                if (str(race["id"]) == race_id or race["name"].lower() == race_id.lower()):
                                    found_race = race
                                    break
                            
                            if found_race:
                                embed = discord.Embed(
                                    title=f"<:btd6Race:1312989026147631154> BTD6 Race: {found_race['name']}",
                                    description=f"Race ID: {found_race['id']}",
                                    color=discord.Color.red()
                                )
                                
                                start_time = int(found_race['start'] / 1000)
                                end_time = int(found_race['end'] / 1000)
                                
                                embed.add_field(
                                    name="Time Information",
                                    value=f"Start: <t:{start_time}:F>\nEnd: <t:{end_time}:F>",
                                    inline=False
                                )
                                
                                embed.add_field(
                                    name="Participation",
                                    value=f"Total Scores: {found_race.get('totalScores', 'Unknown'):,}",
                                    inline=False
                                )
                                
                                await interaction.followup.send(embed=embed)
                            else:
                                await interaction.followup.send("Race not found. Please check the race ID or name and try again.", ephemeral=True)
                        else:
                            await interaction.followup.send("Failed to retrieve race data.", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Error occurred while fetching race data. Status code: {response.status}", ephemeral=True)
        except Exception as e:
            print(f"Exception in racedata command: {str(e)}")
            await handle_logs(interaction, e)
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="racelb")
    @app_commands.describe(race_id="ID of the race you want to view the leaderboard for.")
    async def btd6racelb(self, interaction: discord.Interaction, race_id: str):
        await interaction.response.defer()
        try:
            emoji_data = open_file("storage/emoji_data.json")

            async with ClientSession() as session:
                async with session.get(f"https://data.ninjakiwi.com/btd6/races/{race_id}/leaderboard") as response:
                    if response.status == 200:
                        data = await response.json()            

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

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="races")
    async def btd6races(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            async with ClientSession() as session:
                async with session.get("https://data.ninjakiwi.com/btd6/races") as response:
                    if response.status == 200:
                        data = await response.json()
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
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="profile")
    @app_commands.describe(oak_key="https://support.ninjakiwi.com/hc/en-us/articles/13438499873937-Open-Data-API")
    async def btd6profile(self, interaction: discord.Interaction, oak_key: str = None):
        await interaction.response.defer()
        try:
            if not oak_key:
                member_info = open_file("storage/member_info.json")
                discord_user_id = str(interaction.user.id)
                if (discord_user_id not in member_info or "btd6oakkey" not in member_info[discord_user_id]):
                    await interaction.followup.send("You do not have a linked BTD6 account.")
                    return
                else:
                    oak_key = member_info[discord_user_id]["btd6oakkey"]

            async with ClientSession() as session:
                async with session.get(f"https://data.ninjakiwi.com/btd6/users/{oak_key}") as response:
                    if response.status == 200:
                        data = await response.json()

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
                            embed.add_field(name="Rank", value=str(rank))
                            if int(rank) > 155:
                                embed.add_field(name="Veteran Rank", value=str(veteran_rank))
                                
                            embed.add_field(name="Achievements", value=f"{str(achievements)}/150")
                            embed.add_field(name="Most Experienced Monkey", value=most_experienced_monkey)
                            embed.add_field(name="Followers", value=str(followers))

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

                            embed.add_field(name="Total Cash Earned", value=f"${format_number(total_cash_earned)}")
                            embed.add_field(name="Highest Round", value=str(highest_round))
                            embed.add_field(name="Total Games Won", value=f"{str(total_games_won)}/{str(total_games_played)}")
                            embed.add_field(name="Total Monkeys Placed", value=format_number(total_monkeys_placed))

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
        except Exception as e:
            await handle_logs(interaction, e)

class BloonsTD6Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(BloonsTD6CommandGroup())

async def setup(bot):
    await bot.add_cog(BloonsTD6Cog(bot))