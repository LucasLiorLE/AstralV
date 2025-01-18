from bot_utils import (
    handle_logs, 
    store_log,
    open_file,
    save_file,
    parse_duration
)

from main import botAdmins

import discord
from discord.ext import commands
from discord import app_commands

import asyncio, random, time, traceback
from datetime import datetime, timezone

async def end_giveaway(self, interaction: discord.Interaction, giveaway_id: str, server_id: str):
    try:
        server_info = open_file("info/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            await interaction.followup.send("The specified giveaway could not be found.", ephemeral=True)
            return

        duration = giveaway['endTime'] - giveaway['startTime']
        await asyncio.sleep(duration)

        server_info = open_file("info/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            return

        participants = giveaway.get("participants", [])
        winners_count = giveaway.get("winners", 1)

        if participants:
            winner_list = random.sample(participants, k=min(winners_count, len(participants)))
            formatted_winners = ', '.join(f'<@{winner}>' for winner in winner_list)
        else:
            formatted_winners = "No participants."

        embed = discord.Embed(
            title=f"🎉 Giveaway Ended: {giveaway['prize']} 🎉",
            description=f"**Winners:** {formatted_winners}",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"ID: {giveaway_id}")

        channel_id = giveaway.get("channel_id")
        message_id = giveaway.get("message_id")
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            await interaction.followup.send("Giveaway channel could not be found.", ephemeral=True)
            return

        message = await channel.fetch_message(message_id)
        if not message:
            await interaction.followup.send("Giveaway message could not be found.", ephemeral=True)
            return

        await message.reply(embed=embed)

    except Exception as e:
        await handle_logs(interaction, e)

class GiveawayGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="giveaway", description="Giveaway related commands")

    @app_commands.command(name="reroll", description="Rerolls a giveaway's winner/s")
    @app_commands.describe(id="ID of the giveaway", winners="Number of winners to reroll")
    async def greroll(self, interaction: discord.Interaction, id: str, winners: int):
        await interaction.response.defer()
        try:
            server_id = str(interaction.guild_id)
            server_info = open_file("info/server_info.json")
            
            if server_id not in server_info or "giveaways" not in server_info[server_id]:
                return await interaction.followup.send("No giveaways found for this server.", ephemeral=True)

            giveaways = server_info[server_id]["giveaways"]
            if id not in giveaways:
                return await interaction.followup.send(f"Giveaway with ID `{id}` not found.", ephemeral=True)

            giveaway = giveaways[id]

            participants = giveaway.get("participants", [])
            if len(participants) < winners:
                return await interaction.followup.send(
                    "Not enough participants to reroll the specified number of winners.", ephemeral=True
                )

            rerolled_winners = random.sample(participants, winners)
            formatted_winners = ", ".join([f"<@{user}>" for user in rerolled_winners])

            embed = discord.Embed(
                title=f"🎉 Giveaway Rerolled: {giveaway['prize']} 🎉",
                description=f"**New Winners:** {formatted_winners}",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"ID: {id}")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="create", description="Creates a giveaway")
    @app_commands.describe(
        prize="The prize of the giveaway",
        duration="Duration of the giveaway. Ex. 1d6h30m15s",
        description="An optional description to add",
        requirement="A role required to join the giveaway",
        winners="The number of people who will win the giveaway"
    )
    async def ggiveaway(self, interaction: discord.Interaction, prize: str, duration: str, description: str = None, requirement: discord.Role = None, winners: int = 1):
        await interaction.response.defer()
        try:
            server_info = open_file("info/server_info.json")
            duration_timedelta = parse_duration(duration)
            if duration_timedelta is None or duration_timedelta.total_seconds() <= 0:
                raise ValueError("Duration must be greater than 0.")

            start_time = int(time.time())
            end_time = start_time + int(duration_timedelta.total_seconds())

            giveaway_id = str(int(time.time()))

            server_id = str(interaction.guild.id)
            if server_id not in server_info:
                server_info[server_id] = {}

            if "giveaways" not in server_info[server_id]:
                server_info[server_id]["giveaways"] = {}

            server_info[server_id]["giveaways"][giveaway_id] = {
                "host": interaction.user.id,
                "prize": prize,
                "startTime": start_time,
                "endTime": end_time,
                "description": description or "No description provided.",
                "requirement": requirement.id if requirement else None,
                "winners": winners,
                "participants": [],
            }
            save_file("info/server_info.json", server_info)

            embed = discord.Embed(
                title=f"🎉 {prize} 🎉",
                description=(f"{description}\n\n" if description else "") +
                f"**Ends at**: <t:{end_time}:T> (<t:{end_time}:R>)\n" +
                (f"**Requirement**: {requirement.mention}\n" if requirement else "")
            )
            embed.set_footer(text=f"{winners} Winner(s)")
            embed.set_author(name=f"ID: {giveaway_id} | Hosted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

            view = GiveawayButtonView(giveaway_id, server_id)

            message = await interaction.followup.send(embed=embed, view=view)
            server_info[server_id]["giveaways"][giveaway_id]["channel_id"] = interaction.channel_id
            server_info[server_id]["giveaways"][giveaway_id]["message_id"] = message.id
            save_file("info/server_info.json", server_info)

            asyncio.create_task(end_giveaway(interaction, giveaway_id, server_id))
            
        except Exception as e:
            await handle_logs(interaction, e)

class GiveawayButtonView(discord.ui.View):
    def __init__(self, giveaway_id: str, server_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.server_id = server_id

    async def disable_buttons(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Enter/Leave Giveaway", style=discord.ButtonStyle.blurple)
    async def enter_leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            server_info = open_file("info/server_info.json")
            server_info.setdefault(self.server_id, {}).setdefault("giveaways", {})

            if self.giveaway_id not in server_info[self.server_id]["giveaways"]:
                raise KeyError(f"Giveaway ID {self.giveaway_id} not found in server {self.server_id}.")

            giveaway = server_info[self.server_id]["giveaways"][self.giveaway_id]
            participants = giveaway["participants"]

            if interaction.user.id in participants:
                participants.remove(interaction.user.id)
                message = "You have left the giveaway."
            else:
                participants.append(interaction.user.id)
                message = "You have joined the giveaway."

            embed = interaction.message.embeds[0]
            description_lines = embed.description.split("\n")
            for i, line in enumerate(description_lines):
                if line.startswith("**Participants:**"):
                    description_lines[i] = f"**Participants:** {len(participants)}"
                    break
            else:
                description_lines.append(f"**Participants:** {len(participants)}")
            
            embed.description = "\n".join(description_lines)

            save_file("info/server_info.json", server_info)

            await interaction.message.edit(embed=embed, view=self)

            await interaction.response.send_message(content=message, ephemeral=True)

        except KeyError as ke:
            await interaction.response.send_message("An error occurred: Giveaway not found.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

class AlertGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="alert", description="Used for updates, and allows you to follow along!")

    @app_commands.command(name="follow", description="Subscribe or unsubscribe from updates")
    async def alert_follow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            member_info = open_file("info/member_info.json")
            user = interaction.user.id

            if user not in member_info:
                member_info[user] = {
                    "subscribed": 0
                }
            
            if member_info[user]["subscribed"] == 0:
                member_info[user]["subscribed"] = 1
                await interaction.followup.send("You are now subscribed to updates!")
            else:
                member_info[user]["subscribed"] = 0
                await interaction.followup.send("You are now unsubscribed from updates!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="send", description="Sends an update to all subscribed users")
    @app_commands.describe(
        type="The type of alert",
        description="Provide a brief description of what's going on",
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Alert", value="alert"),
            app_commands.Choice(name="Update", value="update"),
            app_commands.Choice(name="Warning", value="warning")
        ]
    )
    async def alert_send(self, interaction: discord.Interaction, type: str, description: str):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                await interaction.followup.send("You do not have permission to use this command.")
                return


            alertIDs = []
            member_info = open_file("info/member_info.json")
            for member in member_info:
                if member_info[member]["subscribed"] == 1:
                    alertIDs.append(member)


            embed=discord.Embed(
                title="New update!" if type.value == "alert" else "ALERT" if type.value == "alert" else "WARNING",
                description=description
            )
        except Exception as e:
            await handle_logs(interaction, e)

class MiscCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(AlertGroup())
        self.bot.tree.add_command(GiveawayGroup())

    @app_commands.command(name="afk", description="AFK and set a status of why.")
    @app_commands.describe(reason="Your reason to AFK")
    async def afk(self, interaction: discord.Interaction, reason: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = str(interaction.user.id)
            server_id = str(interaction.guild.id)

            server_info = open_file("info/server_info.json")
            afk_data = server_info.setdefault("afk", {}).setdefault(server_id, {})

            if user_id in afk_data:
                await interaction.followup.send("You are already AFK! Talk if you want to unAFK!")
                return

            afk_data[user_id] = {
                "reason": reason,
                "time": datetime.now(timezone.utc).isoformat(),
                "original_name": interaction.user.display_name
            }
            
            save_file("info/server_info.json", server_info)

            await interaction.user.edit(nick=f"[AFK] {interaction.user.display_name}")
            await interaction.followup.send(f"You are now AFK. Reason: {reason or 'None'}")
        except Exception as e:
            await handle_logs(interaction, e)
            
async def setup(bot):
    await bot.add_cog(MiscCog(bot))