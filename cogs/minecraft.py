from bot_utils import (
    handle_logs,
    mc_fetchUUID,
    load_commands,
    open_file
)

import discord
from discord.ext import commands
from discord import app_commands

class MinecraftCommandsGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="minecraft", description="Minecraft related commands")

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
    async def minecraftavatar(self, interaction: discord.Interaction, username: str):
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