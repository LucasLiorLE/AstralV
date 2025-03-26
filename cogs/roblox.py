from bot_utils import (
    rbx_fetchUserID,
    rbx_fetchUserBio,

    check_user,
    open_json,
    save_json,
    load_commands,
    handle_logs,
)

import discord
from discord.ext import commands
from discord.ui import View, Button, button
from discord import app_commands, ButtonStyle

import random, asyncio, aiohttp
from collections import deque
from datetime import datetime
from typing import List
import time

async def get_connected_accounts(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    member_info = open_json("storage/member_info.json")
    choices = []
    
    for user_id, info in member_info.items():
        if "roblox_username" in info:
            username = info["roblox_username"]
            id = info["roblox_id"]
            if current.lower() in username.lower():
                try:
                    display = f"{username} ({id})"
                    choices.append(app_commands.Choice(name=display, value=username))
                except:
                    choices.append(app_commands.Choice(name=username, value=username))
    
    return choices[:25]

async def autocomplete_badge_name(interaction: discord.Interaction, current: str):
    gloves = open_json("storage/bot_data.json")["cgloves"]
    badge_names = [glove for glove in gloves.keys()]
    return [
        app_commands.Choice(name=badge, value=badge)
        for badge in badge_names if current.lower() in badge.lower()
    ][:25]

class SequenceButton(discord.ui.View):
    def __init__(self, sequence: str):
        super().__init__(timeout=None)
        self.sequence = sequence

    @discord.ui.button(label="Show Sequence", style=discord.ButtonStyle.primary)
    async def show_sequence(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(self.sequence, ephemeral=True)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class CGlovesGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="cgloves", description="Slap Battles glove-related commands", guild_only=False)
        self.setup_commands()

    def setup_commands(self):
        # Gonna use this for some stuff until a rework for load_commands
        command_help = open_json("storage/command_help.json")
        cgloves_data = command_help.get("roblox", {}).get("cgloves", {})
        
        if "description" in cgloves_data:
            self.description = cgloves_data["description"]
            
        if "subcommands" in cgloves_data:
            for cmd in self.commands:
                if cmd.name in cgloves_data["subcommands"]:
                    cmd_data = cgloves_data["subcommands"][cmd.name]
                    cmd.description = cmd_data.get("description", cmd.description)
                    
                    if "parameters" in cmd_data:
                        for param_name, param_desc in cmd_data["parameters"].items():
                            if param_name in cmd._params:
                                cmd._params[param_name].description = param_desc

    @app_commands.command(name="check")
    @app_commands.autocomplete(username=get_connected_accounts)
    async def check(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if username:
                roblox_id = await rbx_fetchUserID(username)
                if roblox_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_json("storage/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

                roblox_id = member_info[discord_user_id]["roblox_id"]

            gloves = open_json("storage/bot_data.json")["cgloves"]
            all_badge_ids = [badge_id for badge_ids in gloves.values() for badge_id in badge_ids]

            def split_into_chunks(lst, chunk_size):
                for i in range(0, len(lst), chunk_size):
                    yield lst[i:i + chunk_size]

            badge_chunks = list(split_into_chunks(all_badge_ids, 99))
            all_badge_data = []

            async with aiohttp.ClientSession() as session:
                for chunk in badge_chunks:
                    url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, chunk))}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            all_badge_data.extend(data["data"])
                        else:
                            await interaction.followup.send("An error occurred while fetching the user's gloves.")
                            return

                if not all_badge_data:
                    await interaction.followup.send(f"No badges found for the user: {username if username else interaction.user.name}")
                    return

                owned = [
                    glove
                    for glove, badge_ids in gloves.items()
                    if all(
                        any(badge.get("badgeId") == badge_id for badge in all_badge_data)
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
                    color=0xDA8EE7,
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
                    for badge in all_badge_data
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

                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        badge_embed = discord.Embed(
                            title=f"Additional Badges for {username if username else interaction.user.name} ({roblox_id}):",
                            color=0xDA8EE7,
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

        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="compare")
    @app_commands.autocomplete(username1=get_connected_accounts, username2=get_connected_accounts)
    async def compare(self, interaction: discord.Interaction, username1: str = None, member1: discord.Member = None, username2: str = None, member2: discord.Member = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if username1:
                roblox_id1 = await rbx_fetchUserID(username1)
                if roblox_id1 is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username1}.")
                    return
                display_name1 = username1
            else:
                discord_user_id1 = str(member1.id) if member1 is not None else str(interaction.user.id)
                member_info = open_json("storage/member_info.json")
                if discord_user_id1 not in member_info or "roblox_id" not in member_info[discord_user_id1]:
                    await interaction.followup.send("The first account is not linked.")
                    return
                roblox_id1 = member_info[discord_user_id1]["roblox_id"]
                display_name1 = member_info[discord_user_id1]["roblox_username"]

            if username2:
                roblox_id2 = await rbx_fetchUserID(username2)
                if roblox_id2 is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username2}.")
                    return
                display_name2 = username2
            else:
                if not member2:
                    await interaction.followup.send("Please provide either a username or member to compare with.")
                    return
                discord_user_id2 = str(member2.id)
                if discord_user_id2 not in member_info or "roblox_id" not in member_info[discord_user_id2]:
                    await interaction.followup.send("The second account is not linked.")
                    return
                roblox_id2 = member_info[discord_user_id2]["roblox_id"]
                display_name2 = member_info[discord_user_id2]["roblox_username"]

            gloves = open_json("storage/bot_data.json")["cgloves"]
            all_badge_ids = [badge_id for badge_ids in gloves.values() for badge_id in badge_ids]

            def split_into_chunks(lst, chunk_size):
                for i in range(0, len(lst), chunk_size):
                    yield lst[i:i + chunk_size]

            badge_chunks = list(split_into_chunks(all_badge_ids, 99))

            async def get_user_data(roblox_id):
                all_badge_data = []
                async with aiohttp.ClientSession() as session:
                    for chunk in badge_chunks:
                        url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, chunk))}"
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                all_badge_data.extend(data["data"])

                owned = [
                    glove
                    for glove, badge_ids in gloves.items()
                    if all(
                        any(badge.get("badgeId") == badge_id for badge in all_badge_data)
                        for badge_id in badge_ids
                    )
                ]
                return owned

            owned1 = await get_user_data(roblox_id1)
            owned2 = await get_user_data(roblox_id2)

            compare_embed = discord.Embed(
                title=f"Glove Comparison",
                description=f"Comparing gloves between {display_name1} and {display_name2}",
                color=0xDA8EE7
            )

            total_gloves = len(gloves)
            owned1_count = len(owned1)
            owned2_count = len(owned2)
            
            unique_to_1 = set(owned1) - set(owned2)
            unique_to_2 = set(owned2) - set(owned1)
            shared_gloves = set(owned1) & set(owned2)
            not_owned_by_neither = set(gloves.keys()) - set(owned1) - set(owned2)

            compare_embed.add_field(
                name=f"{display_name1}'s Stats",
                value=f"Total Gloves: {owned1_count}/{total_gloves} ({(owned1_count/total_gloves*100):.1f}%)",
                inline=True
            )
            compare_embed.add_field(
                name=f"{display_name2}'s Stats",
                value=f"Total Gloves: {owned2_count}/{total_gloves} ({(owned2_count/total_gloves*100):.1f}%)",
                inline=True
            )
            compare_embed.add_field(name="\u200b", value="\u200b", inline=True)

            if unique_to_1:
                compare_embed.add_field(
                    name=f"Gloves only {display_name1} has",
                    value=", ".join(sorted(unique_to_1)) if unique_to_1 else "None",
                    inline=False
                )
            if unique_to_2:
                compare_embed.add_field(
                    name=f"Gloves only {display_name2} has",
                    value=", ".join(sorted(unique_to_2)) if unique_to_2 else "None",
                    inline=False
                )
            compare_embed.add_field(
                name="Shared Gloves",
                value=", ".join(sorted(shared_gloves)) if shared_gloves else "None",
                inline=False
            )
            if not_owned_by_neither:
                compare_embed.add_field(
                    name="Not owned by neither",
                    value=", ".join(sorted(not_owned_by_neither)) if not_owned_by_neither else "None",
                    inline=False
                )

            await interaction.followup.send(embed=compare_embed)

        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="search")
    @app_commands.autocomplete(badge=autocomplete_badge_name, user=get_connected_accounts)
    async def search(self, interaction: discord.Interaction, badge: str, user: str = None):
        await interaction.response.defer()
    
        try:
            if user:
                roblox_id = await rbx_fetchUserID(user)
                if roblox_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {user}.")
                    return
            else:
                discord_user_id = str(interaction.user.id)
                member_info = open_json("storage/member_info.json")
    
                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("Your account is not linked.")
                    return
    
                roblox_id = member_info[discord_user_id]["roblox_id"]
    
            gloves = open_json("storage/bot_data.json")["cgloves"]
            if badge not in gloves:
                await interaction.followup.send("Invalid badge name.")
                return
    
            badge_ids = gloves[badge]
            url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, badge_ids))}"
    
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data["data"]:
                            await interaction.followup.send(f"{user or interaction.user.name} does not have the `{badge}` badge.")
                            return
    
                        awarded_date = data["data"][0]["awardedDate"]

                        date, _, _ = awarded_date.partition(".")
                        date = datetime.strptime(date + "+0000", "%Y-%m-%dT%H:%M:%S%z")
                        epoch_time = int(date.timestamp())
    
                        embed = discord.Embed(
                            title=f"Badge Info: {badge}",
                            description=f"**User:** {user or interaction.user.name}\n**Obtained:** <t:{epoch_time}:F>",
                            color=0xDA8EE7
                        )
                        await interaction.followup.send(embed=embed)
    
                    else:
                        await interaction.followup.send("Failed to retrieve badge data.")
    
        except Exception as error:
            await handle_logs(interaction, error)

