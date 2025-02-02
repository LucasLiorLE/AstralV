from bot_utils import (
    open_file,
    save_file,
    send_modlog_embed,
    store_modlog,
    check_mod,
    dmbed,
    check_user,
    parse_duration,
    create_interaction,
    error,
    handle_logs
)

import discord 
from discord.ext import commands
from discord import app_commands

import time
from datetime import datetime, timedelta, timezone

class DelLog(discord.ui.Select):
    def __init__(
        self,
        log_type,
        member: discord.Member,
        embed: discord.Embed,
        interaction: discord.Interaction,
        *args,
        **kwargs,
    ):
        placeholder = f"Delete a {log_type}"
        super().__init__(placeholder=placeholder, *args, **kwargs)

        self.log_type = log_type
        self.member = member
        self.embed = embed
        self.interaction = interaction

        server_info = open_file("storage/server_info.json")
        
        if self.log_type == "warn":
            self.logs = server_info.get("warnings", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})
        elif self.log_type == "note":
            self.logs = server_info.get("notes", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})

        self.options = [
            discord.SelectOption(
                label=f"{self.log_type.capitalize()} Case #{case_number}",
                description=log["reason"] if "reason" in log else "No reason provided",
                value=str(case_number)
            )
            for case_number, log in self.logs.items()
        ]

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_index = self.values[0]
            server_info = open_file("storage/server_info.json")

            if selected_index in self.logs:
                del self.logs[selected_index]

                if not self.logs:
                    if self.log_type == "warn":
                        server_info["warnings"].get(str(interaction.guild.id), {}).pop(str(self.member.id), None)
                    elif self.log_type == "note":
                        server_info["notes"].get(str(interaction.guild.id), {}).pop(str(self.member.id), None)
                else:
                    if self.log_type == "warn":
                        server_info["warnings"][str(interaction.guild.id)][str(self.member.id)] = self.logs
                    elif self.log_type == "note":
                        server_info["notes"][str(interaction.guild.id)][str(self.member.id)] = self.logs

                save_file("storage/server_info.json", server_info)

                self.embed.clear_fields()
                if self.logs:
                    for index, log in sorted(self.logs.items(), key=lambda x: int(x[0])):
                        time_str = f"<t:{log['time']}:R>"
                        moderator_id = int(log["moderator"])
                        moderator = interaction.guild.get_member(moderator_id)
                        moderator_name = moderator.display_name if moderator else "Unknown"
                        self.embed.add_field(
                            name=f"Case #{index} - {self.log_type.capitalize()} by {moderator_name}",
                            value=f"Reason: {log['reason']}\nTime: {time_str}",
                            inline=False
                        )

                    self.options = [
                        discord.SelectOption(
                            label=f"{self.log_type.capitalize()} Case #{index}",
                            description=log["reason"],
                            value=str(index)
                        )
                        for index, log in sorted(self.logs.items(), key=lambda x: int(x[0]))
                    ]
                else:
                    self.embed.description = f"No {self.log_type}s left for {self.member.display_name}."

                await interaction.response.edit_message(embed=self.embed, view=self.view)
                await interaction.followup.send(f"Deleted {self.log_type.capitalize()} Case #{selected_index} for {self.member.display_name}.", ephemeral=True)
            else:
                await interaction.response.send_message("Invalid selection. Please choose a valid log to delete.", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("Invalid selection. Please try again.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

class LogSelect(discord.ui.Select):
    def __init__(self, options, interaction, user, current_page):
        super().__init__(
            placeholder=f"Current page: {current_page}",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.interaction = interaction
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if not check_user(interaction, interaction.message.interaction.user):
            await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)
            return

        await interaction.response.defer()
        selected_page = int(self.values[0])
        embed, _, _ = await send_modlog_embed(self.interaction, self.user, selected_page)
        await interaction.message.edit(embed=embed)
        self.placeholder = f"Current page: {selected_page}"
        await interaction.message.edit(view=self.view)

class MessageCheck:
    @staticmethod
    def cleanCommand(message: discord.Message) -> bool:
        is_bot_message = message.author == message.guild.me
        starts_with_question = message.content.startswith('>')  
        return is_bot_message or starts_with_question

    @staticmethod
    def is_text_only(message: discord.Message) -> bool:
        has_embeds = bool(message.embeds)
        has_attachments = bool(message.attachments)
        return not has_embeds and not has_attachments and bool(message.content.strip())

    @staticmethod
    def is_from_user(message: discord.Message, user: discord.User) -> bool:
        return message.author == user

    @staticmethod
    def has_embeds(message: discord.Message) -> bool:
        return bool(message.embeds)

    @staticmethod
    def has_attachments(message: discord.Message) -> bool:
        return bool(message.attachments)

    @staticmethod
    async def purge_messages(channel: discord.TextChannel, amount: int, check_func, interaction: discord.Interaction = None, reason: str = None) -> list:
        messages_to_delete = []
        async for message in channel.history(limit=100):
            if len(messages_to_delete) >= amount:
                break
            if check_func(message):
                messages_to_delete.append(message)
        
        if messages_to_delete:
            if len(messages_to_delete) > 1:
                try:
                    await channel.delete_messages(messages_to_delete, reason=reason)
                    await interaction.followup.send(f"Succesfully deleted {len(messages_to_delete)} messages", ephemeral=True)
                    return messages_to_delete
                except discord.HTTPException as e:
                    return []
            else:
                try:
                    await messages_to_delete[0].delete()
                    return [messages_to_delete[0]]
                except discord.HTTPException as e:
                    return []

        return []

class PurgeCommandGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="purge", description="Purge commands for messages")
        
        self.bot = bot

    @app_commands.command(name="any", description="Purges any type of message")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await interaction.channel.purge(limit=amount, reason=reason)

            text = f"Deleted {amount} messages."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="user", description="Purges messages from a specific user.")
    @app_commands.describe(member="The user to purge the messages for", amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def upurge(self, interaction: discord.Interaction, member: discord.Member, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, lambda msg: MessageCheck.is_from_user(msg, member), interaction, reason)

            text = f"Deleted {amount} messages from {member}."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="embeds", description="Purges messages containing embeds.")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def epurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_embeds, interaction, reason)

            text = f"Deleted {amount} messages with embeds."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="attachments", description="Purges messages containing attachments.")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_attachments, interaction, reason)
            
            text = f"Deleted {amount} messages with attachments."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="text", description="Purges messages based on criteria (Default: 10)")
    @app_commands.describe(amount="The amount of messages to be deleted (Default: 10)", reason="Reason for clearing the messages")
    async def tpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.is_text_only, interaction, reason)

            text = f"Deleted {amount} text messages."

            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

class SetCommandGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="set", description="Set the server's preferences.")

        self.bot = bot

    @app_commands.command(name="selogs", description="Changes the log channels of your server")
    @app_commands.describe(option="Choose the type of log (Message Logs, DM Logs, Mod Logs)", channel="The channel to send logs to")
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Message Logs", value="messageLogs"),
            app_commands.Choice(name="DM Logs", value="dmLogs"),
            app_commands.Choice(name="Mod Logs", value="modLogs"),
        ]
    )
    async def setlogs(self, interaction: discord.Interaction, option: app_commands.Choice[str], channel: discord.TextChannel):
        await interaction.response.defer()
        try:
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)

            if not await check_mod(interaction, "administrator"):
                return

            if guild_id not in server_info["preferences"]:
                server_info["preferences"][guild_id] = {}

            server_info["preferences"][guild_id][option.value] = channel.id
            save_file("storage/server_info.json", server_info)

            await interaction.followup.send(f"{option.name} will be set to: {channel.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="seroles", description="Allows you to set the server roles")
    @app_commands.describe(option="Choose the role to set", role="The role to set for members")
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Member", value="member"),
            app_commands.Choice(name="Moderator", value="moderator"),
            app_commands.Choice(name="Manager", value="manager")
        ]
    )
    async def setroles(self, interaction: discord.Interaction, option: str, role: discord.Role):
        await interaction.response.defer()
        try:
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)

            if not await check_mod(interaction, "administrator"):
                return

            if guild_id not in server_info["preferences"]:
                server_info["preferences"][guild_id] = {}

            server_info["preferences"][guild_id][option] = role.id
            save_file("storage/server_info.json", server_info)

            await interaction.followup.send(f"The role '{role.name}' has been set for members.")
        except Exception as e:
            await handle_logs(interaction, e)
