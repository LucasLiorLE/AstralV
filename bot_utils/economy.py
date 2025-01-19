import time
from typing import List, Union, Optional, Dict, Any
from .file_handler import (
    open_file,
    save_file
)

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
        },
        "cooldowns": {
            "daily": "2000-01-01T00:00:00+00:00",
            "weekly": "2000-01-01T00:00:00+00:00",
            "monthly": "2000-01-01T00:00:00+00:00"
        },
        "streaks": {
            "daily": 0,
            "weekly": 0,
            "monthly": 0
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