async def get_friends(session: aiohttp.ClientSession, user_id: int) -> dict:
    url = f"https://friends.roblox.com/v1/users/{user_id}/friends"
    async with session.get(url) as response:
        data = await response.json()
        if response.status == 200:
            return {int(friend['id']): friend['name'] for friend in data.get('data', [])}
        elif "errors" in data and data["errors"] and data["errors"][0].get("message") == "":
            return None
        return {}

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class RobloxGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="roblox", description="Roblox account-related commands", guild_only=False)
        load_commands(self.commands, "roblox")

    @app_commands.command(name="connect")
    async def rbxconnect(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            color_sequence = " ".join(
                random.choices(
                    ["orange", "strawberry", "pear", "apple", "banana", "watermelon"], k=10
                )
            )
            view = SequenceButton(color_sequence)
            await interaction.followup.send(
                "Please update your roblox bio to the provided sequence after you click the button. You will have 1 minute.",
                view=view
            )

            await asyncio.sleep(60)

            roblox_user_id = await rbx_fetchUserID(username)
            if roblox_user_id is None:
                await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                return

            bio = await rbx_fetchUserBio(roblox_user_id)

            if color_sequence in bio:
                member_info = open_json("storage/member_info.json")
                discord_user_id = str(interaction.user.id)

                if discord_user_id not in member_info:
                    member_info[discord_user_id] = {}

                member_info[discord_user_id]["roblox_username"] = username
                member_info[discord_user_id]["roblox_id"] = roblox_user_id
                save_json("storage/member_info.json", member_info)

                await interaction.followup.send(f"Success! Your Roblox account is now linked.")

            else:
                await interaction.followup.send("Failed! Your Roblox bio did not match the given sequence.")
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="description")
    @app_commands.autocomplete(username=get_connected_accounts)
    async def rbxdescription(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None):
        await interaction.response.defer()
        try:
            if username:
                roblox_user_id = await rbx_fetchUserID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_json("storage/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

                roblox_user_id = member_info[discord_user_id]["roblox_id"]

            bio = await rbx_fetchUserBio(roblox_user_id)
            embed = discord.Embed(title=f"User Description for {roblox_user_id}", description=bio, color=0x808080)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="info")
    @app_commands.autocomplete(username=get_connected_accounts)
    async def rbxinfo(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None):
        await interaction.response.defer()
        try:
            if username:
                roblox_user_id = await rbx_fetchUserID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_json("storage/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

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

    @app_commands.command(name="avatar")
    @app_commands.autocomplete(username=get_connected_accounts)
    async def rbxavatar(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None, items: bool = False):
        await interaction.response.defer()
        try:
            if username:
                roblox_user_id = await rbx_fetchUserID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_json("storage/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

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

    @app_commands.command(name="friendswith")
    @app_commands.autocomplete(username1=get_connected_accounts, username2=get_connected_accounts)
    async def friendswith(self, interaction: discord.Interaction, username1: str = None, username2: str = None):
        await interaction.response.defer()
        start_time = time.time()
        
        if not username1 or not username2:
            return await interaction.followup.send("Please provide both usernames.")
        if username1.lower() == username2.lower():
            return await interaction.followup.send("Please provide two different usernames.")

        status_msg = await interaction.followup.send("⚠️ Starting search...", ephemeral=True)
        
        async with aiohttp.ClientSession() as session:
            try:
                id1, id2 = await asyncio.gather(
                    rbx_fetchUserID(username1), rbx_fetchUserID(username2)
                )
                if not id1 or not id2:
                    await status_msg.delete()
                    return await interaction.followup.send(f"Could not find Roblox user(s): {username1 if not id1 else ''} {username2 if not id2 else ''}")
            except Exception as e:
                await status_msg.delete()
                return await interaction.followup.send(f"Error fetching user IDs: {str(e)}")

            if id1 == id2:
                await status_msg.delete()
                return await interaction.followup.send("You cannot check closeness with the same user!")

            try:
                friends1, friends2 = await asyncio.gather(
                    get_friends(session, id1), get_friends(session, id2)
                )
                if friends1 is None or friends2 is None:
                    await status_msg.delete()
                    return await interaction.followup.send(f"Cannot access friend list for {username1 if friends1 is None else username2}. Their friends list may be private.")
            except Exception as e:
                await status_msg.delete()
                return await interaction.followup.send(f"Error fetching friends: {str(e)}")

            if id2 in friends1:
                await status_msg.delete()
                return await self.send_embed(interaction, [id1, id2], [username1, username2], 1, start_time)

            await status_msg.edit(content="⚠️ Users aren't direct friends. Starting breadth-first search...")
            path, total_checked = await self.bidirectional_bfs(session, id1, id2, friends1, friends2, status_msg)
            
            if not path:
                return await interaction.followup.send(f"No connection found between {username1} and {username2} after checking {total_checked} users.")
            
            await self.send_embed(interaction, path, [username1, username2], len(path) - 1, start_time, total_checked)

    async def bidirectional_bfs(self, session, id1, id2, friends1, friends2, status_msg):
        forward_queue, backward_queue = deque([(id1, None)]), deque([(id2, None)])
        forward_visited, backward_visited = {id1: None}, {id2: None}
        usernames, total_checked = {id1: "User1", id2: "User2"}, 0
        last_update = time.time()
        
        while forward_queue and backward_queue:
            total_checked += 1
            current_time = time.time()
            
            if current_time - last_update >= 1:
                forward_depth = len(forward_visited)
                backward_depth = len(backward_visited)
                total_visited = forward_depth + backward_depth
                status = (
                    f"⚠️ Searching...\n"
                    f"Users checked: {total_checked}\n"
                    f"Forward search depth: {forward_depth}\n"
                    f"Backward search depth: {backward_depth}\n"
                    f"Total visited users: {total_visited}"
                )
                await status_msg.edit(content=status)
                last_update = current_time

            if await self.process_queue(session, forward_queue, forward_visited, backward_visited, usernames):
                return self.build_path(forward_visited, backward_visited), total_checked
            
            if await self.process_queue(session, backward_queue, backward_visited, forward_visited, usernames):
                return self.build_path(forward_visited, backward_visited), total_checked
        
        return None, total_checked

    async def process_queue(self, session, queue, visited, opposite_visited, usernames):
        if queue:
            current_id, parent = queue.popleft()
            friends = await get_friends(session, current_id)
            if friends is None:
                return False

            for friend_id, friend_name in friends.items():
                if friend_id in opposite_visited:
                    visited[friend_id] = current_id
                    return True
                if friend_id not in visited:
                    visited[friend_id] = current_id
                    queue.append((friend_id, current_id))
                    usernames[friend_id] = friend_name
        return False

    def build_path(self, forward_visited, backward_visited):
        path = []
        current = next(iter(set(forward_visited) & set(backward_visited)))
        while current:
            path.append(current)
            current = forward_visited[current]
        path.reverse()
        
        current = backward_visited[next(iter(set(forward_visited) & set(backward_visited)))]
        while current:
            path.append(current)
            current = backward_visited[current]
        return path

    async def send_embed(self, interaction, path, usernames, degrees, start_time, total_checked=0):
        path_str = " → ".join(f"[{usernames[i]}](https://www.roblox.com/users/{uid}/profile)" for i, uid in enumerate(path))
        elapsed_time = round(time.time() - start_time, 2)
        embed = discord.Embed(title="Friend Connection Path", description=path_str, color=0xDA8EE7)
        embed.set_footer(text=f"Degrees of separation: {degrees} | Users checked: {total_checked} | Time taken: {elapsed_time}s")
        await interaction.followup.send(embed=embed)

class GloveView(View):
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
        self.additional_badges_button.disabled = self.current_page == "additional_badges"
        self.gamepass_data_button.disabled = self.current_page == "gamepass_data"

    @button(label="Glove Data", style=ButtonStyle.secondary)
    async def glove_data_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            return await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
        
        self.current_page = "glove_data"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.glove_embed], view=self)

    @button(label="Full Glove Data", style=ButtonStyle.secondary)
    async def full_glove_data_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            return await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)

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
            color=0xDA8EE7,
        )

        await interaction.response.edit_message(embeds=[full_glove_embed], view=self)

    @button(label="Additional Badges", style=ButtonStyle.secondary)
    async def additional_badges_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            return await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            
        self.current_page = "additional_badges"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.badge_embed], view=self)

    @button(label="Gamepass Data", style=ButtonStyle.secondary)
    async def gamepass_data_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            return await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            
        self.current_page = "gamepass_data"
        self.update_buttons()

        gamepass_embed = discord.Embed(title=f"Gamepass Data for {interaction.user.name}", color=0xDA8EE7)
        gamepass_embed.add_field(name="Owned", value=", ".join(self.owned_gamepasses) if self.owned_gamepasses else "None", inline=False)
        gamepass_embed.add_field(name="Not Owned", value=", ".join(self.not_owned_gamepasses) if self.not_owned_gamepasses else "None", inline=False)

        await interaction.response.edit_message(embed=gamepass_embed, view=self)

class RobloxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(RobloxGroup())
        self.bot.tree.add_command(CGlovesGroup())
        load_commands(self.__cog_app_commands__, "roblox")

async def setup(bot):
    await bot.add_cog(RobloxCog(bot))