import discord
from discord.ext import commands, tasks
from discord import app_commands

from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from bot_utils import (
    handle_logs
)

MEMBER_INFO_PATH = Path(__file__).parents[2] / "storage" / "member_info.json"

def load_member_info():
    with open(MEMBER_INFO_PATH, 'r') as f:
        return json.load(f)

def save_member_info(data):
    with open(MEMBER_INFO_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def is_valid_value(value: int, min_val: int, max_val: int) -> bool:
    if value is None:
        return True
    try:
        return min_val <= value <= max_val
    except TypeError:
        return False

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

    @app_commands.command(name="plan")
    async def plan(self, interaction: discord.Interaction, 
                  current_level: int, target_level: int):
        await interaction.response.defer()
        try:
            member_info = load_member_info()
            user_id = str(interaction.user.id)
            
            if user_id not in member_info:
                member_info[user_id] = {"EXP": {"total": 0, "cooldown": 0}}
            
            member_info[user_id]["MEE6Plan"] = {
                "enabled": True,
                "start_level": current_level,
                "target_level": target_level,
                "last_update": datetime.now().timestamp(),
                "history": [{
                    "timestamp": datetime.now().timestamp(),
                    "level": current_level,
                    "exp": 0
                }]
            }
            
            save_member_info(member_info)
            
            await interaction.followup.send(
                "Level tracking enabled! I will DM you daily to ask for your current level and EXP."
            )
            
            await interaction.user.send(
                "What is your current level and EXP? Please enter level, EXP (ex. 100, 4000)"
            )
            
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="show")
    async def show(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            member_info = load_member_info()
            user_id = str(interaction.user.id)
            
            if user_id not in member_info or "MEE6Plan" not in member_info[user_id]:
                return await interaction.followup.send("No tracking plan set! Use `/mee6 plan` first.")
            
            plan = member_info[user_id]["MEE6Plan"]
            history = plan["history"]
            
            if len(history) < 2:
                return await interaction.followup.send("Not enough data yet. Please provide at least two updates!")
            
            first = history[0]
            last = history[-1]
            days = (last["timestamp"] - first["timestamp"]) / (24 * 3600)
            if days < 1:
                return await interaction.followup.send("Please wait at least 24 hours for progress tracking.")
            
            total_exp_gained = self.calculate_exp(last["level"]) + last["exp"] - (self.calculate_exp(first["level"]) + first["exp"])
            daily_rate = int(total_exp_gained / days)
            
            embed = discord.Embed(title="MEE6 Level Progress", color=discord.Color.blue())
            embed.add_field(name="Current Progress", value=
                f"Starting Level: {plan['start_level']}\n"
                f"Current Level: {last['level']}\n"
                f"Target Level: {plan['target_level']}\n"
                f"Daily EXP Rate: {daily_rate:,}", inline=False)
            
            milestones = [25, 50, 75, 100, 125, 150]
            predictions = []
            current_total_exp = self.calculate_exp(last["level"]) + last["exp"]
            
            for milestone in milestones:
                if milestone <= last["level"]:
                    continue
                    
                target_exp = self.calculate_exp(milestone)
                exp_needed = target_exp - current_total_exp
                days_needed = exp_needed / daily_rate
                completion_date = datetime.now() + timedelta(days=days_needed)
                predictions.append(f"Level {milestone}: <t:{int(completion_date.timestamp())}:D>")
            
            if predictions:
                embed.add_field(name="Estimated Achievement Dates", value="\n".join(predictions), inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as error:
            await handle_logs(interaction, error)

class Mee6Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(Mee6CommandGroup())
        self.check_updates.start()

    @tasks.loop(hours=24)
    async def check_updates(self):
        try:
            member_info = load_member_info()
            now = datetime.now().timestamp()
            
            for user_id, data in member_info.items():
                if "MEE6Plan" in data and data["MEE6Plan"]["enabled"]:
                    last_update = data["MEE6Plan"]["last_update"]
                    if now - last_update >= 24 * 3600:
                        try:
                            user = await self.bot.fetch_user(int(user_id))
                            await user.send("What is your current level and EXP? Please enter level, EXP (ex. 100, 4000)")
                        except:
                            continue
                            
        except Exception as error:
            print(f"Error in check_updates: {error}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not isinstance(message.channel, discord.DMChannel):
            return
            
        try:
            member_info = load_member_info()
            user_id = str(message.author.id)
            
            if user_id not in member_info or "MEE6Plan" not in member_info[user_id]:
                return
                
            try:
                level, exp = map(int, message.content.split(','))
            except:
                return
                
            member_info[user_id]["MEE6Plan"]["history"].append({
                "timestamp": datetime.now().timestamp(),
                "level": level,
                "exp": exp
            })
            member_info[user_id]["MEE6Plan"]["last_update"] = datetime.now().timestamp()
            
            save_member_info(member_info)
            await message.channel.send("Progress updated! Use `/mee6 show` to see your progress.")
            
        except Exception as error:
            print(f"Error in on_message: {error}")

async def setup(bot):
    await bot.add_cog(Mee6Cog(bot))