import discord
from discord.ext import commands
from discord import app_commands

import math
from datetime import datetime, timedelta

from bot_utils import (
    handle_logs
)

def is_valid_value(value: int, min_val: int, max_val: int) -> bool:
    if value is None:
        return True
    try:
        return min_val <= value <= max_val
    except TypeError:
        return False

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class TDSCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="tds", description="TDS level related commands", guild_only=False)

    def calculate_exp(self, level: int) -> int:
        if level <= 10:
            return 45 + (level * 3.5)
        elif level <= 40:
            return level * 8
        else:
            return 260 + (level * 1.5)
        
    @app_commands.command(name="calculate")
    @app_commands.choices(
        gamemode=[
            app_commands.Choice(name="Easy", value="easy"),
            app_commands.Choice(name="Casual", value="casual"),
            app_commands.Choice(name="Intermediate", value="intermediate"),
            app_commands.Choice(name="Molten", value="molten"),
            app_commands.Choice(name="Fallen", value="fallen"),
            app_commands.Choice(name="Hardcore", value="hardcore")
        ]
    )
    async def calculate(self, interaction: discord.Interaction, 
                    current_level: int, current_exp: float,
                    target_level: int = None, target_exp: float = None,
                    target_date: str = None, games_per_day: int = None,
                    gamemode: str = "fallen", vip: bool = False,
                    vip_plus: bool = False, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if target_level is None and target_exp is None:
                return await interaction.followup.send("You must provide either a target level or target EXP!", ephemeral=True)
            
            if not (
                is_valid_value(current_level, 1, 25000) and 
                is_valid_value(target_level, 2, 25000) and 
                is_valid_value(current_exp, 0, 100000) and 
                is_valid_value(target_exp, 1, 100000)
            ):
                return await interaction.followup.send("Invalid level or EXP values!", ephemeral=True)

            mode_config = {
                "easy": {"exp": 50, "time": 15, "reward": "200 coins", "reward_amount": 200, "type": "coins"},
                "casual": {"exp": 90, "time": 20, "reward": "400 coins", "reward_amount": 400, "type": "coins"},
                "intermediate": {"exp": 120, "time": 20, "reward": "500 coins", "reward_amount": 500, "type": "coins"},
                "molten": {"exp": 185, "time": 25, "reward": "750 coins", "reward_amount": 750, "type": "coins"},
                "fallen": {"exp": 250, "time": 30, "reward": "1000 coins", "reward_amount": 1000, "type": "coins"},
                "hardcore": {"exp": 400, "time": 35, "reward": "300 gems", "reward_amount": 300, "type": "gems"}
            }

            selected_mode = mode_config[gamemode]
            base_exp_per_game = selected_mode["exp"]

            exp_multiplier = 1.0
            coin_multiplier = 1.0
            
            if vip_plus:
                exp_multiplier += 0.50
                coin_multiplier += 0.20
            elif vip:
                exp_multiplier += 0.25

            if selected_mode["type"] == "coins":
                reward_amount = math.floor(selected_mode["reward_amount"] * coin_multiplier)
            else:
                reward_amount = selected_mode["reward_amount"]

            total_current_exp = sum(self.calculate_exp(i) for i in range(current_level)) + current_exp
            
            if target_exp is not None:
                target_level = target_level or current_level
                total_target_exp = sum(self.calculate_exp(i) for i in range(target_level)) + target_exp
                
                if total_target_exp <= total_current_exp:
                    await interaction.followup.send("Target EXP must be higher than current total EXP!", ephemeral=True)
                    return
                required_exp = total_target_exp - total_current_exp
            else:
                total_target_exp = sum(self.calculate_exp(i) for i in range(target_level + 1))
                if total_target_exp <= total_current_exp:
                    await interaction.followup.send("Target level must result in higher EXP than current!", ephemeral=True)
                    return
                required_exp = total_target_exp - total_current_exp

            if target_date:
                try:
                    target = datetime.strptime(target_date, "%m/%d/%Y")
                    now = datetime.now()
                    days_until = (target - now).days + 1
                    
                    if days_until <= 0:
                        await interaction.followup.send("Target date must be in the future!", ephemeral=True)
                        return

                    if games_per_day is None:
                        daily_games = math.ceil(required_exp / (base_exp_per_game * exp_multiplier * days_until))
                    else:
                        daily_games = games_per_day
                    
                    completion_date = target
                except ValueError:
                    await interaction.followup.send("Invalid date format! Use MM/DD/YYYY", ephemeral=True)
                    return
            else:
                if not games_per_day:
                    await interaction.followup.send("Either target_date or games_per_day must be provided!", ephemeral=True)
                    return
                
                daily_games = games_per_day
                days_needed = math.ceil(required_exp / (daily_games * base_exp_per_game * exp_multiplier))
                try:
                    completion_date = datetime.now() + timedelta(days=days_needed)
                except OverflowError:
                    return await interaction.followup.send("Please provide smaller target/current level/exp!", ephemeral=True)

            total_games = daily_games * (days_until if target_date else days_needed)
            total_rewards = total_games * reward_amount
            total_time = (total_games * selected_mode["time"]) / 60

            embed = discord.Embed(
                title="Tower Defense Level Calculator",
                color=discord.Color.blue()
            )

            main_info = (
                f"Total Required EXP: {required_exp:,.2f}\n"
                f"Estimated Games: {total_games:,}\n"
                f"Total {selected_mode['type']}: {total_rewards:,}\n"
                f"Total Time: {total_time:,.1f} hours\n"
            )

            if target_date:
                target_timestamp = int(target.timestamp())
                main_info += f"Days until target: {days_until:,}\n"
                main_info += f"Target completion: <t:{target_timestamp}:F>"
            else:
                completion_timestamp = int(completion_date.timestamp())
                main_info += f"Estimated days: {days_needed:,}\n"
                main_info += f"Estimated completion: <t:{completion_timestamp}:F>"

            embed.add_field(name="Main Info", value=main_info, inline=False)

            daily_info = (
                f"Games per day: {daily_games:,}\n"
                f"Time per day: {(daily_games * selected_mode['time'] / 60):,.1f} hours\n"
                f"{selected_mode['type'].title()} per day: {(daily_games * reward_amount):,}"
            )
            embed.add_field(name="Daily Requirements", value=daily_info, inline=False)

            status_info = (
                f"Current Level/EXP: {current_level}/{current_exp:,.2f}\n"
                f"Target Level/EXP: {target_level}/{target_exp if target_exp else 0:,.2f}\n"
                f"Mode: {gamemode.title()} ({selected_mode['exp']} EXP)\n"
                f"EXP Multiplier: {exp_multiplier}x"
            )
            if selected_mode["type"] == "coins" and coin_multiplier > 1:
                status_info += f"\nCoin Multiplier: {coin_multiplier}x"
            
            embed.add_field(name="Status Info", value=status_info, inline=False)
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)

        except Exception as error:
            await handle_logs(interaction, error)

class TDSCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.bot.tree.add_command(TDSCommandGroup())
        
async def setup(bot):
    await bot.add_cog(TDSCog(bot))