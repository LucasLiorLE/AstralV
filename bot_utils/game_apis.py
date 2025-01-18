import discord
from aiohttp import ClientSession
from typing import Optional, Union, Dict, Any, TypedDict
import os

cr_api = os.getenv("cr_api")

class ClanData(TypedDict):
    """Type definition for Clash Royale clan data"""
    name: str
    tag: str
    clanScore: int
    clanWarTrophies: int
    requiredTrophies: int
    donationsPerWeek: int
    members: int
    description: str
    type: str

"""
CLASH ROYALE COMMANDS
"""

async def get_player_data(tag: str) -> Optional[Dict[str, Any]]:
    """
    Fetches Clash Royale player data from the official API.
    
    Parameters:
        tag (str): Player's unique identifier
        
    Returns:
        Optional[Dict[str, Any]]: Player data if found, None if not found
        
    Raises:
        aiohttp.ClientError: On API connection issues
    """
    api_url = f"https://api.clashroyale.com/v1/players/{tag}"  
    headers = {"Authorization": f"Bearer {cr_api}"}

    async with ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            response_json = await response.json()

            if response.status == 200:
                return response_json
            if response.status == 400:
                return True

async def get_clan_data(clan_tag: str) -> Optional[ClanData]:
    """
    Fetches Clash Royale clan data from the official API.
    
    Parameters:
        clan_tag (str): Clan's unique identifier
        
    Returns:
        Optional[ClanData]: Structured clan data if found, None if not found
    """
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

async def fetch_roblox_bio(roblox_user_id) -> Optional[str]:
    """
    Fetches a Roblox user bio based on user ID.
    
    Args: 
        roblox_user_id (int): The ID to the account.
        
    Returns:
        Optional[str]: The Roblox bio of the user.
        """
    async with ClientSession() as session:
        url = f"https://users.roblox.com/v1/users/{roblox_user_id}"
        async with session.get(url) as response:
            data = await response.json()
            return data.get("description", "")

async def GetRobloxID(roblox_username) -> Optional[int]:
    """
    Fetches a Roblox user ID based on username via API.
    
    Args:
        roblox_username (str): The username to the account.

    Returns:
        Optional[int]: The user ID.
    """
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

async def getUUID(interaction: discord.Interaction, username: str) -> Union[str, False]:
    """
    Fetches a Minecraft UUID based on username via API.
    
    Args:
        interaction (discord.Interaction): The interaction it was called from.
        username (str): The username to the account.
        
    Returns:
        Union[str, False]: The UUID of the account."""
    async with ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as response:
            if response.status == 200:
                return (await response.json())["id"]
            else:
                await interaction.followup.send(f"The usename is incorrect or the minecraft API is down. Exiting with status: {response.status}")
                return False
