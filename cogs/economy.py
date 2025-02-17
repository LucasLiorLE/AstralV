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

# Hourly shop system

items = open_file("storage/economy/items.json")
SHOP = []

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
    
# Currency system
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Not coming soon.")
        load_commands(self.commands, "economy")
        

class EcoAdminGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="ecoadmin", description="Economy admin commands.")
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

            await interaction.followup.send(
                f"Successfully bought {quantity}x {display_item_name(shop_item['item'])} for {total_cost:,} coins!"
            )

        except Exception as e:
            await handle_logs(interaction, e)

class AuctionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="auction", description="Not coming soon.")

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
        bot.tree.add_command(MarketGroup())
        bot.tree.add_command(ShopGroup())
        bot.tree.add_command(AuctionGroup())
        
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
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            result = await process_transaction(user_id, "withdraw", amount)
            
            if result[0] == True:
                await interaction.followup.send(result[1], ephemeral=True)
            else:
                await interaction.followup.send(result[1], ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="deposit") 
    async def deposit(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            result = await process_transaction(user_id, "deposit", amount)
            
            if result[0] == True:
                await interaction.followup.send(result[1], ephemeral=True)
            else:
                await interaction.followup.send(result[1], ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="pay")
    async def pay(self, interaction: discord.Interaction):
        pass

    # Basic ways to get money
    @app_commands.command(name="beg")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def beg(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)
            
            coin_boost = eco[user_id]['boosts']['coins']
            base_amount = random.randint(80, 150)
            total_amount = int(base_amount * (coin_boost / 100))
            r = random.randint(1, 4)

            t = {
                "n": [
                    "Go beg somewhere else kid.", 
                    "Do I look rich to you?", 
                    "nah im good.", 
                    "Begging is for losers", 
                    "imagine being so bad!",
                    "rigged rng gave you no coins lmao.",
                    "don't beg in the alley"
                ],
                "y": [
                    f"Sure hon, here have {total_amount} coins.", 
                    f"God felt bad so he gave you {total_amount} coins...",
                    f"a dog took pity on you and gave you {total_amount} coins.",
                    f"Spend {total_amount} coins well...",
                    f"{total_amount} coins appeared out of thin air!",
                    f"you got some coins but im evil so i won't tell you how much",
                    f"the criminals felt so bad they gave you {total_amount} coins",
                    f"You got paied {total_amount} coins to stop begging"
                ]
            }

            embed = discord.Embed(title="plzs moneys im pour")
            if r == 1:
                embed.color = discord.Color.red()
                embed.description = random.choice(t["n"])
                embed.set_footer(text="begging is for losers!")
            else:
                eco[user_id]['balance']['purse'] += total_amount
                save_file(eco_path, eco)
                embed.color = discord.Color.green()
                embed.description = random.choice(t["y"])
                embed.set_footer(text=f"With a coin multiplier of {coin_boost}%")

                if base_amount == 143: # little reference :)
                    embed.set_footer(text="i love you")

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

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('fishing_rod')
                d = f"Your fishing rod broke :("
                f = f"Would have earned {total_amount} coins..."
            else:
                eco[user_id]['balance']['purse'] += total_amount
                d = f"Nice catch! You got {total_amount} coins!"
                f = f"With coin boost: {coin_boost}%"

            embed = discord.Embed(
                title="Fishie fishie :)",
                description=d,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f)

            save_file(eco_path, eco)
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

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            embed = discord.Embed(title="Gone Hunting!")
            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('rifle')
                embed.color = discord.Color.red()
                embed.description = "Your rifle broke :("
                embed.set_footer(text=f"Would have earned {total_amount} coins...")
            else:
                eco[user_id]['balance']['purse'] += total_amount
                embed.color = discord.Color.green()
                embed.description = f"Nice shot! You got {total_amount} coins!"
                embed.set_footer(text=f"With coin boost: {coin_boost}%")

            save_file(eco_path, eco)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dig")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def dig(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            has_shovel = 'shovel' in eco[user_id].get('inventory', {})
            
            if not has_shovel:
                return await interaction.followup.send("You need a shovel to dig! Buy one from the shop.")

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            embed = discord.Embed(title="Time to Dig!")
            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('shovel')
                embed.color = discord.Color.red()
                embed.description = "Your shovel broke :("
                embed.set_footer(text=f"Would have earned {total_amount} coins...")
            else:
                eco[user_id]['balance']['purse'] += total_amount
                embed.color = discord.Color.green()
                embed.description = f"Found something valuable! You got {total_amount} coins!"
                embed.set_footer(text=f"With coin boost: {coin_boost}%")

            save_file(eco_path, eco)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="search")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def search(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            base_amount = random.randint(80, 150)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            t = {
                "success": [
                    f"You found {total_amount} coins in an old coat!", 
                    f"You searched the couch cushions and found {total_amount} coins!",
                    f"Someone dropped {total_amount} coins on the street!",
                    f"You found {total_amount} coins in a vending machine!",
                    f"There was {total_amount} coins under your pillow!",
                    f"You dug through trash and found {total_amount} coins!",
                    f"A kind stranger gave you {total_amount} coins!"
                ],
                "fail": [
                    "You searched but found nothing...",
                    "Better luck next time!",
                    "Nothing here but dust.",
                    "Maybe try searching somewhere else?",
                    "All you found was pocket lint.",
                    "The search was unsuccessful.",
                    "You wasted time searching for nothing."
                ]
            }

            embed = discord.Embed(title="Searching...")
            success = random.random() < 0.75
            if success:
                eco[user_id]['balance']['purse'] += total_amount
                save_file(eco_path, eco)
                embed.color = discord.Color.green()
                embed.description = random.choice(t["success"])
                embed.set_footer(text=f"With coin boost: {coin_boost}%")
            else:
                embed.color = discord.Color.red()
                embed.description = random.choice(t["fail"])
                embed.set_footer(text="Keep searching!")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="crime")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def crime(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            base_amount = random.randint(80, 150)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            t = {
                "success": [
                    f"You successfully pickpocketed {total_amount} coins!", 
                    f"You hacked an ATM and got {total_amount} coins!",
                    f"You robbed a store and got away with {total_amount} coins!",
                    f"Your heist was successful! You got {total_amount} coins!",
                    f"You scammed someone and got {total_amount} coins!",
                    f"Your crime spree earned you {total_amount} coins!",
                    f"The perfect crime netted you {total_amount} coins!"
                ],
                "fail": [
                    "You got caught and had to run away!",
                    "The police were nearby!",
                    "Your target was too difficult to rob.",
                    "Someone saw you and you had to abort!",
                    "The security was too tight!",
                    "Your plan failed miserably!",
                    "Crime doesn't pay today!"
                ]
            }

            embed = discord.Embed(title="Time for Crime!")
            success = random.random() < 0.6
            if success:
                eco[user_id]['balance']['purse'] += total_amount
                save_file(eco_path, eco)
                embed.color = discord.Color.green()
                embed.description = random.choice(t["success"])
                embed.set_footer(text=f"With coin boost: {coin_boost}%")
            else:
                embed.color = discord.Color.red()
                embed.description = random.choice(t["fail"])
                embed.set_footer(text="Better luck next crime!")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="daily")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            
            check_user_stat(['cooldowns'], user_id)
            check_user_stat(['cooldowns', 'daily'], user_id, str)
            check_user_stat(['streaks'], user_id)
            check_user_stat(['streaks', 'daily'], user_id, int)
            
            eco = open_file(eco_path)
            
            now = datetime.now(timezone.utc)
            cooldown = eco[user_id]['cooldowns']['daily']
            last_daily = datetime.fromisoformat(cooldown if cooldown else '2000-01-01T00:00:00+00:00')

            days_passed = (now - last_daily).days

            if days_passed < 1:
                time_left = last_daily + timedelta(days=1) - now
                hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                return await interaction.followup.send(f"You can claim your daily reward in {hours}h {minutes}m {seconds}s")

            streak = eco[user_id]['streaks']['daily']
            
            if days_passed > 3:
                streak = 0
            elif days_passed > 1:
                streak = max(0, streak - (days_passed - 1))

            base_amount = 10000
            streak_multiplier = 1 + (streak * 0.05)
            total_amount = int(base_amount * streak_multiplier * (eco[user_id]['boosts']['coins'] / 100))

            eco[user_id]['balance']['purse'] += total_amount
            eco[user_id]['streaks']['daily'] = streak + 1 
            eco[user_id]['cooldowns']['daily'] = now.isoformat()
            save_file(eco_path, eco)

            embed = discord.Embed(
                title="Daily Reward!",
                description=(
                    f"You received {total_amount:,} coins!\n"
                    f"Streak: {streak + 1} days (+{(streak_multiplier - 1) * 100:.1f}% bonus)\n"
                    f"Next streak bonus: +{((streak + 1) * 0.05) * 100:.1f}%"
                ),
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="weekly")
    async def weekly(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            
            check_user_stat(['cooldowns'], user_id)
            check_user_stat(['cooldowns', 'weekly'], user_id, str)
            check_user_stat(['streaks'], user_id)
            check_user_stat(['streaks', 'weekly'], user_id, int)
            
            eco = open_file(eco_path)
            
            now = datetime.now(timezone.utc)
            cooldown = eco[user_id]['cooldowns']['weekly']
            last_weekly = datetime.fromisoformat(cooldown if cooldown else '2000-01-01T00:00:00+00:00')

            if (now - last_weekly).days < 7:
                time_left = last_weekly + timedelta(days=7) - now
                days = time_left.days
                hours = time_left.seconds // 3600
                return await interaction.followup.send(f"You can claim your weekly reward in {days}d {hours}h")

            coin_boost = eco[user_id]['boosts']['coins']
            streak = eco[user_id]['streaks']['weekly']
            base_amount = 100000
            streak_bonus = min(streak * 500, 900000)
            total_amount = int((base_amount + streak_bonus) * (coin_boost / 100))

            eco[user_id]['balance']['purse'] += total_amount
            eco[user_id]['streaks']['weekly'] += 1
            eco[user_id]['cooldowns']['weekly'] = now.isoformat()
            save_file(eco_path, eco)

            embed = discord.Embed(
                title="Weekly Reward!",
                description=f"You received {total_amount} coins!\nStreak: {streak + 1} weeks (+{streak_bonus} bonus)",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="monthly")
    async def monthly(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            
            check_user_stat(['cooldowns'], user_id)
            check_user_stat(['cooldowns', 'monthly'], user_id, str)
            check_user_stat(['streaks'], user_id)
            check_user_stat(['streaks', 'monthly'], user_id, int)
            
            eco = open_file(eco_path)
            
            now = datetime.now(timezone.utc)
            cooldown = eco[user_id]['cooldowns']['monthly']
            last_monthly = datetime.fromisoformat(cooldown if cooldown else '2000-01-01T00:00:00+00:00')

            if (now - last_monthly).days < 30:
                time_left = last_monthly + timedelta(days=30) - now
                days = time_left.days
                hours = time_left.seconds // 3600
                return await interaction.followup.send(f"You can claim your monthly reward in {days}d {hours}h")

            coin_boost = eco[user_id]['boosts']['coins']
            streak = eco[user_id]['streaks']['monthly']
            base_amount = 5000000
            streak_bonus = min(streak * 5000, 20000000) 
            total_amount = int((base_amount + streak_bonus) * (coin_boost / 100))

            eco[user_id]['balance']['purse'] += total_amount
            eco[user_id]['streaks']['monthly'] += 1
            eco[user_id]['cooldowns']['monthly'] = now.isoformat()
            save_file(eco_path, eco)

            embed = discord.Embed(
                title="Monthly Reward!",
                description=f"You received {total_amount} coins!\nStreak: {streak + 1} months (+{streak_bonus} bonus)",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="coinflip")
    @app_commands.describe(guess="Heads or tails?", amount="Optional amount if you want to bet!")
    @app_commands.choices(
        guess=[
            app_commands.Choice(name="Heads", value="Heads"),
            app_commands.Choice(name="Tails", value="Tails"),
        ]
    )
    async def coinflip(self, interaction: discord.Interaction, guess: str = None, amount: str = None):
        await interaction.response.defer()
        try:
            coin = random.choice(["Heads", "Tails"])
            
            if not guess:
                return await interaction.followup.send(f"The coin landed on {coin}!")

            won = coin.lower() == guess.lower()
            if not amount:
                return await interaction.followup.send(
                    f"{'Congrats' if won else 'Bad luck'}! The coin landed on {coin}!"
                )

            try:
                bet = abs(convert_number(amount))
            except ValueError:
                return await interaction.followup.send("Invalid amount format. Use formats like 10k, 50m, etc.")

            user_id = str(interaction.user.id)
            eco = check_user_exists(user_id)

            if eco[user_id]["balance"]["purse"] < bet:
                return await interaction.followup.send("You don't have enough coins!")

            eco[user_id]["balance"]["purse"] += bet if won else -bet
            save_file(eco_path, eco)

            return await interaction.followup.send(
                f"The coin landed on {coin}! You {'won' if won else 'lost'} {bet:,} coins!"
            )

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