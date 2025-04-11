from bot_utils import (
    parse_duration,
    open_json,
    save_json,
    handle_logs,
    DB
)

import time, asyncio, json
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands


class PollButtonView(discord.ui.View):
    def __init__(self, poll_id: str, options: list):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.options = options
        
        for i, option in enumerate(options):
            self.add_item(PollButton(i, option))
class PollButton(discord.ui.Button):
    def __init__(self, index: int, option: str):
        super().__init__(label=option, style=discord.ButtonStyle.blurple, custom_id=f"poll_option_{index}")
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        db = DB()
        try:
            poll_id = int(self.view.poll_id)

            db.execute("DELETE FROM poll_votes WHERE poll_id = %s AND user_id = %s", (poll_id, interaction.user.id))
            db.execute("INSERT INTO poll_votes (poll_id, user_id, option_index) VALUES (%s, %s, %s)", (poll_id, interaction.user.id, self.index))

            votes = db.fetch_all("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = %s GROUP BY option_index", (poll_id,))
            vote_map = {row["option_index"]: row["count"] for row in votes}
            total = sum(vote_map.values())

            vote_counts = []
            for i, opt in enumerate(self.view.options):
                count = vote_map.get(i, 0)
                percent = (count / total * 100) if total > 0 else 0
                vote_counts.append(f"**{opt}**: {count} votes ({percent:.1f}%)")

            embed = interaction.message.embeds[0]
            lines = embed.description.split("\n")
            embed.description = f"{lines[0]}\n{lines[1]}\n\n" + "\n".join(vote_counts)

            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception as e:
            await handle_logs(interaction, e)

class PollButtonView(discord.ui.View):
    def __init__(self, poll_id: str, options: list):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.options = options
        for i, option in enumerate(options):
            self.add_item(PollButton(i, option))

async def end_poll(bot: commands.Bot, poll_id: int):
    db = DB()
    await asyncio.sleep(1)
    try:
        poll = db.fetch_all("SELECT * FROM polls WHERE id = %s", (poll_id,))
        if not poll:
            return
        poll = poll[0]
        wait_time = poll["end_time"] - int(time.time())
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        options = json.loads(poll["options"])
        votes = db.fetch_all("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = %s GROUP BY option_index", (poll_id,))
        vote_map = {row["option_index"]: row["count"] for row in votes}
        total = sum(vote_map.values())

        vote_counts = [f"{opt}: {vote_map.get(i, 0)} votes ({(vote_map.get(i, 0) / total * 100) if total else 0:.1f}%)" for i, opt in enumerate(options)]

        embed = discord.Embed(
            title=f"📊 Poll Ended: {poll['question']}",
            description="\n".join(vote_counts),
            color=discord.Color.red()
        )
        embed.set_footer(text=f"ID: {poll_id}")

        channel = await bot.fetch_channel(poll["channel_id"])
        message = await channel.fetch_message(poll["message_id"])

        view = PollButtonView(poll_id=str(poll_id), options=options)
        for item in view.children:
            item.disabled = True

        await message.edit(embed=embed, view=view)
        await message.reply(embed=embed)

    except Exception as e:
        print("Error ending poll:", e)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class PollGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="poll", description="Create and manage polls", guild_only=False)
        DB().execute("""CREATE TABLE IF NOT EXISTS polls (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            start_time INT NOT NULL,
            end_time INT NOT NULL,
            message_id BIGINT,
            channel_id BIGINT
        )""")

        DB().execute("""CREATE TABLE IF NOT EXISTS poll_votes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            poll_id INT NOT NULL,
            user_id BIGINT NOT NULL,
            option_index INT NOT NULL,
            FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
        )""")

    @app_commands.command(name="create")
    async def create(self, interaction: discord.Interaction, question: str, options: str, duration: str):
        await interaction.response.defer()
        db = DB()
        try:
            parsed = parse_duration(duration)
            if not parsed:
                return await interaction.followup.send("Invalid duration!", ephemeral=True)

            option_list = [x.strip() for x in options.split(",") if x.strip()]
            if len(option_list) < 2:
                return await interaction.followup.send("Please provide at least 2 options.", ephemeral=True)

            start_time = int(time.time())
            end_time = start_time + int(parsed.total_seconds())

            poll_id = db.insert_record(
                "INSERT INTO polls (question, options, start_time, end_time) VALUES (%s, %s, %s, %s)",
                (question, json.dumps(option_list), start_time, end_time)
            )

            embed = discord.Embed(
                title="📊 " + question,
                description=f"Vote by clicking below!\nEnds <t:{end_time}:R>\n\n" +
                            "\n".join([f"**{o}**: 0 votes (0.0%)" for o in option_list]),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Poll ID: {poll_id} | Created by {interaction.user.display_name}")

            view = PollButtonView(str(poll_id), option_list)
            message = await interaction.followup.send(embed=embed, view=view)

            db.execute("UPDATE polls SET message_id = %s, channel_id = %s WHERE id = %s",
                       (message.id, interaction.channel_id, poll_id))

            asyncio.create_task(end_poll(interaction.client, poll_id))

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="view")
    async def view(self, interaction: discord.Interaction, id: int):
        db = DB()
        try:
            poll = db.fetch_all("SELECT * FROM polls WHERE id = %s", (id,))
            if not poll:
                return await interaction.response.send_message("Poll not found.", ephemeral=True)
            poll = poll[0]
            options = json.loads(poll["options"])
            now = int(time.time())
            status = "Ended" if now >= poll["end_time"] else "Active"

            votes = db.fetch_all("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = %s GROUP BY option_index", (id,))
            vote_map = {row["option_index"]: row["count"] for row in votes}
            total = sum(vote_map.values())
            vote_counts = [f"{opt}: {vote_map.get(i, 0)} votes ({(vote_map.get(i, 0) / total * 100) if total else 0:.1f}%)" for i, opt in enumerate(options)]

            embed = discord.Embed(
                title=f"📊 Poll {status}: {poll['question']}",
                description="\n".join(vote_counts),
                color=discord.Color.green() if status == "Active" else discord.Color.red()
            )

            embed.set_footer(text=f"Poll ID: {id}")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

class ReminderGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="reminder", description="Set and manage reminders")

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
            
            """
            if duration_delta.total_seconds() > 2592000:
                await interaction.followup.send("Reminder time cannot be longer than 30 days.")
                return
            """

            member_info = open_json("storage/member_info.json")
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
            
            save_json("storage/member_info.json", member_info)
            
            await interaction.followup.send(f"<:check:1292269189536682004> Reminder set! I'll remind you about: {reminder} <t:{end_time}:R>")
            
            await asyncio.sleep(duration_delta.total_seconds())
            
            member_info = open_json("storage/member_info.json")
            if user_id in member_info and "reminders" in member_info[user_id] and reminder_id in member_info[user_id]["reminders"]:
                try:
                    await interaction.user.send(f"**Reminder:** {reminder}")
                except discord.Forbidden:
                    await interaction.channel.send(
                        f"{interaction.user.mention}, **Reminder:** {reminder}\n"
                        "(I tried to DM you but couldn't. Enable DMs for better reminder delivery)"
                    )
                
                del member_info[user_id]["reminders"][reminder_id]
                save_json("storage/member_info.json", member_info)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="list")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            member_info = open_json("storage/member_info.json")
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
            member_info = open_json("storage/member_info.json")
            user_id = str(interaction.user.id)
            
            if (user_id not in member_info or 
                "reminders" not in member_info[user_id] or 
                id not in member_info[user_id]["reminders"]):
                await interaction.followup.send("Reminder not found.")
                return

            reminder = member_info[user_id]["reminders"][id]
            del member_info[user_id]["reminders"][id]
            save_json("storage/member_info.json", member_info)

            await interaction.followup.send(
                f"<:check:1292269189536682004> Removed reminder: {reminder['message']}", 
            )

        except Exception as e:
            await handle_logs(interaction, e)

class UtilCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(ReminderGroup())
        self.bot.tree.add_command(PollGroup())

    @app_commands.command(name="afk")
    async def afk(self, interaction: discord.Interaction, reason: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.guild:
                user_id = str(interaction.user.id)
                try:
                    server_id = str(interaction.guild.id)
                except AttributeError:
                    await interaction.followup.send("This command can only be used in a server.")
                    return

                server_info = open_json("storage/server_info.json")
                afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})

                if user_id in afk_data:
                    await interaction.followup.send("You are already AFK! Talk if you want to unAFK!")
                    return

                afk_data[user_id] = {
                    "reason": reason,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "original_name": interaction.user.display_name
                }
                
                save_json("storage/server_info.json", server_info)

                try:
                    await interaction.user.edit(nick=f"[AFK] {interaction.user.display_name}")
                    await interaction.followup.send(f"You are now AFK. Reason: {reason or 'None'}")
                except discord.errors.Forbidden:
                    await interaction.followup.send(f"You are now AFK. Reason: {reason or 'None'}\nI was unable to change your name.")
            else:
                await interaction.followup.send("You can only use this in a server!")
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(UtilCog(bot))