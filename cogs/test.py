
from datetime import datetime, timezone, timedelta
import json, time

def save_json(filename: str, data) -> None:
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)
    except Exception as e:
        raise Exception(f"Error: Could not save data to '{filename}'. {e}")

def open_json(filename: str) -> str:
    with open(filename, "r") as f:
        file_data = json.load(f)
    return file_data

eco_path = "storage/economy/economy.json"

def create_account(id) -> None:
    players = open_json(eco_path)

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
    root: str, 
    user: int, 
    value_type: type = None
) -> bool:
    players = open_json(eco_path)
    user_str = str(user)
    
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


def update_streak(streak: str, user_id: str):
    check_user_stat(["streaks"], user_id)
    current_streak = check_user_stat(["streaks", streak, "streak"], user_id, 0)
    last_claimed = check_user_stat(["streaks", streak, "last_claimed"], user_id, "2000-01-01 00:00:00.000000+00:00")
    
    old_streak = current_streak
    now = datetime.now(timezone.utc)
    last_claimed = datetime.fromisoformat(last_claimed)
    since_last_claimed = now - last_claimed

    days = since_last_claimed.days
    eco = open_json(eco_path)
    if (streak == "daily" and (days < 1) or \
        streak == "weekly" and (days < 7) or \
        streak == "monthly" and (days < 30)):
        return None, None, int(datetime.timestamp(
                last_claimed + timedelta(days=1) if streak == "daily"
                else last_claimed + timedelta(days=7) if streak == "weekly"
                else last_claimed + timedelta(days=30)
            ))

    if (streak == "daily" and (days > 2) or \
        streak == "weekly" and (days > 8) or \
        streak == "monthly" and (days > 32)):
        eco[user_id]["streaks"][streak]["streak"] = 0
        current_streak = 0

    if streak == "daily": 
        amount = 5000 * ((current_streak * 0.05) + 1)

    if streak == "weekly": 
        amount = 40000 * ((current_streak * 0.1) + 1)

    if streak == "monthly": 
        amount = 200000 * ((current_streak * 0.16) + 1)

    eco[user_id]["balance"]["purse"] += int(amount)
    eco[user_id]["streaks"][streak]["streak"] += 1
    eco[user_id]["streaks"][streak]["last_claimed"] = now.isoformat()
    save_json("storage/economy/economy.json", eco)

    return amount, current_streak, old_streak

import random
items_data = open_json("storage/economy/items.json")
shop_items = []
weights = []

for item_name, item_data in items_data.items():
    if item_data.get("appearInShop", False):
        prices = item_data.get("price")
        if prices.get("currency") == "coins":
            price = prices.get("amount")
        else:
            break
        stock = item_data.get("amount", -1)

        if stock == -1:
            break
        weight = item_data.get("appearInShop").get("weight", 1)
        shop_items.append({
            "item": item_name,
            "price": price,
            "stock": stock,
        })
        weights.append(weight)

SHOP = random.sample(shop_items, counts=weights, k=min(9, len(shop_items)))
print(SHOP)