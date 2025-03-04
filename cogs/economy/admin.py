import discord
from discord import app_commands
from discord.ext import commands
from bot_utils import (
    open_json, 
    save_json,
    handle_logs
)
from .utils import (
    check_user_stat,
    get_item_suggestions
)
from main import botAdmins

class EconomyAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_not_admin(self, id: int) -> bool:
        return not id in botAdmins
    
    def is_not_exists(self, item) -> bool:
        economy_items = open_json("storage/economy/items.json")
        return not item in [k for k in economy_items.keys()]


    @app_commands.command(name="give_items")
    @app_commands.autocomplete(item=get_item_suggestions)
    async def give_items(self, interaction: discord.Interaction, user: discord.User, item: str, amount: int):
        try:
            if self.is_not_admin(interaction.user.id):
                return await interaction.response.send_message("You do not have permission to use this command!", ephemeral=True)
            
            if self.is_not_exists(item):
                return await interaction.response.send_message("That item does not exist!", ephemeral=True)
            
            user_id = str(user.id)
            check_user_stat(["inventory", item], user_id, 0)
            eco = open_json("storage/eocnomy/economy.json")
            eco[user_id]["inventory"][item] += amount
            save_json("storage/economy/economy.json", eco)

            await interaction.response.send_message(f"Successfully added {amount} {item}/s to {user.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="give_coins")
    async def give_coins(self, interaction: discord.Interaction, user: discord.User, amount: int):
        try:
            if self.is_not_admin(interaction.user.id):
                return await interaction.response.send_message("You do not have permission to use this command!", ephemeral=True)

            user_id = str(user.id)
            check_user_stat(["balance", "purse"], user_id, 0)
            eco = open_json("storage/eocnomy/economy.json")
            eco[user_id]["inventory"]["purse"] += amount
            save_json("storage/economy/economy.json", eco)

            await interaction.response.send_message(f"Successfully added {amount} {amount} coins to {user.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="sell_limited_item")
    async def sell_limited_item(self, interaction: discord.Interaction, item: str, price: int, stock: int):
        try:
            if self.is_not_admin(interaction.user.id):
                return await interaction.response.send_message("You do not have permission to use this command!", ephemeral=True)
            
            if self.is_not_exists(item):
                return await interaction.response.send_message("That item does not exist!", ephemeral=True)
            
            items_data = open_json("storage/economy/items.json")
            limiteds = open_json("storage/economy/limited_shop.json")
            limiteds.append({
                "item": item,
                "price": price,
                "stock": stock,
                "description": items_data.get(item).get("description", "No description available"),
                "type": items_data.get(item).get("type", "Unknown")
            })

            save_json("storage/economy/limited_shop.json", limiteds)
            await interaction.response.send_message(f"Successfully added {stock} {item}/s at ${price} to the limited shop!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="remove_limited_item")
    async def remove_limited_item(self, interaction: discord.Interaction, item: str):
        try:
            if self.is_not_admin(interaction.user.id):
                return await interaction.response.send_message("You do not have permission to use this command!", ephemeral=True)

            limiteds = open_json("storage/economy/limited_shop.json")
            limiteds = [limited for limited in limiteds if limited["item"] != item]
            save_json("storage/economy/limited_shop.json", limiteds)

            await interaction.response.send_message(f"Successfully removed {item} from the limited shop!")
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(EconomyAdminCog(bot))
