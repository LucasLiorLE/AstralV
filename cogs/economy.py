from bot_utils import (
    open_file,
    save_file,
    convert_number,
    RestrictedView,
    create_account,
    check_user_stat,
    process_transaction,
    update_stats,
    gambling_stats,
    eco_path,
    handle_logs
)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ButtonStyle
from discord.ui import Button, View, button, Modal, TextInput

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
                "type": data.get("type", "No type")  # Add this line to include the type
            })
    
# Currency system
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Not coming soon.")

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop commands.")

    @app_commands.command(name="view", description="View the shop.")
    async def view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()

            embed = discord.Embed(title="Shop Items", color=discord.Color.blue())
            for item in SHOP:
                amount = "Infinity" if item["amount"] == -1 else item["amount"]
                embed.add_field(
                    name=f"{item['item'].title()}",
                    value=f"**Price**: {item['price']}\n**Amount Left**: {amount}\n**Description**: {item['description']}\n**Type**: {item['type']}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            handle_logs(interaction, e)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    async def buy(self, interaction: discord.Interaction, item_name: str, quantity: int = 1):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()

            user_id = str(interaction.user.id)
            eco = open_file(eco_path)
            
            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)
            
            for item in SHOP:
                if item["item"].lower() == item_name.lower():
                    total_cost = item["price"] * quantity
                    
                    if eco[user_id]["balance"]["purse"] < total_cost:
                        await interaction.followup.send("You don't have enough coins!", ephemeral=True)
                        return
                        
                    if item["amount"] != -1 and item["amount"] < quantity:
                        await interaction.followup.send(f"Not enough {item_name} in stock!", ephemeral=True)
                        return

                    if "inventory" not in eco[user_id]:
                        eco[user_id]["inventory"] = {}

                    if item["item"] in eco[user_id]["inventory"]:
                        eco[user_id]["inventory"][item["item"]] += quantity
                    else:
                        eco[user_id]["inventory"][item["item"]] = quantity

                    eco[user_id]["balance"]["purse"] -= total_cost
                    
                    if item["amount"] != -1:
                        item["amount"] -= quantity

                    save_file(eco_path, eco)
                    await interaction.followup.send(f"You bought {quantity}x {item_name} for {total_cost:,} coins.")
                    return

            await interaction.followup.send(f"Item {item_name} not found in the shop.", ephemeral=True)
        except Exception as e:
            handle_logs(interaction, e)

class AuctionGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="auction", description="Not coming soon.")

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        handle_eco_shop.start()
        bot.tree.add_command(MarketGroup())
        bot.tree.add_command(ShopGroup())
        bot.tree.add_command(AuctionGroup())

    def cog_unload(self):
        handle_eco_shop.cancel()

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = int(error.retry_after)
            retry_time = int((discord.utils.utcnow() + timedelta(seconds=retry_after)).timestamp())
            await interaction.response.send_message(f"Command on cooldown. Try again <t:{retry_time}:R>", ephemeral=True)
        else:
            await handle_logs(interaction, error)

    @app_commands.command(name="balance", description="Check a user's purse and bank balance!")
    @app_commands.describe(member="The user whose balance you want to check.")
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
                    await interaction.followup.send("The user does not have an account.")
                    return
                
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

            async def update_embed():
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
            async def withdraw_callback(self, interaction: discord.Interaction):
                if interaction.user.id != user.id:
                    return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                modal = Modal(title="Withdraw")
                amount_input = TextInput(label="Amount to withdraw")
                modal.add_item(amount_input)

                async def modal_callback(modal_interaction: discord.Interaction):
                    amount = int(amount_input.value)
                    success, transaction_result = await process_transaction(modal_interaction.user.id, "withdraw", amount)
                    if success:
                        eco[user_id]['balance']['purse'] += amount
                        eco[user_id]['balance']['bank'] -= amount
                        save_file(eco_path, eco)

                        updated_embed = await update_embed()
                        await interaction.message.edit(embed=updated_embed, view=view)
                    await modal_interaction.response.send_message(transaction_result, ephemeral=True)

                modal.on_submit = modal_callback
                await interaction.response.send_modal(modal)
            withdraw_button.callback = withdraw_callback
            view.add_item(withdraw_button)

            deposit_button = Button(label="Deposit", style=ButtonStyle.green)
            async def deposit_callback(self, interaction: discord.Interaction):
                if interaction.user.id != user.id:
                    return await interaction.response.send_message("You are not authorized to perform this action.", ephemeral=True)

                modal = Modal(title="Deposit")
                amount_input = TextInput(label="Amount to deposit")
                modal.add_item(amount_input)

                async def modal_callback(modal_interaction: discord.Interaction):
                    amount = int(amount_input.value)
                    success, transaction_result = await process_transaction(modal_interaction.user.id, "deposit", amount)
                    if success:
                        eco[user_id]['balance']['purse'] -= amount
                        eco[user_id]['balance']['bank'] += amount
                        save_file(eco_path, eco)

                        updated_embed = await update_embed()
                        await interaction.message.edit(embed=updated_embed, view=view)
                    await modal_interaction.response.send_message(transaction_result, ephemeral=True)

                modal.on_submit = modal_callback
                await interaction.response.send_modal(modal)
            deposit_button.callback = deposit_callback
            view.add_item(deposit_button)

            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="withdraw", description="Withdraw money from the bank.")
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

    @app_commands.command(name="deposit", description="Deposit money to the bank.")
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

    @app_commands.command(name="pay", description="Pay other user coins.")
    async def pay(self, interaction: discord.Interaction):
        pass

    # Basic ways to get money
    @app_commands.command(name="beg", description="Beg for money on the streets.")
    @app_commands.checks.cooldown(1, 30)
    async def beg(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            eco = open_file(eco_path)
            user_id = str(interaction.user.id)
            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)
            
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

            embed = discord.Embed(title="plzs moneys im pour", timestamp=datetime.now(timezone.utc))
            if r == 1:
                embed.color = discord.Color.red()
                embed.description = random.choice(t["n"])
                embed.footer = "begging is for losers!"
            else:
                eco[user_id]['balance']['purse'] += total_amount
                save_file(eco_path, eco)
                embed.color = discord.Color.green()
                embed.description = random.choice(t["y"])
                embed.footer = f"With a coin multiplier of {coin_boost}%"

                if base_amount == 143: # little reference :)
                    embed.footer = "i love you"

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="fish", description="Fish for some coins! Requires a fishing rod.")
    @app_commands.checks.cooldown(1, 30)
    async def fish(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            if 'fishing_rod' not in eco[user_id].get('inventory', {}):
                await interaction.followup.send("You need a fishing rod to fish! Buy one from the shop.")
                return

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('fishing_rod')
                break_msg = f"\nYour fishing rod broke! (Would have earned {total_amount} coins)"
            else:
                eco[user_id]['balance']['purse'] += total_amount
                break_msg = f"\nWith coin boost: {coin_boost}% (Base: {base_amount} → Total: {total_amount})"

            save_file(eco_path, eco)
            await interaction.followup.send(f"You went fishing!{break_msg}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="hunt", description="Hunt for some coins! Requires a rifle.")
    @app_commands.checks.cooldown(1, 30)
    async def hunt(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            if 'rifle' not in eco[user_id].get('inventory', {}):
                await interaction.followup.send("You need a rifle to hunt! Buy one from the shop.")
                return

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('rifle')
                break_msg = f"\nYour rifle broke! (Would have earned {total_amount} coins)"
            else:
                eco[user_id]['balance']['purse'] += total_amount
                break_msg = f"\nWith coin boost: {coin_boost}% (Base: {base_amount} → Total: {total_amount})"

            save_file(eco_path, eco)
            await interaction.followup.send(f"You went hunting!{break_msg}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dig", description="Dig for some coins! Requires a shovel.")
    @app_commands.checks.cooldown(1, 30)
    async def dig(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            if 'shovel' not in eco[user_id].get('inventory', {}):
                await interaction.followup.send("You need a shovel to dig! Buy one from the shop.")
                return

            base_amount = random.randint(500, 1200)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            if random.random() < 0.1:
                eco[user_id]['inventory'].pop('shovel')
                break_msg = f"\nYour shovel broke! (Would have earned {total_amount} coins)"
            else:
                eco[user_id]['balance']['purse'] += total_amount
                break_msg = f"\nWith coin boost: {coin_boost}% (Base: {base_amount} → Total: {total_amount})"

            save_file(eco_path, eco)
            await interaction.followup.send(f"You went digging!{break_msg}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="search", description="Search for some coins!")
    @app_commands.checks.cooldown(1, 30)
    async def search(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            base_amount = random.randint(80, 150)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            locations = {
                "success": [
                    f"You found {total_amount} coins in an old coat! (Base: {base_amount})",
                    f"You searched the couch cushions and found {total_amount} coins! (Base: {base_amount})",
                    f"Someone dropped {total_amount} coins on the street! (Base: {base_amount})",
                    f"You found {total_amount} coins in a vending machine return slot! (Base: {base_amount})"
                ],
                "fail": [
                    "You searched but found nothing...",
                    "Better luck next time!",
                    "Nothing here but dust.",
                    "Maybe try searching somewhere else?"
                ]
            }

            success = random.random() < 0.75
            if success:
                eco[user_id]['balance']['purse'] += total_amount
                message = f"{random.choice(locations['success'])}\nCoin boost: {coin_boost}%"
            else:
                message = random.choice(locations["fail"])

            save_file(eco_path, eco)
            await interaction.followup.send(message)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="crime", description="Commit a crime for coins!")
    @app_commands.checks.cooldown(1, 30)
    async def crime(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            base_amount = random.randint(80, 150)
            coin_boost = eco[user_id]['boosts']['coins']
            total_amount = int(base_amount * (coin_boost / 100))

            crimes = {
                "success": [
                    f"You successfully pickpocketed {total_amount} coins! (Base: {base_amount})",
                    f"You hacked an ATM and got {total_amount} coins! (Base: {base_amount})",
                    f"You robbed a store and got away with {total_amount} coins! (Base: {base_amount})",
                    f"Your heist was successful! You got {total_amount} coins! (Base: {base_amount})"
                ],
                "fail": [
                    "You got caught and had to run away!",
                    "The police were nearby, better luck next time!",
                    "Your target was too difficult to rob.",
                    "Someone saw you and you had to abort!"
                ]
            }

            success = random.random() < 0.6
            if success:
                eco[user_id]['balance']['purse'] += total_amount
                message = f"{random.choice(crimes['success'])}\nCoin boost: {coin_boost}%"
            else:
                message = random.choice(crimes["fail"])

            save_file(eco_path, eco)
            await interaction.followup.send(message)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="daily", description="Claim your daily reward!")
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
                await interaction.followup.send(f"You can claim your daily reward in {hours}h {minutes}m {seconds}s")
                return

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

    @app_commands.command(name="weekly", description="Claim your weekly reward!")
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
                await interaction.followup.send(f"You can claim your weekly reward in {days}d {hours}h")
                return

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

    @app_commands.command(name="monthly", description="Claim your monthly reward!")
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
                await interaction.followup.send(f"You can claim your monthly reward in {days}d {hours}h")
                return

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

    """
    GAME COMMANDS (PART OF ECO)
    """

    @app_commands.command(name="coinflip", description="50% chance to double or lose everything.")
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
            won = coin == guess

            if amount and not guess:
                await interaction.followup.send("You need to guess heads or tails to bet an amount!")
                return

            if amount and guess:
                try:
                    amount = convert_number(amount)
                except ValueError:
                    await interaction.followup.send("Invalid amount format. Use formats like 10k, 50m, etc.")
                    return

                user_id = str(interaction.user.id)
                eco = open_file(eco_path)

                if user_id not in eco:
                    create_account(user_id)

                eco = open_file(eco_path)
                player_data = eco[user_id]
                purse_balance = int(player_data["balance"]["purse"])

                if amount > purse_balance:
                    await interaction.followup.send("You don't have enough coins in your purse!")
                    return

                if won:
                    purse_balance += amount
                    message = f"The coin landed on {coin.upper()}! You won {amount} coins!"
                else:
                    purse_balance -= amount
                    message = f"The coin landed on {coin.lower()}... You lost {amount} coins."

                player_data["balance"]["purse"] = purse_balance
                save_file(eco_path, eco)

                await interaction.followup.send(message)
                return

            if guess:
                if won:
                    await interaction.followup.send(f"Congrats! The coin landed on {coin.upper()}!")
                else:
                    await interaction.followup.send(f"Bad luck! The coin landed on {coin.lower()}.")
                return

            await interaction.followup.send(f"The coin landed on {coin.lower()}!")

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="inventory", description="Check your inventory!")
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
                    await interaction.followup.send("This user doesn't have an account!")
                    return

            inventory = eco[user_id].get('inventory', {})
            
            if not inventory:
                await interaction.followup.send(f"{user.display_name}'s inventory is empty!")
                return

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
                    grouped_items[item_type].append(f"{item_name.title()}: {amount}x")

            for item_type, item_list in grouped_items.items():
                embed.add_field(
                    name=f"📦 {item_type.title()}",
                    value="\n".join(item_list) or "Empty",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
