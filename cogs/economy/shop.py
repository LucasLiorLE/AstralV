import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
from typing import List, Dict
from bot_utils import (
    open_json, 
    save_json
)
from .utils import (
    display_item_name,
    check_user_stat
)

class ShopType:
    REGULAR = "regular"
    MERCHANT = "merchant"
    LIMITED = "limited"

class ShopData:
    def __init__(self):
        self.shops: Dict[str, List[dict]] = {
            ShopType.REGULAR: self._init_regular_shop(),
            ShopType.MERCHANT: [],
            ShopType.LIMITED: self._init_limited_shop()
        }

    def get_shop(self, shop_type: str) -> List[dict]:
        return self.shops.get(shop_type, [])

    def reload_limited_shop(self):
        self.shops[ShopType.LIMITED] = self._init_limited_shop()
        
    def _init_limited_shop(self) -> List[dict]:
        limited_shop = open_json("storage/economy/limited_shop.json")
        if not isinstance(limited_shop, list):
            limited_shop = []
        return limited_shop

    def _init_regular_shop(self) -> List[dict]:
        items_data = open_json("storage/economy/items.json")
        regular_items = []

        for item_name, item_data in items_data.items():
            prices = item_data.get("price")
            if prices and prices.get("currency") == "coins":
                appear_in_shop = item_data.get("appearInShop", {})
                if isinstance(appear_in_shop, dict) and appear_in_shop.get("amount", 0) == -1:
                    regular_items.append({
                        "item": item_name,
                        "price": prices.get("amount"),
                        "stock": -1,
                        "description": item_data.get("description", "No description available"),
                        "type": item_data.get("type", "Unknown")
                    })

        return regular_items

SHOP_DATA = ShopData()

def update_merchant_shop():
    items_data = open_json("storage/economy/items.json")
    merchant_items = []
    weights = []

    for item_name, item_data in items_data.items():
        appear_in_shop = item_data.get("appearInShop", {})
        prices = item_data.get("price", {})
        
        if (isinstance(appear_in_shop, dict) and 
            appear_in_shop.get("amount", 0) > 0 and 
            prices.get("currency") == "coins"):
            
            weight = appear_in_shop.get("weight", 1)
            merchant_items.append({
                "item": item_name,
                "price": prices.get("amount"),
                "stock": appear_in_shop.get("amount"),
                "description": item_data.get("description", "No description available"),
                "type": item_data.get("type", "Unknown")
            })
            weights.append(weight)

    if merchant_items:
        try:
            selected_items = random.sample(
                merchant_items,
                k=min(5, len(merchant_items))
            )
            SHOP_DATA.shops[ShopType.MERCHANT] = selected_items
        except ValueError as e:
            print(f"Error updating merchant shop: {e}")
            SHOP_DATA.shops[ShopType.MERCHANT] = []

@tasks.loop(hours=1)
async def update_shops():
    update_merchant_shop()

def create_shop_embed(shop_type: str, shop_items: List[dict]) -> discord.Embed:
    title_prefix = {
        ShopType.REGULAR: "🏪 Regular",
        ShopType.MERCHANT: "💎 Merchant",
        ShopType.LIMITED: "⏰ Limited",
    }
    
    embed = discord.Embed(
        title=f"{title_prefix.get(shop_type, '')} Shop",
        color=discord.Color.blue()
    )

    if not shop_items:
        embed.description = f"The {shop_type} shop is currently empty."
        return embed
    
    items_by_type = {}
    for item in shop_items:
        item_type = item["type"]
        if item_type not in items_by_type:
            items_by_type[item_type] = []
        items_by_type[item_type].append(item)
    
    for item_type, items in items_by_type.items():
        items_text = []
        for item in items:
            stock_text = "∞" if item["stock"] == -1 else str(item["stock"])
            name = display_item_name(item["item"])
            price = item["price"]
            desc = item["description"]
            items_text.append(f"**{name}** - {price:,} coins\n*{desc}*\nStock: {stock_text}")
        
        embed.add_field(
            name=f"📦 {item_type.title()}",
            value="\n\n".join(items_text) or "No items available",
            inline=False
        )
    
    return embed

