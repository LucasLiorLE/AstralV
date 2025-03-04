import discord
from discord import app_commands
from discord.ext import commands
import random
import time
import asyncio
from bot_utils import (
    send_cooldown,
    open_json, 
    save_json
)
from .utils import (
    display_item_name,
    check_user_stat,
    command_cooldown,
    display_item_name
)

class FishingCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="fish", description="Economy fishing commands")
        self.eco_path = "storage/economy/economy.json"
        self.fish_path = "storage/economy/fish.json"
        self.items_path = "storage/economy/items.json"
        self.user_cooldowns = {}

    def calculate_required_exp(self, level):
        return (level + 1) * 5

    def check_level_up(self, user_id, eco):
        check_user_stat(["fishing", "exp"], user_id, 0)
        check_user_stat(["fishing", "level"], user_id, 0)
        
        current_level = eco[user_id]["fishing"]["level"]
        current_exp = eco[user_id]["fishing"]["exp"]
        required_exp = self.calculate_required_exp(current_level)
        
        if current_exp >= required_exp:
            eco[user_id]["fishing"]["level"] += 1
            eco[user_id]["fishing"]["exp"] = 0
            return True
        return False

    def get_current_rod(self, user_id, eco):
        check_user_stat(["fishing", "rod"], user_id, None)
        return eco[user_id]["fishing"]["rod"]

    def get_current_boat(self, user_id, eco):
        check_user_stat(["fishing", "boat"], user_id, None)
        return eco[user_id]["fishing"]["boat"]

    def get_rod_level(self, rod_name, fish_data):
        if not rod_name or rod_name not in fish_data["rods"]:
            return 0
        return fish_data["rods"][rod_name]["rod_level"]

    def get_boat_level(self, boat_name, fish_data):
        if not boat_name or boat_name not in fish_data["boats"]:
            return 0
        return fish_data["boats"][boat_name]["boat_level"]

    def get_fish_price(self, fish_name, items_data):
        if fish_name in items_data and "price" in items_data[fish_name]:
            return items_data[fish_name]["price"]["amount"]
        return 0

    async def show_profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        check_user_stat(["fishing", "level"], user_id, 0)
        check_user_stat(["fishing", "exp"], user_id, 0)
        check_user_stat(["fishing", "rod"], user_id, None)
        check_user_stat(["fishing", "boat"], user_id, None)
        check_user_stat(["balance", "fish_tokens"], user_id, 0)
        
        eco = open_json(self.eco_path)
        fish_data = open_json(self.fish_path)
        items_data = open_json(self.items_path)
        
        fishing_level = eco[user_id]["fishing"]["level"]
        exp = eco[user_id]["fishing"]["exp"]
        required_exp = self.calculate_required_exp(fishing_level)
        fish_tokens = eco[user_id]["balance"]["fish_tokens"]
        current_rod = self.get_current_rod(user_id, eco)
        current_boat = self.get_current_boat(user_id, eco)
        current_rod_level = self.get_rod_level(current_rod, fish_data)
        current_boat_level = self.get_boat_level(current_boat, fish_data)
        
        total_fish = 0
        rarest_fish = None
        highest_value = 0
        for fish_name, count in eco[user_id]["inventory"].items():
            if fish_name in fish_data["fish"]:
                total_fish += count
                fish_price = self.get_fish_price(fish_name, items_data)
                if fish_price > highest_value:
                    highest_value = fish_price
                    rarest_fish = fish_name
        
        embed = discord.Embed(
            title=f"🎣 {interaction.user.name}'s Fishing Profile",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Stats",
            value=f"Level: {fishing_level}\nEXP: {exp}/{required_exp}\nFish Tokens: {fish_tokens:,}",
            inline=False
        )
        
        equipment = []
        equipment.append(f"Rod: {display_item_name(current_rod) if current_rod else 'None'} (Level {current_rod_level})")
        equipment.append(f"Boat: {display_item_name(current_boat) if current_boat else 'None'} (Level {current_boat_level})")
        
        embed.add_field(
            name="⚔️ Equipment",
            value="\n".join(equipment),
            inline=False
        )
        
        achievements = []
        achievements.append(f"Total Fish Caught: {total_fish:,}")
        if rarest_fish:
            achievements.append(f"Rarest Fish: {display_item_name(rarest_fish)}")
        
        embed.add_field(
            name="🏆 Achievements",
            value="\n".join(achievements),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, view=self.AllView("profile", self))

    class AllView(discord.ui.View):
        def __init__(self, page, bot_self):
            super().__init__(timeout=None)
            self.page = page
            self.bot_self = bot_self

        @discord.ui.button(label="Catch", style=discord.ButtonStyle.primary)
        async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                import traceback
                user_id = str(interaction.user.id)
                cooldown_result = command_cooldown(30, "beg", user_id)
                
                if isinstance(cooldown_result, tuple):
                    done, cooldown = cooldown_result
                    if not done:
                        return await send_cooldown(interaction, cooldown)
                
                check_user_stat(["fishing", "level"], user_id, 0)
                check_user_stat(["fishing", "exp"], user_id, 0)
                check_user_stat(["fishing", "rod"], user_id, None)
                check_user_stat(["fishing", "boat"], user_id, None)
                check_user_stat(["balance", "fish_tokens"], user_id, 0)
                
                eco = open_json(self.bot_self.eco_path)
                fish_data = open_json(self.bot_self.fish_path)
                
                current_rod = self.bot_self.get_current_rod(user_id, eco)
                current_boat = self.bot_self.get_current_boat(user_id, eco)
                
                if not current_rod and not current_boat:
                    embed = discord.Embed(
                        title="No Fishing Equipment!",
                        description="You need a fishing rod and boat to fish! Buy one from the shop.",
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                fishing_level = eco[user_id]["fishing"]["level"]
                rod_level = self.bot_self.get_rod_level(current_rod, fish_data) if current_rod else 0
                boat_level = self.bot_self.get_boat_level(current_boat, fish_data) if current_boat else 0

                eco[user_id]["fishing"]["exp"] += 1
                leveled_up = self.bot_self.check_level_up(user_id, eco)

                available_fish = []
                for fish_name, fish_info in fish_data["fish"].items():
                    if (fish_info["rod_level"] <= rod_level and fish_info["boat_level"] <= boat_level):
                        weight = fish_info.get("weight", 1000000000)
                        available_fish.append((fish_name, weight))

                if not available_fish:
                    embed = discord.Embed(
                        title="No Fish Available!",
                        description="You can't catch any fish with your current equipment.",
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                success_rate = min(80 + (fishing_level / 2), 95)
                
                caught_fish = []
                total_tokens = 0
                attempts = random.randint(1, 50)
                
                eco = open_json(self.bot_self.eco_path)
                
                for fish_name in fish_data["fish"].keys():
                    check_user_stat(["inventory", fish_name], user_id, 0)
                save_json(self.bot_self.eco_path, eco)
                
                eco = open_json(self.bot_self.eco_path)
                for attempt in range(attempts):
                    if random.random() * 100 <= success_rate:
                        fish_names = [f[0] for f in available_fish]
                        weights = [f[1] for f in available_fish]
                        try:
                            fish_name = random.choices(fish_names, weights=weights, k=1)[0]
                            caught_fish.append(fish_name)
                            
                            check_user_stat(["inventory", fish_name], user_id, 0)
                            eco[user_id]["inventory"][fish_name] += 1
                            total_tokens += 1
                        except Exception as e:
                            print(traceback.format_exc())
                            raise

                eco[user_id]["balance"]["fish_tokens"] += total_tokens
                save_json(self.bot_self.eco_path, eco)

                if caught_fish:
                    fish_counts = {}
                    for fish in caught_fish:
                        fish_counts[fish] = fish_counts.get(fish, 0) + 1

                    description = "You caught:\n" + "\n".join(f"{count}x {display_item_name(fish)}" for fish, count in fish_counts.items())
                    description += f"\n\nGained {total_tokens} fish tokens!"
                    if leveled_up:
                        description += f"\n🎉 Level Up! You are now level {eco[user_id]['fishing']['level']}!"
                    
                    embed = discord.Embed(
                        title="🎣 Fishing Success!",
                        description=description,
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="Stats",
                        value=f"Level: {fishing_level}\nEXP: {eco[user_id]['fishing']['exp']}/{self.bot_self.calculate_required_exp(fishing_level)}"
                    )

                    await interaction.response.send_message(embed=embed, view=self.bot_self.AllView("catch", self.bot_self))
                else:
                    embed = discord.Embed(
                        title="Got away!",
                        description="All the fish got away...",
                        color=discord.Color.red()
                    )
                    if leveled_up:
                        embed.description += f"\n🎉 But you leveled up! You are now level {eco[user_id]['fishing']['level']}!"

                    await interaction.response.send_message(embed=embed, view=self.bot_self.AllView("catch", self.bot_self))
            except Exception as e:
                print(traceback.format_exc())
                await interaction.response.send_message("An error occurred while processing your catch. Please try again.", ephemeral=True)

        @discord.ui.button(label="Upgrade", style=discord.ButtonStyle.success)
        async def upgrade_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            check_user_stat(["fishing", "level"], user_id, 0)
            check_user_stat(["fishing", "rod"], user_id, None)
            check_user_stat(["fishing", "boat"], user_id, None)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.bot_self.eco_path)
            fish_data = open_json(self.bot_self.fish_path)
            
            fishing_level = eco[user_id]["fishing"]["level"]
            fish_tokens = eco[user_id]["balance"]["fish_tokens"]
            current_rod = self.bot_self.get_current_rod(user_id, eco)
            current_boat = self.bot_self.get_current_boat(user_id, eco)
            current_rod_level = self.bot_self.get_rod_level(current_rod, fish_data)
            current_boat_level = self.bot_self.get_boat_level(current_boat, fish_data)
            
            embed = discord.Embed(
                title="🎣 Fishing Upgrades",
                description="Choose what to upgrade:",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Your Stats",
                value=f"Level: {fishing_level}\nFish Tokens: {fish_tokens:,}\nCurrent Rod: {display_item_name(current_rod) if current_rod else 'None'}\nCurrent Boat: {display_item_name(current_boat) if current_boat else 'None'}",
                inline=False
            )

            next_rod = None
            for rod_name, rod_data in fish_data["rods"].items():
                rod_level = rod_data["rod_level"]
                if rod_level == current_rod_level + 1:
                    next_rod = (rod_name, rod_data)
                    break

            next_boat = None
            for boat_name, boat_data in fish_data["boats"].items():
                boat_level = boat_data["boat_level"]
                if boat_level == current_boat_level + 1:
                    next_boat = (boat_name, boat_data)
                    break

            if next_rod:
                rod_name, rod_data = next_rod
                req_level = rod_data["fishing_level"]
                req_amount = rod_data["price"].get("coins", 0)
                req_tokens = rod_data["price"].get("fish_tokens", 0)
                
                check_user_stat(["balance", "purse"], user_id, 0)
                user_coins = eco[user_id]["balance"]["purse"]
                
                status = "<:check:1292269189536682004>" if (fishing_level >= req_level and 
                                                           user_coins >= req_amount and 
                                                           fish_tokens >= req_tokens) else "❌"
                requirements = []
                if req_amount > 0:
                    requirements.append(f"{req_amount:,} coins")
                if req_tokens > 0:
                    requirements.append(f"{req_tokens:,} fish tokens")
                
                embed.add_field(
                    name="Next Rod",
                    value=f"{status} {display_item_name(rod_name)}\n└ Required: Level {req_level}, {' and '.join(requirements)}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Next Rod",
                    value="You have the best rod!",
                    inline=False
                )

            if next_boat:
                boat_name, boat_data = next_boat
                req_level = boat_data["fishing_level"]
                req_amount = boat_data["price"].get("coins", 0)
                req_tokens = boat_data["price"].get("fish_tokens", 0)
                
                check_user_stat(["balance", "purse"], user_id, 0)
                user_coins = eco[user_id]["balance"]["purse"]
                
                status = "<:check:1292269189536682004>" if (fishing_level >= req_level and 
                                                           user_coins >= req_amount and 
                                                           fish_tokens >= req_tokens) else "❌"
                requirements = []
                if req_amount > 0:
                    requirements.append(f"{req_amount:,} coins")
                if req_tokens > 0:
                    requirements.append(f"{req_tokens:,} fish tokens")

                embed.add_field(
                    name="Next Boat",
                    value=f"{status} {display_item_name(boat_name)}\n└ Required: Level {req_level}, {' and '.join(requirements)}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Next Boat",
                    value="You have the best boat!",
                    inline=False
                )

            class UpgradeView(discord.ui.View):
                def __init__(self, bot_self):
                    super().__init__(timeout=None)
                    self.bot_self = bot_self

                @discord.ui.button(label="Upgrade Rod", style=discord.ButtonStyle.primary)
                async def upgrade_rod(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if not next_rod:
                        await button_interaction.response.send_message(
                            content="You already have the best fishing rod!",
                            ephemeral=True
                        )
                        return

                    rod_name, rod_data = next_rod
                    req_level = rod_data["fishing_level"]
                    req_amount = rod_data["price"].get("coins", 0)
                    req_tokens = rod_data["price"].get("fish_tokens", 0)
                    
                    check_user_stat(["balance", "purse"], user_id, 0)
                    user_coins = eco[user_id]["balance"]["purse"]

                    if fishing_level < req_level:
                        await button_interaction.response.send_message(
                            f"You need fishing level {req_level} to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    elif user_coins < req_amount:
                        await button_interaction.response.send_message(
                            f"You need {req_amount:,} coins to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    elif fish_tokens < req_tokens:
                        await button_interaction.response.send_message(
                            f"You need {req_tokens:,} fish tokens to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    else:
                        eco[user_id]["balance"]["purse"] -= req_amount
                        eco[user_id]["balance"]["fish_tokens"] -= req_tokens
                        eco[user_id]["fishing"]["rod"] = rod_name
                        save_json(self.bot_self.eco_path, eco)
                        
                        success_embed = discord.Embed(
                            title="Upgrade Successful!",
                            description=f"You upgraded to a {display_item_name(rod_name)}!",
                            color=discord.Color.green()
                        )
                        
                        await button_interaction.response.edit_message(embed=success_embed, view=UpgradeView(self.bot_self))

                @discord.ui.button(label="Upgrade Boat", style=discord.ButtonStyle.primary)
                async def upgrade_boat(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if not next_boat:
                        await button_interaction.response.send_message(
                            content="You already have the best boat!",
                            ephemeral=True
                        )
                        return

                    boat_name, boat_data = next_boat
                    req_level = boat_data["fishing_level"]
                    req_amount = boat_data["price"].get("coins", 0)
                    req_tokens = boat_data["price"].get("fish_tokens", 0)
                    
                    check_user_stat(["balance", "purse"], user_id, 0)
                    user_coins = eco[user_id]["balance"]["purse"]

                    if fishing_level < req_level:
                        await button_interaction.response.send_message(
                            f"You need fishing level {req_level} to upgrade to {display_item_name(boat_name)}!",
                            ephemeral=True
                        )
                    elif user_coins < req_amount:
                        await button_interaction.response.send_message(
                            f"You need {req_amount:,} coins to upgrade to {display_item_name(boat_name)}!",
                            ephemeral=True
                        )
                    elif fish_tokens < req_tokens:
                        await button_interaction.response.send_message(
                            f"You need {req_tokens:,} fish tokens to upgrade to {display_item_name(boat_name)}!",
                            ephemeral=True
                        )
                    else:
                        eco[user_id]["balance"]["purse"] -= req_amount
                        eco[user_id]["balance"]["fish_tokens"] -= req_tokens
                        eco[user_id]["fishing"]["boat"] = boat_name
                        save_json(self.bot_self.eco_path, eco)
                        
                        success_embed = discord.Embed(
                            title="Upgrade Successful!",
                            description=f"You upgraded to a {display_item_name(boat_name)}!",
                            color=discord.Color.green()
                        )
                        
                        await button_interaction.response.edit_message(embed=success_embed, view=UpgradeView(self.bot_self))

                @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
                async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    await self.bot_self.show_profile(button_interaction)

            await interaction.response.send_message(embed=embed, view=UpgradeView(self.bot_self))

        @discord.ui.button(label="Sell", style=discord.ButtonStyle.danger)
        async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            check_user_stat(["inventory"], user_id, {})
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.bot_self.eco_path)
            fish_data = open_json(self.bot_self.fish_path)
            items_data = open_json(self.bot_self.items_path)
            
            total_coins = 0
            total_tokens = 0
            fish_sold = []
            
            for item_name, item_count in eco[user_id]["inventory"].items():
                if item_name in fish_data["fish"] and item_count > 0:
                    price = self.bot_self.get_fish_price(item_name, items_data)
                    total_coins += price * item_count
                    total_tokens += (fish_data["fish"][item_name]["rod_level"] * item_count)
                    fish_sold.append(f"{item_count}x {display_item_name(item_name)}")
                    eco[user_id]["inventory"][item_name] = 0

            if not fish_sold:
                embed = discord.Embed(
                    title="No Fish to Sell",
                    description="You don't have any fish to sell!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                eco[user_id]["balance"]["purse"] += total_coins
                eco[user_id]["balance"]["fish_tokens"] += total_tokens
                save_json(self.bot_self.eco_path, eco)
                
                embed = discord.Embed(
                    title="Fish Sold!",
                    description=f"You sold:\n" + "\n".join(fish_sold),
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Rewards",
                    value=f"Coins: {total_coins:,}\nFish Tokens: {total_tokens:,}"
                )
                await interaction.response.send_message(embed=embed, view=self.bot_self.AllView("catch", self.bot_self))

    async def fish(self, interaction: discord.Interaction, page: str):
        await self.show_profile(interaction)

    @app_commands.command(name="profile")
    async def fish_profile(self, interaction: discord.Interaction):
        """View your fishing profile and stats"""
        await self.show_profile(interaction)

    @app_commands.command(name="start")
    async def fish_start(self, interaction: discord.Interaction):
        """Start fishing!"""
        try:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🎣 Ready to Fish",
                    description="Click the catch button to start fishing!",
                    color=discord.Color.blue()
                ),
                view=self.AllView("catch", self)
            )
        except Exception as e:
            print(traceback.format_exc())
            await interaction.response.send_message("An error occurred while fishing. Please try again.", ephemeral=True)

class FishingCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fishing = FishingCommands()
        self.bot.tree.add_command(self.fishing)

async def setup(bot):
    await bot.add_cog(FishingCommandCog(bot))