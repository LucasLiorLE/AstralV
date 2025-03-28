import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal
from datetime import datetime, timedelta

import random
from string import ascii_letters, digits

from bot_utils import (
    convert_number,
    handle_logs,
    open_json,
    save_json
)

from .utils import (
    check_user_stat,
    get_item_name,
    display_item_name,
    get_item_suggestions
)

async def auto_suggest_items(interaction: discord.Interaction, string: str):
    user = str(interaction.user.id)
    user_data = open_json("storage/economy/economy.json").get(user)
    if user_data is None:
        return []
    
    inventory = user_data.get("inventory", {})
    items = [display_item_name(item) for item in inventory.keys() if string.lower() in item.lower()]
    return [app_commands.Choice(name=item.title(), value=item) for item in items][:25]

class SortSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Newest", description="Sort by newest listings", value="newest"),
            discord.SelectOption(label="Expiring Soon", description="Sort by expiring soonest", value="expiring"),
            discord.SelectOption(label="Price (Low to High)", description="Sort by lowest price", value="price_asc"),
            discord.SelectOption(label="Price (High to Low)", description="Sort by highest price", value="price_desc")
        ]
        super().__init__(placeholder="Sort listings...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        view.sort_by = self.values[0]
        await view.refresh_page(interaction)

class ListingButton(discord.ui.Button):
    def __init__(self, listing_id: str, listing: dict, is_owner: bool):
        self.listing_id = listing_id
        self.listing = listing
        super().__init__(
            label="Remove Listing" if is_owner else f"Buy for {listing['price']:,} each",
            style=discord.ButtonStyle.red if is_owner else discord.ButtonStyle.green,
            custom_id=f"listing_{listing_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.style == discord.ButtonStyle.red:
            market_data = open_json("storage/economy/market.json")
            if "listings" not in market_data:
                market_data["listings"] = {}
                
            if self.listing_id in market_data["listings"]:
                listing = market_data["listings"][self.listing_id]
                
                del market_data["listings"][self.listing_id]
                save_json("storage/economy/market.json", market_data)
                
                user_data = open_json("storage/economy/economy.json")
                seller = str(listing["seller"])
                if listing["item"] not in user_data[seller]["inventory"]:
                    user_data[seller]["inventory"][listing["item"]] = 0
                user_data[seller]["inventory"][listing["item"]] += listing["amount"]
                save_json("storage/economy/economy.json", user_data)
                
                await interaction.response.send_message(f"Listing removed and {listing['amount']}x {display_item_name(listing['item'])} returned to your inventory.")
            else:
                await interaction.response.send_message("This listing no longer exists.")
            return

        economy_data = open_json("storage/economy/economy.json")
        buyer = str(interaction.user.id)
        
        if economy_data[buyer]["balance"]["purse"] < self.listing["price"]:
            await interaction.response.send_message("You can't afford this item.", ephemeral=True)
            return
        
        max_affordable = min(
            self.listing["amount"],
            economy_data[buyer]["balance"]["purse"] // self.listing["price"]
        )
        
        modal = BuyModal(max_affordable)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.interaction_value:
            try:
                amount = int(modal.interaction_value)
                if 1 <= amount <= max_affordable:
                    market_data = open_json("storage/economy/market.json")
                    listing = market_data["listings"].get(self.listing_id)
                    
                    if not listing or listing["amount"] < amount:
                        await interaction.followup.send("This listing is no longer available.", ephemeral=True)
                        return
                    
                    total_cost = listing["price"] * amount
                    seller = str(listing["seller"])
                    
                    economy_data[buyer]["balance"]["purse"] -= total_cost
                    economy_data[seller]["balance"]["purse"] += total_cost
                    
                    if listing["item"] not in economy_data[buyer]["inventory"]:
                        economy_data[buyer]["inventory"][listing["item"]] = 0
                    economy_data[buyer]["inventory"][listing["item"]] += amount
                    
                    listing["amount"] -= amount
                    if listing["amount"] <= 0:
                        del market_data["listings"][self.listing_id]
                    
                    save_json("storage/economy/market.json", market_data)
                    save_json("storage/economy/economy.json", economy_data)
                    
                    await interaction.followup.send(
                        f"Successfully bought {amount}x {display_item_name(listing['item'])} "
                        f"for {total_cost:,} coins."
                    )
                else:
                    await interaction.followup.send("Invalid amount specified.", ephemeral=True)
            except ValueError:
                await interaction.followup.send("Please enter a valid number.", ephemeral=True)

class MarketView(View):
    def __init__(self, bot, listings, user, page=1, search=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.listings = listings
        self.user = user
        self.page = page
        self.search = search
        self.sort_by = "newest"
        self.items_per_page = 5
        self.add_item(SortSelect())
        self.update_buttons()

    def update_buttons(self):
        sorted_listings = self.sort_listings()
        total_pages = (len(sorted_listings) + self.items_per_page - 1) // self.items_per_page
        
        self.previous.disabled = self.page <= 1
        
        self.next.disabled = self.page >= total_pages

    def sort_listings(self):
        if self.sort_by == "newest":
            return self.listings
        elif self.sort_by == "expiring":
            return sorted(self.listings, key=lambda x: x[1]["expires_at"])
        elif self.sort_by == "price_asc":
            return sorted(self.listings, key=lambda x: x[1]["price"])
        else:
            return sorted(self.listings, key=lambda x: x[1]["price"], reverse=True)

    async def create_embed(self):
        sorted_listings = self.sort_listings()
        start_idx = (self.page - 1) * self.items_per_page
        page_listings = sorted_listings[start_idx:start_idx + self.items_per_page]
        
        buttons_to_remove = [item for item in self.children if isinstance(item, ListingButton)]
        for button in buttons_to_remove:
            self.remove_item(button)
        
        title = "Market Listings"
        if self.search:
            title += f" - Search: {self.search}"
        
        embed = discord.Embed(title=title, color=discord.Color.blue())
        
        if not page_listings:
            embed.description = "No listings found on this page."
            return embed
        
        for listing_id, listing in page_listings:
            item_name = display_item_name(listing["item"])
            seller = await self.bot.fetch_user(listing["seller"])
            seller_name = seller.name if seller else "Unknown"
            
            expires_in = listing["expires_at"] - datetime.now().timestamp()
            expires_text = f"{int(expires_in // 3600)} hours" if expires_in > 0 else "Expired"
            
            embed.add_field(
                name=f"{item_name} (ID: {listing_id})",
                value=f"Price: {listing['price']:,} coins\n"
                      f"Amount: {listing['amount']}\n"
                      f"Seller: {seller_name}\n"
                      f"Expires in: {expires_text}",
                inline=False
            )
            
            self.add_item(ListingButton(
                listing_id,
                listing,
                listing["seller"] == self.user.id
            ))
        
        total_pages = (len(sorted_listings) + self.items_per_page - 1) // self.items_per_page
        embed.set_footer(text=f"Page {self.page}/{total_pages}")
        return embed

    async def refresh_page(self, interaction):
        embed = await self.create_embed()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self.refresh_page(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.refresh_page(interaction)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.blurple)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.refresh_page(interaction)

class BuyModal(Modal):
    def __init__(self, max_amount):
        super().__init__(title="Buy Items")
        self.amount = discord.ui.TextInput(
            label=f"Amount (max: {max_amount})",
            placeholder="Enter amount to buy",
            min_length=1,
            max_length=len(str(max_amount)),
            required=True
        )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.interaction_value = self.amount.value
        self.stop()

class MarketCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Market related commands")
        self.market = "storage/economy/market.json"

    @app_commands.command(name="post")
    @app_commands.autocomplete(item=auto_suggest_items)
    async def post(self, interaction: discord.Interaction, price: str, amount: int, days: int, item: str):
        try:
            if not 1 <= days <= 31:
                return await interaction.response.send_message("Days must be between 1 and 31.")

            price = convert_number(price)
            if price <= 0:
                return await interaction.response.send_message("Price must be positive.")

            item_name = get_item_name(item)
            current_amount = check_user_stat(["inventory", item_name], interaction.user.id, int)
            if amount > current_amount:
                return await interaction.response.send_message("You don't have enough of this item.")

            user_data = open_json("storage/economy/economy.json")
            user_data[str(interaction.user.id)]["inventory"][item_name] -= amount
            save_json("storage/economy/economy.json", user_data)

            market_data = open_json(self.market)
            if "listings" not in market_data:
                market_data["listings"] = {}
                
            unique_id = "".join(random.choices(ascii_letters + digits, k=6))
            market_data["listings"][unique_id] = {
                "seller": interaction.user.id,
                "item": item_name,
                "price": price,
                "amount": amount,
                "posted_at": datetime.now().timestamp(),
                "expires_at": (datetime.now() + timedelta(days=days)).timestamp()
            }
            
            save_json(self.market, market_data)

            await interaction.response.send_message(f"Listed {amount}x {display_item_name(item_name)} for {price} coins each (ID: {unique_id})")
            
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="view")
    @app_commands.autocomplete(search=get_item_suggestions)
    async def view(self, interaction: discord.Interaction, page: int = 1, search: str = None):
        try:
            market_data = open_json(self.market)
            current_time = datetime.now().timestamp()
            
            if not isinstance(market_data, dict):
                market_data = {"listings": {}}
            
            listings_to_move = {}
            for k, v in market_data.items():
                if isinstance(v, dict) and all(key in v for key in ["seller", "item", "price", "amount"]):
                    listings_to_move[k] = v
                    
            for k in listings_to_move:
                del market_data[k]
            
            if "listings" not in market_data:
                market_data["listings"] = {}
            
            market_data["listings"].update(listings_to_move)
            
            cleaned_listings = {}
            for k, v in market_data["listings"].items():
                if not isinstance(v, dict):
                    continue
                    
                listing = v.copy()
                
                if "posted_at" not in listing:
                    listing["posted_at"] = current_time
                if "expires_at" not in listing:
                    listing["expires_at"] = current_time + (7 * 24 * 60 * 60)
                
                if listing["expires_at"] > current_time:
                    cleaned_listings[k] = listing
            
            market_data["listings"] = cleaned_listings
            save_json(self.market, market_data)
            
            if search:
                filtered_listings = {}
                search = search.lower()
                for k, v in cleaned_listings.items():
                    item_name = display_item_name(v["item"])
                    if search in item_name.lower():
                        filtered_listings[k] = v
                cleaned_listings = filtered_listings
            
            if not cleaned_listings:
                return await interaction.response.send_message(
                    "No active listings found." if not search else 
                    f"No listings found for '{search}'."
                )

            listings = list(cleaned_listings.items())
            view = MarketView(self.bot, listings, interaction.user, page, search)
            embed = await view.create_embed()
            
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="buy")
    async def buy(self, interaction: discord.Interaction, listing_id: str, amount: int):
        try:
            market_data = open_json(self.market)
            if "listings" not in market_data:
                market_data["listings"] = {}
            
            listing = market_data["listings"].get(listing_id)
            
            if not listing:
                return await interaction.response.send_message("Invalid listing ID.")
            
            if listing["seller"] == interaction.user.id:
                return await interaction.response.send_message("You can't buy your own listing.")

            if amount > listing["amount"]:
                return await interaction.response.send_message(f"Only {listing['amount']} available.")

            total_cost = listing["price"] * amount
            
            economy_data = open_json("storage/economy/economy.json")
            buyer = str(interaction.user.id)
            seller = str(listing["seller"])
            
            if economy_data[buyer]["balance"]["purse"] < total_cost:
                return await interaction.response.send_message("You can't afford this.")

            economy_data[buyer]["balance"]["purse"] -= total_cost
            economy_data[seller]["balance"]["purse"] += total_cost

            if listing["item"] not in economy_data[buyer]["inventory"]:
                economy_data[buyer]["inventory"][listing["item"]] = 0
            economy_data[buyer]["inventory"][listing["item"]] += amount
            
            listing["amount"] -= amount
            if listing["amount"] <= 0:
                del market_data["listings"][listing_id]
            
            save_json("storage/economy/economy.json", economy_data)
            save_json(self.market, market_data)

            await interaction.response.send_message(
                f"Successfully bought {amount}x {display_item_name(listing['item'])} "
                f"for {total_cost} coins from <@{seller}>."
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="edit")
    async def edit(self, interaction: discord.Interaction, listing_id: str, price: str):
        try:
            market_data = open_json(self.market)
            if "listings" not in market_data:
                return await interaction.response.send_message("Invalid listing ID.")
            
            listing = market_data["listings"].get(listing_id)
            if not listing:
                return await interaction.response.send_message("Invalid listing ID.")
            
            if listing["seller"] != interaction.user.id:
                return await interaction.response.send_message("You can only edit your own listings.")
            
            new_price = convert_number(price)
            if new_price <= 0:
                return await interaction.response.send_message("Price must be positive.")
            
            listing["price"] = new_price
            save_json(self.market, market_data)
            
            await interaction.response.send_message(
                f"Updated listing price for {display_item_name(listing['item'])} "
                f"to {new_price:,} coins."
            )
            
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="remove")
    async def remove(self, interaction: discord.Interaction, listing_id: str):
        try:
            market_data = open_json(self.market)
            if "listings" not in market_data:
                return await interaction.response.send_message("Invalid listing ID.")
            
            listing = market_data["listings"].get(listing_id)
            if not listing:
                return await interaction.response.send_message("Invalid listing ID.")
            
            if listing["seller"] != interaction.user.id:
                return await interaction.response.send_message("You can only remove your own listings.")
            
            del market_data["listings"][listing_id]
            save_json(self.market, market_data)
            
            user_data = open_json("storage/economy/economy.json")
            seller = str(interaction.user.id)
            
            if listing["item"] not in user_data[seller]["inventory"]:
                user_data[seller]["inventory"][listing["item"]] = 0
            user_data[seller]["inventory"][listing["item"]] += listing["amount"]
            save_json("storage/economy/economy.json", user_data)
            
            await interaction.response.send_message(
                f"Removed listing and returned {listing['amount']}x "
                f"{display_item_name(listing['item'])} to your inventory."
            )
            
        except Exception as e:
            await handle_logs(interaction, e)

class MarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(MarketCommandGroup())

async def setup(bot):
    await bot.add_cog(MarketCog(bot))