class BuyModal(discord.ui.Modal):
    def __init__(self, item_name: str, max_amount: int, price: int, currency: str):
        super().__init__(title=f"Buy {display_item_name(item_name)}")
        self.item_name = item_name
        self.max_amount = max_amount
        self.price = price
        self.currency = currency
        
        self.amount = discord.ui.TextInput(
            label=f"Amount to buy (Max: {max_amount})",
            placeholder=f"Enter a number between 1 and {max_amount}",
            min_length=1,
            max_length=len(str(max_amount)),
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount < 1 or amount > self.max_amount:
                await interaction.response.send_message(
                    f"Please enter a valid amount between 1 and {self.max_amount}.",
                    ephemeral=True
                )
                return

            total_cost = amount * self.price
            user_id = str(interaction.user.id)

            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["inventory", self.item_name], user_id, 0)
            
            eco = open_json("storage/economy/economy.json")
            current_balance = eco[user_id]["balance"]["purse"]
            
            if current_balance < total_cost:
                await interaction.response.send_message(
                    f"You don't have enough {self.currency}! You need {total_cost:,} but only have {current_balance:,}.",
                    ephemeral=True
                )
                return

            eco[user_id]["balance"]["purse"] -= total_cost
            eco[user_id]["inventory"][self.item_name] += amount
            save_json("storage/economy/economy.json", eco)

            embed = discord.Embed(
                title="Purchase Successful!",
                description=f"You bought {amount}x {display_item_name(self.item_name)} for {total_cost:,} {self.currency}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Remaining Balance",
                value=f"{current_balance - total_cost:,} {self.currency}"
            )

            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.",
                ephemeral=True
            )

class ItemButton(discord.ui.Button):
    def __init__(self, item_name: str, price: int, stock: int, currency: str):
        super().__init__(
            label=display_item_name(item_name),
            style=discord.ButtonStyle.primary,
            custom_id=f"buy_{item_name}"
        )
        self.item_name = item_name
        self.price = price
        self.stock = stock
        self.currency = currency

    async def callback(self, interaction: discord.Interaction):
        max_amount = float('inf') if self.stock == -1 else self.stock
        if self.currency == "coins":
            check_user_stat(["balance", "purse"], str(interaction.user.id), 0)
            eco = open_json("storage/economy/economy.json")
            user_balance = eco[str(interaction.user.id)]["balance"]["purse"]
            max_by_balance = user_balance // self.price
            max_amount = min(max_amount, max_by_balance)
            
        if max_amount < 1:
            await interaction.response.send_message(
                f"You don't have enough {self.currency} to buy this item.",
                ephemeral=True
            )
            return

        modal = BuyModal(self.item_name, int(max_amount), self.price, self.currency)
        await interaction.response.send_modal(modal)

class ItemView(discord.ui.View):
    def __init__(self, shop_items: List[dict], shop_type: str):
        super().__init__(timeout=None)
        
        for item in shop_items:
            self.add_item(ItemButton(
                item_name=item["item"],
                price=item["price"],
                stock=item["stock"],
                currency="coins"
            ))

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopSelect())

