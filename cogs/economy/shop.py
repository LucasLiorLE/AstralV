import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
from typing import List
from bot_utils import (
    open_json, 
    save_json
)
from .utils import (
    display_item_name,
    check_user_stat
)

SHOP = []

async def get_shop_item_suggestions(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    try:
        if not SHOP:
            return []
            
        items_data = open_json("storage/economy/items.json")
        choices = []
        
        for shop_item in SHOP:
            item_name = shop_item["item"]
            if current.lower() in item_name.lower():
                item_type = items_data[item_name].get("type", "Unknown")
                price = shop_item["price"]
                choices.append(
                    app_commands.Choice(
                        name=f"{display_item_name(item_name)} ({item_type}) - {price:,} coins",
                        value=item_name
                    )
                )
        
        return choices[:25]
    except Exception as e:
        print(f"Error in get_shop_item_suggestions: {e}")
        return []


@tasks.loop(hours=1)
async def handle_eco_shop():
    global SHOP
    try:
        items_data = open_json("storage/economy/items.json")
        shop_items = []
        
        for item_name, item_data in items_data.items():
            if item_data.get("appearInShop", False):
                base_price = item_data.get("price", 1000)
                price = int(base_price * random.uniform(0.8, 1.2))
                stock = item_data.get("amount", -1)
                shop_items.append({
                    "item": item_name,
                    "price": price,
                    "stock": stock
                })
        
        SHOP = random.sample(shop_items, min(9, len(shop_items)))
        
    except Exception as e:
        print(f"Error in handle_eco_shop: {e}")
        SHOP = []

class ShopCommandGroup(commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Economy shop commands")

    @app_commands.command(name="view")
    async def view(self, interaction: discord.Interaction): 
        if not SHOP:
            return await interaction.response.send_message(
                "Nothing is in the shop, please check back in a bit!",
                ephemeral=True
            )

        items_data = open_json("storage/economy/items.json")
        embed = discord.Embed(
            title="🏪 Shop",
            description="Items currently available:",
            color=discord.Color.yellow()
        )

        for item in SHOP:
            item_name = item["item"]
            item_data = items_data.get(item_name, {})
            item_type = item_data.get("type", "Unknown")
            item_desc = item_data.get("description", "No description available.")
            item_stock = item_data.get("stock", -1)
            
            embed.add_field(
                name=f"{display_item_name(item_name)} ({item_type})",
                value=(
                    f"Price: {item['price']:,} coins"
                    f"*{item_desc}*"
                    f"Stock left: {"∞" if item_stock == -1 else item_stock}"
                ),
                inline=True
            )
        

    @app_commands.command(name="buy")
    async def buy(self, interaction: discord.Interaction, item: str, quantity: int = 1):
        if quantity <= 0:
            return await interaction.response.send_message("Quantity must be positive!", ephemeral=True)
    
        shop_item = next((item for item in SHOP if item["item"] == item), None)
        if not shop_item:
            return await interaction.response.send_message("That item isn't available right now!", ephemeral=True)
        
        cost = shop_item["price"] * quantity
        user_id = str(interaction.user.id)
        eco, purse = check_user_stat(["balance", "purse"], user_id, 0)
        _, _ = check_user_stat(["inventory"], user_id)

        if purse < cost:
            return await interaction.response.send_message("You don't have enough money in your purse!", ephemeral=True)

        eco[user_id]["balance"]["purse"] -= cost
        eco[user_id]["inventory"][item] += 1

    @app_commands.command(name="sell")
    async def sell(self, interaction: discord.Interaction): 
        ...