class LogPaginator:
    def __init__(self, log_type: str, logs: dict, member: discord.Member, items_per_page: int = 25):
        self.log_type = log_type
        self.logs = logs
        self.member = member
        self.items_per_page = items_per_page
        self.total_pages = max(1, (len(logs) + items_per_page - 1) // items_per_page)

    def get_page(self, page: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.log_type.capitalize()}s for {self.member.display_name}",
            color=0xFFA500 if self.log_type == "warning" else discord.Color.yellow()
        )

        start_idx = (page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        current_logs = dict(list(sorted(self.logs.items(), key=lambda x: int(x[0])))[start_idx:end_idx])

        for case_number, log_data in current_logs.items():
            time_str = f"<t:{log_data['time']}:R>"
            try:
                moderator_id = int(log_data['moderator'])
                moderator = self.member.guild.get_member(moderator_id)
                moderator_name = moderator.display_name if moderator else "Unknown"
            except (ValueError, KeyError):
                moderator_name = log_data['moderator']
            
            embed.add_field(
                name=f"Case #{case_number} - By {moderator_name}",
                value=f"Reason: {log_data['reason']}\nTime: {time_str}",
                inline=False
            )

        embed.set_footer(text=f"Page {page}/{self.total_pages}")
        return embed

class LogPageSelect(discord.ui.Select):
    def __init__(self, paginator: LogPaginator, current_page: int):
        options = [
            discord.SelectOption(
                label=f"Page {i}",
                value=str(i),
                default=(i == current_page)
            )
            for i in range(1, paginator.total_pages + 1)
        ]
        super().__init__(
            placeholder=f"Page {current_page}/{paginator.total_pages}",
            options=options,
            min_values=1,
            max_values=1
        )
        self.paginator = paginator

    async def callback(self, interaction: discord.Interaction):
        page = int(self.values[0])
        embed = self.paginator.get_page(page)
        self.placeholder = f"Page {page}/{self.paginator.total_pages}"
        await interaction.response.edit_message(embed=embed, view=self.view)

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(PurgeCommandGroup(self.bot))

    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def cpurge(self, ctx, amount: int, member: discord.Member = None):
        if amount <= 0:
            await ctx.send("The amount must be greater than zero.", delete_after=5)
            return

        messages_to_delete = []
        
        if member is None:
            deleted_messages = await ctx.channel.purge(limit=amount)
            messages_to_delete = deleted_messages
        else:
            async for message in ctx.channel.history(limit=1000):
                if len(messages_to_delete) >= amount:
                    break
                if message.author.id == member.id:
                    messages_to_delete.append(message)

            await ctx.channel.delete_messages(messages_to_delete)

        reason = f"Deleted {len(messages_to_delete)} message(s)"

        await store_modlog(
            modlog_type="Purge",
            moderator=ctx.author,
            channel=ctx.channel,
            arguments=reason,
            server_id=ctx.guild.id,
            bot=self.bot
        )

    @app_commands.command(name="clean", description="Clean the bot's messages")
    @app_commands.describe(amount="Amount to delete (Default: 10)")
    async def clean(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await check_mod(interaction, "manage_messages"):
                await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
                return

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.cleanCommand, interaction, reason)

            text = f"Cleaned {amount} bot messages."

            await store_modlog(
                modlog_type="Clean",
                moderator=interaction.user,
                arguments=text,
                server_id=interaction.guild_id,
                bot=self.bot
            )

            await interaction.followup.send(text, delete_after=5)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="role", description="Toggle a role for a member")
    @app_commands.describe(member="Member to manage roles for", role="Role to manage", reason="Reason for management")
    async def role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_roles"):
                return
        
            if role in member.roles:
                await member.remove_roles(role)
                task = "removed from"
            else:
                await member.add_roles(role)
                task = "added to"

            embed = discord.Embed(
                    title=f"Role {task}.",
                    description=f"{role.mention} was successfully {task} {member.mention}",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )
            await interaction.followup.send(embed=embed)

            await store_modlog(
                modlog_type="Role",
                moderator=interaction.user,
                user=member,
                arguments=f"{task} role {role.name}",
                server_id=interaction.guild_id,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="lock", description="Lock a channel.")
    @app_commands.describe(
        channel="The channel to lock (default is the current channel)",
        role="The role to lock the channel for (default is 'Member')",
        reason="The reason for locking the channel (default is 'No reason provided')",
    )
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            channel = channel or interaction.channel
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)
            
            if role is None:
                role_id = server_info["preferences"].get(guild_id, {}).get("member")
                role = interaction.guild.get_role(role_id) if role_id else None

            if role is None:
                await interaction.followup.send("No role found to lock the channel for.")
                return

            if role not in channel.overwrites:
                overwrites = {role: discord.PermissionOverwrite(send_messages=False)}
                await channel.edit(overwrites=overwrites)
            else:
                await channel.set_permissions(role, send_messages=False)

            embed = discord.Embed(
                title="Channel Locked",
                description=f"{channel.mention} has been locked for {role.name}.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )

            await store_modlog(
                modlog_type="Lock",
                moderator=interaction.user,
                channel=channel,
                arguments=f"Locked for {role.name}",
                server_id=interaction.guild_id,
                bot=self.bot
            )
        
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="unlock", description="Unlock a channel.")
    @app_commands.describe(
        channel="The channel to unlock (default is the current channel)",
        role="The role to unlock the channel for (default is 'Member')",
        reason="The reason for unlocking the channel (default is 'No reason provided')",
    )
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            channel = channel or interaction.channel
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)
            
            if role is None:
                role_id = server_info["preferences"].get(guild_id, {}).get("member")
                role = interaction.guild.get_role(role_id) if role_id else None

            if role is None:
                await interaction.followup.send("No role found to unlock the channel for.")
                return

            if role in channel.overwrites:
                await channel.set_permissions(role, send_messages=True)

            embed = discord.Embed(
                title="Channel Unlocked",
                description=f"{channel.mention} has been unlocked for {role.name}.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )

            await store_modlog(
                modlog_type="Unlock",
                moderator=interaction.user,
                channel=channel,
                arguments=f"Unlocked for {role.name}",
                server_id=interaction.guild_id,
                bot=self.bot
            )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="slowmode", description="Sets or removes the slowmode delay for the channel.")
    @app_commands.describe(delay="Slowmode in seconds (max of 21600, omit for no slowmode)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slowmode(self, interaction: discord.Interaction, channel: discord.TextChannel = None, delay: int = None):
        await interaction.response.defer()
        try:
            channel = channel or interaction.channel
            if not await check_mod(interaction, "manage_messages"):
                return
            if delay is None or 0:
                await channel.edit(slowmode_delay=0)
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Slowmode", 
                        description="Slowmode has been removed.",
                        color=discord.Color.green()
                    )
                )
            elif 0 < delay <= 21600:
                await channel.edit(slowmode_delay=delay)
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Slowmode", 
                        description=f"Slowmode set to {delay} seconds.", 
                        color=discord.Color.yellow()
                    )
                )
            else:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Slowmode Error", 
                        description="Please provide a delay between 0 and 21600 seconds.", 
                        color=discord.Color.red()
                    )
                )
                return

            await store_modlog(
                modlog_type="Slowmode",
                moderator=interaction.user,
                channel=channel,
                arguments=f"Slowmode of {'0' if delay == None else delay} seconds",
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="nick", description="Changes a member's nickname.")
    @app_commands.describe(member="The member to manage nicknames for", new_nick="The new nickname of the member")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, new_nick: str):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            old_nick = member.display_name
            await member.edit(nick=new_nick)

            arguments = f"Changed {member.name}'s nickname from {old_nick} to {new_nick} for {member.display_name}."
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Nickname Changed", 
                    description=arguments, 
                    color=0x32A852
                )
            )

            await store_modlog(
                modlog_type="Nickname",
                moderator=interaction.user,
                user=member,
                arguments=arguments,
                server_id=interaction.guild_id,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="mute", description="Mutes a member for a specified duration")
    @app_commands.describe(
        member="Member to mute",
        duration="Duration of the mute",
        reason="Reason for the mute"
    )
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "moderate_members"):
                return
            
            duration = parse_duration(duration)

            if not duration:
                await interaction.followup.send("Invalid time format. Please use formats like `1h10m15s` or `15s1h10m`.")
                return

            until = discord.utils.utcnow() + duration
            await member.timeout(until, reason=reason)

            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            human_readable_time = (f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)")

            await dmbed(interaction, member, "muted", reason, human_readable_time)

            await store_modlog(
                modlog_type="Mute",
                moderator=interaction.user,
                user=member,
                reason=reason,
                arguments=f"{reason}\nMuted for {human_readable_time}",
                server_id=interaction.guild_id,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="unmute", description="Unmutes a user.")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "moderate_members"):
                return
            
            await member.timeout(None, reason=reason)

            await dmbed(interaction, member, "unmuted", reason)

            await store_modlog(
                modlog_type="Unmute",
                moderator=interaction.user,
                user=member,
                reason=reason,
                server_id=interaction.guild_id,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="kick", description="Kick a member out of the guild.")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No Reason Provided."):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "kick_members"):
                return
            
            await member.kick(reason=reason)

            await dmbed(interaction, member, "kicked", reason)

            await store_modlog(
                modlog_type="Kick",
                moderator=interaction.user,
                user=member,
                reason=reason,
                server_id=interaction.guild_id,
                bot=self.bot
            )
            
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="warn", description="Warns a user.")
    @app_commands.describe(
        member="The member to warn.", 
        reason="Reason for the warn.",
        auto_mute="If the member will be automatically muted (3+ warnings)."
    )
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str, auto_mute: bool = False):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            if member == self.bot:
                await interaction.followup.send("Why are you warning me 😭!")

            server_info = open_file("storage/server_info.json")
            server_id = str(interaction.guild.id)

            server_info.setdefault("warnings", {})
            server_info["warnings"].setdefault(server_id, {})
            server_info["warnings"][server_id].setdefault(str(member.id), {})

            member_warnings = server_info["warnings"][server_id][str(member.id)]

            if member_warnings:
                try:
                    highest_case_number = max(map(int, member_warnings.keys()), default=0)
                    last_warning_time = member_warnings.get(str(highest_case_number), {}).get("time", 0)

                    if int(time.time()) - last_warning_time < 60:
                        await interaction.followup.send(embed=discord.Embed(
                            title="Warning Error",
                            description=f"{member.mention} has been warned recently and cannot be warned again yet.",
                            color=0xFF0000
                        ))
                        return
                except ValueError as e:
                    pass

            warning_case_number = str(max(map(int, member_warnings.keys()), default=0) + 1)
            server_info["warnings"][str(server_id)][str(member.id)][str(warning_case_number)] = {
                "reason": reason,
                "moderator": str(interaction.user.id),
                "time": int(time.time())
            }

            await dmbed(interaction, member, "warn", reason)
            await store_modlog(
                modlog_type="Warn",
                moderator=interaction.user,
                user=member,
                reason=reason,
                server_id=interaction.guild_id,
                bot=self.bot
            )

            if auto_mute == True: 
                mute_duration = 0
                if len(member_warnings) > 2:
                    mute_duration = (len(member_warnings) - 2) * 60 * 30

                if mute_duration > 0:
                    try:
                        await member.timeout(timedelta(seconds=mute_duration))
                        await interaction.followup.send(embed=discord.Embed(
                            title="Member Muted",
                            description=f"{member.mention} has been automatically muted for {mute_duration // 60} minutes due to {len(member_warnings) + 1} warnings.",
                            color=0xFF0000
                        ))
                    except discord.Forbidden:
                        await interaction.followup.send(embed=discord.Embed(
                            title="Mute Failed",
                            description=f"Failed to mute {member.mention} due to insufficient permissions.",
                            color=0xFF0000
                        ))

        except Exception as e:
            await handle_logs(interaction, e)


    @app_commands.command(name="warns", description="Displays the warnings for a user.")
    @app_commands.describe(member="The member whose warnings you want to check.", page="The page number to view")
    async def warns(self, interaction: discord.Interaction, member: discord.Member = None, page: int = 1):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            member = member or interaction.user
            server_info = open_file("storage/server_info.json")
            server_id = str(interaction.guild.id)
            
            member_warnings = server_info["warnings"].get(server_id, {}).get(str(member.id), {})

            if member_warnings:
                paginator = LogPaginator("warning", member_warnings, member)
                if not 1 <= page <= paginator.total_pages:
                    page = 1
                
                embed = paginator.get_page(page)
                
                view = discord.ui.View()
                if paginator.total_pages > 1:
                    view.add_item(LogPageSelect(paginator, page))
                view.add_item(DelLog("warn", member, embed, interaction))
                
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.followup.send(f"No warnings found for {member.display_name}.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="note", description="Gives a note to a user.")
    @app_commands.describe(member="The member to add a note to", note="Whatever you want to say")
    async def note(self, interaction: discord.Interaction, member: discord.Member, note: str):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            server_info = open_file("storage/server_info.json")
            member_notes = server_info["notes"].setdefault(str(interaction.guild.id), {}).setdefault(str(member.id), {})
            case_number = str(max(map(int, member_notes.keys()), default=0) + 1)
            member_notes[case_number] = {
                "reason": note,
                "moderator": str(interaction.user.id),
                "time": int(time.time())
            }
            save_file("storage/server_info.json", server_info)
            await interaction.followup.send(embed=discord.Embed(
                title="Note Added",
                description=f"Added note to: {member.mention}\nCase #{case_number}\n{note}",
                color=discord.Color.yellow()
            ))
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="notes", description="Displays the notes for a member")
    @app_commands.describe(member="The member whose notes you want to view.", page="The page number to view")
    async def notes(self, interaction: discord.Interaction, member: discord.Member = None, page: int = 1):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            
            member = member or interaction.user
            server_info = open_file("storage/server_info.json")
            member_notes = server_info["notes"].get(str(interaction.guild.id), {}).get(str(member.id), {})

            if member_notes:
                paginator = LogPaginator("note", member_notes, member)
                if not 1 <= page <= paginator.total_pages:
                    page = 1
                
                embed = paginator.get_page(page)
                
                view = discord.ui.View()
                if paginator.total_pages > 1:
                    view.add_item(LogPageSelect(paginator, page))
                view.add_item(DelLog("note", member, embed, interaction))
                
                await interaction.followup.send(embed=embed, view=view)
            else:
                await interaction.followup.send(f"No notes found for {member.display_name}.", ephemeral=True)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="modlogs", description="View moderation logs for a user.")
    async def modlogs(self, interaction: discord.Interaction, member: discord.Member, page: int = 1):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return
            embed, _, total_pages = await send_modlog_embed(interaction, member, page)

            if embed is None:
                return

            options = [discord.SelectOption(label=f"Page {i + 1}", value=str(i + 1)) for i in range(total_pages)]

            select_menu = LogSelect(options, interaction, member, page)
            view = discord.ui.View()
            view.add_item(select_menu)

            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="modstats", description="Check the moderation statistics of a moderator")
    async def modstats(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            member = member or interaction.user
            server_info = open_file("storage/server_info.json")

            stats = {
                "warn": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
                "kick": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
                "mute": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
                "ban": {"last 7 days": 0, "last 30 days": 0, "all time": 0},
            }

            totals = {"last 7 days": 0, "last 30 days": 0, "all time": 0}
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)

            for _, moderators in server_info["modstats"].items():
                user_stats = moderators.get(str(member.id), {})

                for _, action in user_stats.items():
                    action_type = action["type"].lower()
                    action_time = datetime.fromtimestamp(action["timestamp"], timezone.utc)

                    if action_type in stats:
                        if action_time > seven_days_ago:
                            stats[action_type]["last 7 days"] += 1
                            totals["last 7 days"] += 1
                        if action_time > thirty_days_ago:
                            stats[action_type]["last 30 days"] += 1
                            totals["last 30 days"] += 1
                        stats[action_type]["all time"] += 1
                        totals["all time"] += 1

            embed = discord.Embed(
                title=f"Moderation Statistics",
                color=discord.Color.orange(),
                timestamp=now
            )
            embed.set_author(
                name=f"{member.display_name}", 
                icon_url=member.avatar.url
            )

            embed.add_field(name="Mutes (last 7 days):", value=stats["mute"]["last 7 days"])
            embed.add_field(name="Mutes (last 30 days):", value=stats["mute"]["last 30 days"])
            embed.add_field(name="Mutes (all time):", value=stats["mute"]["all time"])

            embed.add_field(name="Bans (last 7 days):", value=stats["ban"]["last 7 days"])
            embed.add_field(name="Bans (last 30 days):", value=stats["ban"]["last 30 days"])
            embed.add_field(name="Bans (all time):", value=stats["ban"]["all time"])

            embed.add_field(name="Kicks (last 7 days):", value=stats["kick"]["last 7 days"])
            embed.add_field(name="Kicks (last 30 days):", value=stats["kick"]["last 30 days"])
            embed.add_field(name="Kicks (all time):", value=stats["kick"]["all time"])

            embed.add_field(name="Warns (last 7 days):", value=stats["warn"]["last 7 days"])
            embed.add_field(name="Warns (last 30 days):", value=stats["warn"]["last 30 days"])
            embed.add_field(name="Warns (all time):", value=stats["warn"]["all time"])

            embed.add_field(name="Total (last 7 days):", value=totals["last 7 days"])
            embed.add_field(name="Total (last 30 days):", value=totals["last 30 days"])
            embed.add_field(name="Total (all time):", value=totals["all time"])

            embed.set_footer(text=f"ID: {member.id}")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @commands.command(name="clean")
    @commands.has_permissions(manage_messages=True)
    async def manual_clean(self, ctx, amount: int = 10, reason: str = "No reason provided"):
        try:
            await ctx.message.delete()
            interaction = await create_interaction(ctx)
            await self.clean.callback(self, interaction, amount, reason)
        except Exception as e:
            error(e)

    @commands.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def manual_warn(self, ctx, member: discord.Member, *, reason: str):
        try:
            interaction = await create_interaction(ctx)
            await self.warn.callback(self, interaction, member, reason)
        except Exception as e:
            error(e)

    @commands.command(name="mute")
    @commands.has_permissions(moderate_members=True)
    async def manual_mute(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            await self.mute.callback(self, interaction, member, duration, reason)
        except Exception as e:
            error(e)

    @commands.command(name="unmute")
    @commands.has_permissions(moderate_members=True)
    async def manual_unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            await self.unmute.callback(self, interaction, member, reason)
        except Exception as e:
            error(e)

    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def manual_kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            await self.kick.callback(self, interaction, member, reason)
        except Exception as e:
            error(e)

    @commands.command(name="notes")
    @commands.has_permissions(manage_messages=True)
    async def manual_notes(self, ctx, member: discord.Member = None):
        try:
            interaction = await create_interaction(ctx)
            await self.notes.callback(self, interaction, member or ctx.author)
        except Exception as e:
            error(e)

    @commands.command(name="note")
    @commands.has_permissions(manage_messages=True)
    async def manual_note(self, ctx, member: discord.Member, *, note: str):
        try:
            interaction = await create_interaction(ctx)
            await self.note.callback(self, interaction, member, note)
        except Exception as e:
            error(e)

    @commands.command(name="warns")
    @commands.has_permissions(manage_messages=True)
    async def manual_warns(self, ctx, member: discord.Member = None):
        try:
            interaction = await create_interaction(ctx)
            await self.warns.callback(self, interaction, member or ctx.author)
        except Exception as e:
            error(e)

    @commands.command(name="modlogs")
    @commands.has_permissions(manage_messages=True)
    async def manual_modlogs(self, ctx, member: discord.Member, page: int = 1):
        try:
            interaction = await create_interaction(ctx)
            await self.modlogs.callback(self, interaction, member, page)
        except Exception as e:
            error(e)

    @commands.command(name="slowmode")
    @commands.has_permissions(manage_messages=True)
    async def manual_slowmode(self, ctx, delay: int = None):
        try:
            interaction = await create_interaction(ctx)
            await self.slowmode.callback(self, interaction, ctx.channel, delay)
        except Exception as e:
            error(e)

    @commands.command(name="role")
    @commands.has_permissions(manage_roles=True)
    async def manual_role(self, ctx, member: discord.Member, role: discord.Role, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            await self.role.callback(self, interaction, member, role, reason)
        except Exception as e:
            error(e)


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors from prefix commands"""
        try:
            if isinstance(error, discord.ext.commands.errors.CommandNotFound):
                return
            
            interaction = await create_interaction(ctx)
            await handle_logs(interaction, error)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", delete_after=5)
            await ctx.message.clear_reactions()

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
