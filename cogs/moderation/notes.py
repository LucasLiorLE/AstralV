import discord
from discord.ext import commands
from discord import app_commands

import time
from datetime import datetime, timezone

from bot_utils import (
    get_context_object,
    handle_logs,
    open_json,
    save_json
)

from .utils import (
    check_moderation_info,
    LogPaginator,
    LogPageSelect,
    DelLog
)

class NoteCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def handle_note(self, ctx_or_interaction, member: discord.Member, note: str):
        ctx = get_context_object(ctx_or_interaction)

        has_mod, embed = check_moderation_info(ctx_or_interaction, "manage_messages", "moderator")
        if not has_mod:
            return await ctx["send"](embed=embed)

        if len(note) > 1024:
            return await ctx["send"]("Note must be less than 1024 characters.")

        server_info = open_json("storage/server_info.json")
        guild_id = str(ctx["guild_id"])

        server_info.setdefault("notes", {}).setdefault(guild_id, {}).setdefault(str(member.id), {})
        case_numbers = [int(x) for x in server_info["notes"][guild_id][str(member.id)].keys()]
        next_case = str(max(case_numbers + [0]) + 1)

        server_info["notes"][guild_id][str(member.id)][next_case] = {
            "reason": note,
            "moderator": str(ctx["user"].id),
            "time": int(time.time())
        }
        save_json("storage/server_info.json", server_info)

        embed = discord.Embed(
            title=f"Member note.",
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Action", value="Note", inline=False) 
        embed.add_field(name="Reason", value=note, inline=False)

        await ctx["send"](embed=embed)

    @commands.hybrid_command(name="note")
    async def note(self, ctx, member: discord.Member, *, note: str):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            await self.handle_note(ctx, member, note)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="notes")
    async def notes(self, ctx, member: discord.Member = None, page: int = 1):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            member = member or ctx.author

            has_mod, embed = check_moderation_info(ctx, "manage_messages", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            server_info = open_json("storage/server_info.json")
            member_notes = server_info.get("notes", {}).get(str(ctx.guild.id), {}).get(str(member.id), {})

            if member_notes:
                paginator = LogPaginator("note", member_notes, member)
                if not 1 <= page <= paginator.total_pages:
                    page = 1

                embed = paginator.get_page(page)

                view = discord.ui.View()
                if paginator.total_pages > 1:
                    view.add_item(LogPageSelect(paginator, page))
                view.add_item(DelLog("note", member, embed, ctx))

                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send(f"No notes found for {member.display_name}.")

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(NoteCommands(bot))
