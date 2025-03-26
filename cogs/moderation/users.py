import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
from datetime import datetime, timedelta

from bot_utils import (
    get_role_hierarchy,
    parse_duration,
    handle_logs,
    open_json,
    save_json
)

from .utils import (
    store_modlog,
    check_moderation_info,
    dm_moderation_embed,
)

class UsersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_tempbans.start()

    def cog_unload(self):
        self.check_tempbans.cancel()

    @tasks.loop(minutes=1)
    async def check_tempbans(self):
        data = open_json("storage/server_info.json")
        current_time = int(time.time())
        
        if 'tempbans' not in data:
            data['tempbans'] = {}
            save_json("storage/server_info.json", data)
            return
            
        for guild_id in data['tempbans'].copy():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
                
            for user_id, ban_data in data['tempbans'][guild_id].copy().items():
                if current_time >= ban_data['expires']:
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        await guild.unban(user, reason="Temporary ban expired")
                        await store_modlog(
                            modlog_type="Unban",
                            moderator=self.bot.user,
                            user=user,
                            reason="Temporary ban expired",
                            server_id=guild.id,
                            bot=self.bot
                        )
                        del data['tempbans'][guild_id][user_id]
                    except:
                        continue
                        
            if not data['tempbans'][guild_id]:
                del data['tempbans'][guild_id]
                
        save_json("storage/server_info.json", data)

    @commands.hybrid_command(name="kick")
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
            
        try:
            has_mod, embed = check_moderation_info(ctx, "kick_members", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            if member.id == ctx.author.id:
                return await ctx.send("You cannot kick yourself.")

            if member.bot:
                return await ctx.send("You cannot kick bots.")

            if len(reason) > 1024:
                return await ctx.send("Please provide a shorter reason.")

            await member.kick(reason=reason)
            await dm_moderation_embed(ctx, member, "kick", reason)

            await store_modlog(
                modlog_type="Kick",
                moderator=ctx.author,
                user=member,
                reason=reason,
                server_id=ctx.guild.id,
                bot=self.bot
            )
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="ban")
    async def ban(self, ctx: commands.Context, user: discord.User, duration: str = None, *, reason: str = "No reason provided"):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
            
        try:
            has_mod, embed = check_moderation_info(ctx, "ban_members", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            if not user:
                return await ctx.send("You must specify either a user or a user ID to ban.")

            member = ctx.guild.get_member(user.id)
            if member and not get_role_hierarchy(ctx.author, member):
                return await ctx.send("You require a higher role hierarchy than the target user!")

            seconds = parse_duration(duration) if duration else 0
            
            await ctx.guild.ban(user, reason=reason)
            await dm_moderation_embed(ctx, user, "banned", reason)

            if seconds > 0:
                data = open_json("storage/server_info.json")
                if 'tempbans' not in data:
                    data['tempbans'] = {}
                if str(ctx.guild.id) not in data['tempbans']:
                    data['tempbans'][str(ctx.guild.id)] = {}
                    
                data['tempbans'][str(ctx.guild.id)][str(user.id)] = {
                    'expires': int(time.time()) + seconds
                }
                save_json("storage/server_info.json", data)
                
                expire_time = datetime.now() + timedelta(seconds=seconds)
                reason = f"{reason} (Temporary: until {expire_time.strftime('%Y-%m-%d %H:%M:%S')})"

            await store_modlog(
                modlog_type="Ban",
                moderator=ctx.author,
                user=user,
                reason=reason,
                server_id=ctx.guild.id,
                bot=self.bot
            )

            duration_text = f" for {duration}" if duration else ""
            await ctx.send(f"Successfully banned {user}{duration_text}")

        except discord.NotFound:
            await ctx.send("This user does not exist.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to ban users")
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="unban")
    async def unban(self, ctx: commands.Context, user: discord.User, reason: str = "No reason provided"):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
            
        try:
            has_mod, embed = check_moderation_info(ctx, "ban_members", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)
            
            if not user:
                return await ctx.send("You must specify either a user or a user ID to unban.")

            try:
                await ctx.guild.unban(user, reason=reason)
                await dm_moderation_embed(ctx, user, "unbanned", reason)

                await store_modlog(
                    modlog_type="Unban",
                    moderator=ctx.author,
                    user=user,
                    reason=reason,
                    server_id=ctx.guild.id,
                    bot=self.bot
                )
            except discord.NotFound:
                await ctx.send("User not found or is not banned")
            except discord.Forbidden:
                await ctx.send("I don't have permission to unban users")

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(UsersCog(bot))