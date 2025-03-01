from bot_utils import (
    open_file,
    save_file,
    load_commands,
    handle_logs,
)

import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Set, List
import random

class Room:
    def __init__(self, owner_id: int, channel_id: str, password: str = None):
        self.owner_id = owner_id
        self.channel_id = channel_id
        self.password = password
        self.members: Set[str] = set()
        self.guild_names: Dict[str, str] = {}
        self.anonymous_names: Dict[str, Dict[int, str]] = {}
        self.is_anonymous: bool = False

    def get_anonymous_name(self, channel_id: str, user_id: int) -> str:
        if (channel_id not in self.anonymous_names):
            self.anonymous_names[channel_id] = {}
        if (user_id not in self.anonymous_names[channel_id]):
            anon_id = len(self.anonymous_names[channel_id]) + 1
            self.anonymous_names[channel_id][user_id] = f"anonymous{anon_id}"
        return self.anonymous_names[channel_id][user_id]

class UserphoneGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="userphone", description="Userphone commands allows you to talk to people in different servers!")
        self.rooms: Dict[str, Room] = {}
        
        load_commands(self.commands, "userphone")

    @app_commands.command(name="create")
    async def create(self, interaction: discord.Interaction, password: str = None):
        try:
            await interaction.response.defer()
            channel_id = str(interaction.channel_id)
            if (channel_id in self.rooms):
                await interaction.followup.send("This channel already has a room!", ephemeral=True)
                return

            room = Room(interaction.user.id, channel_id, password)
            room.members.add(channel_id)
            room.guild_names[channel_id] = interaction.guild.name
            self.rooms[channel_id] = room

            if password:
                await interaction.followup.send(
                    f"📞 Created private room! Others can join with:\n`/userphone join {channel_id} {password}`",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"📞 Created public room! Others can join with:\n`/userphone join {channel_id}`",
                    ephemeral=False
                )

        except Exception as e:
            await handle_logs(interaction, e)

    async def get_public_rooms(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        public_rooms = []
        for room_id, room in self.rooms.items():
            if not room.password:
                member_count = len(room.members)
                servers = ", ".join(room.guild_names.values())
                public_rooms.append(
                    app_commands.Choice(
                        name=f"Room {room_id} ({member_count} members) - {servers}",
                        value=room_id
                    )
                )
        return public_rooms[:25]

    @app_commands.command(name="join")
    @app_commands.autocomplete(room_id=get_public_rooms)
    async def join(self, interaction: discord.Interaction, room_id: str = None, password: str = None, anonymous: bool = False):
        try:
            await interaction.response.defer(ephemeral=False)
            
            channel_id = str(interaction.channel_id)
            
            for room in self.rooms.values():
                if (channel_id in room.members):
                    await interaction.followup.send("This channel is already in a room!", ephemeral=True)
                    return

            if (room_id is None):
                public_rooms = [r for r in self.rooms.values() if not r.password]
                if (not public_rooms):
                    await interaction.followup.send("No public rooms available!", ephemeral=True)
                    return
                room = random.choice(public_rooms)
                room_id = room.channel_id

            if (room_id not in self.rooms):
                await interaction.followup.send("Room not found!", ephemeral=True)
                return

            room = self.rooms[room_id]

            if (room.password and password != room.password):
                await interaction.followup.send("Invalid password!", ephemeral=True)
                return

            if (anonymous and not room.is_anonymous):
                if (len(room.members) == 0):
                    room.is_anonymous = True
                else:
                    await interaction.followup.send("Cannot join as anonymous - room is not anonymous!", ephemeral=True)
                    return
            elif (not anonymous and room.is_anonymous):
                await interaction.followup.send("This is an anonymous room - must join as anonymous!", ephemeral=True)
                return

            room.members.add(channel_id)
            room.guild_names[channel_id] = interaction.guild.name

            join_message = f"📞 {interaction.guild.name} joined the room!"
            if (room.is_anonymous):
                join_message = f"📞 Someone joined the room!"

            for member_channel in room.members:
                try:
                    channel = interaction.client.get_channel(int(member_channel))
                    if (channel):
                        await channel.send(join_message)
                except Exception:
                    pass

            await interaction.followup.send("📞 Joined the room!")

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="list")
    async def list_rooms(self, interaction: discord.Interaction):
        try:
            if (not self.rooms):
                await interaction.response.send_message("No active rooms!", ephemeral=True)
                return

            public_rooms = [(room_id, room) for room_id, room in self.rooms.items() if not room.password]
            sorted_rooms = sorted(public_rooms, key=lambda x: len(x[1].members), reverse=True)[:5]

            embed = discord.Embed(
                title="Top 5 Active Public Rooms",
                color=discord.Color.blue()
            )

            for (room_id, room) in sorted_rooms:
                embed.add_field(
                    name=f"Room {room_id} ({len(room.members)} members)",
                    value=f"Members from: {', '.join(room.guild_names.values())}\nJoin with: `/userphone join {room_id}`",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="leave") 
    async def leave(self, interaction: discord.Interaction):
        try:
            channel_id = str(interaction.channel_id)
            
            for (room_id, room) in self.rooms.items():
                if (channel_id in room.members):
                    room.members.remove(channel_id)
                    del room.guild_names[channel_id]

                    if (not room.members):
                        del self.rooms[room_id]
                    else:
                        for member_channel in room.members:
                            try:
                                channel = interaction.client.get_channel(int(member_channel))
                                if (channel):
                                    await channel.send(f"📞 {interaction.guild.name} left the room!")
                            except Exception:
                                pass

                    await interaction.response.send_message("📞 Left the room!", ephemeral=False)
                    return

            await interaction.response.send_message("You're not in any room!", ephemeral=True)

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="anonymous")
    async def toggle_anonymous(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            channel_id = str(interaction.channel_id)
            user_id = str(interaction.user.id)
            
            in_room = False
            for room in self.rooms.values():
                if (channel_id in room.members):
                    in_room = True
                    break
                    
            if (not in_room):
                await interaction.followup.send("You must be in a room to toggle anonymous mode!", ephemeral=True)
                return

            member_data = open_file("storage/member_info.json")
            
            if (user_id not in member_data):
                member_data[user_id] = {"userphone_anom": False}
            
            member_data[user_id]["userphone_anom"] = not member_data[user_id].get("userphone_anom", False)
            
            if (member_data[user_id]["userphone_anom"]):
                await interaction.followup.send("Anonymous mode enabled.", ephemeral=True)
            else:
                await interaction.followup.send("Anonymous mode disabled.", ephemeral=True)
            
            save_file("storage/member_info.json", member_data)

        except Exception as e:
            await handle_logs(interaction, e)

class UserphoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.userphone_group = UserphoneGroup()
        self.bot.tree.add_command(self.userphone_group)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (message.author.bot):
            return

        if not message.content:  # Skip empty messages
            return

        channel_id = str(message.channel.id)
        
        for room in self.userphone_group.rooms.values():
            if (channel_id in room.members):
                member_data = open_file("storage/member_info.json")
                is_anonymous = member_data.get(str(message.author.id), {}).get("user_anom", False)

                for other_channel_id in room.members:
                    if (other_channel_id != channel_id):
                        try:
                            channel = self.bot.get_channel(int(other_channel_id))
                            if (channel):
                                if (is_anonymous):
                                    anon_name = room.get_anonymous_name(channel_id, message.author.id)
                                    await channel.send(f"**{anon_name}**: {message.content}")
                                else:
                                    await channel.send(
                                        f"**{message.author.name}** ({room.guild_names[channel_id]}): {message.content}"
                                    )
                        except Exception as e:
                            print(f"Error forwarding message: {e}")
                break

async def setup(bot):
    await bot.add_cog(UserphoneCog(bot))