from main import open_file, save_file, store_log, handle_logs, parse_duration, get_next_report_id, blacklist_user, is_user_blacklisted, botAdmins

import discord
from discord.ext import commands
from discord import app_commands

import asyncio, random, time, traceback
from datetime import datetime, timezone

class ReportButtons(discord.ui.View):
    def __init__(self, report_id, reports_data, message):
        super().__init__(timeout=None)
        self.report_id = str(report_id)
        self.reports_data = reports_data
        self.message = message

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.",ephemeral=True,)
            return

        report["Status"] = "Accepted"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been accepted!")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Accepted\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been accepted.", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defe
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        if report["Status"] != "Open":
            await interaction.followup.send(f"Ticket ID {self.report_id} has already been processed.", ephemeral=True)
            return

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.red(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)
        await interaction.followup.send(f"Ticket ID {self.report_id} has been declined.", ephemeral=True)

    @discord.ui.button(label="Blacklist", style=discord.ButtonStyle.secondary)
    async def blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        report = self.reports_data.get(self.report_id)
        if not report:
            await interaction.followup.send(f"Report ID {self.report_id} not found.", ephemeral=True)
            return

        blacklist_user(interaction.user.id)

        report["Status"] = "Declined"
        report["Reviewed by"] = interaction.user.display_name
        save_file("reports.json", self.reports_data)
        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} for user: {report['User']} has been declined.\nYou are now ticket blacklisted.")

        await interaction.followup.send(f"The report has been declined and the reported is now blacklisted.", ephemeral=True)

        reporter = interaction.guild.get_member(report["Reporter"])
        if reporter:
            await reporter.send(f"Your ticket ID: {self.report_id} has been declined and you have been blacklisted.")

        embed = discord.Embed(
            title=f"Report ID: {self.report_id}",
            description=f"**Type:** {report['Type']}\n**Proof:** {report['Proof']}\n**Reported User:** {report['User']}\n**Other:** {report['Other']}\n**Status:** Declined (Blacklisted)\n**Reviewed by:** {interaction.user.display_name} ({interaction.user.id})",
            color=discord.Color.greyple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Reported by {report['Reporter'].user.display_name}", icon_url=report['Reporter'].avatar.url)

        await self.message.edit(embed=embed, view=None)

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

    @app_commands.command(name="error_test", description="Demonstrates intentional error generation")
    async def error_test(self, interaction: discord.Interaction):
        error_list = []
        try:
            print(error_list[0]) 
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="report", description="Report an in game rule breaker")
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Auto Win", value="Auto Win"),
            app_commands.Choice(name="Ability Spam", value="Ability Spam"),
            app_commands.Choice(name="Alchemist Auto Brew", value="Alchemist Auto Brew"),
            app_commands.Choice(name="Bob Auto Farm", value="Bob Auto Farm"),
            app_commands.Choice(name="Bypassing", value="Bypassing"),
            app_commands.Choice(name="False Votekick", value="False Votekick"),
            app_commands.Choice(name="Flight", value="Flight"),
            app_commands.Choice(name="Framing Exploit", value="Framing Exploit"),
            app_commands.Choice(name="Item Vacuum", value="Item Vacuum"),
            app_commands.Choice(name="Kick Exploit", value="Kick Exploit"),
            app_commands.Choice(name="Godmode", value="Godmode"),
            app_commands.Choice(name="NSFW", value="NSFW"),
            app_commands.Choice(name="Reach", value="Reach"),
            app_commands.Choice(name="Rhythm Ability Spam", value="Rhythm Ability Spam"),
            app_commands.Choice(name="Slap Aura", value="Slap Aura"),
            app_commands.Choice(name="Slap Auto Farm", value="Slap Auto Farm"),
            app_commands.Choice(name="Slapple Farm", value="Slapple Farm"),
            app_commands.Choice(name="Teleport", value="Teleport"),
            app_commands.Choice(name="Toxicity", value="Toxicity"),
            app_commands.Choice(name="Trap Auto Farm", value="Trap Auto Farm"),
            app_commands.Choice(name="Anti Acid/Lava", value="Anti Acid/Lava"),
            app_commands.Choice(name="Anti Ragdoll", value="Anti Ragdoll"),
            app_commands.Choice(name="Anti Void", value="Anti Void"),
            app_commands.Choice(name="Other", value="Other"),
        ]
    )
    @app_commands.describe(
        type="The type of exploit they used",
        proof="Use medal or youtube and post the link",
        user="The user to report",
        other="Any other information needed)",
    )
    async def report(self, interaction: discord.Interaction, type: str, proof: str, user: str, other: str):
        await interaction.response.defer(ephemeral=True)
        try:
            member_info = open_file("info/member_info.json")
            reporter_id = str(interaction.user.id)

            if member_info.get(reporter_id, {}).get("TicketBlacklist"):
                await interaction.followup.send("You are blacklisted from submitting reports.", ephemeral=True)
                return

            reports_data = open_file("info/reports.json")
            report_id = get_next_report_id(reports_data)

            timestamp = datetime.now().isoformat()
            new_report = {
                "Status": "Open",
                "Reporter": reporter_id,
                "User": user,
                "Proof": proof,
                "Type": type,
                "Other": other,
                "Timestamp": timestamp,
            }

            reports_data[str(report_id)] = new_report
            save_file("reports.json", reports_data)

            report_embed = discord.Embed(
                title=f"Report ID: {report_id}",
                description=f"**Type:** {type}\n**Proof:** {proof}\n**Reported User:** {user}\n**Other:** {other}",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )

            report_embed.set_footer(text=f"Reported by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

            guild = interaction.client.get_guild(1279160584662679673)
            report_channel = guild.get_channel(1292649491203096646)
            if report_channel:
                message = await report_channel.send(embed=report_embed, view=None)
                await message.edit(view=ReportButtons(report_id, reports_data, message))
                await interaction.followup.send(f"Your report has been submitted for {user}.")
            else:
                await interaction.followup.send("Report channel not found.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)
        
async def setup(bot):
    await bot.add_cog(MiscCog(bot))