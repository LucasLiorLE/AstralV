import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    get_role_hierarchy,
    parse_duration,
    create_interaction,
    get_member,
    handle_logs
)

from .utils import (
    store_modlog,  
    check_moderation_info,
    dm_moderation_embed
)

class MuteCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
                await interaction.followup.send("An error occurred while trying to mute this user.")

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

async def setup(bot):
    await bot.add_cog(MuteCommands(bot))
