import time
import discord
from discord import app_commands
from typing import (
    TypedDict,
    Optional,
    Dict,
    Any,
    List,
    TypeAlias,
    Literal,
    Tuple,
)

from bot_utils import (
    open_json,
    save_json,
)

class LevelsData(TypedDict):
    EXP: int
    retire: int
    prestige: int
    rebirth: int

class BalanceData(TypedDict):
    bank: int
    purse: int
    maxBank: int
    fish_tokens: int

class GearData(TypedDict):
    helmet: Optional[str]
    chestplate: Optional[str]
    leggings: Optional[str]
    boots: Optional[str]
    rune: Optional[str]
    ring: Optional[str]
    weapon: Optional[str]

class BoostsData(TypedDict):
    coins: int
    exp: int

class PointsData(TypedDict):
    health: int
    damage: int
    speed: int
    extra: int

class CooldownsData(TypedDict):
    daily: str
    weekly: str
    monthly: str

class StreaksData(TypedDict):
    daily: int
    weekly: int
    monthly: int

class PlayerData(TypedDict):
    playerID: int
    joinTimestamp: int
    levels: LevelsData
    balance: BalanceData
    inventory: Dict[str, Any]
    pets: Dict[str, Any]
    gear: GearData
    boosts: BoostsData
    points: PointsData
    cooldowns: CooldownsData
    streaks: StreaksData

PlayerId: TypeAlias = str
EconomyData: TypeAlias = Dict[PlayerId, PlayerData]

eco_path: str = "storage/economy/economy.json"

def display_item_name(item_name: str) -> str:
    """Convert item name to display format."""
    return item_name.replace('_', ' ').title() 

def get_item_name(item_name: str) -> str:
    """Convert display format to item name."""
    return item_name.lower().replace(' ', '_')

async def get_item_suggestions(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Get autocomplete suggestions for items."""
    items_data = open_json("storage/economy/items.json")
    choices = []
    
    for item_name, item_data in items_data.items():
        if current.lower() in item_name.lower():
            item_type = item_data.get("type", "Unknown")
            price = item_data.get("price", 1000)
            choices.append(
                app_commands.Choice(
                    name=f"{display_item_name(item_name)} ({item_type}) - {price:,} coins",
                    value=item_name
                )
            )
    
    return choices[:25]

def create_account(id: PlayerId) -> None:
    """
    Creates a new economy account for a user with default starting values.

    Parameters:
        id (PlayerId): The unique identifier for the user.

    Example:
        ```
        create_account("123456789")  # Creates new account for user with ID 123456789
        ```
    """
    players: EconomyData = open_json(eco_path)

    try:
        lastPlayerData = next(reversed(players.values()))
        playerID = lastPlayerData["playerID"] + 1
    except (StopIteration, KeyError):
        playerID = 1

    players[id] = {
        "playerID": playerID,
        "joinTimestamp": int(time.time())
    }

    save_json(eco_path, players)

def check_user_stat(
    root: List[str], 
    user: int, 
    value_type: Optional[type] = None
) -> Any:
    ''' 
    Checks if a certain user stat exists, then returns it. If it does not exist, create it.

    Args:
        root (List[str]): A list representing the path to the nested dictionary keys (e.g., ['balance', 'purse']). 
        user (int): The user ID to check data for.
        value_type (Optional[Union[type, None]]): The type of value to set if the key does not exist. 
                                                 None for a dictionary (default), or any for a value.

    Returns: 
        Any: The value of the data

    Example:
        ```
        coins = check_user_stat(['inventory', 'coins'], 123456789, 0)
        if coins < 10:
            break
        else:
            eco = open_file("file_dir")
            eco[123456789]['inventory']['coins'] -= 10
        ```
    '''
    players: EconomyData = open_json(eco_path)
    user_str: PlayerId = str(user)
    
    if user_str not in players:
        create_account(user_str)
    
    players = open_json(eco_path)
    
    current = players[user_str]
    for key in root[:-1]:
        current = current.setdefault(key, {})
    
    final_key = root[-1]
    if (final_key not in current):
        if value_type is None:
            current[final_key] = {}
        else:
            current[final_key] = value_type
        save_json(eco_path, players)

    return current[final_key]

async def process_transaction(
    user_id: PlayerId,
    transaction_type: Literal["deposit", "withdraw"],
    amount: int
) -> Tuple[bool, str]:
    """
    Process a bank transaction (deposit or withdrawal) for a user.

    Parameters:
        user_id (PlayerId): The ID of the user making the transaction.
        transaction_type (Literal["deposit", "withdraw"]): The type of transaction to perform.
        amount (int): The amount of currency to transfer.

    Returns:
        Tuple[bool, str]: A tuple containing:
            - bool: Whether the transaction was successful
            - str: A message describing the result of the transaction

    Example:
        ```
        success, message = await process_transaction("123456789", "deposit", 1000)
        if success:
            print(f"Transaction successful: {message}")
        else:
            print(f"Transaction failed: {message}")
        ```
    """
    check_user_stat(["balance", "purse"], user_id, 0)
    check_user_stat(["balance", "bank"], user_id, 5000)
    check_user_stat(["balance", "maxBank"], user_id, 25000)
    eco: EconomyData = open_json(eco_path)

    player_data = eco[str(user_id)]
    purse_balance = int(player_data["balance"]["purse"])
    bank_balance = int(player_data["balance"]["bank"])
    max_bank = int(player_data["balance"]["maxBank"])

    if int(amount) <= 0:
        return False, "The amount must be a positive number."

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

    save_json(eco_path, eco)
    
    return True, f"{transaction_type.capitalize()} of {amount} Coins has been processed."

def command_cooldown(cooldown: int, command_name: str, user_id: str) -> tuple[bool, int]:
    current_time = int(time.time())
    eco = open_json("storage/economy/economy.json")
    
    if str(user_id) not in eco:
        eco[str(user_id)] = {}
    if "commands" not in eco[str(user_id)]:
        eco[str(user_id)]["commands"] = {}
    if command_name not in eco[str(user_id)]["commands"]:
        eco[str(user_id)]["commands"][command_name] = {"uses": 0, "cooldown": 0}
    
    last_used = eco[str(user_id)]["commands"][command_name]["cooldown"]
    
    if current_time - last_used < cooldown:
        return False, last_used + cooldown
    
    eco[str(user_id)]["commands"][command_name]["uses"] += 1
    eco[str(user_id)]["commands"][command_name]["cooldown"] = current_time
    save_json("storage/economy/economy.json", eco)
    
    return True, 0