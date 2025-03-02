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
    Tuple
)

from bot_utils import (
    open_json,
    save_json,
    check_user
)

class LevelsData(TypedDict):
    EXP: int
    retire: int
    prestige: int
    rebirth: int
    evolve: int

class BalanceData(TypedDict):
    bank: int
    purse: int
    maxBank: int

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

class GamblingStats(TypedDict):
    wins: int
    losses: int
    draws: int
    coinsWon: int
    coinsLost: int

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
        "joinTimestamp": int(time.time()),
        "balance": {
            "bank": 5000,
            "purse": 0,
            "maxBank": 25000,
        },
        "levels": {
            "EXP": 0,
        },
        "boosts": {
            "coins": 100,
            "exp": 100,
        }
    }


    save_json(eco_path, players)

def check_user_stat(
    root: List[str], 
    user: int, 
    value_type: Optional[type] = None
) -> bool:
    ''' 
    For newer versions of the bot auto updating data without needing to add them manually.

    Args:
        root (List[str]): A list representing the path to the nested dictionary keys (e.g., ['balance', 'purse']). 
        user (int): The user ID to check data for.
        value_type (Optional[Union[type, None]]): The type of value to set if the key does not exist. 
                                                 None for a dictionary (default), or any for a value.

    Returns: 
        bool: Whether or not the data existed or was initialized during this call.

    Example:
        ```
        # Check if user has a 'coins' stat in their inventory
        exists = check_user_stat(['inventory', 'coins'], 123456789, 0)
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

''' 

Maybe I'll use this, not sure yet

def get_player_data(id, data):
    players = open_json(eco_path)
    if id not in players:
        create_account(id)
    
    player_data = players[id]
    if data == "balance":
        return player_data["balance"]["bank"], player_data["balance"]["purse"], player_data["balance"]["maxBank"]
'''
# Base currency system setup

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
    eco: EconomyData = open_json(eco_path)

    if user_id not in eco:
        create_account(user_id)

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

def gambling_stats(user_id: PlayerId, game: str) -> GamblingStats:
    """
    Retrieves or initializes gambling statistics for a user in a specific game.

    Parameters:
        user_id (PlayerId): The ID of the user to get stats for.
        game (str): The name of the game to get stats for.

    Returns:
        GamblingStats: A dictionary containing the user's gambling statistics including:
            - wins (int): Number of wins
            - losses (int): Number of losses
            - draws (int): Number of draws
            - coinsWon (int): Total amount of coins won
            - coinsLost (int): Total amount of coins lost

    Example:
        ```
        stats = gambling_stats("123456789", "blackjack")
        print(f"User has won {stats['wins']} times and lost {stats['losses']} times")
        ```
    """
    eco: EconomyData = open_json(eco_path)
    if user_id not in eco:
        create_account(user_id)
    eco = open_json(eco_path)

    user_info = eco[user_id]

    if game not in user_info:
        user_info[game] = {
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "coinsWon": 0,
            "coinsLost": 0
        }

        save_json(eco_path, eco)
    return user_info[game]

def update_stats(
    user_id: PlayerId, 
    game: str, 
    result: Literal["win", "loss", "draw"],
    amount: int = 0
) -> None:
    """
    Updates the gambling statistics for a user after a game.

    Parameters:
        user_id (PlayerId): The ID of the user to update stats for.
        game (str): The name of the game being played.
        result (Literal["win", "loss", "draw"]): The result of the game.
        amount (int, optional): The amount of coins won or lost. Defaults to 0.

    Returns:
        None: The updated stats are saved to the economy file.

    Example:
        ```
        # Update stats for a user who won 100 coins in blackjack
        update_stats("123456789", "blackjack", "win", 100)
        ```
    """
    eco: EconomyData = open_json(eco_path)
    stats = gambling_stats(user_id, game)
    eco = open_json(eco_path)

    if result == "win":
        stats["wins"] += 1
        stats["coinsWon"] += amount
    elif result == "loss":
        stats["losses"] += 1
        stats["coinsLost"] += amount
    elif result == "draw":
        stats["draws"] += 1

    eco[user_id][game] = stats
    save_json(eco_path, eco)

class Gambling:
    """
    A class to handle gambling-related operations for a specific user.

    Attributes:
        id (PlayerId): The ID of the user this instance is handling gambling for.

    Example:
        ```
        gambling = Gambling("123456789")
        ```
    """
    def __init__(self, id: PlayerId) -> None:
        self.id: PlayerId = id