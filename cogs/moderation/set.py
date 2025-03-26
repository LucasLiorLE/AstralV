import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    open_json,
    save_json,
    handle_logs
)

from .utils import (
    check_moderation_info,
    store_modlog,
)

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
            server_info = open_json("storage/server_info.json")

            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if "moderation" not in server_info:
                server_info["moderation"] = {}

            server_info["moderation"][option.value] = channel.id
            save_json("storage/server_info.json", server_info)
                
            await store_modlog(
                modlog_type="settings_update",
                server_id=interaction.guild_id,
                moderator=interaction.user,
                channel=channel,
                reason=f"Set {option.name} channel",
                bot=interaction.client
            )
            await interaction.followup.send(f"Successfully set {option.name} to {channel.mention}")
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
    async def setroles(self, interaction: discord.Interaction, option: app_commands.Choice[str], role: discord.Role):
        await interaction.response.defer()
        try:
            server_info = open_json("storage/server_info.json")

            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if "moderation" not in server_info:
                server_info["moderation"] = {}

            server_info["moderation"][option.value] = role.id   
            await store_modlog(
                modlog_type="settings_update",
                server_id=interaction.guild_id,
                moderator=interaction.user,
                role=role,
                reason=f"Set {option.name} role",
                bot=interaction.client
            )
            await interaction.followup.send(f"Successfully set {option.name} to {role.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

class SetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.set_command = SetCommandGroup()
        self.bot.tree.add_command(self.set_command)

async def setup(bot):
    await bot.add_cog(SetCog(bot))