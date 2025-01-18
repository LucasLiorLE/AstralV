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
from datetime import datetime, timezone

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
                "description": appear_data.get("description", "No description yet...")
            })
    
class BlackjackView(View):
    def __init__(self, player, deck, player_hand, dealer_hand, bot, amount=0):
        super().__init__(timeout=30 if not bot else None)
        self.player = player
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.bot = bot
        self.result = None
        self.amount = amount

    def get_game_state(self):
        embed = discord.Embed(title="Blackjack Game")
        embed.add_field(name="Your Hand", value=f"{self.player_hand} (Total: {sum(self.player_hand)})")
        
        if self.result is None:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand[0]}, ?")
        else:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand} (Total: {sum(self.dealer_hand)})")
            embed.add_field(name="Result", value=self.result, inline=False)
        
        return embed

    @button(label="Hit", style=ButtonStyle.green)
    async def hit(self, interaction, button):
        if interaction.user != self.player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        self.player_hand.append(self.deck.pop())
        if sum(self.player_hand) > 21:
            self.result = "You busted! Dealer wins."
            update_stats(str(self.player.id), "blackjack", "loss", self.amount)
            await interaction.response.edit_message(embed=self.get_game_state(), view=None)
            self.stop()
            return

        await interaction.response.edit_message(embed=self.get_game_state())

    @button(label="Stand", style=ButtonStyle.red)
    async def stand(self, interaction, button):
        if interaction.user != self.player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        while sum(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

        dealer_total = sum(self.dealer_hand)
        player_total = sum(self.player_hand)

        if dealer_total > 21 or player_total > dealer_total:
            self.result = "You win!"
            update_stats(str(self.player.id), "blackjack", "win", self.amount)
        elif player_total < dealer_total:
            self.result = "Dealer wins!"
            update_stats(str(self.player.id), "blackjack", "loss", self.amount)
        else:
            self.result = "It's a tie!"
            update_stats(str(self.player.id), "blackjack", "draw")

        await interaction.response.edit_message(embed=self.get_game_state(), view=None)
        self.stop()

class ChallengeView(View):
    def __init__(self, challenger, opponent, amount):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.response = None

    @button(label="Accept", style=ButtonStyle.green)
    async def accept(self, interaction, button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("You are not the challenged user!", ephemeral=True)
            return

        self.response = True
        self.stop()

    @button(label="Decline", style=ButtonStyle.red)
    async def decline(self, interaction, button):
        if interaction.user != self.opponent:
            await interaction.response.send_message("You are not the challenged user!", ephemeral=True)
            return

        self.response = False
        self.stop()

    async def on_timeout(self):
        self.response = False

class BlackjackGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="blackjack", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a blackjack game")
    @app_commands.describe(amount="The amount you want to wager", member="User you want to wager against (Or bot if none)")
    async def bjwager(self, interaction: discord.Interaction, amount: int, member: discord.User = None):
        try:
            if member == interaction.user:
                await interaction.response.send_message("You can't go against yourself!", ephemeral=True)
                return
            if member is None:
                await self.start_game(interaction, amount, bot=True)
            else:
                await self.challenge_user(interaction, amount, member=member)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="casual", description="Play a casual game of blackjack")
    @app_commands.describe(member="The user you want to play against")
    async def bjcasual(self, interaction: discord.Interaction, member: discord.User = None):
        try:
            if member == interaction.user:
                await interaction.response.send_message("You can't go against yourself!!", ephemeral=True)
                return
            if member is None:
                await self.start_game(interaction, amount=0, bot=True)
            else:
                await self.challenge_user(interaction, amount=0, member=member)
        except Exception as e:
            await handle_logs(interaction, e)

    async def challenge_user(self, interaction, amount, user):
        view = ChallengeView(interaction.user, user, amount)
        await interaction.response.send_message(
            f"{user.mention}, you have been challenged by {interaction.user.mention} to a blackjack game! Do you accept?",
            view=view
        )
        await view.wait()
        if view.response is None:  
            await interaction.followup.send("The challenge timed out!", ephemeral=True)
        elif view.response:  
            await self.start_game(interaction, amount=amount, bot=False)
        else:  
            await interaction.followup.send(f"{user.mention} declined the challenge.", ephemeral=True)

    async def start_game(self, interaction, amount, bot):
        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(deck)

        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        view = BlackjackView(interaction.user, deck, player_hand, dealer_hand, bot, amount)
        await interaction.followup.send(
            embed=view.get_game_state(),
            view=view
        )
        
    @app_commands.command(name="stats", description="View a user's stats for blackjack")
    @app_commands.describe(user="The user you want to view the stats for.")
    async def bjstats(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        stats = gambling_stats(str(user.id), "blackjack")

        embed = discord.Embed(title=f"{user.name}'s Blackjack Stats")
        embed.add_field(name="Wins", value=stats["wins"])
        embed.add_field(name="Losses", value=stats["losses"])
        embed.add_field(name="Draws", value=stats["draws"])
        embed.add_field(name="Coins Won", value=stats["coinsWon"])
        embed.add_field(name="Coins Lost", value=stats["coinsLost"])

        await interaction.response.send_message(embed=embed)
        
class TicTacToeGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tictactoe", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a tic tac toe game")
    @app_commands.describe(amount="The amount you want to wager")
    async def tttwager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="casual", description="Play a casual gane of tic tac toe")
    async def tttcasual(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="stats", description="View a user's stats for tic tac toe")
    @app_commands.describe(user="The user you want to view the stats for.")
    async def tttstats(self, interaction: discord.Interaction, user: str = None):
        pass


