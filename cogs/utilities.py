import time, asyncio
from datetime import datetime, timezone

from bot_utils import (
    handle_logs,
    save_file,
    open_file,
    load_commands,
    parse_duration
)

import discord
from discord.ext import commands
from discord import app_commands

class ReminderGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="reminder", description="Set and manage reminders")

        load_commands(self.commands, "reminder")

    @app_commands.command(name="add")
    async def add(self, interaction: discord.Interaction, duration: str, reminder: str):
        await interaction.response.defer()
        try:
            duration_delta = parse_duration(duration)
            if not duration_delta:
                await interaction.followup.send("Invalid time format. Use format like: 1d2h3m4s")
                return

            if duration_delta.total_seconds() < 1:
                await interaction.followup.send("Reminder time must be greater than 0 seconds.")
                return

            if duration_delta.total_seconds() > 2592000:  # 30 days
                await interaction.followup.send("Reminder time cannot be longer than 30 days.")
                return

            member_info = open_file("storage/member_info.json")
            user_id = str(interaction.user.id)
            
            if user_id not in member_info:
                member_info[user_id] = {}
            
            if "reminders" not in member_info[user_id]:
                member_info[user_id]["reminders"] = {}

            current_time = int(time.time())
            reminder_id = str(current_time)
            end_time = current_time + int(duration_delta.total_seconds())

            member_info[user_id]["reminders"][reminder_id] = {
                "message": reminder,
                "end_time": end_time
            }
            
            save_file("storage/member_info.json", member_info)
            
            await interaction.followup.send(f"<:check:1292269189536682004> Reminder set! I'll remind you about: {reminder} <t:{end_time}:R>")
            
            await asyncio.sleep(duration_delta.total_seconds())
            
            member_info = open_file("storage/member_info.json")
            if user_id in member_info and "reminders" in member_info[user_id] and reminder_id in member_info[user_id]["reminders"]:
                try:
                    await interaction.user.send(f"**Reminder:** {reminder}")
                except discord.Forbidden:
                    await interaction.channel.send(
                        f"{interaction.user.mention}, **Reminder:** {reminder}\n"
                        "(I tried to DM you but couldn't. Enable DMs for better reminder delivery)"
                    )
                
                del member_info[user_id]["reminders"][reminder_id]
                save_file("storage/member_info.json", member_info)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="list") 
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            member_info = open_file("storage/member_info.json")
            user_id = str(interaction.user.id)
            
            if user_id not in member_info or "reminders" not in member_info[user_id] or not member_info[user_id]["reminders"]:
                await interaction.followup.send("You have no active reminders.")
                return

            embed = discord.Embed(title="Your Active Reminders", color=discord.Color.blue())
            
            for rid, rinfo in member_info[user_id]["reminders"].items():
                embed.add_field(
                    name=f"ID: {rid}",
                    value=f"Message: {rinfo['message']}\nTime: <t:{rinfo['end_time']}:R>",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="remove")
    async def remove(self, interaction: discord.Interaction, id: str):
        await interaction.response.defer()
        try:
            member_info = open_file("storage/member_info.json")
            user_id = str(interaction.user.id)
            
            if (user_id not in member_info or 
                "reminders" not in member_info[user_id] or 
                id not in member_info[user_id]["reminders"]):
                await interaction.followup.send("Reminder not found.")
                return

            reminder = member_info[user_id]["reminders"][id]
            del member_info[user_id]["reminders"][id]
            save_file("storage/member_info.json", member_info)

            await interaction.followup.send(
                f"<:check:1292269189536682004> Removed reminder: {reminder['message']}", 
            )

        except Exception as e:
            await handle_logs(interaction, e)

class UtilCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(ReminderGroup())

        load_commands(self.__cog_app_commands__, "util")

    @app_commands.command(name="afk")
    async def afk(self, interaction: discord.Interaction, reason: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            server_id = str(interaction.guild.id)

            server_info = open_file("storage/server_info.json")
            afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})

            if user_id in afk_data:
                await interaction.followup.send("You are already AFK! Talk if you want to unAFK!")
                return

            afk_data[user_id] = {
                "reason": reason,
                "time": datetime.now(timezone.utc).isoformat(),
                "original_name": interaction.user.display_name
            }
            
            save_file("storage/server_info.json", server_info)

            await interaction.user.edit(nick=f"[AFK] {interaction.user.display_name}")
            await interaction.followup.send(f"You are now AFK. Reason: {reason or 'None'}")
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(UtilCog(bot))