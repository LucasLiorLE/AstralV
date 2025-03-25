from bot_utils import (
    parse_duration,
    open_json,
    save_json,
    load_commands,
    handle_logs, 
)

from main import botAdmins

import discord
from discord.ext import commands
from discord import app_commands

import asyncio, random, time
from datetime import datetime

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
            server_info = open_json("storage/server_info.json")
            server_info.setdefault(self.server_id, {}).setdefault("giveaways", {})

            if self.giveaway_id not in server_info[self.server_id]["giveaways"]:
                raise KeyError(f"Giveaway ID {self.giveaway_id} not found in server {self.server_id}.")

            giveaway = server_info[self.server_id]["giveaways"][self.giveaway_id]
            participants = giveaway["participants"]

            required_role_id = giveaway.get("requirement")
            if required_role_id:
                member_roles = [role.id for role in interaction.user.roles]
                if required_role_id not in member_roles:
                    await interaction.response.send_message(
                        "You don't have the required role to enter this giveaway!", 
                        ephemeral=True
                    )
                    return

            if interaction.user.id in participants:
                try:
                    participants.remove(interaction.user.id)
                except ValueError:
                    pass
                message = "You have left the giveaway."
            else:
                participants.append(interaction.user.id)
                winners = giveaway.get("winners", 1)
                chance = (winners / len(participants)) * 100
                message = f"You have joined the giveaway! Your chance of winning is {chance:.1f}%"

            embed = interaction.message.embeds[0]
            description_lines = embed.description.split("\n")
            for i, line in enumerate(description_lines):
                if line.startswith("**Participants:**"):
                    description_lines[i] = f"**Participants:** {len(participants)}"
                    break
            else:
                description_lines.append(f"**Participants:** {len(participants)}")
            
            embed.description = "\n".join(description_lines)

            save_json("storage/server_info.json", server_info)

            await interaction.message.edit(embed=embed, view=self)
            await interaction.response.send_message(content=message, ephemeral=True)

        except KeyError:
            await interaction.response.send_message("An error occurred: Giveaway not found.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

async def end_giveaway(interaction: discord.Interaction, giveaway_id: str, server_id: str):
    try:
        server_info = open_json("storage/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            await interaction.followup.send("The specified giveaway could not be found.", ephemeral=True)
            return

        duration = giveaway['endTime'] - giveaway['startTime']
        await asyncio.sleep(duration)

        server_info = open_json("storage/server_info.json")
        giveaway = server_info.get(server_id, {}).get("giveaways", {}).get(giveaway_id)

        if not giveaway:
            return

        participants = giveaway.get("participants", [])
        winners_count = giveaway.get("winners", 1)

        if not participants:
            formatted_winners = "No one entered the giveaway!"
        else:
            winner_list = random.sample(participants, k=min(winners_count, len(participants)))
            formatted_winners = ', '.join(f'<@{winner}>' for winner in winner_list)

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
        
        load_commands(self.commands, "giveaway")
        for command in self.commands:
            command.guild_only = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("Giveaway commands can only be used within a server!", ephemeral=True)
            return False
        return True

    @app_commands.command(name="reroll")
    async def greroll(self, interaction: discord.Interaction, id: str, winners: int):
        await interaction.response.defer()
        try:
            server_id = str(interaction.guild_id)
            server_info = open_json("storage/server_info.json")
            
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

    @app_commands.command(name="create")
    async def ggiveaway(self, interaction: discord.Interaction, prize: str, duration: str, description: str = None, requirement: discord.Role = None, winners: int = 1):
        await interaction.response.defer()
        try:
            server_info = open_json("storage/server_info.json")
            duration_timedelta = parse_duration(duration)

            if duration_timedelta is None or duration_timedelta.total_seconds() <= 0:
                return await interaction.followup.send("Invalid duration specified. Please use a valid format (e.g., `1h`, `30m`, `2d`).", ephemeral=True)
            if winners <= 0:
                return await interaction.followup.send("Number of winners must be at least 1.", ephemeral=True)

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
            save_json("storage/server_info.json", server_info)

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
            save_json("storage/server_info.json", server_info)

            asyncio.create_task(end_giveaway(interaction, giveaway_id, server_id))
            
        except Exception as e:
            await handle_logs(interaction, e)

class AlertGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="alert", description="Used for updates, and allows you to follow along!")
        self.bot = bot
        load_commands(self.commands, "alert")

    @app_commands.command(name="follow")
    async def alert_follow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            member_info = open_json("storage/member_info.json")
            user = str(interaction.user.id)

            if user not in member_info:
                member_info[user] = {
                    "subscribed": 0,
                    "check_latest_alert": 0
                }
            
            if member_info[user].get("subscribed", 0) == 0:
                member_info[user]["subscribed"] = 1
                await interaction.followup.send("You are now subscribed to updates!")
            else:
                member_info[user]["subscribed"] = 0
                await interaction.followup.send("You are now unsubscribed from updates!")
            
            save_json("storage/member_info.json", member_info)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="send") 
    async def alert_send(self, interaction: discord.Interaction, type: str, description: str):
        await interaction.response.defer()
        try:
            if interaction.user.id not in botAdmins:
                await interaction.followup.send("You do not have permission to use this command.")
                return

            member_info = open_json("storage/member_info.json")
            memory = open_json("storage/memory.json")
            
            if "alerts" not in memory:
                memory["alerts"] = {"last_id": 0}

            next_id = str(memory["alerts"].get("last_id", 0) + 1)
            memory["alerts"]["last_id"] = int(next_id)

            memory["alerts"][next_id] = {
                "type": type,
                "description": description,
                "timestamp": int(time.time())
            }

            for member_id in member_info:
                if member_info[member_id].get("subscribed", 0) == 1:
                    member_info[member_id]["latest_alert_id"] = next_id

            save_json("storage/memory.json", memory)
            save_json("storage/member_info.json", member_info)

            await interaction.followup.send(f"Alert sent successfully with ID: {next_id}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="check")
    async def alert_check(self, interaction: discord.Interaction, id: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            member_info = open_json("storage/member_info.json")
            memory = open_json("storage/memory.json")
            
            if "alerts" not in memory:
                await interaction.followup.send("No alerts found.")
                return

            if id is None:
                id = str(memory["alerts"].get("last_id", 0))
                if id == "0":
                    await interaction.followup.send("No alerts found.")
                    return

            if id not in memory["alerts"] or id == "last_id":
                await interaction.followup.send(f"Alert with ID {id} not found.")
                return

            alert = memory["alerts"][id]
            color_map = {
                "alert": discord.Color.red(),
                "update": 0xDA8EE7,
                "warning": discord.Color.yellow()
            }

            embed = discord.Embed(
                title=alert["type"].title(),
                description=alert["description"],
                color=color_map.get(alert["type"], 0xDA8EE7),
                timestamp=datetime.fromtimestamp(alert["timestamp"])
            )
            embed.set_footer(text=f"Alert ID: {id}")
            
            latest_id = str(memory["alerts"]["last_id"])
            if id != latest_id:
                embed.add_field(
                    name="Note",
                    value=f"This is an older alert. Latest alert ID is {latest_id}.",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    async def send_alert_message(self, interaction: discord.Interaction):
        await asyncio.sleep(0.5)
        try:
            memory = open_json("storage/memory.json")
            latest_id = memory["alerts"]["last_id"]
            await interaction.followup.send(
                f"<@{interaction.user.id}>, you have a new alert! (ID: {latest_id})\n"
                "Use `/alert check` to view it, or specify an ID with `/alert check id:number` to view older alerts."
            )
        except:
            pass

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
        try:
            bot_data = open_json("storage/bot_data.json")
            poll = bot_data.setdefault("polls", {}).get(self.view.poll_id)
            
            if not poll:
                return await interaction.response.send_message("This poll no longer exists!", ephemeral=True)
            
            for i in range(len(self.view.options)):
                if interaction.user.id in poll[f"option_{i}"]:
                    poll[f"option_{i}"].remove(interaction.user.id)
            
            poll[f"option_{self.index}"].append(interaction.user.id)
            save_json("storage/bot_data.json", bot_data)

            vote_counts = []
            total_votes = sum(len(poll[f"option_{j}"]) for j in range(len(self.view.options)))
            
            for i, option in enumerate(self.view.options):
                votes = len(poll[f"option_{i}"])
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                vote_counts.append(f"**{option}**: {votes} votes ({percentage:.1f}%)")

            try:
                embed = interaction.message.embeds[0]
                description_lines = embed.description.split("\n")
                updated_desc = f"{description_lines[0]}\n{description_lines[1]}\n\n" + "\n".join(vote_counts)
                embed.description = updated_desc
                await interaction.message.edit(embed=embed, view=self.view)
                message = f"You voted for {self.label}!"
            except Exception as error:
                print(f"Failed to update poll message: {error}")
                message = f"You voted for {self.label}!\n\nCurrent results:\n" + "\n".join(vote_counts)

            await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            await handle_logs(interaction, e)

async def end_poll(interaction: discord.Interaction, poll_id: str):
    try:
        bot_data = open_json("storage/bot_data.json")
        poll = bot_data.get("polls", {}).get(poll_id)

        if not poll:
            return

        duration = poll['endTime'] - poll['startTime']
        await asyncio.sleep(duration)

        bot_data = open_json("storage/bot_data.json")
        poll = bot_data.get("polls", {}).get(poll_id)
        
        if not poll:
            return

        options = poll["options"]
        vote_counts = []
        total_votes = sum(len(poll[f"option_{i}"]) for i in range(len(options)))
        
        for i, option in enumerate(options):
            votes = len(poll[f"option_{i}"])
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            vote_counts.append(f"{option}: {votes} votes ({percentage:.1f}%)")

        embed = discord.Embed(
            title=f"📊 Poll Ended: {poll['question']}",
            description="\n".join(vote_counts),
            color=discord.Color.red()
        )
        embed.set_footer(text=f"ID: {poll_id}")

        try:
            channel = await interaction.client.fetch_channel(poll["channel_id"])
            message = await channel.fetch_message(poll["message_id"])
            view = PollButtonView(poll_id, options)
            for child in view.children:
                child.disabled = True
            await message.edit(embed=embed, view=view)
            try:
                await message.reply(embed=embed)
            except:
                pass
        except:
            pass

    except Exception as e:
        await handle_logs(interaction, e)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class PollGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="poll", description="Create and manage polls", guild_only=False)

    @app_commands.command(name="create")
    async def create_poll(self, interaction: discord.Interaction, question: str, options: str, duration: str):
        await interaction.response.defer()
        try:
            duration_timedelta = parse_duration(duration)
            if duration_timedelta is None or duration_timedelta.total_seconds() <= 0:
                return await interaction.followup.send("Invalid duration specified. Please use a valid format (e.g., `1h`, `30m`, `2d`).", ephemeral=True)
            
            option_list = [opt.strip() for opt in options.split(",")]
            if len(option_list) < 2:
                return await interaction.followup.send("Please provide at least 2 options!", ephemeral=True)
            
            bot_data = open_json("storage/bot_data.json")
            
            if "polls" not in bot_data:
                bot_data["polls"] = {"last_id": 0}
            
            poll_id = str(bot_data["polls"].get("last_id", 0) + 1)
            bot_data["polls"]["last_id"] = int(poll_id)

            start_time = int(time.time())
            end_time = start_time + int(duration_timedelta.total_seconds())

            if "polls" not in bot_data:
                bot_data["polls"] = {}

            poll_data = {
                f"option_{i}": [] for i in range(len(option_list))
            }
            poll_data.update({
                "question": question,
                "options": option_list,
                "startTime": start_time,
                "endTime": end_time,
            })
            
            bot_data["polls"][poll_id] = poll_data

            embed = discord.Embed(
                title="📊 " + question,
                description=f"Vote by clicking one of the buttons below!\nEnds <t:{end_time}:R>\n\n" + 
                          "\n".join(f"**{opt}**: 0 votes (0.0%)" for opt in option_list),
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Poll ID: {poll_id} | Created by {interaction.user.display_name}")

            view = PollButtonView(poll_id, option_list)
            message = await interaction.followup.send(embed=embed, view=view)
            
            poll_data["channel_id"] = interaction.channel_id 
            poll_data["message_id"] = message.id
            save_json("storage/bot_data.json", bot_data)

            asyncio.create_task(end_poll(interaction, poll_id))

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="view")
    async def view_poll(self, interaction: discord.Interaction, id: str):
        await interaction.response.defer()
        try:
            bot_data = open_json("storage/bot_data.json")
            
            if "polls" not in bot_data or id not in bot_data["polls"] or id == "last_id":
                return await interaction.followup.send("Poll not found.", ephemeral=True)

            poll = bot_data["polls"][id]
            options = poll["options"]
            vote_counts = []
            total_votes = sum(len(poll[f"option_{i}"]) for i in range(len(options)))
            current_time = int(time.time())
            
            for i, option in enumerate(options):
                votes = len(poll[f"option_{i}"])
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                vote_counts.append(f"{option}: {votes} votes ({percentage:.1f}%)")

            status = "Ended" if current_time >= poll["endTime"] else "Active"
            
            embed = discord.Embed(
                title=f"📊 Poll {status}: {poll['question']}",
                description="\n".join(vote_counts),
                color=discord.Color.blue() if status == "Active" else discord.Color.red()
            )
            
            if status == "Active":
                embed.add_field(
                    name="Time Remaining",
                    value=f"Ends <t:{poll['endTime']}:R>",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Ended",
                    value=f"<t:{poll['endTime']}:R>",
                    inline=False
                )
                
            embed.set_footer(text=f"Poll ID: {id}")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="extend")
    async def extend_poll(self, interaction: discord.Interaction, id: str, duration: str):
        await interaction.response.defer()
        try:
            bot_data = open_json("storage/bot_data.json")
            
            if "polls" not in bot_data or id not in bot_data["polls"]:
                return await interaction.followup.send("Poll not found.", ephemeral=True)

            duration_delta = parse_duration(duration)
            if duration_delta is None or duration_delta.total_seconds() <= 0:
                return await interaction.followup.send("Invalid duration specified.", ephemeral=True)

            poll = bot_data["polls"][id]
            new_end_time = poll["endTime"] + int(duration_delta.total_seconds())
            poll["endTime"] = new_end_time
            
            try:
                channel = await interaction.client.fetch_channel(poll["channel_id"])
                message = await channel.fetch_message(poll["message_id"])
                embed = message.embeds[0]
                desc_parts = embed.description.split("\n")
                desc_parts[1] = f"Ends <t:{new_end_time}:R>"
                embed.description = "\n".join(desc_parts)
                await message.edit(embed=embed)
            except:
                pass

            save_json("storage/bot_data.json", bot_data)
            await interaction.followup.send(f"Poll duration extended. New end time: <t:{new_end_time}:R>")

        except Exception as e:
            await handle_logs(interaction, e)

class MiscCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(AlertGroup(bot))
        self.bot.tree.add_command(GiveawayGroup())
        self.bot.tree.add_command(PollGroup())

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        member_info = open_json("storage/member_info.json")
        user = str(ctx.author.id)
        if user in member_info and member_info[user].get("check_latest_alert", 0) == 1:
            await ctx.reply(f"<@{ctx.author.id}>, you have a new alert! Please use `/alert check` to view it.")

    async def interaction_check(self, interaction: discord.Interaction) -> bool | None:
        if (interaction.command and interaction.command.name in 
            ["check", "send", "follow"]): # Might include moderation commands later.
            return True
            
        member_info = open_json("storage/member_info.json")
        user = str(interaction.user.id)
        if user in member_info and member_info[user].get("check_latest_alert", 0) == 1:
            asyncio.create_task(self.send_alert_message(interaction))
        return True

async def setup(bot):
    await bot.add_cog(MiscCog(bot))
    bot.tree.interaction_check = bot.get_cog("MiscCog").interaction_check   