import discord
from discord.ext import commands
from discord import app_commands

import time

from bot_utils import (
    handle_logs,
    open_json,
    save_json
)

from .utils import (
    store_modlog,
    check_moderation_info,
    dm_moderation_embed,
    LogPaginator,
    LogPageSelect,
    DelLog
)

class WarnCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def handle_warn(self, ctx, member: discord.Member, reason: str):
        has_mod, embed = check_moderation_info(ctx, "manage_messages", "moderator")
        if not has_mod:
            return await ctx.send(embed=embed)

        if member.id == ctx.author.id:
            return await ctx.send("You cannot warn yourself.")

        if member.bot:
            return await ctx.send("You cannot warn bots.")

        if len(reason) > 1024:
            return await ctx.send("Please provide a shorter reason.")

        server_info = open_json("storage/server_info.json")
        guild_id = str(ctx.guild.id)

        server_info.setdefault("warnings", {}).setdefault(guild_id, {}).setdefault(str(member.id), {})
        case_numbers = [int(x) for x in server_info["warnings"][guild_id][str(member.id)].keys()]
        next_case = str(max(case_numbers + [0]) + 1)

        server_info["warnings"][guild_id][str(member.id)][next_case] = {
            "reason": reason,
            "moderator": str(ctx.author.id),
            "time": int(time.time())
        }
        save_json("storage/server_info.json", server_info)

        await dm_moderation_embed(ctx, member, "warn", reason)

        await store_modlog(
            modlog_type="Warn",
            moderator=ctx.author,
            user=member,
            reason=reason,
            server_id=ctx.guild.id,
            bot=self.bot
        )

    @commands.hybrid_command(name="warn")
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            await self.handle_warn(ctx, member, reason)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="warns", aliases=["warnings"])
    async def warns(self, ctx, member: discord.Member = None, page: int = 1):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            member = member or ctx.author

            has_mod, embed = check_moderation_info(ctx, "manage_messages", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            server_info = open_json("storage/server_info.json")
            member_warnings = server_info.get("warnings", {}).get(str(ctx.guild.id), {}).get(str(member.id), {})

            if member_warnings:
                paginator = LogPaginator("warning", member_warnings, member)
                if not 1 <= page <= paginator.total_pages:
                    page = 1

                embed = paginator.get_page(page)

                view = discord.ui.View()
                if paginator.total_pages > 1:
                    view.add_item(LogPageSelect(paginator, page))
                view.add_item(DelLog("warn", member, embed, ctx))

                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send(f"No warnings found for {member.display_name}.")

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(WarnCommands(bot))
