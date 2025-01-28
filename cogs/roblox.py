from bot_utils import (
    open_file,
    save_file,
    GetRobloxID,
    fetch_roblox_bio,
    check_user,
    handle_logs
)

import discord
from discord.ext import commands
from discord.ui import View, Button, button
from discord import app_commands, ButtonStyle

import random, asyncio, aiohttp
from datetime import datetime

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
            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_file("info/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

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
            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_file("info/member_info.json")

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

    @app_commands.command(name="avatar", description="Provides a Roblox account's avatar.")
    @app_commands.describe(username="The username of the Roblox account (leave blank to use linked account).", items="Whether or not to display the list of currently worn items (default: False).")
    async def rbxavatar(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None, items: bool = False):
        await interaction.response.defer()
        try:
            if username:
                roblox_user_id = await GetRobloxID(username)
                if roblox_user_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_file("info/member_info.json")

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
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        
        self.current_page = "glove_data"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.glove_embed], view=self)

    @button(label="Full Glove Data", style=ButtonStyle.secondary)
    async def full_glove_data_button(self, interaction: discord.Interaction, button: Button):
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

    @button(label="Additional Badges", style=ButtonStyle.secondary)
    async def additional_badges_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "additional_badges"
        self.update_buttons()
        await interaction.response.edit_message(embeds=[self.badge_embed], view=self)

    @button(label="Gamepass Data", style=ButtonStyle.secondary)
    async def gamepass_data_button(self, interaction: discord.Interaction, button: Button):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return
        self.current_page = "gamepass_data"
        self.update_buttons()

        gamepass_embed = discord.Embed(title=f"Gamepass Data for {interaction.user.name}", color=0xFF0000)
        gamepass_embed.add_field(name="Owned", value=", ".join(self.owned_gamepasses) if self.owned_gamepasses else "None", inline=False)
        gamepass_embed.add_field(name="Not Owned", value=", ".join(self.not_owned_gamepasses) if self.not_owned_gamepasses else "None", inline=False)

        await interaction.response.edit_message(embed=gamepass_embed, view=self)

class RobloxCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.bot.tree.add_command(RobloxGroup())

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="cgloves", description="Check all the user's gloves in slap battles.")
    @app_commands.describe(username="The user to check gloves for (leave empty to check your own)", ephemeral="If the message is hidden (Useful if no perms)")
    async def cgloves(self, interaction: discord.Interaction, username: str = None, member: discord.Member = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if username:
                roblox_id = await GetRobloxID(username)
                if roblox_id is None:
                    await interaction.followup.send(f"Failed to retrieve Roblox ID for {username}.")
                    return
            else:
                discord_user_id = str(member.id) if member is not None else str(interaction.user.id)
                member_info = open_file("info/member_info.json")

                if discord_user_id not in member_info or "roblox_id" not in member_info[discord_user_id]:
                    await interaction.followup.send("The specified account (or yours) is not linked.")
                    return

                roblox_id = member_info[discord_user_id]["roblox_id"]

            gloves = open_file("storage/gloves.json")
            all_badge_ids = [badge_id for badge_ids in gloves.values() for badge_id in badge_ids]

            def split_into_chunks(lst, chunk_size):
                for i in range(0, len(lst), chunk_size):
                    yield lst[i:i + chunk_size] # First time using yield in 6k lines of code

            badge_chunks = list(split_into_chunks(all_badge_ids, 99))
            all_badge_data = []

            async with aiohttp.ClientSession() as session:
                for chunk in badge_chunks:
                    url = f"https://badges.roblox.com/v1/users/{roblox_id}/badges/awarded-dates?badgeIds={','.join(map(str, chunk))}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            all_badge_data.extend(data["data"]) # I don't think I've ued extend in 6k lines of code either lol
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
                    color=interaction.user.top_role.color or 0xFF0000,
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

async def setup(bot):
    await bot.add_cog(RobloxCog(bot))