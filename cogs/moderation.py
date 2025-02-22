from bot_utils import (
    send_modlog_embed,
    store_modlog,
    check_moderation_info,
    dm_moderation_embed,

    check_user,
    get_context_object,
    get_role_hierarchy,
    parse_duration,
    create_interaction,
    get_member,
    get_channel,
    get_role,
    handle_logs,
    
    open_file,
    save_file,
    load_commands,
    handle_logs,
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
        interaction: discord.Interaction | commands.Context,
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
                description=(log["reason"] if "reason" in log else "No reason provided.")[:100],
                value=str(case_number)
            )
            for case_number, log in self.logs.items()
        ]

    async def callback(self, interaction: discord.Interaction):
        try:
            original_user = (
                self.interaction.user if isinstance(self.interaction, discord.Interaction) 
                else self.interaction.author
            )
            
            if not check_user(interaction, original_user):
                return await interaction.response.send_message(
                    "You cannot interact with this button.", 
                    ephemeral=True
                )

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
                        moderator_id = log["moderator"]
                        moderator = interaction.guild.get_member(int(moderator_id)) if moderator_id.isdigit() else None
                        moderator_name = moderator.display_name if moderator else "Unknown"
                        self.embed.add_field(
                            name=f"Case #{index} - {self.log_type.capitalize()} by {moderator_name}",
                            value=f"Reason: {log['reason'][:100]}\nTime: {time_str}",
                            inline=False
                        )

                    self.options = [
                        discord.SelectOption(
                            label=f"{self.log_type.capitalize()} Case #{index}",
                            description=log["reason"][:100],
                            value=str(index)
                        )
                        for index, log in sorted(self.logs.items(), key=lambda x: int(x[0]))
                    ]
                else:
                    self.embed.description = f"No {self.log_type}s left for {self.member.display_name}."

                try:
                    await interaction.response.edit_message(embed=self.embed, view=self.view)
                    await interaction.followup.send(
                        f"Deleted {self.log_type.capitalize()} Case #{selected_index} for {self.member.display_name}.", 
                        ephemeral=True
                    )
                except discord.NotFound:
                    await interaction.response.send_message(
                        f"Deleted {self.log_type.capitalize()} Case #{selected_index} for {self.member.display_name}.",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "Invalid selection. Please choose a valid log to delete.", 
                    ephemeral=True
                )

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
            return await interaction.response.send_message("You cannot interact with this button.", ephemeral=True)

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
        starts_with_question = message.content.startswith('.')  
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
                    await interaction.followup.send(f"Succesfully deleted {len(messages_to_delete)} messages")
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
    def __init__(self):
        super().__init__(name="purge", description="Purge commands for messages")

    @app_commands.command(name="any")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await interaction.channel.purge(limit=amount, reason=reason)

            text = f"Deleted {amount} messages."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="user")
    async def upurge(self, interaction: discord.Interaction, member: discord.Member, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, lambda msg: MessageCheck.is_from_user(msg, member), interaction, reason)

            text = f"Deleted {amount} messages from {member}."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="embeds") 
    async def epurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_embeds, interaction, reason)

            text = f"Deleted {amount} messages with embeds."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="attachments")
    async def attpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_attachments, interaction, reason)
            
            text = f"Deleted {amount} messages with attachments."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="text")
    async def tpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.is_text_only, interaction, reason)

            text = f"Deleted {amount} text messages."

            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    def setup_commands(self):
        load_commands(self, "moderation")

class SetCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="set", description="Set the server's preferences.")

    @app_commands.command(name="logs")
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

            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if guild_id not in server_info["preferences"]:
                server_info["preferences"][guild_id] = {}

            server_info["preferences"][guild_id][option.value] = channel.id
            save_file("storage/server_info.json", server_info)

            await interaction.followup.send(f"{option.name} will be set to: {channel.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="roles")
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

            has_mod, embed = check_moderation_info(interaction, "administrator", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if guild_id not in server_info["preferences"]:
                server_info["preferences"][guild_id] = {}

            server_info["preferences"][guild_id][option] = role.id
            save_file("storage/server_info.json", server_info)

            await interaction.followup.send(f"The role '{role.name}' has been set to: {option.title()}.")
        except Exception as e:
            await handle_logs(interaction, e)

    def setup_commands(self):
        load_commands(self, "moderation")
        
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
        self.command_help = open_file("storage/command_help.json")
        
        purge_group = PurgeCommandGroup()
        purge_group.setup_commands()
        self.bot.tree.add_command(purge_group)

        set_group = SetCommandGroup()
        set_group.setup_commands()
        self.bot.tree.add_command(set_group)

        load_commands(self.__cog_app_commands__, "moderation")

    async def manual_get_user(self, ctx: commands.Context, user: str | int | discord.User) -> discord.User:
        try:
            user_id = int(user)
            user = await self.bot.fetch_user(user_id)
        except ValueError:
            try:
                user = await commands.UserConverter().convert(ctx, user)
            except commands.UserNotFound:
                return None
        return user
    
    async def handle_warn(self, ctx_or_interaction, member: discord.Member, reason: str):
        """Shared handler for both slash and manual warn commands"""
        ctx = get_context_object(ctx_or_interaction)

        has_mod, embed = check_moderation_info(ctx_or_interaction, "manage_messages", "moderator")
        if not has_mod:
            return await ctx["send"](embed=embed)

        if member.id == ctx["user"].id:
            return await ctx["send"]("You cannot warn yourself.", ephemeral=ctx["is_interaction"])

        if member.bot:
            return await ctx["send"]("You cannot warn bots.", ephemeral=ctx["is_interaction"])

        if len(reason) > 1024:
            return await ctx["send"]("Please provide a shorter reason.", ephemeral=ctx["is_interaction"])

        server_info = open_file("storage/server_info.json")
        guild_id = str(ctx["guild_id"])

        server_info.setdefault("warnings", {}).setdefault(guild_id, {}).setdefault(str(member.id), {})
        case_numbers = [int(x) for x in server_info["warnings"][guild_id][str(member.id)].keys()]
        next_case = str(max(case_numbers + [0]) + 1)

        server_info["warnings"][guild_id][str(member.id)][next_case] = {
            "reason": reason,
            "moderator": str(ctx["user"].id),
            "time": int(time.time())
        }
        save_file("storage/server_info.json", server_info)

        await dm_moderation_embed(ctx_or_interaction, member, "warn", reason)

        await store_modlog(
            modlog_type="Warn",
            moderator=ctx["user"],
            user=member,
            reason=reason,
            server_id=ctx["guild_id"],
            bot=self.bot
        )

    async def handle_warns(self, ctx_or_interaction, member: discord.Member = None, page: int = 1):
        """Shared handler for both slash and manual warn commands"""
        ctx = get_context_object(ctx_or_interaction)
        member = member or ctx["user"]

        has_mod, embed = check_moderation_info(ctx_or_interaction, "manage_messages", "moderator")
        if not has_mod:
            return await ctx["send"](embed=embed)

        server_info = open_file("storage/server_info.json")
        member_warnings = server_info["warnings"].get(str(ctx["guild_id"]), {}).get(str(member.id), {})

        if member_warnings:
            paginator = LogPaginator("warning", member_warnings, member)
            if not 1 <= page <= paginator.total_pages:
                page = 1

            embed = paginator.get_page(page)

            view = discord.ui.View()
            if paginator.total_pages > 1:
                view.add_item(LogPageSelect(paginator, page))
            view.add_item(DelLog("warn", member, embed, ctx_or_interaction))

            await ctx["send"](embed=embed, view=view)
        else:
            await ctx["send"](f"No warnings found for {member.display_name}.", ephemeral=ctx["is_interaction"])

    async def handle_note(self, ctx_or_interaction, member: discord.Member, note: str):
        """Shared handler for both slash and manual note commands"""
        ctx = get_context_object(ctx_or_interaction)

        has_mod, embed = check_moderation_info(ctx_or_interaction, "manage_messages", "moderator")
        if not has_mod:
            return await ctx["send"](embed=embed)

        if len(note) > 1024:
            return await ctx["send"]("Note must be less than 1024 characters.", ephemeral=ctx["is_interaction"])

        server_info = open_file("storage/server_info.json")
        guild_id = str(ctx["guild_id"])

        server_info.setdefault("notes", {}).setdefault(guild_id, {}).setdefault(str(member.id), {})
        case_numbers = [int(x) for x in server_info["notes"][guild_id][str(member.id)].keys()]
        next_case = str(max(case_numbers + [0]) + 1)

        server_info["notes"][guild_id][str(member.id)][next_case] = {
            "reason": note,
            "moderator": str(ctx["user"].id),
            "time": int(time.time())
        }
        save_file("storage/server_info.json", server_info)

        embed = discord.Embed(
            title=f"Member note.",
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Action", value="Note", inline=False) 
        embed.add_field(name="Reason", value=note, inline=False)

        await ctx["send"](embed=embed)

    async def handle_notes(self, ctx_or_interaction, member: discord.Member = None, page: int = 1):
        """Shared handler for both slash and manual note commands"""
        ctx = get_context_object(ctx_or_interaction)
        member = member or ctx["user"]

        has_mod, embed = check_moderation_info(ctx_or_interaction, "manage_messages", "moderator")
        if not has_mod:
            return await ctx["send"](embed=embed)

        server_info = open_file("storage/server_info.json")
        member_notes = server_info["notes"].get(str(ctx["guild_id"]), {}).get(str(member.id), {})

        if member_notes:
            paginator = LogPaginator("note", member_notes, member)
            if not 1 <= page <= paginator.total_pages:
                page = 1

            embed = paginator.get_page(page)

            view = discord.ui.View()
            if paginator.total_pages > 1:
                view.add_item(LogPageSelect(paginator, page))
            view.add_item(DelLog("note", member, embed, ctx_or_interaction))

            await ctx["send"](embed=embed, view=view)
        else:
            await ctx["send"](f"No notes found for {member.display_name}.", ephemeral=ctx["is_interaction"])

    @app_commands.command(name="clean")
    async def clean(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.cleanCommand, interaction, reason)

            text = f"Cleaned {amount} bot messages."

            await store_modlog(
                modlog_type="Clean",
                moderator=interaction.user,
                arguments=text,
                server_id=interaction.guild_id,
                bot=self.bot
            )

            await interaction.followup.send(text)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="role")
    async def role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = "No reason provided."):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_roles", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not get_role_hierarchy(interaction.user, member):
                return await interaction.followup.send("You require a higher role hierachy than the target user!")

            if not get_role_hierarchy(interaction.user, role):
                return await interaction.followup.send("You cannot manage a role higher than or equal to your highest role!")

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

    @app_commands.command(name="lock")
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            channel = channel or interaction.channel
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)
            
            if role is None:
                role_id = server_info["preferences"].get(guild_id, {}).get("member")
                role = interaction.guild.get_role(role_id) if role_id else None

            if role is None:
                role = interaction.guild.default_role

            overwrite = channel.overwrites_for(role)
            overwrite.send_messages = False
            await channel.set_permissions(role, overwrite=overwrite)

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

    @app_commands.command(name="unlock")
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)
            
            channel = channel or interaction.channel
            server_info = open_file("storage/server_info.json")
            guild_id = str(interaction.guild_id)
            
            if role is None:
                role_id = server_info["preferences"].get(guild_id, {}).get("member")
                role = interaction.guild.get_role(role_id) if role_id else None

            if role is None:
                role = interaction.guild.default_role

            overwrite = channel.overwrites_for(role)
            overwrite.send_messages = True
            await channel.set_permissions(role, overwrite=overwrite)

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

    @app_commands.command(name="slowmode")
    async def slowmode(self, interaction: discord.Interaction, channel: discord.TextChannel = None, delay: int = None):
        await interaction.response.defer()
        try:
            channel = channel or interaction.channel

            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

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
                        title="Slowmode handle_logs", 
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

    @app_commands.command(name="nick")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(self, interaction: discord.Interaction, member: discord.Member, new_nick: str):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_nicknames", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)
            
            old_nick = member.display_name
            await member.edit(nick=new_nick)

            arguments = f"Changed {member.name}'s nickname from {old_nick} to {new_nick} ."
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

    @app_commands.command(name="mute")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "moderate_members", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not get_role_hierarchy(interaction.user, member):
                return await interaction.followup.send("You require a higher role hierachy than the target user!")

            duration = parse_duration(duration)

            if not duration:
                return await interaction.followup.send("Invalid time format. Please use formats like `1h10m15s` or `15s1h10m`.")

            until = discord.utils.utcnow() + duration
            await member.timeout(until, reason=reason)

            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            human_readable_time = (f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)")

            await dm_moderation_embed(interaction, member, "muted", reason, human_readable_time)

            await store_modlog(
                modlog_type="Mute",
                moderator=interaction.user,
                user=member,
                reason=reason,
                arguments=f"{reason}\nMuted for {human_readable_time}",
                server_id=interaction.guild_id,
                bot=self.bot
            )

        except OverflowError:
            await interaction.followup.send("The duration is too long. Please provide a shorter duration.")
    
        except commands.MemberNotFound:
            await interaction.followup.send("User not found.")

        except discord.Forbidden:
            await interaction.followup.send("I do not have the required permissions to mute this user.")

        except discord.HTTPException as e:
            if e.code == 50013:
                await interaction.followup.send("I do not have the required permissions to mute this user.")
            else:
                await interaction.followup.send("An handle_logs occurred while trying to mute this user.")

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="unmute")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "moderate_members", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not get_role_hierarchy(interaction.user, member):
                return await interaction.followup.send("You require a higher role hierachy than the target user!")
            
            await member.timeout(None, reason=reason)

            await dm_moderation_embed(interaction, member, "unmuted", reason)

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

    @app_commands.command(name="kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No Reason Provided."):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "kick_members", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not get_role_hierarchy(interaction.user, member):
                return await interaction.followup.send("You require a higher role hierachy than the target user!")
            
            await member.kick(reason=reason)

            await dm_moderation_embed(interaction, member, "kicked", reason)

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

    @app_commands.command(name="ban")
    async def ban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "ban_members", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not user:
                return await interaction.followup.send("You must specify either a user or a user ID to unban.")

            await interaction.guild.ban(user, reason=reason)
            await dm_moderation_embed(interaction, user, "banned", reason)

            await store_modlog(
                modlog_type="Ban",
                moderator=interaction.user,
                user=user,
                reason=reason,
                server_id=interaction.guild_id,
                bot=self.bot
            )

        except discord.NotFound:
            await interaction.followup.send("This user does not exist.")
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to unban users")
            
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="unban")
    async def unban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided"):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "ban_members", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)
            
            if not user:
                return await interaction.followup.send("You must specify either a user or a user ID to unban.")

            try:
                await interaction.guild.unban(user, reason=reason)
                await dm_moderation_embed(interaction, user, "unbanned", reason)

                await store_modlog(
                    modlog_type="Unban",
                    moderator=interaction.user,
                    user=user,
                    reason=reason,
                    server_id=interaction.guild_id,
                    bot=self.bot
                )
            except discord.NotFound:
                await interaction.followup.send("User not found or is not banned")
            except discord.Forbidden:
                await interaction.followup.send("I don't have permission to unban users")

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="warn")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        await interaction.response.defer()
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)
            
            if (member.bot) or (member == interaction.user):
                return await interaction.followup.send("You cannot warn a bot or yourself!")

            if not get_role_hierarchy(interaction.user, member):
                return await interaction.followup.send("You require a higher role hierachy than the target user!")

            if len(reason) > 1024:
                return await interaction.followup.send("Reason must be less than 1024 characters.")

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
                            title="Warn warning",
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

            await dm_moderation_embed(interaction, member, "warn", reason)
            await store_modlog(
                modlog_type="Warn",
                moderator=interaction.user,
                user=member,
                reason=reason,
                server_id=interaction.guild_id,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="warns")
    async def warns(self, interaction: discord.Interaction, member: discord.Member = None, page: int = 1):
        await interaction.response.defer()
        try:
            await self.handle_warns(interaction, member, page)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="note")
    async def note(self, interaction: discord.Interaction, member: discord.Member, note: str):
        await interaction.response.defer()
        try:
            await self.handle_note(interaction, member, note)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="notes") 
    async def notes(self, interaction: discord.Interaction, member: discord.Member = None, page: int = 1):
        await interaction.response.defer()
        try:
            await self.handle_notes(interaction, member, page)
        except Exception as e:
            await handle_logs(interaction, e)

    @commands.command(name="purge")
    async def manuaL_purge(self, ctx, amount: int = 10, reason: str = "No reason provided"):
        try:
            await ctx.message.delete()
            interaction = await create_interaction(ctx)
            await self.PurgeCommandGroup.apurge.callback(self, interaction, amount, reason)

            conf_msg = await ctx.send(f"Purged {amount} messages.")
            await conf_msg.delete(delay=5)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="clean")
    async def manual_clean(self, ctx, amount: int = 10, reason: str = "No reason provided"):
        try:
            await ctx.message.delete()
            interaction = await create_interaction(ctx)
            await self.clean.callback(self, interaction, amount, reason)

            conf_msg = await ctx.send(f"Cleaned {amount} bot messages.")
            await conf_msg.delete(delay=5)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="warn")
    async def manual_warn(self, ctx, member: str, *, reason: str):
        try:
            target_member = await get_member(ctx, member)
            if not target_member:
                return await ctx.send("User not found.")
            
            await self.handle_warn(ctx, target_member, reason)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.command(name="mute")
    async def manual_mute(self, ctx, member: str, duration: str, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.mute.callback(self, interaction, target_member, duration, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="unmute")
    async def manual_unmute(self, ctx, member: str, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.unmute.callback(self, interaction, target_member, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="kick")
    async def manual_kick(self, ctx, member: str, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.kick.callback(self, interaction, target_member, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="ban")
    async def manual_ban(self, ctx, user: str, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            user = await self.manual_get_user(ctx, user)

            if not user:
                return await ctx.send("Could not find user. Please provide a valid user mention or ID.", delete_after=5)

            await self.ban.callback(self, interaction, user, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="unban")
    async def manual_unban(self, ctx, user: str, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            user = await self.manual_get_user(ctx, user)

            if not user:
                return await ctx.send("Could not find user. Please provide a valid user mention or ID.", delete_after=5)

            await self.unban.callback(self, interaction, user, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="notes")
    async def manual_notes(self, ctx, member: str = None, page: int = 1):
        try:
            target_member = await get_member(ctx, member)
            if not target_member:
                return await ctx.send("User not found.")
            
            await self.handle_notes(ctx, target_member, page)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.command(name="note")
    async def manual_note(self, ctx, member: str, *, note: str):
        try:
            target_member = await get_member(ctx, member)
            if not target_member:
                return await ctx.send("User not found.")
            
            await self.handle_note(ctx, target_member, note)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.command(name="warns", aliases=["warnings"])
    async def manual_warns(self, ctx, member: str = None, page: int = 1):
        try:
            target_member = await get_member(ctx, member)
            if not target_member:
                return await ctx.send("User not found.")
            
            await self.handle_warns(ctx, target_member, page)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.command(name="modlogs")
    async def manual_modlogs(self, ctx, member: str, page: int = 1):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.modlogs.callback(self, interaction, target_member, page)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="slowmode")
    async def manual_slowmode(self, ctx, delay: int = None):
        try:
            interaction = await create_interaction(ctx)
            await self.slowmode.callback(self, interaction, ctx.channel, delay)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="nick", aliases=["nickname"])
    async def manual_nick(self, ctx, member: str, *, new_nick: str):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.nick.callback(self, interaction, target_member, new_nick)

        except discord.Forbidden:
            await interaction.followup.send("I cannot change this member's nickname.")
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="role")
    async def manual_role(self, ctx, member: str, role: discord.Role, *, reason: str = "No reason provided"):
        try:
            interaction = await create_interaction(ctx)
            target_member = await get_member(ctx, member)

            if not target_member:
                return await interaction.followup.send("User not found.")

            await self.role.callback(self, interaction, target_member, role, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="lock")
    async def manual_lock(self, ctx, channel: str = None, role: str = None, reason: str = "No reason provided"):
        try:
            channel = await get_channel(ctx, channel)
            role = await get_role(ctx, role)

            if not channel or not role:
                return await ctx.send("Invalid channel or role provided.", delete_after=5)

            interaction = await create_interaction(ctx)
            await self.lock.callback(self, interaction, channel, role, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.command(name="unlock")
    async def manual_unlock(self, ctx, channel: str = None, role: str = None, reason: str = "No reason provided"): 
        try:
            channel = await get_channel(ctx, channel)
            role = await get_role(ctx, role)

            if not channel or not role:
                return await ctx.send("Invalid channel or role provided.", delete_after=5)

            interaction = await create_interaction(ctx)
            await self.unlock.callback(self, interaction, channel, role, reason)
        except Exception as e:
            handle_logs(ctx, e)

    @commands.Cog.listener()
    async def on_command_handle_logs(self, ctx, handle_logs):
        try:
            if isinstance(handle_logs, discord.ext.commands.handle_logss.CommandNotFound):
                return
            
            if isinstance(handle_logs, commands.MissingRequiredArgument):
                command_name = ctx.command.name
                if ctx.command.parent:
                    command_name = f"{ctx.command.parent.name} {command_name}"
                    
                help_data = self.command_help.get("moderation", {}).get(command_name, {})
                if not help_data:
                    help_data = self.command_help.get(command_name, {})
                
                if help_data:
                    embed = discord.Embed(
                        title=f"Missing Required Argument: {handle_logs.param.name}",
                        description=help_data.get("description", "No description available."),
                        color=discord.Color.red()
                    )
                    
                    if "parameters" in help_data:
                        params = help_data["parameters"]
                        param_text = "\n".join([f"**{param}**: {desc}" for param, desc in params.items()])
                        embed.add_field(name="Parameters", value=param_text, inline=False)
                    
                    if "subcommands" in help_data:
                        subcmd_text = "\n".join([f"**{cmd}**: {data.get('description', 'No description')}" 
                                               for cmd, data in help_data["subcommands"].items()])
                        embed.add_field(name="Subcommands", value=subcmd_text, inline=False)
                        
                    return await ctx.send(embed=embed, delete_after=30)
            
            interaction = await create_interaction(ctx)
            await handle_logs(interaction, handle_logs)
        except Exception as e:
            await ctx.send(f"An handle_logs occurred: {str(e)}", delete_after=5)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))