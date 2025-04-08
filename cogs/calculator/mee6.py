import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, button

from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io

from bot_utils import (
    handle_logs
)

from .utils import (
    is_valid_value,
    load_member_info,
    save_member_info
)

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
        
        history = member_info[user_id]["MEE6Plan"]["history"]
        options = []
        for i, entry in enumerate(list(reversed(history))[:25]):
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
            history = self.member_info[self.user_id]["MEE6Plan"]["history"]
            indices = [int(i) for i in interaction.data["values"]]
            
            self.member_info[self.user_id]["MEE6Plan"]["history"] = [
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
class Mee6CommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="mee6", description="Mee6 level related commands", guild_only=False)

    def calculate_exp(self, level: int) -> int:
        total_exp = 0
        for l in range(1, level + 1):
            total_exp += 5 * (l ** 2) + 50 * l + 100
        return total_exp

    def validate_exp_gain(self, old_level: int, old_exp: int, new_level: int, new_exp: int, timestamp_diff: float) -> tuple[bool, str]:
        old_total = self.calculate_exp(old_level) + old_exp
        new_total = self.calculate_exp(new_level) + new_exp
        exp_diff = new_total - old_total
        
        if exp_diff < 0:
            return False, "Level/EXP cannot decrease. Do you want to continue?"
        
        minutes = timestamp_diff / 60
        if minutes > 0:
            exp_per_minute = exp_diff / minutes
            if exp_per_minute > 25:
                return False, f"Gaining {exp_per_minute:.1f} EXP per minute seems unusually high. Are you sure?"
            
        return True, ""

    @app_commands.command(name="calculate")
    async def calculate(self, interaction: discord.Interaction, 
                    current_level: int, current_exp: int, 
                    target_level: int = None, target_exp: int = None,
                    target_date: str = None, exp_per_day: int = None,
                    mee6_pro: bool = False, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            old_target_exp = target_exp

            if not (
                is_valid_value(current_level, 1, 500) and 
                is_valid_value(target_level, 2, 500) and 
                is_valid_value(current_exp, 0, 1000000) and 
                is_valid_value(target_exp, 1, 1000000)
            ):
                return await interaction.followup.send("Invalid level or EXP values!", ephemeral=True)

            if target_level is None and target_exp is None:
                return await interaction.followup.send("You must provide either a target level or target EXP!", ephemeral=True)
            
            total_current_exp = self.calculate_exp(current_level) + current_exp
            
            if target_exp is not None:
                target_level = target_level or current_level
                total_target_exp = self.calculate_exp(target_level) + target_exp
                
                if total_target_exp <= total_current_exp:
                    await interaction.followup.send("Target EXP must be higher than current total EXP!", ephemeral=True)
                    return
                required_exp = total_target_exp - total_current_exp
            else:
                target_exp = self.calculate_exp(target_level)
                if target_exp <= total_current_exp:
                    await interaction.followup.send("Target level must result in higher EXP than current!", ephemeral=True)
                    return
                required_exp = target_exp - total_current_exp

            if required_exp == 0:
                await interaction.followup.send("You have already reached or exceeded this target!", ephemeral=True)
                return
            
            if mee6_pro:
                required_exp = int(required_exp / 1.5)

            if target_date:
                try:
                    target = datetime.strptime(target_date, "%m/%d/%Y")
                    now = datetime.now()
                    days_until = (target - now).days + 1
                    
                    if days_until <= 0:
                        await interaction.followup.send("Target date must be in the future!")
                        return
                    
                    required_daily_exp = required_exp / days_until
                    completion_date = target
                except ValueError:
                    await interaction.followup.send("Invalid date format! Use MM/DD/YYYY")
                    return
            else:
                if not exp_per_day:
                    await interaction.followup.send("Either target_date or exp_per_day must be provided!")
                    return
                
                days_needed = round(required_exp / exp_per_day)
                try:
                    completion_date = datetime.now() + timedelta(days=days_needed)
                except OverflowError:
                    return await interaction.followup.send("Please provide smaller target/current level/exp!")
                required_daily_exp = exp_per_day

            embed = discord.Embed(
                title="Mee6 Level Calculator",
                color=discord.Color.blue()
            )

            main_info = (
                f"Total Required EXP: {required_exp:,}\n"
                f"Minimum Messages: {int(required_exp / 20 * 1.8):,}\n"
            )

            if target_date:
                target_timestamp = int(target.timestamp())
                main_info += f"Estimated Days: {days_until:,}\n"
                main_info += f"Estimated completion: <t:{target_timestamp}:F>"
            else:
                completion_timestamp = int(completion_date.timestamp())
                main_info += f"Estimated Days: {days_needed:,}\n"
                main_info += f"Estimated completion: <t:{completion_timestamp}:F>"

            embed.add_field(name="Main Info", value=main_info, inline=False)

            daily_chat_info = ""
            chat_hours_needed = (exp_per_day if exp_per_day else required_daily_exp) / 1200
            hours = int(chat_hours_needed)
            minutes = int((chat_hours_needed - hours) * 60)
            
            daily_chat_info += f"Time: {hours} hours {minutes} minutes\n"
            daily_chat_info += f"Messages: {int((exp_per_day if exp_per_day else required_daily_exp) / 20):,} minimum messages per day\n"
            daily_chat_info += f"EXP: {int(exp_per_day if exp_per_day else required_daily_exp):,} exp per day"
            
            embed.add_field(name="Est. Daily Chat Info", value=daily_chat_info, inline=False)

            other_info = (
                f"Current Level/EXP: {current_level}/{current_exp:,}\n"
                f"Target Level/EXP: {target_level}/{old_target_exp if old_target_exp else 0:,}\n"
                f"Total current level EXP: {total_current_exp:,}\n"
                f"Total target level EXP: {target_exp if target_exp else self.calculate_exp(target_level):,}"
            )
            
            embed.add_field(name="Other Info", value=other_info, inline=False)

            embed.set_footer(text=f"Estimates based on 1.2k EXP per hour of chatting", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="add")
    async def add(self, interaction: discord.Interaction, 
                levels: str, exps: str = None, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            try:
                level_list = [int(level.strip()) for level in levels.split(",")]
                if exps:
                    exp_list = [int(exp.strip()) for exp in exps.split(",")]
                    exp_list.extend([0] * (len(level_list) - len(exp_list)))
                else:
                    exp_list = [0] * len(level_list)
            except ValueError:
                return await interaction.followup.send("Invalid format! Please use numbers separated by commas.", ephemeral=True)

            if not all(is_valid_value(level, 1, 500) for level in level_list):
                return await interaction.followup.send("All levels must be between 1 and 500!", ephemeral=True)
            
            if not all(is_valid_value(exp, 0, 1000000) for exp in exp_list):
                return await interaction.followup.send("All exp values must be between 0 and 1,000,000!", ephemeral=True)

            calculations = []
            total_exp = 0
            
            for level, exp in zip(level_list, exp_list):
                level_exp = self.calculate_exp(level) + exp
                total_exp += level_exp
                calculations.append(f"Level {level} ({exp:,} exp) = {level_exp:,} exp")

            final_level = 1
            while self.calculate_exp(final_level + 1) <= total_exp:
                final_level += 1
            
            remaining_exp = total_exp - self.calculate_exp(final_level)

            embed = discord.Embed(
                title="Mee6 Level Addition Calculator",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Calculations", 
                value="\n".join(calculations), 
                inline=False
            )

            main_info = (
                f"Total EXP: {total_exp:,}\n"
                f"Final Level: {final_level}\n"
                f"Remaining EXP: {remaining_exp:,}\n"
                f"Progress: {remaining_exp:,}/{(self.calculate_exp(final_level + 1) - self.calculate_exp(final_level)):,} exp"
            )

            embed.add_field(
                name="Result", 
                value=main_info, 
                inline=False
            )

            await interaction.followup.send(embed=embed)

        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="update")
    async def update(self, interaction: discord.Interaction, level: int, exp: int):
        await interaction.response.defer()
        try:
            member_info = load_member_info()
            user_id = str(interaction.user.id)
            
            if user_id not in member_info:
                member_info[user_id] = {}
         
            if "MEE6Plan" not in member_info[user_id]:
                member_info[user_id]["MEE6Plan"] = {
                    "enabled": True,
                    "history": []
                }
            
            history = member_info[user_id]["MEE6Plan"]["history"]
            now = datetime.now().timestamp()

            if history:
                last_entry = history[-1]
                is_valid, message = self.validate_exp_gain(
                    last_entry["level"], 
                    last_entry["exp"], 
                    level, 
                    exp,
                    now - last_entry["timestamp"]
                )
                
                if not is_valid:
                    view = ConfirmView()
                    await interaction.followup.send(message, view=view)
                    
                    await view.wait()
                    if not view.value:
                        await interaction.followup.send("Update cancelled.")
                        return
            
            hundred_days_ago = now - (100 * 24 * 3600)
            member_info[user_id]["MEE6Plan"]["history"] = [
                entry for entry in history
                if entry["timestamp"] >= hundred_days_ago
            ]
            
            member_info[user_id]["MEE6Plan"]["history"].append({
                "timestamp": now,
                "level": level,
                "exp": exp
            })
            
            save_member_info(member_info)
            await interaction.followup.send("Progress updated! Use `/mee6 show` to see your progress.")
            
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="show")
    async def show(self, interaction: discord.Interaction, target_level: int = None):
        await interaction.response.defer()
        try:
            if target_level is not None and not is_valid_value(target_level, 1, 500):
                return await interaction.followup.send("Target level must be between 1 and 500!", ephemeral=True)
                
            member_info = load_member_info()
            user_id = str(interaction.user.id)
            
            if user_id not in member_info or "MEE6Plan" not in member_info[user_id]:
                return await interaction.followup.send("No tracking data! Use `/mee6 update` first.")
            
            history = member_info[user_id]["MEE6Plan"]["history"]
            
            if len(history) < 2:
                return await interaction.followup.send("Not enough data yet. Please provide at least two updates!")
            
            first = history[0]
            last = history[-1]
            days = (last["timestamp"] - first["timestamp"]) / (24 * 3600)
            
            total_exp_gained = self.calculate_exp(last["level"]) + last["exp"] - (self.calculate_exp(first["level"]) + first["exp"])
            daily_rate = int(total_exp_gained / days) if days > 0 else total_exp_gained
            
            embed = discord.Embed(title="MEE6 Level Progress", color=discord.Color.blue())
            embed.add_field(name="Current Progress", value=
                f"Starting Level: {first['level']}\n"
                f"Current Level: {last['level']}\n"
                f"Daily EXP Rate: {daily_rate:,}", inline=False)

            now = datetime.now().timestamp()
            
            daily_rates = []
            for i in range(len(history) - 1):
                curr = history[i]
                next_entry = history[i + 1]
                days_between = (next_entry["timestamp"] - curr["timestamp"]) / (24 * 3600)
                if days_between > 0:
                    exp_gained = (self.calculate_exp(next_entry["level"]) + next_entry["exp"]) - (self.calculate_exp(curr["level"]) + curr["exp"])
                    daily_rates.append((next_entry["timestamp"], exp_gained / days_between))

            if target_level:
                if target_level <= last["level"]:
                    embed.add_field(name="Target Level Status", 
                                  value=f"You have already achieved level {target_level}!", 
                                  inline=False)
                else:
                    current_total_exp = self.calculate_exp(last["level"]) + last["exp"]
                    target_exp = self.calculate_exp(target_level)
                    exp_needed = target_exp - current_total_exp
                    days_needed = exp_needed / daily_rate if daily_rate > 0 else float('inf')
                    eta = datetime.now() + timedelta(days=days_needed) if days_needed != float('inf') else None
                    
                    status = f"Level {target_level}: "
                    if eta:
                        status += f"<t:{int(eta.timestamp())}:R>"
                    else:
                        status += "Unknown"
                    
                    embed.add_field(name="Target Level Status", value=status, inline=False)

            milestones = [15, 25, 30, 40, 69, 100, 125, 150]
            milestone_text = ""
            current_total_exp = self.calculate_exp(last["level"]) + last["exp"]
            
            for milestone in milestones:
                if milestone <= last["level"]:
                    continue
                milestone_exp = self.calculate_exp(milestone)
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

            current_total_exp = self.calculate_exp(last["level"]) + last["exp"]
            future_estimates = ""
            periods = [(7, "7 days"), (30, "30 days"), (100, "100 days"), (365, "1 year")]
            
            for days_ahead, label in periods:
                future_exp = current_total_exp + (daily_rate * days_ahead)
                future_level = 1
                while self.calculate_exp(future_level + 1) <= future_exp:
                    future_level += 1
                remaining_exp = future_exp - self.calculate_exp(future_level)
                future_estimates += f"{label}: Level {future_level} + {remaining_exp:,.0f} exp\n"

            if future_estimates:
                embed.add_field(name="Estimated Progress", value=future_estimates, inline=False)

            plt.clf()
            fourteen_days_ago = now - (14 * 24 * 3600)
            recent_history = [(h["timestamp"], self.calculate_exp(h["level"]) + h["exp"]) 
                            for h in history 
                            if h["timestamp"] >= fourteen_days_ago]
            
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

class Mee6Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(Mee6CommandGroup())

async def setup(bot):
    await bot.add_cog(Mee6Cog(bot))