from bot_utils import (
    open_file,
    save_file,
    convert_number,
    RestrictedView,
    create_account,
    check_user_stat,
    process_transaction,
    eco_path,
    create_interaction,
    error,
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
                "type": data.get("type", "No type")
            })
    
# Currency system
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Not coming soon.")
        self.command_help = open_file("storage/command_help.json").get("economy", {})
        
        for command in self.commands:
            if command.name in self.command_help:
                command.description = self.command_help[command.name]["description"]
                if "parameters" in self.command_help[command.name]:
                    for param_name, param_desc in self.command_help[command.name]["parameters"].items():
                        if param_name in command._params:
                            command._params[param_name].description = param_desc

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop commands.")
        self.command_help = open_file("storage/command_help.json").get("economy", {}).get("shop", {})
        
        for command in self.commands:
            if command.name in self.command_help.get("subcommands", {}):
                cmd_data = self.command_help["subcommands"][command.name]
                command.description = cmd_data["description"]
                if "parameters" in cmd_data:
                    for param_name, param_desc in cmd_data["parameters"].items():
                        if param_name in command._params:
                            command._params[param_name].description = param_desc

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
        self.command_help = open_file("storage/command_help.json").get("economy", {})
        handle_eco_shop.start()
        bot.tree.add_command(MarketGroup())
        bot.tree.add_command(ShopGroup())
        bot.tree.add_command(AuctionGroup())

        for command in self.__cog_app_commands__:
            if isinstance(command, app_commands.Command):
                command_data = self.command_help.get(command.name)
                if command_data:
                    command.description = command_data["description"]
                    if "parameters" in command_data:
                        for param_name, param_desc in command_data["parameters"].items():
                            if param_name in command._params:
                                command._params[param_name].description = param_desc

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
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
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

    @app_commands.command(name="fish", description="Fish for some coins! Requires a fishing rod.")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id)) 
    async def fish(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            has_rod = 'fishing_rod' in eco[user_id].get('inventory', {})
            
            if not has_rod:
                await interaction.followup.send("You need a fishing rod to fish! Buy one from the shop.")
                return

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

    @app_commands.command(name="hunt", description="Hunt for some coins! Requires a rifle.")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def hunt(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            has_rifle = 'rifle' in eco[user_id].get('inventory', {})
            
            if not has_rifle:
                await interaction.followup.send("You need a rifle to hunt! Buy one from the shop.")
                return

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

    @app_commands.command(name="dig", description="Dig for some coins! Requires a shovel.")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def dig(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = str(interaction.user.id)
            eco = open_file(eco_path)

            if user_id not in eco:
                create_account(user_id)
                eco = open_file(eco_path)

            has_shovel = 'shovel' in eco[user_id].get('inventory', {})
            
            if not has_shovel:
                await interaction.followup.send("You need a shovel to dig! Buy one from the shop.")
                return

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

    @app_commands.command(name="search", description="Search for some coins! Requires a shovel.")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
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

    @app_commands.command(name="crime", description="Commit a crime for coins! Requires a shovel.")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
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
        """Shop commands"""
        await ctx.send("Available commands: shop view, shop buy <item> [quantity]")

    @manual_shop.command(name="view")
    async def manual_shop_view(self, ctx):
        try:
            interaction = await create_interaction(ctx) 
            shop_cmd = self.bot.tree.get_command("shop")
            await shop_cmd.get_command("view").callback(self, interaction)
        except Exception as e:
            error(e)

    @manual_shop.command(name="buy")
    async def manual_shop_buy(self, ctx, item_name: str, quantity: int = 1):
        try:
            interaction = await create_interaction(ctx)
            
            if not SHOP:
                await handle_eco_shop()

            closest_item = find_closest_item(item_name, SHOP)
            if not closest_item:
                await ctx.send(f"No item found matching '{item_name}'")
                return

            shop_cmd = self.bot.tree.get_command("shop")
            await shop_cmd.get_command("buy").callback(self, interaction, closest_item, quantity)
            
        except Exception as e:
            error(e)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
