import discord
import time

from typing import Optional, Tuple, Dict, Any, Union
from datetime import datetime, timezone

from discord.ext import commands

from bot_utils import (
    save_json,
    open_json,
    check_user,
    handle_logs,
    get_context_object
)

def is_valid_bot_instance(interaction_or_context: Union[discord.Interaction, commands.Context]) -> bool:
    """
    Checks if the bot is running as a proper bot application and not a user account.
    
    Parameters:
        interaction_or_context (Union[discord.Interaction, commands.Context]): The interaction or context to check.
        
    Returns:
        bool: True if running as bot application, False if user account.

    Example:
        ```
        if is_valid_bot_instance(interaction):
            await interaction.response.send_message("Bot is running properly")
        else:
            await interaction.response.send_message("Cannot run as user account")
        ```
    """
    if isinstance(interaction_or_context, discord.Interaction):
        return interaction_or_context.client.user.bot
    return interaction_or_context.bot.user.bot

async def dm_moderation_embed(
        interaction: discord.Interaction | commands.Context, 
        user: discord.User, 
        action: str, 
        reason: str, 
        duration: Optional[str] = None
    ) -> None:
    """
    Sends moderation action embeds to both the server and target user's DMs.
    
    Parameters:
        interaction (Union[discord.Interaction, commands.Context]): The interaction/context that triggered the action
        user (discord.User): The user receiving the moderation action
        action (str): Type of moderation action (e.g. ban, kick, mute, etc.)
        reason (str): Reason for the moderation action
        duration (str, optional): Duration of temporary actions like mutes/bans

    Example:
        ```
        # Send ban notification
        await dm_moderation_embed(
            interaction=ctx,
            user=member,
            action="banned",
            reason="Violating server rules",
            duration="7 days"
        )

        # Send kick notification without duration
        await dm_moderation_embed(
            interaction=interaction,
            user=member,
            action="kicked",
            reason="Spamming in channels"
        )
        ```
    """
    if not is_valid_bot_instance(interaction):
        embed = discord.Embed(
            title="Error",
            description="❌ This bot cannot be used as a user account.",
            color=discord.Color.red()
        )
        if isinstance(interaction, discord.Interaction):
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"Member {action}.", 
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(name="Member", value=user.mention, inline=False)
    embed.add_field(name="Action", value=action.title(), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    if duration:
        embed.add_field(name="Duration", value=duration, inline=False)

    try:
        if isinstance(interaction, discord.Interaction):
            guild = interaction.guild
            moderator = interaction.user
        else:
            guild = interaction.guild
            moderator = interaction.author

        if guild is None:
            raise ValueError("Could not determine guild from interaction/context")

        MemberEmbed = discord.Embed(
            title=f"You have been {action} in {guild.name}.",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        MemberEmbed.add_field(name="Moderator", value=moderator.mention, inline=False)
        MemberEmbed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            MemberEmbed.add_field(name="Duration", value=duration, inline=False)
        MemberEmbed.set_footer(text="If you think this is a mistake, please contact a staff user.")
        await user.send(embed=MemberEmbed)
    except (discord.Forbidden, discord.HTTPException):
        embed.set_footer(text="I was unable to DM this user.")
    except ValueError as e:
        embed.set_footer(text=str(e))

    if isinstance(interaction, discord.Interaction):
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
    else:
        await interaction.send(embed=embed)
        
def check_mod_server_info(id: int) -> Dict[str, Any]:
    """
    Checks and initializes basic moderation data structures in server_info.json.
    
    Parameters:
        id (int): The guild ID of the server.
        
    Returns:
        Dict[str, Any]: The updated server info dictionary containing initialized moderation data structures.

    Example:
        ```
        server_info = check_mod_server_info(guild.id)
        if "modlogs" in server_info:
            print("Moderation logs are initialized")
        ```
    """
    server_info = open_json("storage/server_info.json")

    server_info.setdefault("preferences", {})
    server_info.setdefault("modlogs", {})
    server_info.setdefault("modstats", {})
    server_info.setdefault("warnings", {})
    server_info.setdefault("notes", {})

    server_info["preferences"].setdefault(id, {})
    server_info["modlogs"].setdefault(id, {})
    server_info["modstats"].setdefault(id, {})
    server_info["warnings"].setdefault(id, {})
    server_info["notes"].setdefault(id, {})

    save_json("storage/server_info.json", server_info)

    return server_info

def check_moderation_info(ctx_or_interaction, permission_name: str, minimum_role: str) -> tuple[bool, discord.Embed]:
    """
    Checks if a user has the required permissions or roles to use moderation commands.

    Parameters:
        ctx_or_interaction (Union[discord.Interaction, commands.Context]): The context or interaction to check.
        permission_name (str): The name of the permission to check for.
        minimum_role (str): The minimum role required if permission check fails.

    Returns:
        tuple[bool, discord.Embed]: A tuple containing:
            - bool: Whether the user has permission
            - discord.Embed: Error embed if permission denied, None if granted

    Example:
        ```
        has_permission, error_embed = check_moderation_info(ctx, "ban_members", "moderator")
        if not has_permission:
            await ctx.send(embed=error_embed)
            return
        ```
    """
    try:
        if isinstance(ctx_or_interaction, discord.Interaction):
            user = ctx_or_interaction.user
            guild = ctx_or_interaction.guild
        else:
            user = ctx_or_interaction.author
            guild = ctx_or_interaction.guild

        if not guild:
            return False, discord.Embed(
                title="Error",
                description="This command can only be used in a server.",
                color=discord.Color.red()
            )

        if user.id == guild.owner_id:
            return True, None

        member = guild.get_member(user.id)
        if not member:
            return False, discord.Embed(
                title="Error",
                description="Could not verify your server membership.",
                color=discord.Color.red()
            )

        if getattr(member.guild_permissions, permission_name, False):
            return True, None

        server_info = open_json("storage/server_info.json")
        guild_prefs = server_info.get("preferences", {}).get(str(guild.id), {})
        required_role_id = guild_prefs.get(minimum_role)

        if not required_role_id:
            return False, discord.Embed(
                title="Error",
                description=f"No {minimum_role} role has been set for this server.",
                color=discord.Color.red()
            )

        required_role = guild.get_role(required_role_id)
        if not required_role:
            return False, discord.Embed(
                title="Error",
                description=f"The configured {minimum_role} role could not be found.",
                color=discord.Color.red()
            )

        if required_role in member.roles:
            return True, None

        return False, discord.Embed(
            title="Missing Permissions",
            description=f"You need the `{required_role.name}` role or `{permission_name}` permission to use this command.",
            color=discord.Color.red()
        )

    except Exception as e:
        return False, discord.Embed(
            title="Error",
            description=f"An error occurred while checking permissions: {str(e)}",
            color=discord.Color.red()
        )

def no_permission_embed(
        permission: str = None,
        role: str = None
    ) -> discord.Embed:
    """
    Creates an embed that indicates lack of required role/permission to use a command.

    Parameters:
        permission (str, optional): The permission name that is required.
        role (str, optional): The role name that is required.

    Returns:
        discord.Embed: An embed explaining the missing permissions/roles.

    Example:
        ```
        # Create embed for missing ban permission
        embed = no_permission_embed(permission="ban_members")
        await ctx.send(embed=embed)

        # Create embed for missing moderator role
        embed = no_permission_embed(role="Moderator")
        await ctx.send(embed=embed)
        ```
    """
    embed = discord.Embed(
        title="Missing Permissions",
        description="❌ You do not have permission to use this command!",
        color=0xFF0000
    )

    embed.set_footer(text=(
                f"You need the "
                f"{f"{permission.replace('_', ' ').title()} permission" if permission else None} "
                f"{"or" if permission and role else None} "
                f"{f"{role} role" if role else None} to use this command."
            )
        )
    return embed

async def store_modlog(
        modlog_type: str,
        server_id: int,
        moderator: discord.User,
        user: Optional[discord.User] = None,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
        reason: str = "No reason provided.",
        arguments: Optional[str] = None,
        bot: Optional[discord.Client] = None
    ) -> None:
    """
    Stores and sends moderation action logs.

    Parameters:
        modlog_type (str): Type of moderation action (ban, kick, warn, etc.)
        server_id (int): Discord server ID where action occurred
        moderator (discord.User): Staff member who performed the action
        user (discord.User, optional): User affected by the action
        channel (discord.TextChannel, optional): Channel affected by the action
        role (discord.Role, optional): Role affected by the action
        reason (str): Reason for the moderation action
        arguments (str, optional): Additional context or arguments
        bot: Discord bot instance for sending logs

    Raises:
        discord.Forbidden: If bot lacks permissions to send to modlog channel
        discord.HTTPException: If sending the modlog message fails
        ValueError: If channel ID format is invalid

    Example:
        ```
        # Store a ban log
        await store_modlog(
            modlog_type="ban",
            server_id=guild.id,
            moderator=ctx.author,
            user=member,
            reason="Multiple rule violations",
            bot=bot
        )

        # Store a channel lockdown log
        await store_modlog(
            modlog_type="lockdown",
            server_id=guild.id,
            moderator=interaction.user,
            channel=text_channel,
            reason="Raid prevention",
            bot=bot
        )

        # Store a role modification log
        await store_modlog(
            modlog_type="role_update",
            server_id=guild.id,
            moderator=ctx.author,
            role=role,
            reason="Updated permissions",
            arguments="Added manage messages permission",
            bot=bot
        )
        ```
    """
    if bot and not bot.user.bot:
        raise ValueError("This bot cannot be used as a user account.")

    server_info = open_json("storage/server_info.json")
    for key in ["preferences", "modlogs", "modstats", "warnings"]:
        server_info.setdefault(key, {})
        if key in ["modlogs", "modstats", "warnings"]:
            server_info[key].setdefault(str(server_id), {})

    modlog_channel = None
    channel_id = server_info["preferences"].get(str(server_id), {}).get("modLogs")
    
    if channel_id and bot:
        try:
            modlog_channel = bot.get_channel(int(channel_id))
            if not modlog_channel:
                raise discord.NotFound(f"Could not find channel with ID {channel_id}")
        except ValueError:
            raise ValueError(f"Invalid channel ID format: {channel_id}")
        except Exception as e:
            raise Exception(f"Error retrieving modlog channel: {str(e)}")

    embed = discord.Embed(
        title="Moderation Log",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
    )
    
    embed_fields = {
        "Type": modlog_type,
        "Reason": reason,
        "Moderator": moderator.mention,
    }
    
    if role:
        embed_fields["Role affected"] = role.mention
    if user:
        embed_fields["User affected"] = user.mention
    if channel:
        embed_fields["Channel affected"] = channel.mention
    if arguments:
        embed_fields["Extra arguments"] = arguments

    for name, value in embed_fields.items():
        embed.add_field(name=name, value=value, inline=False)

    if user:
        user_id = str(user.id)
        moderator_id = str(moderator.id)
        
        server_info["modlogs"][str(server_id)].setdefault(user_id, {})
        
        last_case_number = max(map(int, server_info["modlogs"][str(server_id)][user_id].keys()), default=0)
        new_case_number = last_case_number + 1
        
        modlog_entry = {
            "Type": modlog_type,
            "User": str(user),
            "Moderator": str(moderator),
            "Reason": reason,
            "Time": int(time.time()),
        }
        
        server_info["modlogs"][str(server_id)][user_id][str(new_case_number)] = modlog_entry

        if modlog_type.title() in ["Kick", "Mute", "Ban", "Warn"]:
            server_info["modstats"][str(server_id)].setdefault(moderator_id, {})
            server_info["modstats"][str(server_id)][moderator_id][str(new_case_number)] = {
                "type": modlog_type.title(),
                "timestamp": int(time.time()),
            }

    if modlog_channel:
        try:
            await modlog_channel.send(embed=embed)
        except discord.Forbidden:
            raise discord.Forbidden(f"Missing permissions to send messages in modlog channel {modlog_channel.id}")
        except discord.HTTPException as e:
            raise discord.HTTPException(f"Failed to send modlog message: {e}")

    save_json("storage/server_info.json", server_info)

async def send_modlog_embed(
        interaction: discord.Interaction, 
        user: discord.User, 
        page: int
    ) -> Tuple[Optional[discord.Embed], int, int]:
    """
    Generates and sends an embed displaying a user's moderation history.

    Parameters:
        interaction (discord.Interaction): The interaction requesting the logs
        user (discord.User): User whose logs are being requested
        page (int): Page number of logs to display

    Returns:
        tuple: (embed, total_logs, total_pages)
            - embed: discord.Embed containing the log entries
            - total_logs: Total number of logs for the user
            - total_pages: Total number of pages available

    Example:
        ```
        # Display first page of user's modlogs
        embed, total_logs, total_pages = await send_modlog_embed(
            interaction=interaction,
            user=member,
            page=1
        )
        if embed:
            await interaction.followup.send(embed=embed)
            if total_pages > 1:
                print(f"User has {total_logs} logs across {total_pages} pages")

        # Display specific page of modlogs
        embed, _, _ = await send_modlog_embed(
            interaction=interaction,
            user=member,
            page=3  # Show third page
        )
        if embed:
            await interaction.followup.send(embed=embed)
        ```
    """
    if not is_valid_bot_instance(interaction):
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error",
                description="❌ This bot cannot be used as a user account.",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return None, 0, 0

    server_info = open_json("storage/server_info.json")
    server_id = str(interaction.guild.id)
    user_id = str(user.id)

    user_logs = server_info["modlogs"].get(server_id, {}).get(user_id, {})
    total_logs = len(user_logs)

    if total_logs == 0:
        await interaction.followup.send(f"No logs found for {user}.", ephemeral=True)
        return None, total_logs, 0

    logs_per_page = 10
    total_pages = (total_logs // logs_per_page) + (1 if total_logs % logs_per_page > 0 else 0)

    if page < 1 or page > total_pages:
        await interaction.followup.send(f"Invalid page number. Please provide a page between 1 and {total_pages}.", ephemeral=True)
        return None, total_logs, total_pages

    embed = discord.Embed(
        title=f"Modlogs for {user}", 
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    start_index = (page - 1) * logs_per_page
    end_index = start_index + logs_per_page
    logs_to_display = list(user_logs.items())[start_index:end_index]

    for case_number, log in logs_to_display:
        embed.add_field(
            name=f"Case #{case_number}",
            value=(
                f"Type: {log['Type']}\n"
                f"User: {log['User']}\n"
                f"Moderator: {log['Moderator']}\n"
                f"Reason: {log['Reason']}\n"
                f"Time: <t:{log['Time']}:F>"
            ),
            inline=False
        )

    embed.set_footer(text=f"{total_logs} total logs | Page {page} of {total_pages}", icon_url=user.avatar.url)

    return embed, total_logs, total_pages

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

class DelLog(discord.ui.Select):
    def __init__(
        self,
        log_type,
        member: discord.Member,
        embed: discord.Embed,
        interaction: discord.Interaction | commands.Context,
        page: int = 1,
        *args,
        **kwargs,
    ):
        placeholder = f"Delete a {log_type}"
        super().__init__(placeholder=placeholder, *args, **kwargs)

        self.log_type = log_type
        self.member = member
        self.embed = embed
        self.interaction = interaction
        self.page = page
        self.items_per_page = 25

        server_info = open_json("storage/server_info.json")
        
        if self.log_type == "warn":
            self.logs = server_info.get("warnings", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})
        elif self.log_type == "note":
            self.logs = server_info.get("notes", {}).get(str(interaction.guild.id), {}).get(str(member.id), {})

        sorted_logs = sorted(self.logs.items(), key=lambda x: int(x[0]))
        total_logs = len(sorted_logs)
        self.total_pages = max(1, (total_logs + self.items_per_page - 1) // self.items_per_page)

        start_idx = (self.page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, total_logs)
        current_page_logs = dict(sorted_logs[start_idx:end_idx])

        self.options = [
            discord.SelectOption(
                label=f"{self.log_type.capitalize()} Case #{case_number}",
                description=(log["reason"] if "reason" in log else "No reason provided.")[:100],
                value=str(case_number)
            )
            for case_number, log in current_page_logs.items()
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
            server_info = open_json("storage/server_info.json")

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

                save_json("storage/server_info.json", server_info)

                self.embed.clear_fields()
                if self.logs:
                    sorted_logs = sorted(self.logs.items(), key=lambda x: int(x[0]))
                    total_logs = len(sorted_logs)
                    self.total_pages = max(1, (total_logs + self.items_per_page - 1) // self.items_per_page)

                    if self.page > self.total_pages:
                        self.page = self.total_pages

                    start_idx = (self.page - 1) * self.items_per_page
                    end_idx = min(start_idx + self.items_per_page, total_logs)
                    current_page_logs = dict(sorted_logs[start_idx:end_idx])

                    for index, log in current_page_logs.items():
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
                        for index, log in current_page_logs.items()
                    ]
                    
                    if self.total_pages > 1:
                        self.embed.set_footer(text=f"Page {self.page}/{self.total_pages}")
                else:
                    self.embed.description = f"No {self.log_type}s left for {self.member.display_name}."

                view = discord.ui.View()
                if self.logs:
                    view.add_item(self)
                    if self.total_pages > 1:
                        view.add_item(PageButtons(self))

                try:
                    await interaction.response.edit_message(embed=self.embed, view=view)
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

class PageButtons(discord.ui.View):
    def __init__(self, select: DelLog):
        super().__init__()
        self.select = select

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.select.page > 1:
            self.select.page -= 1
            await self.update_page(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.select.page < self.select.total_pages:
            self.select.page += 1
            await self.update_page(interaction)

    async def update_page(self, interaction: discord.Interaction):
        sorted_logs = sorted(self.select.logs.items(), key=lambda x: int(x[0]))
        start_idx = (self.select.page - 1) * self.select.items_per_page
        end_idx = min(start_idx + self.select.items_per_page, len(sorted_logs))
        current_page_logs = dict(sorted_logs[start_idx:end_idx])

        self.select.embed.clear_fields()
        for index, log in current_page_logs.items():
            time_str = f"<t:{log['time']}:R>"
            moderator_id = log["moderator"]
            moderator = interaction.guild.get_member(int(moderator_id)) if moderator_id.isdigit() else None
            moderator_name = moderator.display_name if moderator else "Unknown"
            self.select.embed.add_field(
                name=f"Case #{index} - {self.select.log_type.capitalize()} by {moderator_name}",
                value=f"Reason: {log['reason'][:100]}\nTime: {time_str}",
                inline=False
            )

        self.select.embed.set_footer(text=f"Page {self.select.page}/{self.select.total_pages}")

        self.select.options = [
            discord.SelectOption(
                label=f"{self.select.log_type.capitalize()} Case #{index}",
                description=log["reason"][:100],
                value=str(index)
            )
            for index, log in current_page_logs.items()
        ]

        await interaction.response.edit_message(embed=self.select.embed, view=self)