class connect4Group(app_commands.Group):
    def __init__(self):
        super().__init__(name="connect4", description="Not coming soon")

    @app_commands.command(name="wager", description="Wager in a connect 4 game")
    @app_commands.describe(amount="The amount you want to wager")
    async def c4wager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="casual", description="Play a casual gane of connect 4")
    async def c4casual(self, interaction: discord.Interaction):
        pass

    @app_commands.command(name="stats", description="View a user's stats for connect 4")
    @app_commands.describe(user="The user you want to view the stats for.")

    async def c4stats(self, interaction: discord.Interaction, user: str = None):
        pass

class slotsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="slots", description="Not coming soon")

    @app_commands.command(name="wager", description="Gamble in slots")
    @app_commands.describe(amount="The amount you want to wager")
    async def slotwager(self, interaction: discord.Interaction, amount: int):
        pass

    @app_commands.command(name="stats", description="View a user's stats for slots")
    @app_commands.describe(user="The user you want to view the stats for.")
    async def slotstats(self, interaction: discord.Interaction, user: str = None):
        pass

# Currency system
class MarketGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="market", description="Not coming soon.")

class ShopGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="shop", description="Shop commands.")

    @app_commands.command(name="show", description="View the shop.")
    async def show(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()

            embed = discord.Embed(title="Shop Items", color=discord.Color.blue())
            for item in SHOP:
                amount = "Infinity" if item["amount"] == -1 else item["amount"]
                embed.add_field(
                    name=f"{item['item']}",
                    value=f"**Price**: {item['price']}\n**Amount Left**: {amount}\n**Description**: {item['description']}]n**Type**: {item['type']}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            handle_logs(interaction, e)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    async def buy(self, interaction: discord.Interaction, item_name: str, quantity: int):
        await interaction.response.defer()
        try:
            if not SHOP:
                await handle_eco_shop()
        
            for item in SHOP:
                if item["item"].lower() == item_name.lower():
                    if item["amount"] == -1 or item["amount"] >= quantity:
                        item["amount"] = item["amount"] - quantity if item["amount"] != -1 else -1
                        await interaction.followup.send(f"You bought {quantity}x {item_name} for {item['price'] * quantity} coins.")
                        return
                    else:
                        await interaction.followup.send(f"Not enough {item_name} in stock.", ephemeral=True)
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

        bot.tree.add_command(BlackjackGroup())
        bot.tree.add_command(TicTacToeGroup())
        bot.tree.add_command(connect4Group())
        bot.tree.add_command(slotsGroup())

        bot.tree.add_command(MarketGroup())
        bot.tree.add_command(ShopGroup())
        bot.tree.add_command(AuctionGroup())


    @app_commands.command(name="balance", description="Check a user's purse and bank balance!")
    @app_commands.describe(member="The user whose balance you want to check.")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            user = user or interaction.user
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
    async def beg(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            eco = open_file(eco_path)
            user_id = str(interaction.user.id)
            if user_id not in eco:
                create_account(user_id)
            eco = open_file(eco_path)
            
            purse = eco[user_id]['balance']['purse']
            coin_boost = eco[user_id]['boosts']['coins']
            amount = int(random.randint(80, 150) * (coin_boost / 100))
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
                    f"Sure hon, here have {amount} coins.", 
                    f"God felt bad so he gave you {amount} coins...",
                    f"a dog took pity on you and gave you {amount} coins.",
                    f"Spend {amount} coins well...",
                    f"{amount} coins appeared out of thin air!",
                    f"you got some coins but im evil so i won't tell you how much",
                    f"the criminals felt so bad they gave you {amount} coins",
                    f"You got paied {amount} coins to stop begging"
                ]
            }

            embed = discord.Embed(title="plzs moneys im pour", timestamp=datetime.now(timezone.utc))
            if r == 1:
                embed.color = discord.Color.red()
                embed.description = random.choice(t["n"])
                embed.footer = "begging is for losers!"
            else:
                purse += amount
                save_file(eco_path, eco)
                embed.color = discord.Color.green()
                embed.description = random.choice(t["y"])
                embed.footer = f"With a coin multiplier of {coin_boost}%"

                if amount == 143: # little reference :)
                    embed.footer = "i love you"

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)



    @app_commands.command(name="fish", description="Not coming soon.")
    async def fish(self, interaction: discord.Interaction):
        pass
    @app_commands.command(name="hunt", description="Not coming soon.")
    async def hunt(self, interaction: discord.Interaction):
        pass
    @app_commands.command(name="dig", description="Not coming soon.")
    async def dig(self, interaction: discord.Interaction):
        pass
    @app_commands.command(name="search", description="Not coming soon.")
    async def search(self, interaction: discord.Interaction):
        pass
    @app_commands.command(name="crime", description="Not coming soon.")
    async def crime(self, interaction: discord.Interaction):
        pass

    # Other ways to get money
    @app_commands.command(name="daily", description="Not coming soon.")
    async def daily(self, interaction: discord.Interaction):
        pass
    '''
        await interaction.response.defer()
        try:
            eco = open_file(eco_path)
            user_id = str(interaction.user.id)
            if user_id not in eco:
                create_account(user_id)
            eco = open_file(eco_path)

            purse = eco[user_id]['balance']['purse']
            coin_boost = eco[user_id]['boosts']['coins']
            streak = eco[user_id]['streaks']['daily']
    '''


            
    @app_commands.command(name="weekly", description="Not coming soon.")
    async def weekly(self, interaction: discord.Interaction):
        pass
    @app_commands.command(name="monthly", description="Not coming soon.")
    async def monthly(self, interaction: discord.Interaction):
        pass

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

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
