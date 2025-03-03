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

    def get_rod_level(self, rod_name, fish_data):
        if not rod_name or rod_name not in fish_data["rods"]:
            return 0
        return fish_data["rods"][rod_name]["rod_level"]

    async def show_profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        check_user_stat(["fishing", "level"], user_id, 0)
        check_user_stat(["fishing", "exp"], user_id, 0)
        check_user_stat(["fishing", "rod"], user_id, None)
        check_user_stat(["balance", "fish_tokens"], user_id, 0)
        
        eco = open_json(self.eco_path)
        fish_data = open_json(self.fish_path)
        
        fishing_level = eco[user_id]["fishing"]["level"]
        exp = eco[user_id]["fishing"]["exp"]
        required_exp = self.calculate_required_exp(fishing_level)
        fish_tokens = eco[user_id]["balance"]["fish_tokens"]
        current_rod = self.get_current_rod(user_id, eco)
        current_rod_level = self.get_rod_level(current_rod, fish_data)
        
        total_fish = 0
        rarest_fish = None
        highest_value = 0
        for fish_name, count in eco[user_id]["inventory"].items():
            if fish_name in fish_data["fish"]:
                total_fish += count
                fish_price = fish_data["fish"][fish_name]["price"]["amount"]
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
        
        rod_display = "None" if not current_rod else f"{display_item_name(current_rod)} (Level {current_rod_level})"
        embed.add_field(
            name="⚔️ Equipment",
            value=f"Current Rod: {rod_display}",
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

    @app_commands.command(name="leaderboard")
    async def fish_leaderboard(self, interaction: discord.Interaction):
        """View the fishing leaderboard"""
        eco = open_json(self.eco_path)
        
        user_stats = []
        for user_id, data in eco.items():
            try:
                if "fishing" in data:
                    fishing_data = data["fishing"]
                    level = fishing_data.get("level", 0)
                    total_fish = sum(count for item_name, count in data.get("inventory", {}).items() 
                                   if item_name in open_json(self.fish_path)["fish"])
                    fish_tokens = data.get("balance", {}).get("fish_tokens", 0)
                    
                    user = await self.bot.fetch_user(int(user_id))
                    username = user.name if user else "Unknown User"
                    
                    user_stats.append({
                        "username": username,
                        "level": level,
                        "total_fish": total_fish,
                        "fish_tokens": fish_tokens
                    })
            except:
                continue
        
        user_stats.sort(key=lambda x: (x["level"], x["total_fish"]), reverse=True)
        
        embed = discord.Embed(
            title="🎣 Fishing Leaderboard",
            color=discord.Color.gold()
        )
        
        level_lb = ""
        for i, stats in enumerate(user_stats[:10], 1):
            level_lb += f"{i}. {stats['username']}: Level {stats['level']} ({stats['total_fish']:,} fish caught)\n"
        
        embed.add_field(
            name="Top Fishers",
            value=level_lb if level_lb else "No data available",
            inline=False
        )
        
        user_stats.sort(key=lambda x: x["fish_tokens"], reverse=True)
        token_lb = ""
        for i, stats in enumerate(user_stats[:5], 1):
            token_lb += f"{i}. {stats['username']}: {stats['fish_tokens']:,} tokens\n"
        
        embed.add_field(
            name="Richest Fishers",
            value=token_lb if token_lb else "No data available",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    class AllView(discord.ui.View):
        def __init__(self, page, bot_self):
            super().__init__(timeout=None)
            self.page = page
            self.bot_self = bot_self

        @discord.ui.button(label="Catch", style=discord.ButtonStyle.primary)
        async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            cooldown_result = command_cooldown(30, "beg", user_id)
            if isinstance(cooldown_result, tuple):
                done, cooldown = cooldown_result
                if not done:
                    return await send_cooldown(interaction, cooldown)
            else:
                return await interaction.response.send_message("Error checking cooldown", ephemeral=True)

            check_user_stat(["fishing", "level"], user_id, 0)
            check_user_stat(["fishing", "exp"], user_id, 0)
            check_user_stat(["fishing", "rod"], user_id, None)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.bot_self.eco_path)
            fish_data = open_json(self.bot_self.fish_path)
            
            current_rod = self.bot_self.get_current_rod(user_id, eco)
            if not current_rod:
                embed = discord.Embed(
                    title="No Fishing Rod!",
                    description="You need a fishing rod to fish! Buy one from the shop.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            fishing_level = eco[user_id]["fishing"]["level"]
            rod_level = self.bot_self.get_rod_level(current_rod, fish_data)

            eco[user_id]["fishing"]["exp"] += 1
            leveled_up = self.bot_self.check_level_up(user_id, eco)

            available_fish = []
            for fish_name, fish_info in fish_data["fish"].items():
                if (fish_info["fishing_level"] <= fishing_level and 
                    fish_info["rod_level"] <= rod_level):
                    available_fish.append((fish_name, fish_info))

            if not available_fish:
                embed = discord.Embed(
                    title="No Fish Available!",
                    description="You can't catch any fish with your current rod and level.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            success_rate = min(80 + (fishing_level / 2), 95)
            
            caught_fish = []
            total_tokens = 0
            attempts = random.randint(1, 50)
            
            for _ in range(attempts):
                if random.random() * 100 <= success_rate:
                    weights = [1 / fish_info["rod_level"] for _, fish_info in available_fish]
                    fish, fish_info = random.choices(available_fish, weights=weights, k=1)[0]
                    caught_fish.append(fish)
                    
                    check_user_stat(["inventory", fish], user_id, 0)
                    eco[user_id]["inventory"][fish] += 1
                    total_tokens += 1

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

        @discord.ui.button(label="Upgrade", style=discord.ButtonStyle.success)
        async def upgrade_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            check_user_stat(["fishing", "level"], user_id, 0)
            check_user_stat(["fishing", "rod"], user_id, None)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.bot_self.eco_path)
            fish_data = open_json(self.bot_self.fish_path)
            
            fishing_level = eco[user_id]["fishing"]["level"]
            fish_tokens = eco[user_id]["balance"]["fish_tokens"]
            current_rod = self.bot_self.get_current_rod(user_id, eco)
            current_rod_level = self.bot_self.get_rod_level(current_rod, fish_data)
            
            embed = discord.Embed(
                title="🎣 Fishing Upgrades",
                description="Choose what to upgrade:",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Your Stats",
                value=f"Level: {fishing_level}\nFish Tokens: {fish_tokens:,}\nCurrent Rod: {display_item_name(current_rod) if current_rod else 'None'}",
                inline=False
            )

            available_rods = []
            next_rod = None
            for rod_name, rod_data in fish_data["rods"].items():
                rod_level = rod_data["rod_level"]
                if rod_level == current_rod_level + 1:
                    next_rod = (rod_name, rod_data)
                    break

            if next_rod:
                rod_name, rod_data = next_rod
                req_level = rod_data["fishing_level"]
                req_amount = rod_data["price"]["amount"]
                req_currency = rod_data["price"]["currency"]
                
                if req_currency == "coins":
                    check_user_stat(["balance", "purse"], user_id, 0)
                    user_currency = eco[user_id]["balance"]["purse"]
                else:
                    user_currency = fish_tokens
                
                status = "<:check:1292269189536682004>" if fishing_level >= req_level and user_currency >= req_amount else "❌"
                available_rods.append(
                    f"{status} {display_item_name(rod_name)}\n"
                    f"└ Required: Level {req_level}, {req_amount:,} {req_currency}"
                )
            else:
                available_rods.append("You have the best rod!")

            embed.add_field(
                name="Next Rod",
                value="\n".join(available_rods),
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
                    req_currency = rod_data["price"]["currency"]
                    req_amount = rod_data["price"]["amount"]
                    
                    if req_currency == "coins":
                        check_user_stat(["balance", "purse"], user_id, 0)
                        user_currency = eco[user_id]["balance"]["purse"]
                    else:
                        user_currency = fish_tokens

                    if fishing_level < rod_data["fishing_level"]:
                        await button_interaction.response.send_message(
                            f"You need fishing level {rod_data['fishing_level']} to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    elif user_currency < req_amount:
                        await button_interaction.response.send_message(
                            f"You need {req_amount:,} {req_currency} to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    else:
                        if req_currency == "coins":
                            eco[user_id]["balance"]["purse"] -= req_amount
                        else:
                            eco[user_id]["balance"]["fish_tokens"] -= req_amount
                            
                        eco[user_id]["fishing"]["rod"] = rod_name
                        save_json(self.bot_self.eco_path, eco)
                        
                        success_embed = discord.Embed(
                            title="Upgrade Successful!",
                            description=f"You upgraded to a {display_item_name(rod_name)}!",
                            color=discord.Color.green()
                        )
                        
                        class SuccessView(discord.ui.View):
                            def __init__(self, bot_self):
                                super().__init__(timeout=None)
                                self.bot_self = bot_self

                            @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
                            async def back_button(self, back_interaction: discord.Interaction, button: discord.ui.Button):
                                await self.bot_self.show_profile(back_interaction)

                        await button_interaction.response.edit_message(embed=success_embed, view=SuccessView(self.bot_self))

                @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
                async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    await self.bot_self.show_profile(button_interaction)

            await interaction.response.send_message(embed=embed, view=UpgradeView(self))

        @discord.ui.button(label="Sell", style=discord.ButtonStyle.danger)
        async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            check_user_stat(["inventory"], user_id, {})
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.bot_self.eco_path)
            fish_data = open_json(self.bot_self.fish_path)
            
            total_coins = 0
            total_tokens = 0
            fish_sold = []
            
            for item_name, item_count in eco[user_id]["inventory"].items():
                if item_name in fish_data["fish"] and item_count > 0:
                    price = fish_data["fish"][item_name]["price"]["amount"]
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
        if page == "upgrade": 
            user_id = str(interaction.user.id)
            check_user_stat(["fishing", "level"], user_id, 0)
            check_user_stat(["fishing", "rod"], user_id, None)
            check_user_stat(["balance", "fish_tokens"], user_id, 0)
            
            eco = open_json(self.eco_path)
            fish_data = open_json(self.fish_path)
            
            fishing_level = eco[user_id]["fishing"]["level"]
            fish_tokens = eco[user_id]["balance"]["fish_tokens"]
            current_rod = self.get_current_rod(user_id, eco)
            current_rod_level = self.get_rod_level(current_rod, fish_data)
                        
            embed = discord.Embed(
                title="🎣 Fishing Upgrades",
                description="Choose what to upgrade:",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Your Stats",
                value=f"Level: {fishing_level}\nFish Tokens: {fish_tokens:,}\nCurrent Rod: {display_item_name(current_rod) if current_rod else 'None'}",
                inline=False
            )

            available_rods = []
            next_rod = None
            for rod_name, rod_data in fish_data["rods"].items():
                rod_level = rod_data["rod_level"]
                if rod_level == current_rod_level + 1:
                    next_rod = (rod_name, rod_data)
                    break

            if next_rod:
                rod_name, rod_data = next_rod
                req_level = rod_data["fishing_level"]
                req_amount = rod_data["price"]["amount"]
                req_currency = rod_data["price"]["currency"]
                
                if req_currency == "coins":
                    check_user_stat(["balance", "purse"], user_id, 0)
                    user_currency = eco[user_id]["balance"]["purse"]
                else:  
                    user_currency = fish_tokens
                
                status = "<:check:1292269189536682004>" if fishing_level >= req_level and user_currency >= req_amount else "❌"
                available_rods.append(
                    f"{status} {display_item_name(rod_name)}\n"
                    f"└ Required: Level {req_level}, {req_amount:,} {req_currency}"
                )
            else:
                available_rods.append("You have the best rod!")

            embed.add_field(
                name="Next Rod",
                value="\n".join(available_rods),
                inline=False
            )

            class UpgradeView(discord.ui.View):
                def __init__(self, bot_self):
                    super().__init__(timeout=None)
                    self.bot_self = bot_self

                @discord.ui.button(label="Upgrade Rod", style=discord.ButtonStyle.primary)
                async def upgrade_rod(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if not next_rod:
                        await button_interaction.response.edit_message(
                            content="You already have the best fishing rod!",
                            embed=embed,
                            view=self
                        )
                        return

                    rod_name, rod_data = next_rod
                    req_currency = rod_data["price"]["currency"]
                    req_amount = rod_data["price"]["amount"]
                    
                    
                    if req_currency == "coins":
                        check_user_stat(["balance", "purse"], user_id, 0)
                        user_currency = eco[user_id]["balance"]["purse"]
                    else:  
                        user_currency = fish_tokens

                    if fishing_level < rod_data["fishing_level"]:
                        await button_interaction.response.send_message(
                            f"You need fishing level {rod_data['fishing_level']} to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    elif user_currency < req_amount:
                        await button_interaction.response.send_message(
                            f"You need {req_amount:,} {req_currency} to upgrade to {display_item_name(rod_name)}!",
                            ephemeral=True
                        )
                    else:
                        if req_currency == "coins":
                            eco[user_id]["balance"]["purse"] -= req_amount
                        else:  
                            eco[user_id]["balance"]["fish_tokens"] -= req_amount
                            
                        eco[user_id]["fishing"]["rod"] = rod_name
                        save_json(self.bot_self.eco_path, eco)
                        
                        next_next_rod = None
                        for next_name, next_data in fish_data["rods"].items():
                            if next_data["rod_level"] == rod_data["rod_level"] + 1:
                                next_next_rod = (next_name, next_data)
                                break
                        
                        success_embed = discord.Embed(
                            title="Upgrade Successful!",
                            description=f"You upgraded to a {display_item_name(rod_name)}!",
                            color=discord.Color.green()
                        )
                        
                        if next_next_rod:
                            next_name, next_data = next_next_rod
                            success_embed.add_field(
                                name="Next Upgrade Available",
                                value=f"{display_item_name(next_name)}\nRequired: Level {next_data['fishing_level']}, {next_data['price']['amount']:,} {next_data['price']['currency']}",
                                inline=False
                            )
                            await button_interaction.response.edit_message(embed=success_embed, view=self)
                        else:
                            success_embed.add_field(
                                name="Maximum Level Reached",
                                value="You have the best fishing rod!",
                                inline=False
                            )
                            await button_interaction.response.edit_message(embed=success_embed)

                @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
                async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    await self.bot_self.fish(button_interaction, "catch")

            await interaction.response.send_message(embed=embed, view=UpgradeView(self))
        else:
            await self.show_profile(interaction)

    @app_commands.command(name="profile")
    async def fish_profile(self, interaction: discord.Interaction):
        """View your fishing profile and stats"""
        await self.show_profile(interaction)

    @app_commands.command(name="upgrade")
    async def fish_upgrade(self, interaction: discord.Interaction):
        """View the fishing shop and upgrade your rod"""
        user_id = str(interaction.user.id)
        check_user_stat(["fishing", "level"], user_id, 0)
        check_user_stat(["fishing", "rod"], user_id, None)
        check_user_stat(["balance", "fish_tokens"], user_id, 0)
        
        eco = open_json(self.eco_path)
        fish_data = open_json(self.fish_path)
        
        fishing_level = eco[user_id]["fishing"]["level"]
        fish_tokens = eco[user_id]["balance"]["fish_tokens"]
        current_rod = self.get_current_rod(user_id, eco)
        current_rod_level = self.get_rod_level(current_rod, fish_data)
        
        embed = discord.Embed(
            title="🎣 Fishing Upgrades",
            description="Choose what to upgrade:",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Your Stats",
            value=f"Level: {fishing_level}\nFish Tokens: {fish_tokens:,}\nCurrent Rod: {display_item_name(current_rod) if current_rod else 'None'}",
            inline=False
        )

        available_rods = []
        next_rod = None
        for rod_name, rod_data in fish_data["rods"].items():
            rod_level = rod_data["rod_level"]
            if rod_level == current_rod_level + 1:
                next_rod = (rod_name, rod_data)
                break

        if next_rod:
            rod_name, rod_data = next_rod
            req_level = rod_data["fishing_level"]
            req_amount = rod_data["price"]["amount"]
            req_currency = rod_data["price"]["currency"]
            
            if req_currency == "coins":
                check_user_stat(["balance", "purse"], user_id, 0)
                user_currency = eco[user_id]["balance"]["purse"]
            else:
                user_currency = fish_tokens
            
            status = "<:check:1292269189536682004>" if fishing_level >= req_level and user_currency >= req_amount else "❌"
            available_rods.append(
                f"{status} {display_item_name(rod_name)}\n"
                f"└ Required: Level {req_level}, {req_amount:,} {req_currency}"
            )
        else:
            available_rods.append("You have the best rod!")

        embed.add_field(
            name="Next Rod",
            value="\n".join(available_rods),
            inline=False
        )

        class UpgradeView(discord.ui.View):
            def __init__(self, bot_self):
                super().__init__(timeout=None)
                self.bot_self = bot_self

            @discord.ui.button(label="Upgrade Rod", style=discord.ButtonStyle.primary)
            async def upgrade_rod(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if not next_rod:
                    await button_interaction.response.edit_message(
                        content="You already have the best fishing rod!",
                        embed=embed,
                        view=self
                    )
                    return

                rod_name, rod_data = next_rod
                req_currency = rod_data["price"]["currency"]
                req_amount = rod_data["price"]["amount"]
                
                if req_currency == "coins":
                    check_user_stat(["balance", "purse"], user_id, 0)
                    user_currency = eco[user_id]["balance"]["purse"]
                else:  
                    user_currency = fish_tokens

                if fishing_level < rod_data["fishing_level"]:
                    await button_interaction.response.send_message(
                        f"You need fishing level {rod_data['fishing_level']} to upgrade to {display_item_name(rod_name)}!",
                        ephemeral=True
                    )
                elif user_currency < req_amount:
                    await button_interaction.response.send_message(
                        f"You need {req_amount:,} {req_currency} to upgrade to {display_item_name(rod_name)}!",
                        ephemeral=True
                    )
                else:
                    if req_currency == "coins":
                        eco[user_id]["balance"]["purse"] -= req_amount
                    else:  
                        eco[user_id]["balance"]["fish_tokens"] -= req_amount
                            
                    eco[user_id]["fishing"]["rod"] = rod_name
                    save_json(self.bot_self.eco_path, eco)
                    
                    success_embed = discord.Embed(
                        title="Upgrade Successful!",
                        description=f"You upgraded to a {display_item_name(rod_name)}!",
                        color=discord.Color.green()
                    )
                    
                    class SuccessView(discord.ui.View):
                        def __init__(self, bot_self):
                            super().__init__(timeout=None)
                            self.bot_self = bot_self

                        @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
                        async def back_button(self, back_interaction: discord.Interaction, button: discord.ui.Button):
                            await self.bot_self.show_profile(back_interaction)

                    await button_interaction.response.edit_message(embed=success_embed, view=SuccessView(self.bot_self))

            @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
            async def back_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await self.bot_self.show_profile(button_interaction)

        await interaction.response.send_message(embed=embed, view=UpgradeView(self))

    @app_commands.command(name="catch")
    async def fish_catch(self, interaction: discord.Interaction):
        """Start fishing and view available upgrades"""
        user_id = str(interaction.user.id)
        cooldown_result = command_cooldown(30, "beg", user_id)
        if isinstance(cooldown_result, tuple):
            done, cooldown = cooldown_result
            if not done:
                return await send_cooldown(interaction, cooldown)
        else:
            return await interaction.response.send_message("Error checking cooldown", ephemeral=True)

        check_user_stat(["fishing", "level"], user_id, 0)
        check_user_stat(["fishing", "exp"], user_id, 0)
        check_user_stat(["fishing", "rod"], user_id, None)
        check_user_stat(["balance", "fish_tokens"], user_id, 0)
        
        eco = open_json(self.eco_path)
        fish_data = open_json(self.fish_path)
        
        current_rod = self.get_current_rod(user_id, eco)
        if not current_rod:
            embed = discord.Embed(
                title="No Fishing Rod!",
                description="You need a fishing rod to fish! Buy one from the shop.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        fishing_level = eco[user_id]["fishing"]["level"]
        rod_level = self.get_rod_level(current_rod, fish_data)

        eco[user_id]["fishing"]["exp"] += 1
        leveled_up = self.check_level_up(user_id, eco)

        available_fish = []
        for fish_name, fish_info in fish_data["fish"].items():
            if (fish_info["fishing_level"] <= fishing_level and 
                fish_info["rod_level"] <= rod_level):
                available_fish.append((fish_name, fish_info))

        if not available_fish:
            embed = discord.Embed(
                title="No Fish Available!",
                description="You can't catch any fish with your current rod and level.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        success_rate = min(80 + (fishing_level / 2), 95)
        
        caught_fish = []
        total_tokens = 0
        attempts = random.randint(1, 50)
        
        for _ in range(attempts):
            if random.random() * 100 <= success_rate:
                weights = [1 / fish_info["rod_level"] for _, fish_info in available_fish]
                fish, fish_info = random.choices(available_fish, weights=weights, k=1)[0]
                caught_fish.append(fish)
                
                check_user_stat(["inventory", fish], user_id, 0)
                eco[user_id]["inventory"][fish] += 1
                total_tokens += 1

        eco[user_id]["balance"]["fish_tokens"] += total_tokens
        save_json(self.eco_path, eco)

        if caught_fish:
            fish_counts = {}
            for fish in caught_fish:
                fish_counts[fish] = fish_counts.get(fish, 0) + 1

            description = "**You caught**:\n" + "\n".join(f"{count}x {display_item_name(fish)}" for fish, count in fish_counts.items())
            if leveled_up:
                description += f"\n🎉 Level Up! You are now level {eco[user_id]['fishing']['level']}!"
            
            embed = discord.Embed(
                title=self.interaction.user,
                description=description,
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Stats",
                value=f"Level: {fishing_level}\nEXP: {eco[user_id]['fishing']['exp']}/{self.calculate_required_exp(fishing_level)}"
            )

            await interaction.response.send_message(embed=embed, view=self.AllView("catch", self))
        else:
            embed = discord.Embed(
                title="Got away!",
                description="All the fish got away...",
                color=discord.Color.red()
            )
            if leveled_up:
                embed.description += f"\n🎉 But you leveled up! You are now level {eco[user_id]['fishing']['level']}!"

            await interaction.response.send_message(embed=embed, view=self.AllView("catch", self))

    @app_commands.command(name="sell")
    async def fish_sell(self, interaction: discord.Interaction):
        """Sell your fish and view available upgrades"""
        user_id = str(interaction.user.id)
        check_user_stat(["inventory"], user_id, {})
        check_user_stat(["balance", "purse"], user_id, 0)
        check_user_stat(["balance", "fish_tokens"], user_id, 0)
        
        eco = open_json(self.eco_path)
        fish_data = open_json(self.fish_path)
        
        total_coins = 0
        total_tokens = 0
        fish_sold = []
        
        for item_name, item_count in eco[user_id]["inventory"].items():
            if item_name in fish_data["fish"] and item_count > 0:
                price = fish_data["fish"][item_name]["price"]["amount"]
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
            save_json(self.eco_path, eco)
            
            embed = discord.Embed(
                title="Fish Sold!",
                description=f"You sold:\n" + "\n".join(fish_sold),
                color=discord.Color.green()
            )
            embed.add_field(
                name="Rewards",
                value=f"Coins: {total_coins:,}\nFish Tokens: {total_tokens:,}"
            )
            await interaction.response.send_message(embed=embed, view=self.AllView("catch", self))

class FishingCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fishing = FishingCommands()
        self.bot.tree.add_command(self.fishing)

async def setup(bot):
    await bot.add_cog(FishingCommandCog(bot))