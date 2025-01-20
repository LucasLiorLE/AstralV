from bot_utils import (
    handle_logs
)

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Set
import random

class Room:
    def __init__(self, owner_id: int, channel_id: str, password: str = None):
        self.owner_id = owner_id
        self.channel_id = channel_id
        self.password = password
        self.members: Set[str] = set()
        self.guild_names: Dict[str, str] = {}

class UserphoneGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="userphone", description="Userphone commands allows you to talk to people in different servers!")
        self.rooms: Dict[str, Room] = {}

    @app_commands.command(
        name="create",
        description="Create a userphone room"
    )
    @app_commands.describe(
        password="Optional password to make the room private"
    )
    async def create(self, interaction: discord.Interaction, password: str = None):
        try:
            channel_id = str(interaction.channel_id)
            if channel_id in self.rooms:
                await interaction.response.send_message("This channel already has a room!", ephemeral=True)
                return

            room = Room(interaction.user.id, channel_id, password)
            room.members.add(channel_id)
            room.guild_names[channel_id] = interaction.guild.name
            self.rooms[channel_id] = room

            if password:
                await interaction.response.send_message(
                    f"📞 Created private room! Others can join with:\n`/userphone join {channel_id} {password}`",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"📞 Created public room! Others can join with:\n`/userphone join {channel_id}`",
                    ephemeral=False
                )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(
        name="join",
        description="Join a userphone room"
    )
    @app_commands.describe(
        room_id="The room ID to join (leave empty for random public room)",
        password="Password for private rooms"
    )
    async def join(self, interaction: discord.Interaction, room_id: str = None, password: str = None):
        try:
            channel_id = str(interaction.channel_id)
            
            for room in self.rooms.values():
                if channel_id in room.members:
                    await interaction.response.send_message("This channel is already in a room!", ephemeral=True)
                    return

            if room_id is None:
                public_rooms = [r for r in self.rooms.values() if not r.password]
                if not public_rooms:
                    await interaction.response.send_message("No public rooms available!", ephemeral=True)
                    return
                room = random.choice(public_rooms)
                room_id = room.channel_id

            if room_id not in self.rooms:
                await interaction.response.send_message("Room not found!", ephemeral=True)
                return

            room = self.rooms[room_id]

            if room.password and password != room.password:
                await interaction.response.send_message("Invalid password!", ephemeral=True)
                return

            room.members.add(channel_id)
            room.guild_names[channel_id] = interaction.guild.name

            for member_channel in room.members:
                try:
                    channel = interaction.client.get_channel(int(member_channel))
                    if channel:
                        await channel.send(f"📞 {interaction.guild.name} joined the room!")
                except Exception:
                    pass

            await interaction.response.send_message("📞 Joined the room!", ephemeral=False)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(
        name="list",
        description="List active userphone rooms"
    )
    async def list_rooms(self, interaction: discord.Interaction):
        try:
            if not self.rooms:
                await interaction.response.send_message("No active rooms!", ephemeral=True)
                return

            public_rooms = [(room_id, room) for room_id, room in self.rooms.items() if not room.password]
            sorted_rooms = sorted(public_rooms, key=lambda x: len(x[1].members), reverse=True)[:5]

            embed = discord.Embed(
                title="Top 5 Active Public Rooms",
                color=discord.Color.blue()
            )

            for room_id, room in sorted_rooms:
                embed.add_field(
                    name=f"Room {room_id} ({len(room.members)} members)",
                    value=f"Members from: {', '.join(room.guild_names.values())}\nJoin with: `/userphone join {room_id}`",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(
        name="leave",
        description="Leave the current userphone room"
    )
    async def leave(self, interaction: discord.Interaction):
        try:
            channel_id = str(interaction.channel_id)
            
            for room_id, room in self.rooms.items():
                if channel_id in room.members:
                    room.members.remove(channel_id)
                    del room.guild_names[channel_id]

                    if not room.members:
                        del self.rooms[room_id]
                    else:
                        for member_channel in room.members:
                            try:
                                channel = interaction.client.get_channel(int(member_channel))
                                if channel:
                                    await channel.send(f"📞 {interaction.guild.name} left the room!")
                            except Exception:
                                pass

                    await interaction.response.send_message("📞 Left the room!", ephemeral=False)
                    return

            await interaction.response.send_message("You're not in any room!", ephemeral=True)

        except Exception as e:
            await handle_logs(interaction, e)

class UserphoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.userphone_group = UserphoneGroup()
        self.bot.tree.add_command(self.userphone_group)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        channel_id = str(message.channel.id)
        
        for room in self.userphone_group.rooms.values():
            if channel_id in room.members:
                for other_channel_id in room.members:
                    if other_channel_id != channel_id:
                        try:
                            channel = self.bot.get_channel(int(other_channel_id))
                            if channel:
                                await channel.send(
                                    f"**{message.author.name}** ({room.guild_names[channel_id]}): {message.content}"
                                )
                        except Exception as e:
                            print(f"Error forwarding message: {e}")
                break

async def setup(bot):
    await bot.add_cog(UserphoneCog(bot))
