from bot_utils import (
    RestrictedView,

    eco_path,
    create_account,
    check_user_stat,
    check_user_exists,
    process_transaction,

    convert_number,
    create_interaction,
    error,

    open_file,
    save_file,
    load_commands,
    handle_logs
)

from main import botAdmins

import discord
from discord.ext import commands, tasks
from discord import app_commands, ButtonStyle
from discord.ui import Button, Modal, TextInput

import random
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

items = open_file("storage/economy/items.json")
SHOP = []

market_path = "storage/economy/market.json"
market_data = open_file(market_path)

listings_path = "storage/economy/market_listings.json"
listings_data = open_file(listings_path)

class MarketView(discord.ui.View):
    def __init__(self, items_dict, filters=None):
        super().__init__(timeout=60)
        self.page = 0
        self.items_per_page = 10
        self.items = sorted(items_dict.values(), key=lambda x: x['price_per_unit'])
        self.filters = filters or {}
        
        filter_select = discord.ui.Select(
            placeholder="Filter by type...",
            options=[
                discord.SelectOption(label="All", value="all"),
                discord.SelectOption(label="Animals", value="animal"),
                discord.SelectOption(label="Fish", value="fish"),
                discord.SelectOption(label="Tools", value="tool")
            ]
        )
        filter_select.callback = self.filter_callback
        self.add_item(filter_select)

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.gray)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        
        if (self.page + 1) * self.items_per_page < len(self.items):
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.gray)
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def filter_callback(self, interaction: discord.Interaction):
        filter_value = interaction.data['values'][0]
        if filter_value != "all":
            self.items = [i for i in self.items if i['type'] == filter_value]
        self.page = 0
        self.update_buttons()
        await self.update_message(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self.update_buttons()
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        start_idx = self.page * self.items_per_page
        current_items = self.items[start_idx:start_idx + self.items_per_page]
        
        embed = discord.Embed(title="Market Listings", color=discord.Color.blue())
        for item in current_items:
            embed.add_field(
                name=f"#{item['id']} - {display_item_name(item['item'])}",
                value=f"Price: {item['price_per_unit']:,} coins each\nQuantity: {item['quantity']}\nSeller: {item['seller_name']}",
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)

def update_market_price(item_name: str, is_buy: bool) -> int:
    """Update market price based on hourly sales volume"""
    now = datetime.now(timezone.utc)
    last_reset = datetime.fromisoformat(market_data.get("last_reset", "2024-01-01T00:00:00+00:00"))
    
    if (now - last_reset).total_seconds() >= 3600:
        market_data["hourly_sales"] = {}
        market_data["last_reset"] = now.isoformat()

    if item_name not in market_data["prices"]:
        market_data["prices"][item_name] = items[item_name]["price"]
    if item_name not in market_data["hourly_sales"]:
        market_data["hourly_sales"][item_name] = 0

    if not is_buy:
        market_data["hourly_sales"][item_name] += 1

    base_price = items[item_name]["price"]
    current_price = market_data["prices"][item_name]
    market_settings = items[item_name].get("market", {
        "hourlyThreshold": 1000,
        "maxPriceMultiplier": 3.0,
        "priceIncrementPerThousand": 0.005
    })
    
    hourly_sales = market_data["hourly_sales"][item_name]
    threshold = market_settings["hourlyThreshold"]
    
    if hourly_sales > threshold:
        sales_thousands = (hourly_sales - threshold) / 1000
        increase_percent = sales_thousands * market_settings["priceIncrementPerThousand"]
        new_price = int(current_price * (1 + increase_percent))
        
        max_price = base_price * market_settings["maxPriceMultiplier"]
        new_price = min(new_price, max_price)
    else:
        decrease_percent = 0.02
        new_price = int(current_price * (1 - decrease_percent))
        new_price = max(base_price, new_price)

    market_data["prices"][item_name] = new_price
    save_file(market_path, market_data)
    return new_price

def get_market_price(item_name: str) -> int:
    """Get current market price for an item"""
    if item_name not in market_data["prices"]:
        market_data["prices"][item_name] = items[item_name]["price"]
    return market_data["prices"][item_name]

@tasks.loop(hours=1)
async def handle_eco_shop():
    global SHOP
    SHOP = []
    shop_items = random.sample(list(items.items()), min(10, len(items)))
    for name, data in shop_items:
        if "appearInShop" in data:
            appear_data = data["appearInShop"]
            SHOP.append({
                "item": name,
                "price": appear_data.get("buyPrice", 0),
                "amount": appear_data.get("amount", 0),
                "description": appear_data.get("description", "No description yet..."),
                "type": data.get("type", "No type")
            })
    
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Market commands")
        
    def setup_commands(self):
        load_commands(self, "economy")

    @app_commands.command(name="list")
    async def list_item(self, interaction: discord.Interaction, item: str, quantity: int, price_per_unit: int):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)
            
            item_name = normalize_item_name(item)
            if item_name not in eco[user_id].get('inventory', {}):
                return await interaction.followup.send("You don't have this item!")
            
            if eco[user_id]['inventory'][item_name] < quantity:
                return await interaction.followup.send("You don't have enough of this item!")

            listings = listings_data["market"]["listings"]
            listing_id = listings_data["market"]["last_id"] + 1
            listings_data["market"]["last_id"] = listing_id
            
            listings[str(listing_id)] = {
                "id": listing_id,
                "seller_id": user_id,
                "seller_name": interaction.user.display_name,
                "item": item_name,
                "quantity": quantity,
                "price_per_unit": price_per_unit,
                "type": items[item_name]["type"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            eco[user_id]['inventory'][item_name] -= quantity
            if eco[user_id]['inventory'][item_name] <= 0:
                del eco[user_id]['inventory'][item_name]

            save_file(eco_path, eco)
            save_file(listings_path, listings_data)
            
            await interaction.followup.send(f"Listed {quantity}x {display_item_name(item_name)} for {price_per_unit:,} coins each!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="buy")
    async def buy_item(self, interaction: discord.Interaction, item: str, quantity: int):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)
            
            item_name = normalize_item_name(item)
            available_listings = sorted([
                l for l in listings_data["market"]["listings"].values()
                if l["item"] == item_name
            ], key=lambda x: x["price_per_unit"])

            if not available_listings:
                return await interaction.followup.send("No listings found for this item!")

            total_available = sum(l["quantity"] for l in available_listings)
            if total_available < quantity:
                return await interaction.followup.send(f"Only {total_available} available!")

            remaining = quantity
            total_cost = 0
            used_listings = []

            for listing in available_listings:
                if remaining <= 0:
                    break
                    
                amount_from_listing = min(remaining, listing["quantity"])
                total_cost += amount_from_listing * listing["price_per_unit"]
                remaining -= amount_from_listing
                used_listings.append((listing, amount_from_listing))

            if eco[user_id]["balance"]["purse"] < total_cost:
                return await interaction.followup.send(f"You need {total_cost:,} coins!")

            eco[user_id]["balance"]["purse"] -= total_cost
            if item_name not in eco[user_id].get("inventory", {}):
                eco[user_id]["inventory"][item_name] = 0
            eco[user_id]["inventory"][item_name] += quantity

            for listing, amount_used in used_listings:
                seller_id = listing["seller_id"]
                if seller_id not in eco:
                    create_account(seller_id)
                
                payment = amount_used * listing["price_per_unit"]
                eco[seller_id]["balance"]["purse"] += payment
                
                listing["quantity"] -= amount_used
                if listing["quantity"] <= 0:
                    del listings_data["market"]["listings"][str(listing["id"])]

            save_file(eco_path, eco)
            save_file(listings_path, listings_data)
            
            await interaction.followup.send(
                f"Bought {quantity}x {display_item_name(item_name)} for {total_cost:,} coins!"
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="view")
    async def view_listings(self, interaction: discord.Interaction, item: str = None):
        await interaction.response.defer()
        try:
            listings = listings_data["market"]["listings"]
            if item:
                item_name = normalize_item_name(item)
                filtered_listings = {
                    k: v for k, v in listings.items()
                    if v["item"] == item_name
                }
            else:
                filtered_listings = listings

            if not filtered_listings:
                return await interaction.followup.send("No listings found!")

            view = MarketView(filtered_listings)
            await view.update_message(interaction)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="cancel")
    async def cancel_listing(self, interaction: discord.Interaction, listing_id: int):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            listing_str = str(listing_id)
            
            if listing_str not in listings_data["market"]["listings"]:
                return await interaction.followup.send("Listing not found!")
                
            listing = listings_data["market"]["listings"][listing_str]
            if listing["seller_id"] != user_id:
                return await interaction.followup.send("This is not your listing!")

            eco = check_user_exists(user_id)
            item_name = listing["item"]
            
            if item_name not in eco[user_id].get("inventory", {}):
                eco[user_id]["inventory"][item_name] = 0
            eco[user_id]["inventory"][item_name] += listing["quantity"]
            
            del listings_data["market"]["listings"][listing_str]
            
            save_file(eco_path, eco)
            save_file(listings_path, listings_data)
            
            await interaction.followup.send("Listing cancelled!")
        except Exception as e:
            await handle_logs(interaction, e)

class EcoAdminGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="ecoadmin", description="Economy admin commands.")
        
    def setup_commands(self):
        load_commands(self, "economy")

    @app_commands.command(name="give")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                return await interaction.followup.send("You do not have permission to use this command.")

            user_id = str(member.id)
            eco = check_user_exists(user_id)

            eco[user_id]['balance']['purse'] += amount
            save_file(eco_path, eco)

            await interaction.followup.send(f"Successfully gave {amount} coins to {member.display_name}!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="set")
    async def set(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                return await interaction.followup.send("You do not have permission to use this command.")

            user_id = str(member.id)
            eco = check_user_exists(user_id)

            eco[user_id]['balance']['purse'] = amount
            save_file(eco_path, eco)

            await interaction.followup.send(f"Successfully set {member.display_name}'s coins to {amount}!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="item")
    async def item(self, interaction: discord.Interaction, member: discord.Member, item_name: str, quantity: int):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                return await interaction.followup.send("You do not have permission to use this command.")

            user_id = str(member.id)
            eco = check_user_exists(user_id)

            item_name = normalize_item_name(item_name)
            if item_name not in eco[user_id].get('inventory', {}):
                eco[user_id]['inventory'][item_name] = 0

            eco[user_id]['inventory'][item_name] += quantity
            save_file(eco_path, eco)

            await interaction.followup.send(f"Successfully added {quantity}x {item_name} to {member.display_name}'s inventory!")
        except Exception as e:
            await handle_logs(interaction, e)

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop commands.")
        
    def setup_commands(self):
        load_commands(self, "economy")

    @app_commands.command(name="view")
    async def view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()
            
            shop_items = SHOP
            if not shop_items:
                return await interaction.followup.send("The shop is currently empty. Try again later!")

            embed = discord.Embed(
                title="Shop Items",
                description="Current items available for purchase:",
                color=discord.Color.blue()
            )

            for item in shop_items:
                stock_display = "∞" if item['amount'] == -1 else item['amount']
                embed.add_field(
                    name=f"{display_item_name(item['item'])} - {item['price']:,} coins",
                    value=f"Type: {item['type']}\nDescription: {item['description']}\nStock: {stock_display}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="buy")
    async def buy(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()

            if quantity < 1:
                return await interaction.followup.send("Quantity must be positive!")

            closest_item = find_closest_item(item_name, SHOP)
            if not closest_item:
                return await interaction.followup.send(f"No item found matching '{item_name}'")

            shop_item = next((item for item in SHOP if item["item"] == closest_item), None)
            if not shop_item:
                return await interaction.followup.send("That item is not available in the shop right now!")

            if shop_item["amount"] < quantity:
                return await interaction.followup.send("Not enough stock available!")

            total_cost = shop_item["price"] * quantity
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            if eco[user_id]["balance"]["purse"] < total_cost:
                return await interaction.followup.send("You don't have enough coins!")

            if "inventory" not in eco[user_id]:
                eco[user_id]["inventory"] = {}
            if shop_item["item"] not in eco[user_id]["inventory"]:
                eco[user_id]["inventory"][shop_item["item"]] = 0
            
            eco[user_id]["inventory"][shop_item["item"]] += quantity
            eco[user_id]["balance"]["purse"] -= total_cost

            save_file(eco_path, eco)

            update_market_price(shop_item["item"], True)

            await interaction.followup.send(
                f"Successfully bought {quantity}x {display_item_name(shop_item['item'])} for {total_cost:,} coins!"
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="sell")
    async def sell(self, interaction: discord.Interaction, item: str, amount: int = 1):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            if 'inventory' not in eco[user_id]:
                return await interaction.followup.send("You don't have anything to sell!")

            items_to_sell: List[Tuple[str, int]] = []
            total_value = 0

            if item.lower() == "all":
                for inv_item, amount in eco[user_id]['inventory'].items():
                    if inv_item in items and items[inv_item]['type'] in ['animal', 'fish']:
                        items_to_sell.append((inv_item, amount))
            else:
                item_name = normalize_item_name(item)
                if item_name not in items:
                    return await interaction.followup.send(f"The item '{display_item_name(item)}' doesn't exist!")
                
                if item_name not in eco[user_id]['inventory'] or eco[user_id]['inventory'][item_name] < amount:
                    return await interaction.followup.send(f"You don't have enough {display_item_name(item_name)} to sell!")

                if items[item_name]['type'] not in ['animal', 'fish']:
                    return await interaction.followup.send("This item cannot be sold!")
                
                items_to_sell.append((item_name, amount))

            if not items_to_sell:
                return await interaction.followup.send("No items to sell!")

            item_list = []
            for item_name, qty in items_to_sell:
                price = get_market_price(item_name)
                value = price * qty
                total_value += value
                item_list.append(f"• {display_item_name(item_name)} x{qty} = {value:,} coins")

            tax = int(total_value * 0.05)
            final_value = total_value - tax

            embed = discord.Embed(
                title="Sell Confirmation",
                description="Are you sure you want to sell these items?",
                color=discord.Color.gold()
            )
            embed.add_field(name="Items to Sell", value="\n".join(item_list), inline=False)
            embed.add_field(name="Total Value", value=f"{total_value:,} coins", inline=True)
            embed.add_field(name="Tax (5%)", value=f"{tax:,} coins", inline=True)
            embed.add_field(name="Final Value", value=f"{final_value:,} coins", inline=True)

            view = discord.ui.View(timeout=30)

            async def execute_sale():
                for item_name, qty in items_to_sell:
                    eco[user_id]['inventory'][item_name] -= qty
                    if eco[user_id]['inventory'][item_name] <= 0:
                        del eco[user_id]['inventory'][item_name]
                    update_market_price(item_name, False)

                eco[user_id]['balance']['purse'] += final_value
                save_file(eco_path, eco)

            confirm_button = Button(label="Confirm", style=ButtonStyle.green)
            async def confirm_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != interaction.user.id:
                    return await button_interaction.response.send_message("This confirmation is not for you!", ephemeral=True)

                await execute_sale()
                embed.color = discord.Color.green()
                embed.description = "Items sold successfully!"
                await button_interaction.message.edit(embed=embed, view=None)
                await button_interaction.response.send_message(f"You received {final_value:,} coins!", ephemeral=True)

            cancel_button = Button(label="Cancel", style=ButtonStyle.red)
            async def cancel_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != interaction.user.id:
                    return await button_interaction.response.send_message("This confirmation is not for you!", ephemeral=True)

                embed.color = discord.Color.red()
                embed.description = "Sale cancelled!"
                await button_interaction.message.edit(embed=embed, view=None)
                await button_interaction.response.send_message("Sale cancelled!", ephemeral=True)

            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            view.add_item(confirm_button)
            view.add_item(cancel_button)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await handle_logs(interaction, e)

class AuctionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="auction", description="Not coming soon.")
        
    def setup_commands(self):
        load_commands(self, "economy")

def normalize_item_name(item_name):
    """Normalize item name to underscore format used in storage"""
    return item_name.lower().replace(" ", "_")

def display_item_name(item_name):
    """Convert stored item name format to display format"""
    return item_name.replace("_", " ").title()

def find_closest_item(search_term: str, shop_items: list) -> str:
    """Find closest matching item name from search term"""
    normalized_search = "".join(search_term.lower().split())
    normalized_items = [(item["item"], "".join(item["item"].lower().split())) for item in shop_items]
    
    for orig, norm in normalized_items:
        if norm == normalized_search:
            return orig
            
    matches = [orig for orig, norm in normalized_items if norm.startswith(normalized_search)]
    if matches:
        return min(matches)
    
    return None

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.command_help = open_file("storage/command_help.json")
        handle_eco_shop.start()

        ecoadmin_group = EcoAdminGroup()
        ecoadmin_group.setup_commands()
        bot.tree.add_command(ecoadmin_group)

        market_group = MarketGroup()
        market_group.setup_commands()
        bot.tree.add_command(market_group)

        shop_group = ShopGroup()  
        shop_group.setup_commands()
        bot.tree.add_command(shop_group)
        
        auction_group = AuctionGroup()
        auction_group.setup_commands()
        bot.tree.add_command(auction_group)
        
        load_commands(self.__cog_app_commands__, "economy")

    def cog_unload(self):
        handle_eco_shop.cancel()

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = int(error.retry_after)
            retry_time = int((discord.utils.utcnow() + timedelta(seconds=retry_after)).timestamp())
            return await interaction.response.send_message(
                f"Command on cooldown. Try again <t:{retry_time}:R>", 
                ephemeral=True
            )
        return await handle_logs(interaction, error)

    @app_commands.command(name="balance")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            user = member or interaction.user
            user_id = str(user.id)

            eco = open_file(eco_path)

            if user_id not in eco:
                if user_id == str(interaction.user.id):
                    create_account(user_id)
                else:
                    return await interaction.followup.send("The user does not have an account.")
                
                eco = open_file(eco_path)

            player_data = eco[user_id]
            purse_balance = int(player_data["balance"]["purse"])
            bank_balance = int(player_data["balance"]["bank"])
            max_bank = int(player_data["balance"]["maxBank"])

            embed = discord.Embed(
                title=f"{user.display_name}'s Balance",
                description=(
                    f"**Wallet:** {purse_balance}\n"
                    f"**Bank:** {bank_balance} / {max_bank} ({(bank_balance / max_bank) * 100:.2f}%)"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            async def update_embed(eco):
                updated_embed = discord.Embed(
                    title=f"{user.display_name}'s Balance",
                    description=(
                        f"**Wallet:** {eco[user_id]['balance']['purse']}\n"
                        f"**Bank:** {eco[user_id]['balance']['bank']} / {eco[user_id]['balance']['maxBank']} "
                        f"({(eco[user_id]['balance']['bank'] / eco[user_id]['balance']['maxBank']) * 100:.2f}%)"
                    ),
                    color=discord.Color.green()
                )
                updated_embed.set_footer(text=f"Requested by {interaction.user.display_name}")
                return updated_embed

            view = RestrictedView(interaction.user)

            withdraw_button = Button(label="Withdraw", style=ButtonStyle.red)
            async def withdraw_callback(interaction: discord.Interaction):
                if interaction.user.id != user.id:
                    return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                modal = Modal(title="Withdraw")
                amount_input = TextInput(label="Amount to withdraw")
                modal.add_item(amount_input)

                async def modal_callback(modal_interaction: discord.Interaction):
                    try:
                        amount = abs(int(amount_input.value))
                        success, transaction_result = await process_transaction(modal_interaction.user.id, "withdraw", amount)
                        if success:
                            eco = open_file(eco_path)
                            updated_embed = await update_embed(eco)
                            await modal_interaction.message.edit(embed=updated_embed)
                        await modal_interaction.response.send_message(transaction_result, ephemeral=True)
                    except ValueError:
                        await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)

                modal.on_submit = modal_callback
                await interaction.response.send_modal(modal)

            withdraw_button.callback = withdraw_callback
            view.add_item(withdraw_button)

            deposit_button = Button(label="Deposit", style=ButtonStyle.green)
            async def deposit_callback(interaction: discord.Interaction):
                if interaction.user.id != user.id:
                    return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                modal = Modal(title="Deposit")
                amount_input = TextInput(label="Amount to deposit")
                modal.add_item(amount_input)

                async def modal_callback(modal_interaction: discord.Interaction):
                    try:
                        amount = abs(int(amount_input.value))
                        success, transaction_result = await process_transaction(modal_interaction.user.id, "deposit", amount)
                        if success:
                            eco = open_file(eco_path)
                            updated_embed = await update_embed(eco)
                            await modal_interaction.message.edit(embed=updated_embed)
                        await modal_interaction.response.send_message(transaction_result, ephemeral=True)
                    except ValueError:
                        await modal_interaction.response.send_message("Please enter a valid number.", ephemeral=True)

                modal.on_submit = modal_callback
                await interaction.response.send_modal(modal)

            deposit_button.callback = deposit_callback
            view.add_item(deposit_button)

            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        try:
            user_id = str(interaction.user.id)
            result = await process_transaction(user_id, "withdraw", amount)
            await interaction.response.send_message(result[1], ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="deposit") 
    async def deposit(self, interaction: discord.Interaction, amount: int):
        try:
            user_id = str(interaction.user.id)
            result = await process_transaction(user_id, "deposit", amount)
            await interaction.response.send_message(result[1], ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="pay")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await interaction.response.defer()
        try:
            if member.id == interaction.user.id:
                return await interaction.followup.send("You can't pay yourself!")

            if amount <= 0:
                return await interaction.followup.send("Amount must be positive!")

            sender_id = str(interaction.user.id)
            receiver_id = str(member.id)

            eco = check_user_exists(sender_id)
            eco = check_user_exists(receiver_id)

            if eco[sender_id]['balance']['purse'] < amount:
                return await interaction.followup.send("You don't have enough coins!")

            eco[sender_id]['balance']['purse'] -= amount
            eco[receiver_id]['balance']['purse'] += amount
            save_file(eco_path, eco)

            await interaction.followup.send(f"Successfully paid {amount:,} coins to {member.display_name}!")

        except Exception as e:
            await handle_logs(interaction, e)

        @app_commands.command(name="request")
        @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
        async def request(self, interaction: discord.Interaction, member: discord.Member, amount: int):
            await interaction.response.defer()
            try:
                if member.id == interaction.user.id:
                    return await interaction.followup.send("You cannot request from yourself!")

                if amount <= 0:
                    return await interaction.followup.send("Amount must be positive!")

                requester_id = str(interaction.user.id)
                sender_id = str(member.id)

                eco = check_user_exists(requester_id)
                eco = check_user_exists(sender_id)

                if eco[sender_id]['balance']['purse'] < amount:
                    return await interaction.followup.send("The user doesn't have enough coins!")

                embed = discord.Embed(
                    title="Payment Request",
                    description=f"{interaction.user.display_name} has requested {amount:,} coins from you!",
                    color=discord.Color.blue()
                )

                view = discord.ui.View(timeout=60)

                accept_button = Button(label="Accept", style=ButtonStyle.green)
                async def accept_callback(button_interaction: discord.Interaction):
                    if button_interaction.user.id != member.id:
                        return await button_interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                    eco[sender_id]['balance']['purse'] -= amount
                    eco[requester_id]['balance']['purse'] += amount
                    save_file(eco_path, eco)

                    embed.color = discord.Color.green()
                    embed.description = f"✅ {button_interaction.user.display_name} sent {amount:,} coins to {interaction.user.display_name}!"
                    await button_interaction.message.edit(embed=embed, view=None)
                    await button_interaction.response.send_message(f"You sent {amount:,} coins to {interaction.user.display_name}!", ephemeral=True)

                accept_button.callback = accept_callback
                view.add_item(accept_button)

                decline_button = Button(label="Decline", style=ButtonStyle.red)
                async def decline_callback(button_interaction: discord.Interaction):
                    if button_interaction.user.id != member.id:
                        return await button_interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                    embed.color = discord.Color.red()
                    embed.description = f"❌ {button_interaction.user.display_name} declined the payment request."
                    await button_interaction.message.edit(embed=embed, view=None)
                    await button_interaction.response.send_message("Payment request declined.", ephemeral=True)

                decline_button.callback = decline_callback
                view.add_item(decline_button)

                await interaction.followup.send(f"{member.mention}", embed=embed, view=view)

            except Exception as e:
                await handle_logs(interaction, e)

    @app_commands.command(name="trade")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def trade(self, interaction: discord.Interaction, 
                   member: discord.Member,
                   item: str = None, item_amount: int = 1, 
                   coins: int = 0,
                   requested_item: str = None, requested_amount: int = 1, 
                   requested_coins: int = 0):
        await interaction.response.defer()
        try:
            if member.id == interaction.user.id:
                return await interaction.followup.send("You cannot trade with yourself!")

            if coins < 0 or requested_coins < 0:
                return await interaction.followup.send("Coin amounts must be non-negative!")
                
            if (item_amount < 1 and item) or (requested_amount < 1 and requested_item):
                return await interaction.followup.send("Item amounts must be positive!")

            if not item and coins == 0:
                return await interaction.followup.send("You must offer either an item or coins to trade!")

            if not requested_item and requested_coins == 0:
                return await interaction.followup.send("You must request either an item or coins to trade!")

            trader_id = str(interaction.user.id)
            receiver_id = str(member.id)

            eco = check_user_exists(trader_id)
            eco = check_user_exists(receiver_id)

            if item:
                item = normalize_item_name(item)
                if item not in items:
                    return await interaction.followup.send(f"The item '{display_item_name(item)}' doesn't exist!")
                if item not in eco[trader_id].get('inventory', {}) or eco[trader_id]['inventory'][item] < item_amount:
                    return await interaction.followup.send(f"You don't have {item_amount}x {display_item_name(item)} to trade!")

            if requested_item:
                requested_item = normalize_item_name(requested_item)
                if requested_item not in items:
                    return await interaction.followup.send(f"The item '{display_item_name(requested_item)}' doesn't exist!")
                if requested_item not in eco[receiver_id].get('inventory', {}) or eco[receiver_id]['inventory'][requested_item] < requested_amount:
                    return await interaction.followup.send(f"{member.display_name} doesn't have {requested_amount}x {display_item_name(requested_item)} to trade!")

            if coins > 0 and coins > eco[trader_id]['balance']['purse']:
                return await interaction.followup.send("You don't have enough coins for this trade!")
            if requested_coins > 0 and requested_coins > eco[receiver_id]['balance']['purse']:
                return await interaction.followup.send(f"{member.display_name} doesn't have enough coins for this trade!")

            embed = discord.Embed(
                title="Trade Offer",
                description=f"{interaction.user.display_name} wants to trade with you!",
                color=discord.Color.blue()
            )

            offering = []
            if item:
                offering.append(f"• {display_item_name(item)} ({item_amount}x)")
            if coins > 0:
                offering.append(f"• {coins:,} coins")

            requesting = []
            if requested_item:
                requesting.append(f"• {display_item_name(requested_item)} ({requested_amount}x)")
            if requested_coins > 0:
                requesting.append(f"• {requested_coins:,} coins")

            embed.add_field(name="Offering", value="\n".join(offering), inline=True)
            embed.add_field(name="Requesting", value="\n".join(requesting), inline=True)

            view = discord.ui.View(timeout=60)

            async def execute_trade():
                eco[trader_id]['inventory'][item] -= item_amount
                if item not in eco[receiver_id].get('inventory', {}):
                    eco[receiver_id]['inventory'][item] = 0
                eco[receiver_id]['inventory'][item] += item_amount

                if requested_item:
                    eco[receiver_id]['inventory'][requested_item] -= requested_amount
                    if requested_item not in eco[trader_id].get('inventory', {}):
                        eco[trader_id]['inventory'][requested_item] = 0
                    eco[trader_id]['inventory'][requested_item] += requested_amount

                eco[trader_id]['balance']['purse'] -= coins
                eco[receiver_id]['balance']['purse'] += coins
                eco[receiver_id]['balance']['purse'] -= requested_coins
                eco[trader_id]['balance']['purse'] += requested_coins

                if eco[trader_id]['inventory'][item] <= 0:
                    del eco[trader_id]['inventory'][item]
                if requested_item and eco[receiver_id]['inventory'][requested_item] <= 0:
                    del eco[receiver_id]['inventory'][requested_item]

                save_file(eco_path, eco)

            accept_button = Button(label="Accept Trade", style=ButtonStyle.green)
            async def accept_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != member.id:
                    return await button_interaction.response.send_message("This trade is not for you!", ephemeral=True)

                if (item not in eco[trader_id].get('inventory', {}) or 
                    eco[trader_id]['inventory'][item] < item_amount or
                    coins > eco[trader_id]['balance']['purse'] or
                    (requested_item and (requested_item not in eco[receiver_id].get('inventory', {}) or 
                    eco[receiver_id]['inventory'][requested_item] < requested_amount)) or
                    requested_coins > eco[receiver_id]['balance']['purse']):
                    return await button_interaction.response.send_message("Trade conditions are no longer met!", ephemeral=True)

                await execute_trade()
                embed.color = discord.Color.green()
                embed.description = "Trade completed successfully!"
                await button_interaction.message.edit(embed=embed, view=None)
                await button_interaction.response.send_message("Trade completed!", ephemeral=True)

            decline_button = Button(label="Decline Trade", style=ButtonStyle.red)
            async def decline_callback(button_interaction: discord.Interaction):
                if button_interaction.user.id != member.id:
                    return await button_interaction.response.send_message("This trade is not for you!", ephemeral=True)

                embed.color = discord.Color.red()
                embed.description = "Trade declined!"
                await button_interaction.message.edit(embed=embed, view=None)
                await button_interaction.response.send_message("Trade declined!", ephemeral=True)

            accept_button.callback = accept_callback
            decline_button.callback = decline_callback
            view.add_item(accept_button)
            view.add_item(decline_button)

            await interaction.followup.send(f"{member.mention}", embed=embed, view=view)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="coinflip")
    @app_commands.choices(
        guess=[
            app_commands.Choice(name="Heads", value="Heads"),
            app_commands.Choice(name="Tails", value="Tails"),
        ]
    )
    async def coinflip(self, interaction: discord.Interaction, guess: str = None, amount: str = None):
        try:
            coin = random.choice(["Heads", "Tails"])

            if not guess:
                return await interaction.response.send_message(f"The coin landed on {coin}!")

            won = coin.lower() == guess.lower()
            if not amount:
                return await interaction.response.send_message(f"{'Congrats' if won else 'Bad luck'}! The coin landed on {coin}!")

            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            if amount.lower() == "all":
                bet = eco[user_id]["balance"]["purse"]
            else:
                try:
                    bet = convert_number(amount)
                    if bet < 1:
                        return await interaction.followup.send("Please enter a value greater than 0.")
                except ValueError:
                    return await interaction.followup.send("Invalid amount format. Use formats like 10k, 50m, etc.")

                if eco[user_id]["balance"]["purse"] < bet:
                    return await interaction.followup.send("You don't have enough coins!")

            eco[user_id]["balance"]["purse"] += bet if won else -bet
            save_file(eco_path, eco)

            return await interaction.response.send_message(f"The coin landed on {coin}! You {'won' if won else 'lost'} {bet:,} coins!")

        except Exception as e:
            return await handle_logs(interaction, e)

    @app_commands.command(name="inventory")
    @app_commands.describe(member="The user whose inventory you want to check.")
    async def inventory(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            user = member or interaction.user
            user_id = str(user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                if user_id == str(interaction.user.id):
                    create_account(user_id)
                    eco = open_file(eco_path)
                else:
                    return await interaction.followup.send("This user doesn't have an account!")

            inventory = eco[user_id].get('inventory', {})
            
            if not inventory:
                return await interaction.followup.send(f"{user.display_name}'s inventory is empty!")

            embed = discord.Embed(
                title=f"{user.display_name}'s Inventory",
                color=discord.Color.blue()
            )

            grouped_items = {}
            for item_name, amount in inventory.items():
                if item_name in items:
                    item_type = items[item_name].get('type', 'Misc')
                    if item_type not in grouped_items:
                        grouped_items[item_type] = []
                    grouped_items[item_type].append(f"{display_item_name(item_name)}: {amount}x")

            for item_type, item_list in grouped_items.items():
                embed.add_field(
                    name=f"📦 {item_type.title()}",
                    value="\n".join(item_list) or "Empty",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="hunt")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def hunt(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            has_rifle = 'rifle' in eco[user_id].get('inventory', {})
            
            if not has_rifle:
                return await interaction.followup.send("You need a rifle to hunt! Buy one from the shop.")

            animals = {
                "rabbit": 35,
                "deer": 25,
                "fox": 20,
                "boar": 10,
                "wolf": 7,
                "bear": 3
            }

            embed = discord.Embed(title="Gone Hunting!")

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('rifle')
                embed.color = discord.Color.red()
                embed.description = "Your rifle broke :("
                save_file(eco_path, eco)
                return await interaction.followup.send(embed=embed)

            animal = random.choices(list(animals.keys()), weights=list(animals.values()))[0]
            
            if 'inventory' not in eco[user_id]:
                eco[user_id]['inventory'] = {}
            if animal not in eco[user_id]['inventory']:
                eco[user_id]['inventory'][animal] = 0
            
            eco[user_id]['inventory'][animal] += 1

            coin_bonus = ""
            if random.random() < 0.5:
                base_coins = random.randint(500, 1200)
                coin_boost = eco[user_id]['boosts']['coins']
                total_coins = int(base_coins * (coin_boost / 100))
                eco[user_id]['balance']['purse'] += total_coins
                coin_bonus = f"\nBonus: {total_coins:,} coins!"

            save_file(eco_path, eco)

            embed.color = discord.Color.green()
            embed.description = f"You caught a {display_item_name(animal)}! (Worth {items[animal]['price']:,} coins){coin_bonus}"
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="fish")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id)) 
    async def fish(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            has_rod = 'fishing_rod' in eco[user_id].get('inventory', {})
            
            if not has_rod:
                return await interaction.followup.send("You need a fishing rod to fish! Buy one from the shop.")

            fish_types = {
                "cod": 35,
                "salmon": 25,
                "tuna": 20,
                "swordfish": 10,
                "shark": 7,
                "whale": 3
            }

            embed = discord.Embed(title="Gone Fishing! 🎣")

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('fishing_rod')
                embed.color = discord.Color.red()
                embed.description = "Your fishing rod broke :("
                save_file(eco_path, eco)
                return await interaction.followup.send(embed=embed)

            fish = random.choices(list(fish_types.keys()), weights=list(fish_types.values()))[0]
            
            if 'inventory' not in eco[user_id]:
                eco[user_id]['inventory'] = {}
            if fish not in eco[user_id]['inventory']:
                eco[user_id]['inventory'][fish] = 0
            
            eco[user_id]['inventory'][fish] += 1

            coin_bonus = ""
            if random.random() < 0.5:
                base_coins = random.randint(500, 1200)
                coin_boost = eco[user_id]['boosts']['coins']
                total_coins = int(base_coins * (coin_boost / 100))
                eco[user_id]['balance']['purse'] += total_coins
                coin_bonus = f"\nBonus: {total_coins:,} coins!"

            save_file(eco_path, eco)

            embed.color = discord.Color.blue()
            embed.description = f"You caught a {display_item_name(fish)}! (Worth {items[fish]['price']:,} coins){coin_bonus}"
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @commands.command(name="balance", aliases=["bal"])
    async def manual_balance(self, ctx, member: discord.Member = None):
        try:
            interaction = await create_interaction(ctx)
            await self.balance.callback(self, interaction, member)
        except Exception as e:
            error(e)

    @commands.command(name="withdraw", aliases=["with"])
    async def manual_withdraw(self, ctx, amount: int):
        try:
            interaction = await create_interaction(ctx)
            await self.withdraw.callback(self, interaction, amount)
        except Exception as e:
            error(e)

    @commands.command(name="deposit", aliases=["dep"])
    async def manual_deposit(self, ctx, amount: int):
        try:
            interaction = await create_interaction(ctx)
            await self.deposit.callback(self, interaction, amount)
        except Exception as e:
            error(e)

    @commands.command(name="beg")
    async def manual_beg(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.beg.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="fish")
    async def manual_fish(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.fish.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="hunt")
    async def manual_hunt(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.hunt.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="dig")
    async def manual_dig(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.dig.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="search")
    async def manual_search(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.search.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="crime")
    async def manual_crime(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.crime.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="daily")
    async def manual_daily(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.daily.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="weekly")
    async def manual_weekly(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.weekly.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="monthly")
    async def manual_monthly(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            await self.monthly.callback(self, interaction)
        except Exception as e:
            error(e)

    @commands.command(name="coinflip", aliases=["cf"])
    async def manual_coinflip(self, ctx, guess: str = None, amount: str = None):
        try:
            interaction = await create_interaction(ctx)
            await self.coinflip.callback(self, interaction, guess, amount)
        except Exception as e:
            error(e)

    @commands.command(name="inventory", aliases=["inv"])
    async def manual_inventory(self, ctx, member: discord.Member = None):
        try:
            interaction = await create_interaction(ctx)
            await self.inventory.callback(self, interaction, member)
        except Exception as e:
            error(e)

    @commands.group(name="shop", invoke_without_command=True)
    async def manual_shop(self, ctx):
        try:
            interaction = await create_interaction(ctx)
            shop_cmd = self.bot.tree.get_command("shop")
            await shop_cmd.get_command("view").callback(shop_cmd, interaction)
        except Exception as e:
            error(e)

    @manual_shop.command(name="view")
    async def manual_shop_view(self, ctx):
        try:
            interaction = await create_interaction(ctx) 
            shop_cmd = self.bot.tree.get_command("shop")
            await shop_cmd.get_command("view").callback(shop_cmd, interaction)
        except Exception as e:
            error(e)

    @manual_shop.command(name="buy")
    async def manual_shop_buy(self, ctx, item_name: str = None, quantity: int = 1):
        try:
            if not item_name:
                help_data = self.command_help.get("economy", {}).get("shop", {}).get("subcommands", {}).get("buy", {})
                if help_data:
                    embed = discord.Embed(
                        title="Missing Required Argument: item_name",
                        description=help_data.get("description", "No description available."),
                        color=discord.Color.red()
                    )
                    if "parameters" in help_data:
                        params = help_data["parameters"]
                        param_text = "\n".join([f"**{param}**: {desc}" for param, desc in params.items()])
                        embed.add_field(name="Parameters", value=param_text, inline=False)
                    return await ctx.send(embed=embed, delete_after=30)
                return

            interaction = await create_interaction(ctx)
            
            if not SHOP:
                await handle_eco_shop()

            closest_item = find_closest_item(item_name, SHOP)
            if not closest_item:
                await ctx.send(f"No item found matching '{item_name}'")
                return

            shop_cmd = self.bot.tree.get_command("shop")
            await shop_cmd.get_command("buy").callback(shop_cmd, interaction, closest_item, quantity)
            
        except Exception as e:
            error(e)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))