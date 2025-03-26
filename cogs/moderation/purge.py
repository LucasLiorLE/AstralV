import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    open_file,
    handle_logs
)

from .utils import (
    store_modlog,
    check_moderation_info,
)


class MessageCheck:
    @staticmethod
    def cleanCommand(message: discord.Message) -> bool:
        is_bot_message = message.author == message.guild.me
        starts_with_question = message.content.startswith('.')  
        return is_bot_message or starts_with_question

    @staticmethod
    def is_text_only(message: discord.Message) -> bool:
        has_embeds = bool(message.embeds)
        has_attachments = bool(message.attachments)
        return not has_embeds and not has_attachments and bool(message.content.strip())

    @staticmethod
    def is_from_user(message: discord.Message, user: discord.User) -> bool:
        return message.author == user

    @staticmethod
    def has_embeds(message: discord.Message) -> bool:
        return bool(message.embeds)

    @staticmethod
    def has_attachments(message: discord.Message) -> bool:
        return bool(message.attachments)

    @staticmethod
    async def purge_messages(channel: discord.TextChannel, amount: int, check_func, interaction: discord.Interaction = None, reason: str = None) -> list:
        messages_to_delete = []
        async for message in channel.history(limit=100):
            if len(messages_to_delete) >= amount:
                break
            if check_func(message):
                messages_to_delete.append(message)
        
        if messages_to_delete:
            if len(messages_to_delete) > 1:
                try:
                    await channel.delete_messages(messages_to_delete, reason=reason)
                    await interaction.followup.send(f"Succesfully deleted {len(messages_to_delete)} messages")
                    return messages_to_delete
                except discord.HTTPException as e:
                    return []
            else:
                try:
                    await messages_to_delete[0].delete()
                    return [messages_to_delete[0]]
                except discord.HTTPException as e:
                    return []

        return []


class PurgeCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="purge", description="Purge commands for messages")

    @app_commands.command(name="any")
    async def apurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:    
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await interaction.channel.purge(limit=amount, reason=reason)

            text = f"Deleted {amount} messages."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="user")
    async def upurge(self, interaction: discord.Interaction, member: discord.Member, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, lambda msg: MessageCheck.is_from_user(msg, member), interaction, reason)

            text = f"Deleted {amount} messages from {member}."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="embeds") 
    async def epurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_embeds, interaction, reason)

            text = f"Deleted {amount} messages with embeds."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="attachments")
    async def attpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.has_attachments, interaction, reason)
            
            text = f"Deleted {amount} messages with attachments."
            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="text")
    async def tpurge(self, interaction: discord.Interaction, amount: int = 10, reason: str = "No reason provided."):
        await interaction.response.defer(ephemeral=True)
        try:
            has_mod, embed = check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            await MessageCheck.purge_messages(interaction.channel, amount, MessageCheck.is_text_only, interaction, reason)

            text = f"Deleted {amount} text messages."

            await store_modlog(
                text,
                interaction.guild.id,
                interaction.user,
                reason=reason,
                bot=interaction.client
            )
        except Exception as e:
            await handle_logs(interaction, e)

    def setup_commands(self):
        command_help = open_file("storage/command_help.json")
        purge_data = command_help.get("moderation", {}).get("purge", {})
        
        if "description" in purge_data:
            self.description = purge_data["description"]
            
        if "subcommands" in purge_data:
            for cmd in self.commands:
                if cmd.name in purge_data["subcommands"]:
                    cmd_data = purge_data["subcommands"][cmd.name]
                    cmd.description = cmd_data.get("description", cmd.description)
                    
                    if "parameters" in cmd_data:
                        for param_name, param_desc in cmd_data["parameters"].items():
                            if param_name in cmd._params:
                                cmd._params[param_name].description = param_desc

class PurgeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.purge_command = PurgeCommandGroup()
        self.purge_command.setup_commands()
        self.bot.tree.add_command(self.purge_command)

    @commands.hybrid_command(name="clean")
    async def manual_clean(self, ctx, amount: int = 10):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.defer()
        try:
            has_mod, embed = check_moderation_info(ctx, "manage_messages", "moderator")
            if not has_mod:
                return await ctx.send(embed=embed)

            deleted = await ctx.channel.purge(limit=amount, check=MessageCheck.cleanCommand)
            
            text = f"Cleaned {len(deleted)} bot messages and commands."
            await store_modlog(
                text,
                ctx.guild.id,
                ctx.author,
                bot=self.bot
            )
            await ctx.send(text, delete_after=5)

        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(PurgeCog(bot))