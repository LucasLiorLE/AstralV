from bot_utils import (
    load_commands,
    handle_logs,
    osuAPI,
    open_file
)

import discord
from discord.ext import commands
from discord import app_commands

from ossapi import UserLookupKey

class OsuCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="osu", description="Osu related commands")

        load_commands(self.commands, "osu")

    @app_commands.command(name="profile")
    async def osuprofile(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        try:
            user = osuAPI.user(username, key=UserLookupKey.USERNAME)
            
            embed = discord.Embed(
                title=f"osu! Profile: {user.username}",
                url=f"https://osu.ppy.sh/users/{user.id}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=user.avatar_url)
            embed.add_field(name="Username", value=user.username or "N/A")
            embed.add_field(name="ID", value=str(user.id) if user.id is not None else "N/A")
            
            pp = f"{user.statistics.pp:,}pp" if user.statistics.pp is not None else "N/A"
            rank = f"#{user.statistics.global_rank:,}" if user.statistics.global_rank is not None else "N/A"

            embed.add_field(name="PP", value=pp)
            embed.add_field(name="Rank", value=rank)
            embed.add_field(name="Country", value=user.country.name or "N/A")
            embed.add_field(name="Playcount", value=f"{user.statistics.play_count:,}" if user.statistics.play_count is not None else "N/A")
            embed.add_field(
                name="Hit Accuracy",
                value=f"{user.statistics.hit_accuracy:.2f}%" if user.statistics.hit_accuracy is not None else "N/A",
                inline=True,
            )
            embed.add_field(
                name="Total Play Time",
                value=f"{user.statistics.play_time // 3600:,} hours" if user.statistics.play_time is not None else "N/A",
                inline=True,
            )
            embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

class OsuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(OsuCommandGroup())

async def setup(bot):
    await bot.add_cog(OsuCog(bot))