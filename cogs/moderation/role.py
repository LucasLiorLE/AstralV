import discord
from discord.ext import commands
from discord import app_commands

import asyncio

from bot_utils import (
    get_role_hierarchy,
    handle_logs,
)

from .utils import (
    store_modlog,
    check_moderation_info,
    dm_moderation_embed,
)

class RoleCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="role", description="Role related commands")
        self.active_tasks = {}

    def _create_role_embed(self, title: str, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Role Management")
        return embed

    def _create_error_embed(self, description: str) -> discord.Embed:
        return self._create_role_embed("Error", description, discord.Color.red())

    def _create_success_embed(self, description: str) -> discord.Embed:
        return self._create_role_embed("Success", description, discord.Color.green())

    def _create_progress_embed(self, description: str) -> discord.Embed:
        return self._create_role_embed("In Progress", description, discord.Color.yellow())

    @app_commands.command(name="add")
    async def role_add(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot assign the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            if not get_role_hierarchy(interaction.guild.me, role):
                embed = self._create_error_embed(f"I cannot assign the role `{role.name}` because it is higher than my highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await member.add_roles(role, reason=reason)
            embed = self._create_success_embed(f"Added role `{role.name}` to {member.mention}.")
            await interaction.response.send_message(embed=embed)
            
            await store_modlog(
                modlog_type="Role Added",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                user=member,
                role=role,
                reason=reason,
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="remove")
    async def role_remove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot remove the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            if not get_role_hierarchy(interaction.guild.me, role):
                embed = self._create_error_embed(f"I cannot remove the role `{role.name}` because it is higher than my highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await member.remove_roles(role, reason=reason)
            embed = self._create_success_embed(f"Removed role `{role.name}` from {member.mention}.")
            await interaction.response.send_message(embed=embed)
            
            await store_modlog(
                modlog_type="Role Removed",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                user=member,
                role=role,
                reason=reason,
            )
        except Exception as e:
            await handle_logs(interaction, e)

    async def _process_mass_role(self, interaction: discord.Interaction, members: list, role: discord.Role, 
                               reason: str, operation_type: str):
        total = len(members)
        batch_size = 10
        estimated_time = (total // batch_size)

        progress_embed = self._create_progress_embed(
            f"{operation_type} role to {total} members.\nEstimated time: {estimated_time} seconds."
        )
        progress_msg = await interaction.followup.send(embed=progress_embed)
        
        task_id = f"{interaction.guild.id}:{role.id}"
        self.active_tasks[task_id] = True

        processed = 0
        for i in range(0, total, batch_size):
            if not self.active_tasks.get(task_id):
                cancel_embed = self._create_role_embed(
                    "Cancelled", 
                    f"Operation cancelled at {processed}/{total} members.",
                    discord.Color.orange()
                )
                await progress_msg.edit(embed=cancel_embed)
                return processed

            batch = members[i:i+batch_size]
            for member in batch:
                if operation_type == "Adding":
                    await member.add_roles(role, reason=reason)
                else:
                    await member.remove_roles(role, reason=reason)
            processed += len(batch)
            
            if i % (batch_size * 5) == 0:
                progress_embed.description = f"Progress: {processed}/{total} members processed..."
                await progress_msg.edit(embed=progress_embed)
            await asyncio.sleep(1)

        del self.active_tasks[task_id]
        success_embed = self._create_success_embed(f"✅ {operation_type} role `{role.name}` to {processed} members.")
        await progress_msg.edit(embed=success_embed)
        return processed

    @app_commands.command(name="bots")
    async def role_bots(self, interaction: discord.Interaction, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot assign the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await interaction.response.defer()
            bots = [m for m in interaction.guild.members if m.bot]
            processed = await self._process_mass_role(interaction, bots, role, reason, "Adding")
            
            await store_modlog(
                modlog_type="Mass Role Added",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                role=role,
                reason=f"Added to all bots ({processed} members). {reason if reason else ''}"
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="all")
    async def role_all(self, interaction: discord.Interaction, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot assign the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await interaction.response.defer()
            processed = await self._process_mass_role(
                interaction, interaction.guild.members, role, reason, "Adding"
            )
            
            await store_modlog(
                modlog_type="Mass Role Added",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                role=role,
                reason=f"Added to all members ({processed} members). {reason if reason else ''}"
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="cancel")
    async def role_cancel(self, interaction: discord.Interaction, role: discord.Role):
        task_id = f"{interaction.guild.id}:{role.id}"
        if task_id in self.active_tasks:
            self.active_tasks[task_id] = False
            embed = self._create_success_embed(f"Cancelling mass role operation for role `{role.name}`...")
        else:
            embed = self._create_error_embed("No active mass role operation found for this role.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removeall")
    async def role_removeall(self, interaction: discord.Interaction, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot remove the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await interaction.response.defer()
            members_with_role = [m for m in interaction.guild.members if role in m.roles]
            processed = await self._process_mass_role(
                interaction, members_with_role, role, reason, "Removing"
            )
            
            await store_modlog(
                modlog_type="Mass Role Removed",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                role=role,
                reason=f"Removed from all members ({processed} members). {reason if reason else ''}"
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="humans")
    async def role_humans(self, interaction: discord.Interaction, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(interaction.user, role):
                embed = self._create_error_embed(f"You cannot assign the role `{role.name}` because it is higher than your highest role.")
                return await interaction.response.send_message(embed=embed)
            
            if not get_role_hierarchy(interaction.guild.me, role):
                embed = self._create_error_embed(f"I cannot assign the role `{role.name}` because it is higher than my highest role.")
                return await interaction.response.send_message(embed=embed)
            
            await interaction.response.defer()
            
            humans = [m for m in interaction.guild.members if not m.bot]
            total = len(humans)
            
            batch_size = 10
            estimated_time = (total // batch_size)
            
            progress_embed = self._create_progress_embed(
                f"Adding role to {total} humans. Estimated time: {estimated_time} seconds."
            )
            progress_msg = await interaction.followup.send(embed=progress_embed)
            
            for i in range(0, total, batch_size):
                batch = humans[i:i+batch_size]
                for member in batch:
                    await member.add_roles(role, reason=reason)
                await asyncio.sleep(1)
                
                if i % (batch_size * 5) == 0:
                    progress_embed.description = f"Progress: {i}/{total} members processed..."
                    await progress_msg.edit(embed=progress_embed)
            
            success_embed = self._create_success_embed(f"✅ Added role `{role.name}` to {total} humans.")
            await progress_msg.edit(embed=success_embed)
            
            await store_modlog(
                modlog_type="Mass Role Added",
                server_id=interaction.guild.id,
                moderator=interaction.user,
                role=role,
                reason=f"Added to all humans ({total} members). {reason if reason else ''}"
            )
        except Exception as e:
            await handle_logs(interaction, e)

class RoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(RoleCommandGroup())

    @commands.command(name="role")
    async def role(self, ctx: commands.Context, member: discord.Member, role: discord.Role, reason: str = None):
        try:
            if not get_role_hierarchy(ctx.author, role):
                embed = discord.Embed(
                    title="Error",
                    description=f"You cannot assign the role `{role.name}` to {member.mention} because it is higher than your highest role.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            if not get_role_hierarchy(ctx.guild.me, role):
                embed = discord.Embed(
                    title="Error",
                    description=f"I cannot assign the role `{role.name}` to {member.mention} because it is higher than my highest role.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            if role in member.roles:
                await member.remove_roles(role)
                action = 'Removed'
            else:
                await member.add_roles(role)
                action = 'Added'

            embed = discord.Embed(
                title="Success",
                description=f"{action} role `{role.name}` {'from' if action == 'Removed' else 'to'} {member.mention}.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

            await store_modlog(
                modlog_type=f"Role {action}", 
                server_id=ctx.guild.id,
                moderator=ctx.author,
                user=member,
                role=role,
                reason=reason,
            )
        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(RoleCog(bot))