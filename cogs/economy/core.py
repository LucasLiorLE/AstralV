import random
import discord
from discord import app_commands
from discord.ext import commands
from bot_utils import (
    send_cooldown,
    open_json,
    save_json,
    handle_logs
)
from .utils import (
    check_user_stat,
    command_cooldown,
    get_item_name,
    process_transaction
)

class MainEconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.eco_path = "storage/economy/economy.json"
        self.places = {
            "Couch": {
                "Success": ["You found {} coins in the couch.", "{} spare coins was under the couch", "You found {} coins between the cushions"],
                "Fail": ["Damn you're more poor than I thought.", "You found nothing"],
                "Death": ["How did you even die this time", "The couch... killed you?"],
                "Items": ["Candy"],
                "Risk": 5
            },  
            "Tree": {
                "Success": ["You found {} coins on the tree!", "{} coins hidden in an acorn...", "There was {} coins lying at the tree!"],
                "Fail": ["The squirrels started throwing acorns at you", "Nice! You found nothing!", "You fell off the tree"],
                "Death": ["You fell off the tree... and died"],
                "Items": ["Stick"],
                "Risk": 5
            },
            "Jacket": {
                "Success": ["You found {} coins in your jacket!", "There was {} coins and some candy wrappers in a jacket...", "Who knew goodwill jackets would have {} coins"],
                "Fail": ["At least there was some candy...", "Only candy wrappers lol", "One singular paper clip."],
                "Death": ["Next time you search something, try not to be next to the owner, especially a gang boss."],
                "Items": ["Candy"],
                "Risk": 5
            },
            "Pocket": {
                "Success": ["You found {} coins in your pocket!", "There was {} coins and some candy wrappers in a pocket..."],
                "Fail": ["At least there was some candy...", "The person you were searching looked at your weird.", "One singular paper clip."],
                "Death": ["Next time you search something, try not to be next to the owner, especially a gang boss."],
                "Items": ["Candy"],
                "Risk": 5
            },
            "Air": {
                "Success": ["You grabbed {} coins out of the air!", "{} coins pop out of thin air."],
                "Fail": ["\"Mommy, why is that man grabbing the air?\"", "Nothing happens", "What did you expect"],
                "Death": ["You suffocated... in the air...", "You forgot to breathe"],
                "Item": [],
                "Risk": 10
            },
            "Car": {
                "Success": ["You found {} coins in a car", ""],
                "Fail": ["The car was locked lol", "The alarm started sounding", "Robbing your uber driver is wild"],
                "Death": ["Turns out the car you were robbing was a stunt car..."],
                "Items": ["Bank Note", "Candy", "String"],
                "Risk": 10
            }
        }
        self.crimes = {}


    def on_death(self, id: str) -> bool:
        check_user_stat(["balance", "purse"], id, 0)
        lifesavers = check_user_stat(["inventory", "lifesaver"], id, 0)
        eco = open_json(self.eco_path)
        if lifesavers <= 0:
            eco[id]["balance"]["purse"] //= 2
        else:
            eco[id]["inventory"]["lifesaver"] -= 1
            return True
        
        save_json(self.eco_path, eco)
        return False

    def add_money(self, id: str, amount: int):
        check_user_stat(["balance", "purse"], id, 0)
        coin_multi = check_user_stat(["boosts", "coin"], id, 100)
        eco = open_json(self.eco_path)
        eco[id]["balance"]["purse"] += amount * coin_multi
        save_json(self.eco_path, eco)
        return amount, coin_multi

    @commands.hybrid_command(name="beg")
    async def beg(self, ctx: commands.Context):
        try:
            user_id = str(ctx.author.id)
            cooldown_result = command_cooldown(30, "beg", user_id)
            if isinstance(cooldown_result, tuple):
                done, cooldown = cooldown_result
                if not done:
                    return await send_cooldown(ctx, cooldown)
            else:
                return await ctx.send("Error checking cooldown", ephemeral=True)

            embed = discord.Embed(
                title=random.choice(["pls munee", "im por", "pls beg", "begging"])
            )

            roll = random.randint(1, 20)
            if roll == 20:
                death = self.on_death(user_id)
                embed.description = random.choice([
                    "wow no pity...", "you starved to death.", "🥶🥶🥶"
                ])
                embed.footer = "Your lifesaver saved you" if death else None
                embed.color = discord.Color.yellow() if death else discord.Color.red()
            elif roll > 16:
                embed.description = random.choice([
                    "imagine begging", "lol no", f"you rolled a {roll}! (no coins lmao)",
                    "\"sorry I\'m selfish\"", "what are you looking at me for??", "people stay clear of your aura",
                    "i have bills to pay", "... ... ... ...", "everyone ignores you" 
                ])
                embed.color = discord.Color.red()
            else:
                amount, coin_multi = self.add_money(user_id, random.randint(80, 400))
                coins = amount * coin_multi
                embed.description = random.choice([
                    f"A grandma hands you {coins} coins", f"You found {coins} coins on the sidewalk", f"{coins} coins fall out of the sky",
                    f"a random stranger gave you {coins} coins", f"A cat hands you {coins} coins.", f"Felt nice. Have {coins} coins.",
                    f"your cup gained {coins} coins", f"God gives you {coins} coins", f"people hand you {coins} coins to make you go away"
                ])
                embed.color = discord.Color.green()

            await ctx.send(embed=embed)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="search")
    async def search(self, ctx: commands.Context):
        try:
            user_id = str(ctx.author.id)
            cooldown_result = command_cooldown(45, "search", user_id)
            if isinstance(cooldown_result, tuple):
                done, cooldown = cooldown_result
                if not done:
                    return await send_cooldown(ctx, cooldown)
            else:
                return await ctx.send("Error checking cooldown", ephemeral=True)

            embed = discord.Embed(
                title="Where would you like to search?",
                description="Please choose a location.",
                color=discord.Color.yellow()
            )
            
            buttons = random.sample(list(self.places.keys()), k=3)
            
            class SearchButtons(discord.ui.View):
                def __init__(self, bot_self):
                    super().__init__(timeout=30)
                    self.bot_self = bot_self
                    
                    for location in buttons:
                        button = discord.ui.Button(
                            label=f"{location}",
                            custom_id=location,
                            style=discord.ButtonStyle.primary
                        )
                        button.callback = self.button_callback
                        self.add_item(button)
                
                async def interaction_check(self, button_interaction: discord.Interaction) -> bool:
                    return button_interaction.user.id == ctx.author.id

                async def button_callback(self, button_interaction: discord.Interaction):
                    location = button_interaction.data["custom_id"]
                    location_data = self.bot_self.places[location]
                    risk = location_data["Risk"]
                    
                    if random.randint(1, 100) <= risk:
                        death = self.bot_self.on_death(user_id)
                        embed = discord.Embed(
                            title=f"Searching {location}...",
                            description=random.choice(location_data["Death"]),
                            color=discord.Color.yellow() if death else discord.Color.red()
                        )
                        if death:
                            embed.set_footer(text="Your lifesaver saved you!")
                        
                    else:
                        success = random.choice([True, False])
                        if success:
                            base_amount = random.randint(100, 500)
                            risk_bonus = risk * 2
                            bonus_multiplier = 1 + (risk_bonus / 100)
                            
                            amount, coin_multi = self.bot_self.add_money(
                                user_id, 
                                int(base_amount * bonus_multiplier)
                            )
                            coins = amount * coin_multi
                            
                            embed = discord.Embed(
                                title=f"Searching {location}...",
                                description=random.choice(location_data["Success"]).format(coins),
                                color=discord.Color.green()
                            )
                            
                            if location_data["Items"] and random.randint(1, 100) <= risk:
                                item = random.choice(location_data["Items"])
                                item = get_item_name(item)
                                check_user_stat(["inventory", item], user_id, 0)
                                eco = open_json(self.bot_self.eco_path)
                                eco[user_id]["inventory"][item] += 1
                                save_json(self.bot_self.eco_path, eco)
                                
                                embed.add_field(
                                    name="Bonus!", 
                                    value=f"You also found a {item}!\n(Found due to {risk}% risk)"
                                )
                        else:
                            embed = discord.Embed(
                                title=f"Searching {location}...",
                                description=random.choice(location_data["Fail"]),
                                color=discord.Color.red()
                            )
                    
                    for child in self.children:
                        child.disabled = True
                    await button_interaction.response.edit_message(embed=embed, view=self)

            view = SearchButtons(self)
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="crime")
    async def crime(self, ctx: commands.Context): ...

    @commands.hybrid_command(name="hunt")
    async def hunt(self, ctx: commands.Context):
        try:
            user_id = str(ctx.author.id)
            check_user_stat(["inventory", "rifle"], user_id, 0)
            eco = open_json("storage/economy/economy.json")
            if eco[user_id]["inventory"]["rifle"] < 1:
                return await ctx.send("You need a rifle to hunt!", ephemeral=True)

            weights = {
                "rabbit": 25, "mole": 23, "deer": 20,
                "fox": 15, "skunk": 12, "boar": 10, 
                "wolf": 8, "bear": 5, "lion": 3, 
                "dragon": 1
            }

            choice = random.sample(list(weights.keys()), counts=list(weights.values()), k=1)
            roll = random.randint(0, 100)
            if roll < 59:
                coins = random.randint(300, 800) * (1 - (weights[choice[0]] / 100))
                self.add_money(user_id, coins)

                embed = discord.Embed(
                    title="Hunting...",
                    description=f"You hunted a {choice[0]} and got {coins} coins!",
                    color=discord.Color.green()
                )
            elif roll < 71:
                embed = discord.Embed(
                    title="Not hunting...",
                    description=(
                        f"The {choice[0]} you found heard you and ran away." if roll > 65 else
                        f"you ran out of the forest when you heard something"
                    ),
                    color=discord.Color.red()
                )
            elif roll < 81: 
                embed = discord.Embed(
                    title="Hunted...",
                    description=(
                        f"You found out you were not alone in the forest the hard way." if roll > 88 else
                        f"damn I cant even back you out of this one..." if roll > 85 else 
                        f"turns out thats where the wolves live."
                    ),
                    color=discord.Color.red()
                )
                death = self.bot_self.on_death(user_id)
                if death:
                    embed.set_footer(text="Your lifesaver saved you!") 
            else:
                embed = discord.Embed(
                    title="Can't hunt...",
                    description=(
                        f"You tripped over a twig and broke your gun." if roll > 98 else
                        f"your gun jammed lol" if roll > 95 else 
                        f"you barely escape with your life sacrificing your rifle."
                    ),
                    color=discord.Color.red()
                )

                eco[user_id]["inventory"]["rifle"] -= 1
                save_json(self.eco_path, eco)

            await ctx.send(embed=embed)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="dig")
    async def dig(self, ctx: commands.Context):
        try:
            user_id = str(ctx.author.id)
            check_user_stat(["inventory", "shovel"], user_id, 0)
            eco = open_json("storage/economy/economy.json")
            if eco[user_id]["inventory"]["shovel"] < 1:
                return await ctx.send("You need a shovel to hunt!", ephemeral=True)

            weights = {
                "rabbit": 25, "mole": 23, "deer": 20,
                "fox": 15, "skunk": 12, "boar": 10, 
                "wolf": 8, "bear": 5, "lion": 3, 
                "dragon": 1
            }

            choice = random.sample(list(weights.keys()), counts=list(weights.values()), k=1)
            coins = random.randint(300, 800) * (1 - (weights[choice[0]] / 100))
            self.add_money(user_id, coins)

            embed = discord.Embed(
                title="Digging...",
                description=f"You hunted a {choice[0]} and got {coins} coins!",
                color=discord.Color.green()
            )

            await ctx.send(embed=embed)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="deposit")
    async def deposit(self, ctx: commands.Context, amount: int):
        try:
            user_id = str(ctx.author.id)
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["balance", "bank"], user_id, 5000)
            check_user_stat(["balance", "maxBank"], user_id, 25000)
            
            if amount <= 0:
                return await ctx.send("Please enter a positive amount.", ephemeral=True)
            
            success, message = await process_transaction(user_id, "deposit", amount)
            
            if success:
                eco = open_json("storage/economy/economy.json")
                new_purse = eco[user_id]["balance"]["purse"]
                new_bank = eco[user_id]["balance"]["bank"]
                max_bank = eco[user_id]["balance"]["maxBank"]
                
                embed = discord.Embed(
                    title="Deposit Successful!",
                    description=message,
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Updated Balance",
                    value=f"👛 Purse: {new_purse:,} coins\n🏦 Bank: {new_bank:,} / {max_bank:,} coins",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="Deposit Failed!",
                    description=message,
                    color=discord.Color.red()
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="withdraw")
    async def withdraw(self, ctx: commands.Context, amount: int):
        try:
            user_id = str(ctx.author.id)
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["balance", "bank"], user_id, 0)
            
            if amount <= 0:
                return await ctx.send("Please enter a positive amount.", ephemeral=True)
            
            success, message = await process_transaction(user_id, "withdraw", amount)
            
            if success:
                eco = open_json("storage/economy/economy.json")
                new_purse = eco[user_id]["balance"]["purse"]
                new_bank = eco[user_id]["balance"]["bank"]
                max_bank = eco[user_id]["balance"]["maxBank"]
                
                embed = discord.Embed(
                    title="Withdrawal Successful!",
                    description=message,
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Updated Balance",
                    value=f"👛 Purse: {new_purse:,} coins\n🏦 Bank: {new_bank:,} / {max_bank:,} coins",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="Withdrawal Failed!",
                    description=message,
                    color=discord.Color.red()
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="balance")
    async def balance(self, ctx: commands.Context):
        try:
            user_id = str(ctx.author.id)
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["balance", "bank"], user_id, 0)
            check_user_stat(["balance", "maxBank"], user_id, 25000)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            async def create_balance_embed():
                eco = open_json(self.eco_path)
                purse = eco[user_id]["balance"]["purse"]
                bank = eco[user_id]["balance"]["bank"]
                max_bank = eco[user_id]["balance"]["maxBank"]
                fish_tokens = eco[user_id]["balance"]["fish_tokens"]
                
                embed = discord.Embed(
                    title=f"{ctx.author.name}'s Balance",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="👛 Purse",
                    value=f"{purse:,} coins",
                    inline=False
                )
                embed.add_field(
                    name="🏦 Bank",
                    value=f"{bank:,} / {max_bank:,} coins",
                    inline=False
                )
                embed.add_field(
                    name="🎣 Fish Tokens",
                    value=f"{fish_tokens:,} tokens",
                    inline=False
                )
                return embed, purse, bank, max_bank

            class BalanceView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=None)

                @discord.ui.button(label="Deposit", style=discord.ButtonStyle.green)
                async def deposit(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    _, purse, bank, max_bank = await create_balance_embed()
                    
                    if purse <= 0:
                        await button_interaction.response.send_message("You don't have any coins to deposit!", ephemeral=True)
                        return
                        
                    space_left = max_bank - bank
                    if space_left <= 0:
                        await button_interaction.response.send_message("Your bank is full!", ephemeral=True)
                        return
                        
                    class DepositModal(discord.ui.Modal):
                        def __init__(self):
                            super().__init__(title="Deposit Coins")
                            self.amount = discord.ui.TextInput(
                                label=f"Amount to deposit (Max: {min(purse, space_left):,})",
                                placeholder=f"Enter a number between 1 and {min(purse, space_left):,}",
                                min_length=1,
                                max_length=len(str(min(purse, space_left))),
                                required=True
                            )
                            self.add_item(self.amount)

                        async def on_submit(self, modal_interaction: discord.Interaction):
                            try:
                                amount = int(self.amount.value)
                                if amount < 1 or amount > min(purse, space_left):
                                    await modal_interaction.response.send_message(
                                        f"Please enter a valid amount between 1 and {min(purse, space_left):,}.",
                                        ephemeral=True
                                    )
                                    return

                                success, message = await process_transaction(user_id, "deposit", amount)
                                
                                if success:
                                    new_embed, _, _, _ = await create_balance_embed()
                                    await button_interaction.message.edit(embed=new_embed)
                                    
                                    await modal_interaction.response.send_message(
                                        f"Successfully deposited {amount:,} coins!", 
                                        ephemeral=True
                                    )
                                else:
                                    await modal_interaction.response.send_message(
                                        f"Failed to deposit: {message}",
                                        ephemeral=True
                                    )
                            except ValueError:
                                await modal_interaction.response.send_message(
                                    "Please enter a valid number.",
                                    ephemeral=True
                                )
                            except Exception as e:
                                await modal_interaction.response.send_message(
                                    "An error occurred while processing your deposit.",
                                    ephemeral=True
                                )

                    modal = DepositModal()
                    await button_interaction.response.send_modal(modal)

                @discord.ui.button(label="Withdraw", style=discord.ButtonStyle.red)
                async def withdraw(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    _, _, bank, _ = await create_balance_embed()
                    
                    if bank <= 0:
                        await button_interaction.response.send_message("You don't have any coins to withdraw!", ephemeral=True)
                        return
                        
                    class WithdrawModal(discord.ui.Modal):
                        def __init__(self):
                            super().__init__(title="Withdraw Coins")
                            self.amount = discord.ui.TextInput(
                                label=f"Amount to withdraw (Max: {bank:,})",
                                placeholder=f"Enter a number between 1 and {bank:,}",
                                min_length=1,
                                max_length=len(str(bank)),
                                required=True
                            )
                            self.add_item(self.amount)

                        async def on_submit(self, modal_interaction: discord.Interaction):
                            try:
                                amount = int(self.amount.value)
                                if amount < 1 or amount > bank:
                                    await modal_interaction.response.send_message(
                                        f"Please enter a valid amount between 1 and {bank:,}.",
                                        ephemeral=True
                                    )
                                    return

                                success, message = await process_transaction(user_id, "withdraw", amount)
                                
                                if success:
                                    new_embed, _, _, _ = await create_balance_embed()
                                    await button_interaction.message.edit(embed=new_embed)
                                    
                                    await modal_interaction.response.send_message(
                                        f"Successfully withdrew {amount:,} coins!", 
                                        ephemeral=True
                                    )
                                else:
                                    await modal_interaction.response.send_message(
                                        f"Failed to withdraw: {message}",
                                        ephemeral=True
                                    )
                            except ValueError:
                                await modal_interaction.response.send_message(
                                    "Please enter a valid number.",
                                    ephemeral=True
                                )
                            except Exception as e:
                                await modal_interaction.response.send_message(
                                    "An error occurred while processing your withdrawal.",
                                    ephemeral=True
                                )

                    modal = WithdrawModal()
                    await button_interaction.response.send_modal(modal)

            initial_embed, _, _, _ = await create_balance_embed()
            view = BalanceView()
            await ctx.send(embed=initial_embed, view=view)

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(MainEconomyCog(bot))