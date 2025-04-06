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
            await interaction.followup.send(f"Successfully set `{option.name}` to {channel.mention}")
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
            await interaction.followup.send(f"Successfully set `{option.name}` to {role.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="auto")
    @app_commands.choices(
        setting=[
            app_commands.Choice(name="Auto Mute 1-5", value="mute1"),
            app_commands.Choice(name="Auto Mute 6-10", value="mute2"),
            app_commands.Choice(name="Auto Kick 1-5", value="kick1"),
            app_commands.Choice(name="Auto Kick 6-10", value="kick2"),
            app_commands.Choice(name="Auto Ban 1-5", value="ban1"),
            app_commands.Choice(name="Auto Ban 6-10", value="ban2")
        ]
    )
    async def setauto(self, interaction: discord.Interaction, setting: app_commands.Choice[str]):
        try:
            has_mod, embed = check_moderation_info(interaction, "administrator", "manager")
            if not has_mod:
                await interaction.response.send_message(embed=embed)
                return

            modal = None
            setting_type = setting.value[:-1]
            start_index = 5 if setting.value.endswith('2') else 0
            
            if setting_type == "mute":
                modal = AutoMuteModal(start_index)
            elif setting_type == "kick":
                modal = AutoKickModal(start_index)
            elif setting_type == "ban":
                modal = AutoBanModal(start_index)
                
            await interaction.response.send_modal(modal)
        except Exception as e:
            await handle_logs(interaction, e)


class BaseAutoModal(discord.ui.Modal):
    def __init__(self, start_index: int = 0):
        super().__init__(title=f"{self.base_title} (Warnings {start_index+1}-{start_index+5})")
        self.start_index = start_index
        
        for i in range(5):
            self.add_item(self.create_text_input(start_index + i))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.final_submit(interaction)
        except Exception as e:
            await interaction.response.send_message("Something went wrong. Please try again.", ephemeral=True)
            await handle_logs(interaction, e)

    def get_all_responses(self):
        return [item.value or "" for item in self.children]

    async def update_settings(self, interaction: discord.Interaction, settings_type: str, new_settings: list):
        server_info = open_json("storage/server_info.json")
        if "moderation" not in server_info:
            server_info["moderation"] = {}
        if "warnings" not in server_info["moderation"]:
            server_info["moderation"]["warnings"] = [{"mute": 0, "kick": False, "ban": 0} for _ in range(10)]

        warnings = server_info["moderation"]["warnings"]
        for i, setting in enumerate(new_settings):
            actual_index = self.start_index + i
            if actual_index < len(warnings):
                if settings_type == "mute" and setting > 0:
                    warnings[actual_index] = {"mute": setting, "kick": False, "ban": 0}
                elif settings_type == "kick" and setting:
                    warnings[actual_index] = {"mute": 0, "kick": True, "ban": 0}
                elif settings_type == "ban" and (setting > 0 or setting == -1):
                    warnings[actual_index] = {"mute": 0, "kick": False, "ban": setting}

        server_info["moderation"]["warnings"] = warnings
        save_json("storage/server_info.json", server_info)

        embed = discord.Embed(
            title="Warning Punishments Summary",
            color=discord.Color.blue()
        )

        for i, warning in enumerate(warnings):
            active_punishments = []
            
            if warning['mute'] > 0:
                active_punishments.append(f"Mute: {warning['mute']}s")
            if warning['kick']:
                active_punishments.append("Kick: Yes")
            if warning['ban'] == -1:
                active_punishments.append("Ban: Permanent")
            elif warning['ban'] > 0:
                active_punishments.append(f"Ban: {warning['ban']}s")
            
            if active_punishments:
                embed.add_field(
                    name=f"Warning {i+1}",
                    value="\n".join(active_punishments),
                    inline=True
                )

        await store_modlog(
            modlog_type="settings_update",
            server_id=interaction.guild_id,
            moderator=interaction.user,
            reason=f"Updated {settings_type} settings for warnings {self.start_index+1}-{self.start_index+5}",
            bot=interaction.client
        )

        await interaction.response.send_message(
            f"Successfully updated {settings_type} settings for warnings {self.start_index+1}-{self.start_index+5}",
            embed=embed
        )


class AutoMuteModal(BaseAutoModal):
    base_title = "Auto Mute Settings"
    
    def create_text_input(self, index: int):
        return discord.ui.TextInput(
            label=f"Warning {index+1} Duration",
            placeholder="e.g. 30m, 1h, 1d",
            required=False,
            max_length=10
        )

    async def final_submit(self, interaction: discord.Interaction):
        from bot_utils import parse_duration
        try:
            responses = self.get_all_responses()
            durations = []
            
            for i, value in enumerate(responses):
                if value:
                    duration = parse_duration(value)
                    if not duration:
                        return await interaction.response.send_message(
                            f"Invalid duration format for Warning {i+1}. Use formats like 30m, 1h, 1d",
                            ephemeral=True
                        )
                    durations.append(int(duration.total_seconds()))
                else:
                    durations.append(0)

            await self.update_settings(interaction, "mute", durations)
        except Exception as e:
            await handle_logs(interaction, e)


class AutoKickModal(BaseAutoModal):
    base_title = "Auto Kick Settings"
    
    def create_text_input(self, index: int):
        return discord.ui.TextInput(
            label=f"Kick at Warning {index+1}",
            placeholder="Yes/No",
            required=False,
            max_length=3
        )

    async def final_submit(self, interaction: discord.Interaction):
        try:
            responses = self.get_all_responses()
            kick_settings = [value.lower() in ['yes', 'y', 'true'] if value else False for value in responses]
            await self.update_settings(interaction, "kick", kick_settings)
        except Exception as e:
            await handle_logs(interaction, e)


class AutoBanModal(BaseAutoModal):
    base_title = "Auto Ban Settings"
    
    def create_text_input(self, index: int):
        return discord.ui.TextInput(
            label=f"Warning {index+1} Ban Duration",
            placeholder="Duration (e.g., 1h30m) or -1 for permanent",
            required=False,
            max_length=10
        )

    async def final_submit(self, interaction: discord.Interaction):
        from bot_utils import parse_duration
        try:
            responses = self.get_all_responses()
            durations = []
            
            for i, value in enumerate(responses):
                if value:
                    if value == "-1":
                        durations.append(-1)
                    else:
                        duration = parse_duration(value)
                        if not duration:
                            return await interaction.response.send_message(
                                f"Invalid duration format for Warning {i+1}. Use formats like 30m, 1h, 1d or -1",
                                ephemeral=True
                            )
                        durations.append(int(duration.total_seconds()))
                else:
                    durations.append(0)

            await self.update_settings(interaction, "ban", durations)
        except Exception as e:
            await handle_logs(interaction, e)


class SetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(SetCommandGroup())

async def setup(bot):
    await bot.add_cog(SetCog(bot))