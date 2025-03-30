import discord
from discord.ext import commands
from discord.ui import Button, View
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta
from bot_utils import open_json
from discord import app_commands

class MessageLink(Button):
    def __init__(self, guild_id: int, channel_id: int, message_id: Optional[int] = None):
        super().__init__(
            label="Go to Message",
            style=discord.ButtonStyle.link,
            url=f"discord://discord.com/channels/{guild_id}/{channel_id}/{message_id if message_id else ''}"
        )

class MessageLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_message_content = {}
        self.snipes: Dict[int, Dict[str, dict]] = defaultdict(lambda: {
            "messages": [],
            "reactions": [],
            "edits": []
        })
        self.max_snipes = 10
        self.snipe_timeout = timedelta(minutes=5)

    def _add_snipe(self, channel_id: int, snipe_type: str, data: dict):
        """Add a snipe to the cache"""
        snipes = self.snipes[channel_id][snipe_type]
        snipes.insert(0, {**data, "timestamp": datetime.utcnow()})
        if len(snipes) > self.max_snipes:
            snipes.pop()

    def _get_snipes(self, channel_id: int, snipe_type: str) -> list:
        """Get valid snipes from cache"""
        now = datetime.utcnow()
        snipes = self.snipes[channel_id][snipe_type]
        valid_snipes = [s for s in snipes if now - s["timestamp"] < self.snipe_timeout]
        self.snipes[channel_id][snipe_type] = valid_snipes
        return valid_snipes

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        self._last_message_content[message.id] = message.content

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return

        if before.content == after.content:
            return

        try:
            server_info = open_json("storage/server_info.json")
            if "moderation" not in server_info or "messageLogs" not in server_info["moderation"]:
                return

            log_channel_id = server_info["moderation"]["messageLogs"]
            
            log_channel = self.bot.get_channel(int(log_channel_id))
            if not log_channel:
                return

            embed = discord.Embed(
                title="Message Edited",
                description=f"Message by {before.author.mention} edited in {before.channel.mention}",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Before", value=before.content or "No content", inline=False)
            embed.add_field(name="After", value=after.content or "No content", inline=False)
            embed.set_footer(text=f"User ID: {before.author.id}")

            view = View()
            view.add_item(MessageLink(before.guild.id, before.channel.id, before.id))
            
            await log_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"Error in message edit logging: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return

        try:
            self._add_snipe(message.channel.id, "messages", {
                "content": message.content,
                "author": message.author,
                "attachments": [a.url for a in message.attachments]
            })

            server_info = open_json("storage/server_info.json")            
            if "moderation" not in server_info or "messageLogs" not in server_info["moderation"]:
                return

            log_channel_id = server_info["moderation"]["messageLogs"]
            
            log_channel = self.bot.get_channel(int(log_channel_id))
            if not log_channel:
                return

            embed = discord.Embed(
                title="Message Deleted",
                description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            content = self._last_message_content.pop(message.id, None) or message.content or "No content"
            embed.add_field(name="Content", value=content, inline=False)
            
            if message.attachments:
                attachment_list = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
                embed.add_field(name="Attachments", value=attachment_list, inline=False)
                
            embed.set_footer(text=f"User ID: {message.author.id}")

            view = View()
            view.add_item(MessageLink(message.guild.id, message.channel.id, message.id))
            
            await log_channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"Error in message delete logging: {e}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        self._add_snipe(reaction.message.channel.id, "reactions", {
            "emoji": str(reaction.emoji),
            "author": user,
            "message_id": reaction.message.id
        })

    @commands.hybrid_command(name="snipe")
    @commands.guild_only()
    @app_commands.choices(type=[
        app_commands.Choice(name="Messages", value="messages"),
        app_commands.Choice(name="Reactions", value="reactions"),
        app_commands.Choice(name="Edits", value="edits")
    ])
    async def snipe(self, ctx: commands.Context, type: str = "messages", index: int = 0):
        snipe_type = type.lower()
        if snipe_type not in ["messages", "reactions", "edits"]:
            return await ctx.send("Invalid snipe type! Use messages, reactions, or edits.")

        snipes = self._get_snipes(ctx.channel.id, snipe_type)
        if not snipes:
            return await ctx.send(f"No {snipe_type} to snipe!")

        if not 0 <= index < len(snipes):
            return await ctx.send(f"Invalid index! Must be between 0 and {len(snipes)-1}")

        snipe = snipes[index]
        embed = discord.Embed(
            title=f"{snipe_type.title()} Snipe",
            color=discord.Color.blurple(),
            timestamp=snipe["timestamp"]
        )

        if snipe_type == "messages":
            embed.description = f"**Content:** {snipe['content'] or 'No content'}\n**Deleted by:** {snipe['author'].mention}"
            if snipe["attachments"]:
                embed.add_field(name="Attachments", value="\n".join(snipe["attachments"]), inline=False)
        elif snipe_type == "reactions":
            embed.description = f"Reaction {snipe['emoji']} removed by {snipe['author'].mention}"
            view = View()
            view.add_item(MessageLink(ctx.guild.id, ctx.channel.id, snipe["message_id"]))
            await ctx.send(embed=embed, view=view)
            return
        elif snipe_type == "edits":
            embed.description = f"Message edited by {snipe['author'].mention}"
            embed.add_field(name="Before", value=snipe["before"] or "No content", inline=False)
            embed.add_field(name="After", value=snipe["after"] or "No content", inline=False)

        embed.set_author(name=str(snipe["author"]), icon_url=snipe["author"].avatar.url)
        embed.set_footer(text=f"#{index+1} | {len(snipes)} snipes available")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MessageLogs(bot))