class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Regular Shop",
                description="Permanent items that are always available",
                value=ShopType.REGULAR,
                emoji="🏪"
            ),
            discord.SelectOption(
                label="Merchant Shop",
                description="Random items with limited stock",
                value=ShopType.MERCHANT,
                emoji="💎"
            ),
            discord.SelectOption(
                label="Limited Shop",
                description="Shop with items hosted by an admin",
                value=ShopType.LIMITED,
                emoji="⏰"
            )
        ]
        super().__init__(
            placeholder="Select a shop type...",
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        shop_type = self.values[0]
        shop_items = SHOP_DATA.get_shop(shop_type)
        embed = create_shop_embed(shop_type, shop_items)
        
        view = discord.ui.View(timeout=None)
        view.add_item(self)
        if shop_items:
            item_view = ItemView(shop_items, shop_type)
            for item in item_view.children:
                view.add_item(item)
        
        await interaction.response.edit_message(embed=embed, view=view)

async def get_shop_item_suggestions(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    try:
        items_data = open_json("storage/economy/items.json")
        choices = []
        
        all_shop_items = []
        for shop_type, shop_items in SHOP_DATA.shops.items():
            for item in shop_items:
                item["shop_type"] = shop_type
            all_shop_items.extend(shop_items)
            
        if not all_shop_items:
            return []
        
        for shop_item in all_shop_items:
            item_name = shop_item["item"]
            if current.lower() in item_name.lower():
                item_type = items_data[item_name].get("type", "Unknown")
                price = shop_item["price"]
                currency = "coins"
                choices.append(
                    app_commands.Choice(
                        name=f"{display_item_name(item_name)} ({item_type}) - {price:,} {currency}",
                        value=item_name
                    )
                )
        
        return choices[:25]
    except Exception as e:
        print(f"Error in get_shop_item_suggestions: {e}")
        return []

class ShopCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Economy shop commands")

    @app_commands.command(name="view")
    async def view_shop(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["inventory"], user_id, {})
            
            regular_shop_items = SHOP_DATA.get_shop(ShopType.REGULAR)
            embed = create_shop_embed(ShopType.REGULAR, regular_shop_items)
            
            view = discord.ui.View(timeout=None)
            view.add_item(ShopSelect())
            if regular_shop_items:
                item_view = ItemView(regular_shop_items, ShopType.REGULAR)
                for item in item_view.children:
                    view.add_item(item)
            
            await interaction.response.send_message(
                embed=embed,
                view=view
            )
        except Exception as e:
            print(f"Error in view_shop: {e}")
            await interaction.response.send_message("An error occurred while trying to view the shop.")

    @app_commands.command(name="buy")
    @app_commands.autocomplete(item=get_shop_item_suggestions)
    async def buy_item(self, interaction: discord.Interaction, item: str, amount: int = 1):
        try:
            item_data = None
            shop_type = None
            
            for shop_name, shop_items in SHOP_DATA.shops.items():
                for shop_item in shop_items:
                    if shop_item["item"] == item:
                        item_data = shop_item
                        shop_type = shop_name
                        break
                if item_data:
                    break
            
            if not item_data:
                await interaction.response.send_message(
                    f"Item {display_item_name(item)} is not available in any shop.",
                    ephemeral=True
                )
                return

            currency = "coins"
            stock = item_data["stock"]
            price = item_data["price"]
            
            if stock != -1 and amount > stock:
                await interaction.response.send_message(
                    f"Not enough stock. Only {stock} {display_item_name(item)} available.",
                    ephemeral=True
                )
                return

            total_cost = amount * price
            user_id = str(interaction.user.id)

            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["inventory", item], user_id, 0)
            
            eco = open_json("storage/economy/economy.json")
            current_balance = eco[user_id]["balance"]["purse"]

            if current_balance < total_cost:
                await interaction.response.send_message(
                    f"You don't have enough {currency}! You need {total_cost:,} but only have {current_balance:,}.",
                    ephemeral=True
                )
                return

            eco[user_id]["balance"]["purse"] -= total_cost
            eco[user_id]["inventory"][item] += amount
            save_json("storage/economy/economy.json", eco)

            if shop_type == ShopType.LIMITED and stock != -1:
                limited_shop = open_json("storage/economy/limited_shop.json")
                for shop_item in limited_shop:
                    if shop_item["item"] == item:
                        shop_item["stock"] -= amount
                        if shop_item["stock"] <= 0:
                            limited_shop.remove(shop_item)
                save_json("storage/economy/limited_shop.json", limited_shop)
                SHOP_DATA.shops[ShopType.LIMITED] = SHOP_DATA._init_limited_shop()

            embed = discord.Embed(
                title="Purchase Successful!",
                description=f"You bought {amount}x {display_item_name(item)} for {total_cost:,} {currency}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Remaining Balance",
                value=f"{current_balance - total_cost:,} {currency}"
            )

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"Error in buy_item: {e}")
            await interaction.response.send_message(
                "An error occurred while trying to buy the item.",
                ephemeral=True
            )

class ShopCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shop = ShopCommandGroup()
        SHOP_DATA.reload_limited_shop()
        update_shops.start()
        self.bot.tree.add_command(self.shop)

async def setup(bot):
    await bot.add_cog(ShopCommandCog(bot))
