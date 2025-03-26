import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    get_role_hierarchy,
    parse_duration,
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

    @commands.hybrid_command(name="mute")
    async def mute(self, ctx, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            has_mod, embed = check_moderation_info(ctx, "moderate_members", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            if not get_role_hierarchy(ctx.author, member):
                return await ctx.send("You require a higher role hierachy than the target user!")

            duration = parse_duration(duration)

            if not duration:
                return await ctx.send("Invalid time format. Please use formats like `1h10m15s` or `15s1h10m`.")

            until = discord.utils.utcnow() + duration
            await member.timeout(until, reason=reason)

            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            human_readable_time = (f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)")

            await dm_moderation_embed(ctx, member, "muted", reason, human_readable_time)

            await store_modlog(
                modlog_type="Mute",
                moderator=ctx.author,
                user=member,
                reason=reason,
                arguments=f"{reason}\nMuted for {human_readable_time}",
                server_id=ctx.guild.id,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="unmute")
    async def unmute(self, ctx, member: discord.Member, reason: str = "No reason provided"):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            has_mod, embed = check_moderation_info(ctx, "moderate_members", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            if not get_role_hierarchy(ctx.author, member):
                return await ctx.send("You require a higher role hierachy than the target user!")
            
            await member.timeout(None, reason=reason)

            await dm_moderation_embed(ctx, member, "unmuted", reason)

            await store_modlog(
                modlog_type="Unmute",
                moderator=ctx.author,
                user=member,
                reason=reason,
                server_id=ctx.guild.id,
                bot=self.bot
            )

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(MuteCommands(bot))
