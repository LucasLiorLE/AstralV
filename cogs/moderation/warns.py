import discord
from discord.ext import commands

import time
from datetime import datetime, timedelta

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
        warnings = server_info["warnings"][guild_id][str(member.id)]
        
        warning_count = len(warnings)
        
        next_case = str(max([int(x) for x in warnings.keys()] + [0]) + 1)
        warnings[next_case] = {
            "reason": reason,
            "moderator": str(ctx.author.id),
            "time": int(time.time())
        }
        
        auto_settings = server_info.get("moderation", {}).get("warnings", [])
        if warning_count < len(auto_settings):
            punishment = auto_settings[warning_count]
            
            try:
                if punishment.get("mute", 0) > 0:
                    duration = timedelta(seconds=punishment["mute"])
                    until = discord.utils.utcnow() + duration
                    
                    try:
                        await member.timeout(until, reason=f"Auto-mute: Reached warning {warning_count + 1}")
                        
                        hours, remainder = divmod(duration.total_seconds(), 3600)
                        minutes, seconds = divmod(remainder, 60)
                        human_readable_time = f"{int(hours)} hour(s) {int(minutes)} minute(s) {int(seconds)} second(s)"
                        
                        await dm_moderation_embed(ctx, member, "muted", 
                            f"Auto-mute: Reached warning {warning_count + 1}", 
                            human_readable_time)
                        
                        await store_modlog(
                            modlog_type="Mute",
                            moderator=ctx.guild.me,
                            user=member,
                            reason=f"Auto-mute: Reached warning {warning_count + 1}",
                            arguments=f"Muted for {human_readable_time}",
                            server_id=ctx.guild.id,
                            bot=self.bot
                        )
                    except discord.Forbidden:
                        await ctx.send("I don't have permission to mute members.")
                    except Exception as e:
                        await ctx.send(f"Error applying auto-mute: {str(e)}")

                elif punishment.get("kick", False):
                    await member.kick(reason=f"Auto-kick: Reached warning {warning_count + 1}")
                    await dm_moderation_embed(ctx, member, "kick", f"Auto-kick: Reached warning {warning_count + 1}")
                    await store_modlog(
                        modlog_type="Kick",
                        moderator=ctx.guild.me,
                        user=member,
                        reason=f"Auto-kick: Reached warning {warning_count + 1}",
                        server_id=ctx.guild.id,
                        bot=self.bot
                    )
                
                elif punishment.get("ban", 0) != 0:
                    ban_duration = punishment["ban"]
                    
                    await ctx.guild.ban(member, reason=f"Auto-ban: Reached warning {warning_count + 1}")
                    await dm_moderation_embed(ctx, member, "banned", f"Auto-ban: Reached warning {warning_count + 1}")
                    
                    if ban_duration > 0:
                        if 'tempbans' not in server_info:
                            server_info['tempbans'] = {}
                        if guild_id not in server_info['tempbans']:
                            server_info['tempbans'][guild_id] = {}
                            
                        server_info['tempbans'][guild_id][str(member.id)] = {
                            'expires': int(time.time()) + ban_duration
                        }
                        
                        expire_time = datetime.now() + timedelta(seconds=ban_duration)
                        reason = f"Auto-ban: Reached warning {warning_count + 1} (Temporary: until {expire_time.strftime('%Y-%m-%d %H:%M:%S')})"
                    else:
                        reason = f"Auto-ban: Reached warning {warning_count + 1} (Permanent)"
                    
                    await store_modlog(
                        modlog_type="Ban",
                        moderator=ctx.guild.me,
                        user=member,
                        reason=reason,
                        server_id=ctx.guild.id,
                        bot=self.bot
                    )
            
            except discord.Forbidden:
                await ctx.send("I don't have permission to perform the auto-moderation action.")
            except Exception as e:
                await ctx.send(f"Error performing auto-moderation: {str(e)}")

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
        
        await ctx.send(f"Successfully warned {member.mention}")

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
