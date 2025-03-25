from bot_utils import (
    mc_fetchUUID,

    load_commands,
    handle_logs,
)

import discord
from discord.ext import commands
from discord import app_commands

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class MinecraftCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="minecraft", description="Minecraft related commands", guild_only=False)

        load_commands(self.commands, "minecraft")
        
    @app_commands.command(name="uuid", description="Get a Minecraft UUID based on a username")
    @app_commands.describe(username="A Minecraft username")
    async def uuid(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            uuid = await mc_fetchUUID(interaction, username)
            if uuid:
                await interaction.followup.send(f"The UUID for {username} is {uuid}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="avatar", description="Provides a Minecraft account's avatar.")
    @app_commands.describe(username="A Minecraft username")
    async def avatar(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            uuid = await mc_fetchUUID(interaction, username)
            if uuid:
                image_url = f"https://api.mineatar.io/body/full/{uuid}"

                embed = discord.Embed(title=f"{username}'s Avatar", color=discord.Color.blue())
                embed.set_image(url=image_url)
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)

                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("UUID not found for the provided username.")
        except Exception as e:
            await handle_logs(interaction, e)

class MinecraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(MinecraftCommandsGroup())

async def setup(bot):
    await bot.add_cog(MinecraftCog(bot))