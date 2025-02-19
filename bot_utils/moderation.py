import discord
import time

from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from .file_handler import (
    save_file,
    open_file
)

async def dm_moderation_embed(
        interaction: discord.Interaction, 
        user: discord.User, 
        action: str, 
        reason: str, 
        duration: Optional[str] = None
    ) -> None:
    """
    Sends moderation action embeds to both the server and target user's DMs.
    
    Parameters:
        interaction (discord.Interaction): The interaction that triggered the moderation action
        user (discord.User): The user receiving the moderation action
        action (str): Type of moderation action (e.g. ban, kick, mute, etc.)
        reason (str): Reason for the moderation action
        duration (str, optional): Duration of temporary actions like mutes/bans
    """
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
        MemberEmbed = discord.Embed(
            title=f"You have been {action} in {interaction.guild.name}.", 
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        MemberEmbed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        MemberEmbed.add_field(name="Reason", value=reason, inline=False)
        if duration:
            MemberEmbed.add_field(name="Duration", value=duration, inline=False)
        MemberEmbed.set_footer(text="If you think this is a mistake, please contact a staff user.")
        await user.send(embed=MemberEmbed)
    except (discord.Forbidden, discord.HTTPException):
        embed.set_footer(text="I was unable to DM this user.")

    await interaction.followup.send(embed=embed)

def check_mod_server_info(id: int) -> Dict[str, Any]:
    """
    Checks whether basic moderation data is in server_info.json
    
    Parameteres:
        id: The guild ID of the server
        
    Returns:
        JsonData: The server info updated.
    """
    server_info = open_file("storage/server_info.json")

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

    save_file("storage/server_info.json", server_info)

    return server_info

def check_moderation_info(
        interaction,
        permission_name: str,
        role: str
    ) -> bool:
    """
    Verifies if a user has a certain role or permission.

    Parameters:
        interaction: The interaction used.
        permission_name (str): The Discord permission name to check (e.g. 'ban_members')
        role (str): The custom role to check for (e.g. 'moderator', 'manager')

    Returns:
        bool: True if the user has permissions, otherwise False.
    """
    guild_id = str(interaction.guild_id)
    server_info = check_mod_server_info(guild_id)

    mod_role_id: Optional[int] = server_info["preferences"][guild_id].get(role)
    has_permission: bool = getattr(interaction.user.guild_permissions, permission_name, False)
    has_role: bool = mod_role_id and discord.utils.get(interaction.user.roles, id=int(mod_role_id))

    if not (has_permission or has_role):
        return False, no_permission_embed(permission_name, role)

    return True, None

def no_permission_embed(
        permission: str = None,
        role: str = None
    ) -> discord.Embed:
    """
    An embed that says they do not have the required role/permission to use a command.

    Parameters:
        permission (str): The permission they are lacking.
        role (str): The role they are lacking.

    Returns:
        discord.Embed: The embed saying they do not have permission.
    """
    embed = discord.Embed(
        title="Missing Permissions",
        description="❌ You do not have permission to use this command!",
        color=0xFF0000
    )

    embed.set_footer(text=(
                f"You need the "
                f"{f"{permission.replace("_", " ").title()} permission" if permission else None} "
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
    """
    server_info = open_file("storage/server_info.json")
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

            if modlog_type.title() == "Warn":
                server_info["warnings"][str(server_id)].setdefault(user_id, {})
                warning_case_number = max(map(int, server_info["warnings"][str(server_id)][user_id].keys()), default=0) + 1
                
                server_info["warnings"][str(server_id)][user_id][str(warning_case_number)] = {
                    "reason": reason,
                    "moderator": str(moderator),
                    "time": int(time.time())
                }

    if modlog_channel:
        try:
            await modlog_channel.send(embed=embed)
        except discord.Forbidden:
            raise discord.Forbidden(f"Missing permissions to send messages in modlog channel {modlog_channel.id}")
        except discord.HTTPException as e:
            raise discord.HTTPException(f"Failed to send modlog message: {e}")

    save_file("storage/server_info.json", server_info)

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
    """
    server_info = open_file("storage/server_info.json")
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