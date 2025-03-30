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
    command_cooldown
)
import random
import time
from typing import List

class WorkCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="work", description="Economy work related commands")
        self.eco_path = "storage/economy/economy.json"
        self.jobs = {
            "Fast-Food Worker": {
                "description": "Work as a fast-food worker at McDonald's",
                "shiftsPerDay": 1,
                "minimumWage": 50000,
                "requiredShiftsBefore": 0,
                "item": "Burger"
            },
            "Cashier": {
                "description": "Work as a cashier at a grocery store",
                "shiftsPerDay": 1,
                "minimumWage": 60000,
                "requiredShiftsBefore": 5
            },
            "Delivery Driver": {
                "description": "Work as a delivery driver for a food delivery service",
                "shiftsPerDay": 1,
                "minimumWage": 70000,
                "requiredShiftsBefore": 10
            },
            "Janitor": {
                "description": "Work as a janitor at a school",
                "shiftsPerDay": 1,
                "minimumWage": 80000,
                "requiredShiftsBefore": 20
            },
            "Security Guard": {
                "description": "Work as a security guard at a mall",
                "shiftsPerDay": 2,
                "minimumWage": 90000,
                "requiredShiftsBefore": 30
            },
            "Construction Worker": {
                "description": "Work as a construction worker at a construction site",
                "shiftsPerDay": 2,
                "minimumWage": 100000,
                "requiredShiftsBefore": 40
            },
            "Banker": {
                "description": "Work as a banker at a bank",
                "shiftsPerDay": 2,
                "minimumWage": 120000,
                "requiredShiftsBefore": 50
            },
            "Teacher": {
                "description": "Work as a teacher at a school",
                "shiftsPerDay": 3,
                "minimumWage": 150000,
                "requiredShiftsBefore": 60
            },
            "Nurse": {
                "description": "Work as a nurse at a hospital",
                "shiftsPerDay": 3,
                "minimumWage": 180000,
                "requiredShiftsBefore": 70
            },
            "Police Officer": {
                "description": "Work as a police officer at a police station",
                "shiftsPerDay": 3,
                "minimumWage": 200000,
                "requiredShiftsBefore": 80
            },
            "Fireman": {
                "description": "Work as a fireman at a fire station",
                "shiftsPerDay": 3,
                "minimumWage": 200000,
                "requiredShiftsBefore": 80
            },
            "Mechanic": {
                "description": "Work as a mechanic at a garage",
                "shiftsPerDay": 3,
                "minimumWage": 200000,
                "requiredShiftsBefore": 80
            },
            "Engineer": {
                "description": "Work as an engineer at a tech company",
                "shiftsPerDay": 4,
                "minimumWage": 300000,
                "requiredShiftsBefore": 100
            },
            "Electrician": {
                "description": "Work as an electrician at an electrical company",
                "shiftsPerDay": 4,
                "minimumWage": 250000,
                "requiredShiftsBefore": 90
            },
            "Plumber": {
                "description": "Work as a plumber at a plumbing company",
                "shiftsPerDay": 4,
                "minimumWage": 250000,
                "requiredShiftsBefore": 90
            },
            "Carpenter": {
                "description": "Work as a carpenter at a construction site",
                "shiftsPerDay": 4,
                "minimumWage": 250000,
                "requiredShiftsBefore": 90
            },
            "Painter": {
                "description": "Work as a painter at a painting company",
                "shiftsPerDay": 4,
                "minimumWage": 250000,
                "requiredShiftsBefore": 90
            },
            "Doctor": {
                "description": "Work as a doctor at a hospital",
                "shiftsPerDay": 5,
                "minimumWage": 500000,
                "requiredShiftsBefore": 150
            },
            "Lawyer": {
                "description": "Work as a lawyer at a law firm",
                "shiftsPerDay": 5,
                "minimumWage": 450000,
                "requiredShiftsBefore": 150
            }
        }


    def update_job(self, user_id: str, job: str):
        check_user_stat(["work", "job"], user_id, None)
        check_user_stat(["work", "job_start_time"], user_id, 0)
        eco = open_json(self.eco_path)
        eco[user_id]["work"]["job"] = job
        eco[user_id]["work"]["job_start_time"] = int(time.time())
        eco[user_id]["work"]["daily_shifts"] = 0
        save_json(self.eco_path, eco)

    def update_work_stats(self, user_id: str, check: str, amount: int):
        check_user_stat(["work", check], user_id, 0)
        eco = open_json(self.eco_path)
        eco[user_id]["work"][check] += amount
        save_json(self.eco_path, eco)

    def check_weekly_quota(self, user_id: str, eco: dict) -> bool:
        check_user_stat(["work", "daily_shifts"], user_id, 0)
        check_user_stat(["work", "last_shift"], user_id, 0)
        check_user_stat(["work", "job"], user_id, None)
        check_user_stat(["work", "job_start_time"], user_id, 0)
        
        current_job = eco[user_id]["work"]["job"]
        if not current_job:
            return True
            
        job_info = self.jobs[current_job]
        required_shifts = job_info["shiftsPerDay"] * 7
        
        current_time = int(time.time())
        job_start_time = eco[user_id]["work"]["job_start_time"]
        if current_time - job_start_time < 604800:
            return True
        
        if eco[user_id]["work"]["daily_shifts"] < required_shifts:
            eco[user_id]["work"]["job"] = None
            eco[user_id]["work"]["daily_shifts"] = 0
            save_json(self.eco_path, eco)
            return False
            
        return True

    def update_daily_shifts(self, user_id: str, eco: dict):
        check_user_stat(["work", "daily_shifts"], user_id, 0)
        check_user_stat(["work", "last_shift"], user_id, 0)
        
        current_time = time.time()
        last_shift = eco[user_id]["work"]["last_shift"]
        
        if current_time - last_shift > 86400:
            eco[user_id]["work"]["daily_shifts"] = 0
            
        eco[user_id]["work"]["daily_shifts"] += 1
        eco[user_id]["work"]["last_shift"] = current_time
        save_json(self.eco_path, eco)

    async def get_available_jobs(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        check_user_stat(["work", "total_shifts"], user_id, 0)
        eco = open_json(self.eco_path)
        current_shifts = eco[user_id]["work"]["total_shifts"]
        
        choices = []
        for job_name, job_info in self.jobs.items():
            if (current.lower() in job_name.lower() and 
                current_shifts >= job_info["requiredShiftsBefore"]):
                choices.append(
                    app_commands.Choice(
                        name=f"{job_name} ({job_info['minimumWage']:,} coins/shift, {job_info['shiftsPerDay']} shifts/day)", 
                        value=job_name.lower()
                    )
                )
        return choices[:25]

    @app_commands.command(name="apply")
    @app_commands.autocomplete(job=get_available_jobs)
    async def work_apply(self, interaction: discord.Interaction, job: str):
        try:
            user_id = str(interaction.user.id)
            check_user_stat(["work", "shifts"], user_id, 0)
            eco = open_json(self.eco_path)
            
            job_title = job.title()
            job_lower = job.lower()
            
            actual_job = None
            for j in self.jobs:
                if j.lower() == job_lower:
                    actual_job = j
                    break
            
            if not actual_job:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Invalid Job",
                        description="That job doesn't exist! Use `/work list` to see available jobs.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            required_shifts = self.jobs[actual_job]["requiredShiftsBefore"]
            check_user_stat(["work", "total_shifts"], user_id, 0)
            current_shifts = eco[user_id]["work"]["total_shifts"]

            if current_shifts < required_shifts:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Not Enough Experience",
                        description=f"You need {required_shifts:,} shifts to apply for this job. You currently have {current_shifts:,} shifts.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            self.update_job(user_id, actual_job)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Job Application Successful!",
                    description=f"You are now working as a {actual_job}!",
                    color=discord.Color.green()
                )
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="list")
    async def work_list(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)
            check_user_stat(["work", "shifts"], user_id, 0)
            eco = open_json(self.eco_path)
            current_shifts = eco[user_id]["work"]["shifts"]

            jobs_list = []
            for job_name, job_info in self.jobs.items():
                status = "<:check:1292269189536682004>" if current_shifts >= job_info["requiredShiftsBefore"] else "❌"
                jobs_list.append(f"{status} {job_name} - {job_info['description']}")

            jobs_per_page = 5
            total_pages = (len(jobs_list) + jobs_per_page - 1) // jobs_per_page
            current_page = 0

            class JobListView(discord.ui.View):
                def __init__(self, jobs_list, total_pages, current_page):
                    super().__init__(timeout=None)
                    self.jobs_list = jobs_list
                    self.total_pages = total_pages
                    self.current_page = current_page

                @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
                async def previous_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if self.current_page > 0:
                        self.current_page -= 1
                        await self.update_message(button_interaction)

                @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
                async def next_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if self.current_page < self.total_pages - 1:
                        self.current_page += 1
                        await self.update_message(button_interaction)

                async def update_message(self, interaction):
                    start_idx = self.current_page * jobs_per_page
                    end_idx = min(start_idx + jobs_per_page, len(self.jobs_list))
                    current_jobs = self.jobs_list[start_idx:end_idx]

                    embed = discord.Embed(
                        title="Available Jobs",
                        description="\n".join(current_jobs),
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
                    await interaction.response.edit_message(embed=embed)

            start_idx = 0
            end_idx = min(jobs_per_page, len(jobs_list))
            current_jobs = jobs_list[start_idx:end_idx]

            embed = discord.Embed(
                title="Available Jobs",
                description="\n".join(current_jobs),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Page 1/{total_pages}")

            await interaction.response.send_message(
                embed=embed,
                view=JobListView(jobs_list, total_pages, current_page)
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="shift")
    async def work_shift(self, interaction: discord.Interaction):
        try:
            user_id = str(interaction.user.id)
            check_user_stat(["work", "job"], user_id, None)
            check_user_stat(["work", "shifts"], user_id, 0)
            check_user_stat(["work", "daily_shifts"], user_id, 0)
            check_user_stat(["work", "last_shift"], user_id, 0)
            check_user_stat(["work", "promotions"], user_id, 0)
            check_user_stat(["balance", "purse"], user_id, 0)
            check_user_stat(["commands"], user_id, {})
            check_user_stat(["commands", "work"], user_id, {"cooldown": 0, "uses": 0})
            check_user_stat(["inventory"], user_id, {})
            
            eco = open_json(self.eco_path)
            current_job = eco[user_id]["work"]["job"]
            
            if not current_job:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="No Job",
                        description="You need to apply for a job first! Use `/work list` to see available jobs.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            cooldown_result = command_cooldown(3600, "work", user_id)
            if isinstance(cooldown_result, tuple):
                done, cooldown = cooldown_result
                if not done:
                    return await send_cooldown(interaction, cooldown)

            if not self.check_weekly_quota(user_id, eco):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="You've Been Fired!",
                        description=f"You didn't complete enough shifts last week for your job as {current_job}. You need to apply for a new job.",
                        color=discord.Color.red()
                    ),
                    ephemeral=True
                )
                return

            job_info = self.jobs[current_job]
            base_earnings = job_info["minimumWage"]
            
            bonus = random.randint(0, 10)
            earnings = int(base_earnings * (1 + bonus/100))
            
            check_user_stat(["work", "total_shifts"], user_id, 0)
            eco[user_id]["work"]["total_shifts"] += 1
            self.update_daily_shifts(user_id, eco)
            
            check_user_stat(["work", "promotions"], user_id, 0)
            promotion_message = ""
            if eco[user_id]["work"]["promotions"] < 20 and random.random() < 0.05:
                eco[user_id]["work"]["promotions"] += 1
                current_promotions = eco[user_id]["work"]["promotions"]
                promotion_bonus = current_promotions * 0.01
                earnings = int(base_earnings * (1 + bonus/100 + promotion_bonus))
                promotion_message = f"\n🎉 Congratulations! You've been promoted! ({current_promotions}/20 promotions)"
            else:
                current_promotions = eco[user_id]["work"]["promotions"]
                if current_promotions > 0:
                    promotion_bonus = current_promotions * 0.01
                    earnings = int(base_earnings * (1 + bonus/100 + promotion_bonus))
            
            eco[user_id]["balance"]["purse"] += earnings
            
            item_reward = ""
            if "item" in job_info and random.random() < 0.05:
                item_name = job_info["item"]
                check_user_stat(["inventory", item_name], user_id, 0)
                eco = open_json(self.eco_path)
                eco[user_id]["inventory"][item_name] += 1
                item_reward = f"\nYou also received a {item_name}!"
            
            save_json(self.eco_path, eco)

            embed = discord.Embed(
                title=f"Work Shift Complete!",
                description=f"You worked a shift as a {current_job} and earned {earnings:,} coins!{promotion_message}{item_reward}",
                color=discord.Color.green()
            )
            
            if bonus > 5:
                embed.add_field(
                    name="Bonus",
                    value=f"You received a {bonus}% bonus for your hard work!",
                    inline=False
                )
            
            required_shifts = job_info["shiftsPerDay"] * 7
            current_shifts = eco[user_id]["work"]["daily_shifts"]
            embed.add_field(
                name="Weekly Progress",
                value=f"Shifts completed: {current_shifts}/{required_shifts}",
                inline=False
            )
            
            embed.add_field(
                name="Stats",
                value=f"Total Shifts: {eco[user_id]['work']['total_shifts']:,}\nPromotions: {current_promotions}/20 (+{current_promotions}% base pay)",
                inline=False
            )

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

class WorkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(WorkCommandGroup())

async def setup(bot):
    await bot.add_cog(WorkCog(bot))