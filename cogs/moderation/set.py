import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    open_json,
    handle_logs
)

from .utils import (
    check_moderation_info,
    store_modlog,
    check_user
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
            guild_id = str(interaction.guild_id)

            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if "moderation" not in server_info:
                server_info["moderation"] = {}

            server_info["moderation"][option.value] = channel.id
                
            store_modlog(server_info, guild_id)
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
            guild_id = str(interaction.guild_id)    

            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if "moderation" not in server_info:
                server_info["moderation"] = {}

            server_info["moderation"][option.value] = role.id   
            store_modlog(server_info, guild_id)
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