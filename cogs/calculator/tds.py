import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, button

import math
from datetime import datetime, timedelta

from bot_utils import (
    handle_logs
)

from .utils import (
    is_valid_value,
    load_member_info,
    save_member_info
)

import matplotlib.pyplot as plt
import io

class ConfirmView(View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.value = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self):
        self.value = False
        self.stop()

class HistoryDeleteView(View):
    def __init__(self, member_info, user_id):
        super().__init__(timeout=60)
        self.member_info = member_info
        self.user_id = user_id
        
        select = discord.ui.Select(
            placeholder="Select entries to delete",
            min_values=1,
            options=[
                discord.SelectOption(label="Loading...", value="loading", description="Please wait...")
            ]
        )
        select.callback = self.delete_select
        self.add_item(select) 
        
        history = member_info[user_id]["TDSPlan"]["history"]
        options = []
        for i, entry in enumerate(reversed(history)):
            timestamp = datetime.fromtimestamp(entry["timestamp"])
            options.append(
                discord.SelectOption(
                    label=f"{timestamp.strftime('%m/%d/%Y %H:%M')}",
                    value=str(len(history) - 1 - i),
                    description=f"Level {entry['level']} + {entry['exp']} exp"
                )
            )
        
        if options:
            select.options = options
            select.max_values = len(options)
        else:
            select.options = [
                discord.SelectOption(label="No entries", value="none", description="No history to delete")
            ]
            select.disabled = True

    async def delete_select(self, interaction: discord.Interaction):
        view = ConfirmView()
        await interaction.response.send_message(
            f"Are you sure you want to delete {len(interaction.data['values'])} selected entries?", 
            view=view, 
            ephemeral=True
        )
        
        await view.wait()
        if view.value:
            history = self.member_info[self.user_id]["TDSPlan"]["history"]
            indices = [int(i) for i in interaction.data["values"]]
            
            self.member_info[self.user_id]["TDSPlan"]["history"] = [
                entry for i, entry in enumerate(history)
                if i not in indices
            ]
            
            save_member_info(self.member_info)
            await interaction.followup.send(f"Deleted {len(indices)} entries from your history.", ephemeral=True)
            self.stop()
        else:
            await interaction.followup.send("Delete operation cancelled.", ephemeral=True)

    async def on_timeout(self):
        self.stop()

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
                    vip_plus: bool = False, ephemeral: bool = False):
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

    @app_commands.command(name="update")
    async def update(self, interaction: discord.Interaction, level: int, exp: float):
        await interaction.response.defer()
        try:
            member_info = load_member_info()
            user_id = str(interaction.user.id)

            if user_id not in member_info:
                member_info[user_id] = {}

            if "TDSPlan" not in member_info[user_id]:
                member_info[user_id]["TDSPlan"] = {
                    "enabled": True,
                    "history": []
                }
            
            now = datetime.now().timestamp()
            hundred_days_ago = now - (100 * 24 * 3600)
            member_info[user_id]["TDSPlan"]["history"] = [
                entry for entry in member_info[user_id]["TDSPlan"]["history"]
                if entry["timestamp"] >= hundred_days_ago
            ]
            
            member_info[user_id]["TDSPlan"]["history"].append({
                "timestamp": now,
                "level": level,
                "exp": exp
            })
            
            save_member_info(member_info)
            await interaction.followup.send("Progress updated! Use `/tds show` to see your progress.")
            
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="show")
    async def show(self, interaction: discord.Interaction, target_level: int = None):
        await interaction.response.defer()
        try:
            if target_level is not None and not is_valid_value(target_level, 1, 10000):
                return await interaction.followup.send("Target level must be between 1 and 10,000!", ephemeral=True)
                
            member_info = load_member_info()
            user_id = str(interaction.user.id)
            
            if user_id not in member_info or "TDSPlan" not in member_info[user_id]:
                return await interaction.followup.send("No tracking data! Use `/tds update` first.")
            
            history = member_info[user_id]["TDSPlan"]["history"]
            
            if len(history) < 2:
                return await interaction.followup.send("Not enough data yet. Please provide at least two updates!")
            
            first = history[0]
            last = history[-1]
            days = (last["timestamp"] - first["timestamp"]) / (24 * 3600)
            
            total_exp_gained = self.calculate_exp(last["level"]) + last["exp"] - (self.calculate_exp(first["level"]) + first["exp"])
            daily_rate = total_exp_gained / days if days > 0 else total_exp_gained
            
            embed = discord.Embed(title="TDS Level Progress", color=discord.Color.blue())
            embed.add_field(name="Current Progress", value=
                f"Starting Level: {first['level']}\n"
                f"Current Level: {last['level']}\n"
                f"Daily EXP Rate: {daily_rate:,.2f}", inline=False)

            now = datetime.now().timestamp()

            daily_rates = []
            for i in range(len(history) - 1):
                curr = history[i]
                next_entry = history[i + 1]
                days_between = (next_entry["timestamp"] - curr["timestamp"]) / (24 * 3600)
                if days_between > 0:
                    exp_gained = (self.calculate_exp(next_entry["level"]) + next_entry["exp"]) - (self.calculate_exp(curr["level"]) + curr["exp"])
                    daily_rates.append((next_entry["timestamp"], exp_gained / days_between))

            current_total_exp = sum(self.calculate_exp(i) for i in range(last["level"])) + last["exp"]
            future_estimates = ""
            periods = [(7, "7 days"), (30, "30 days"), (100, "100 days"), (365, "1 year")]
            
            for days_ahead, label in periods:
                future_exp = current_total_exp + (daily_rate * days_ahead)
                future_level = 1
                while sum(self.calculate_exp(i) for i in range(future_level + 1)) <= future_exp:
                    future_level += 1
                remaining_exp = future_exp - sum(self.calculate_exp(i) for i in range(future_level))
                future_estimates += f"{label}: Level {future_level} + {remaining_exp:,.2f} exp\n"

            if future_estimates:
                embed.add_field(name="Estimated Progress", value=future_estimates, inline=False)

            if target_level:
                if target_level <= last["level"]:
                    embed.add_field(name="Target Level Status", 
                                  value=f"You have already achieved level {target_level}!", 
                                  inline=False)
                else:
                    current_total_exp = sum(self.calculate_exp(i) for i in range(last["level"])) + last["exp"]
                    target_exp = sum(self.calculate_exp(i) for i in range(target_level + 1))
                    exp_needed = target_exp - current_total_exp
                    days_needed = exp_needed / daily_rate if daily_rate > 0 else float('inf')
                    eta = datetime.now() + timedelta(days=days_needed) if days_needed != float('inf') else None
                    
                    status = f"Level {target_level}: "
                    if eta:
                        status += f"<t:{int(eta.timestamp())}:R>"
                    else:
                        status += "Unknown"
                    
                    embed.add_field(name="Target Level Status", value=status, inline=False)

            milestones = [50, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 2500]
            milestone_text = ""
            current_total_exp = sum(self.calculate_exp(i) for i in range(last["level"])) + last["exp"]
            
            for milestone in milestones:
                if milestone <= last["level"]:
                    continue
                milestone_exp = sum(self.calculate_exp(i) for i in range(milestone + 1))
                exp_needed = milestone_exp - current_total_exp
                days_needed = exp_needed / daily_rate if daily_rate > 0 else float('inf')
                eta = datetime.now() + timedelta(days=days_needed) if days_needed != float('inf') else None
                
                milestone_text += f"Level {milestone}: "
                if eta:
                    milestone_text += f"<t:{int(eta.timestamp())}:R>\n"
                else:
                    milestone_text += "Unknown\n"

            if milestone_text:
                embed.add_field(name="Milestone ETAs", value=milestone_text, inline=False)
            
            if days < 7:
                embed.set_footer(text="⚠️ Limited data: ETAs may be inaccurate due to short tracking period", icon_url=interaction.user.avatar.url)
            
            plt.clf()
            fourteen_days_ago = now - (14 * 24 * 3600)
            recent_history = [(h["timestamp"], sum(self.calculate_exp(i) for i in range(h["level"])) + h["exp"]) 
                            for h in history 
                            if h["timestamp"] >= fourteen_days_ago]
            
            graph_file = None
            if len(recent_history) >= 2:
                timestamps, exp_values = zip(*recent_history)
                dates = [datetime.fromtimestamp(ts) for ts in timestamps]
                
                plt.figure(figsize=(10, 5))
                plt.plot(dates, exp_values, 'b-', marker='o')
                plt.gcf().autofmt_xdate()
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.title('EXP Progress - Last 14 Days')
                plt.ylabel('Total EXP')
                
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                
                graph_file = discord.File(buf, filename='exp_graph.png')
                embed.set_image(url="attachment://exp_graph.png")
            
            if graph_file:
                delete_view = HistoryDeleteView(member_info, user_id)
                await interaction.followup.send(embed=embed, file=graph_file, view=delete_view)
            else:
                delete_view = HistoryDeleteView(member_info, user_id)
                await interaction.followup.send(embed=embed, view=delete_view)
            
        except Exception as error:
            await handle_logs(interaction, error)

class TDSCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.bot.tree.add_command(TDSCommandGroup())
        
async def setup(bot):
    await bot.add_cog(TDSCog(bot))