from bot_utils import (
    handle_logs,
    open_file,
    __version__
)

import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands

import time, asyncio, os, tempfile
from aiohttp import ClientSession, ClientError
from datetime import datetime, timezone
from moviepy.editor import VideoFileClip, AudioFileClip
from PIL import Image

class AvatarGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="avatar", description="Avatar related commands.")

    @app_commands.command(name="get", description="Displays a user's global avatar.")
    @app_commands.describe(member="The member to get the avatar for")
    async def get(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=0x808080)
            embed.set_image(url=member.avatar.url if member.avatar else None)
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=(interaction.user.avatar.url if interaction.user.avatar else None)
            )
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="server", description="Displays a user's server-specific avatar.")
    @app_commands.describe(member="The member to get the server-specific avatar for")
    async def server(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        try:
            member = member or interaction.user
            embed = discord.Embed(title=f"{member.display_name}'s Server Avatar", color=0x808080)
            embed.set_image(url=member.display_avatar.url if member.display_avatar else None)
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=(interaction.user.avatar.url if interaction.user.avatar else None)
            )
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(AvatarGroup())

        self.context_userinfo = app_commands.ContextMenu(
            name='User Information',
            callback=self.context_userinfo_callback
        )

        self.bot.tree.add_command(self.context_userinfo)

        self.context_filedata = app_commands.ContextMenu(
            name="File Data", 
            callback=self.context_filedata
        )

        self.bot.tree.add_command(self.context_filedata)

    def exp_required(self, level):
        total_exp = 0
        for l in range(1, level + 1):
            total_exp += 5 * (l ** 2) + 50 * l + 100
        return total_exp

    @app_commands.command(name="help", description="Get details about a specific command.")
    @app_commands.describe(command="The command you'd like to learn about.")
    async def help_command(self, interaction: discord.Interaction, command: str):
        commands_data = open_file("info/commands.json")
        for _, group_commands in commands_data.items():
            for cmd_name, cmd_details in group_commands.items():
                if cmd_name.lower() == command.lower():
                    arguments = cmd_details.get("arguments", {})
                    required_args = [f"[{arg}]" for arg, details in arguments.items() if details.get("required", False)]
                    optional_args = [f"({arg})" for arg, details in arguments.items() if not details.get("required", False)]
                    arg_list = " ".join(required_args + optional_args)

                    embed = discord.Embed(
                        title=f"/{cmd_name.lower()} {arg_list}",
                        description=cmd_details.get("description", "No description provided."),
                        color=discord.Color.blue()
                    )
                    
                    if "example" in cmd_details:
                        embed.add_field(name="Example", value=cmd_details["example"], inline=False)

                    for arg_name, arg_details in arguments.items():
                        arg_info = (
                            f"**Required**: {arg_details.get('required', False)}\n"
                            f"**Default**: {arg_details.get('default', 'None')}\n"
                            f"**Type**: {arg_details.get('type', 'Unknown')}\n"
                            f"**Description**: {arg_details.get('description', 'No description provided.')}")
                        embed.add_field(name=arg_name.title(), value=arg_info, inline=False)

                    embed.set_footer(text="[Required Arguments] (Optional Arguments)")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

        await interaction.response.send_message(f"Command `{command}` not found. Please check your input and try again.", ephemeral=True)
        
    @app_commands.command(name="level", description="View your level globally or in your guild.")
    @app_commands.describe(where="Where you want to view your level.")
    @app_commands.choices(
        where=[
            app_commands.Choice(name="Local (Server)", value="guild"), 
            app_commands.Choice(name="Global", value="global")
        ]
    )
    async def level(self, interaction: discord.Interaction, where: str = "guild"):
        await interaction.response.defer()
        try:
            def calculate_level_info(exp):
                level = 1
                while self.exp_required(level + 1) <= exp:
                    level += 1
                
                current_level_exp = 0 if level == 1 else self.exp_required(level)
                next_level_exp = self.exp_required(level + 1)
                
                exp_progress = exp - current_level_exp
                exp_needed = next_level_exp - current_level_exp
                
                progress_percent = max(0, round((exp_progress / exp_needed) * 100, 2))
                
                return {
                    "level": level,
                    "exp_progress": exp_progress,
                    "exp_needed": exp_needed,
                    "progress_percent": progress_percent
                }
                
            member_id = str(interaction.user.id)
            server_id = str(interaction.guild.id)
            server_info = open_file("info/server_info.json")
                
            if where == "guild": 
                server_exp = server_info.get("exp", {}).get(server_id, {})
                user_exp = server_exp.get(member_id, 0)
                
                exp_list = [(uid, exp) for uid, exp in server_exp.items()]
                exp_list.sort(key=lambda x: x[1], reverse=True)
                rank = next((i for i, (uid, _) in enumerate(exp_list, 1) if uid == member_id), 0)
                total_users = len(exp_list)
                
                title = f"Server Level - {interaction.user.name}"
                rank_text = f"Rank: #{rank}/{total_users}"
            else:
                global_exp_dict = {}
                for server_data in server_info.get("exp", {}).values():
                    for uid, exp in server_data.items():
                        global_exp_dict[uid] = global_exp_dict.get(uid, 0) + exp
                
                user_exp = global_exp_dict.get(member_id, 0)
                
                exp_list = [(uid, exp) for uid, exp in global_exp_dict.items()]
                exp_list.sort(key=lambda x: x[1], reverse=True)
                rank = next((i for i, (uid, _) in enumerate(exp_list, 1) if uid == member_id), 0)
                total_users = len(exp_list)
                
                title = f"Global Level - {interaction.user.name}"
                rank_text = f"Rank: #{rank}/{total_users}"

            info = calculate_level_info(user_exp)
            
            progress = int(info["progress_percent"] / 5)
            progress_bar = "█" * progress + "░" * (20 - progress)

            embed = discord.Embed(
                title=title,
                color=interaction.user.color if interaction.user.color.value else discord.Color.blue()
            )
            
            embed.add_field(
                name=f"Level {info['level']} • {rank_text}", 
                value=f"```\n{progress_bar} {info['progress_percent']}%\n```", 
                inline=False
            )
            
            embed.add_field(
                name="Progress", 
                value=f"{info['exp_progress']:,}/{info['exp_needed']:,} XP", 
                inline=True
            )
            
            embed.add_field(
                name="Total XP", 
                value=f"{user_exp:,} XP", 
                inline=True
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="mlevel", description="Calculate Mee6 levels and time to achieve them.")
    @app_commands.describe( 
        current_level="Your current level",
        current_exp="Your current EXP in that level",
        target_level="The level you want to achieve",
        hours_per_day="Hours you will chat every day"
    )
    async def mlevel(self, interaction: discord.Interaction, current_level: int, current_exp: int, target_level: int, hours_per_day: int):
        await interaction.response.defer()
        try:
            required_exp = self.exp_required(target_level) - (self.exp_required(current_level) + current_exp)

            embed = discord.Embed(
                title="Mee6 Level Calculator",
                description=f"Based on {hours_per_day} hours of chatting per day and gaining {hours_per_day * 1200} EXP.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Info", value=f"Current Level: {current_level}\nCurrent EXP: {current_exp}\nTarget Level: {target_level}", inline=False)
            embed.add_field(name="Required EXP", value=f"{required_exp:,}", inline=False)
            embed.add_field(name="Minimum Messages/Estimated Messages", value=f"{int(required_exp / 20):,}/{int((required_exp / 20) * 1.8):,}", inline=False)
            embed.add_field(name="Estimated Days", value=f"{round(required_exp / (hours_per_day * 1200)):,}", inline=False)
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="ping", description="Shows your latency and the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            start_time = time.time()
            processing_start_time = time.time()
            await asyncio.sleep(0.1)
            processing_time = (time.time() - processing_start_time) * 1000
            end_time = time.time()
            round_trip_latency = round((end_time - start_time) * 1000)
            bot_latency = round(self.bot.latency * 1000)
            color = (0x00FF00 if bot_latency < 81 else 0xFFFF00 if bot_latency < 201 else 0xFF0000)
            embed = discord.Embed(
                title="Pong! 🏓",
                description=(
                    f"Your approximate latency: {round_trip_latency}ms\n"
                    f"Bot's latency: {bot_latency}ms\n"
                    f"Processing Time: {processing_time:.2f}ms\n"
                    f"Response Time: {round_trip_latency + processing_time:.2f}ms"
                ),
                color=color,
            )
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="info", description="Displays information about the bot.")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(title="Bot Info", description="This bot is developed by LucasLiorLE.", color=0x808080)
            embed.add_field(name="Version", value=f"v{__version__}")
            embed.add_field(name="Server Count", value=len(self.bot.guilds))
            embed.add_field(name="Library", value="Discord.py")
            embed.add_field(name="Other", value="Made by LucasLiorLE\nEstimated time: 200 hours+")
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

            view = View()

            website = Button(label="Visit Website", url="https://lucasliorle.github.io")
            view.add_item(website)
            github = Button(label="GitHub Repo", url="https://github.com/LucasLiorLE/APEYE")
            view.add_item(github)

            await interaction.followup.send(embed=embed, view=view)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="serverinfo", description="Shows information about the server.")
    async def serverinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            guild = interaction.guild

            embed = discord.Embed(title="Server Info", color=0x808080)
            embed.add_field(name="Owner", value=guild.owner.mention)
            embed.add_field(name="Members", value=guild.member_count)
            embed.add_field(name="Roles", value=len([role.name for role in guild.roles]))
            embed.add_field(name="Category Channels", value=len(guild.categories))
            embed.add_field(name="Text Channels", value=len([channel for channel in guild.text_channels]))
            embed.add_field(name="Voice Channels", value=len([channel for channel in guild.voice_channels]))
            embed.add_field(name="Role List", value=", ".join([role.name for role in guild.roles]), inline=False)
            embed.add_field(name="Server ID", value=guild.id)
            embed.add_field(name="Server Created", value=f"{guild.created_at.strftime("%m/%d/%Y %I:%M %p")}")
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="roleinfo", description="Provides information for a role.")
    @app_commands.describe(role="The role to get the info for")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        try:
            permissions = role.permissions
            permissions_list = [perm for perm, value in permissions if value]

            embed = discord.Embed(title=f"Role info for {role.name}", color=role.color)
            embed.add_field(name="Role ID", value=role.id)
            embed.add_field(name="Color", value=str(role.color))
            embed.add_field(name="Mentionable", value=str(role.mentionable))
            embed.add_field(name="Hoist", value=str(role.hoist))
            embed.add_field(name="Position",value=f"{role.position}/{len(self, interaction.guild.roles)}",)
            embed.add_field(name="Permissions",value=", ".join(permissions_list) if permissions_list else "No permissions")
            embed.add_field(name="Member Count", value=len(role.members))
            embed.add_field(name="Role Created On",value=f"{role.created_at.strftime("%m/%d/%Y %H:%M")} ({(datetime.now(timezone.utc) - role.created_at).days} days ago)")

            if role.icon:
                embed.set_thumbnail(url=role.icon.url)

            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    async def context_userinfo_callback(self, interaction: discord.Interaction, user: discord.Member):
        await self.userinfo(interaction, user)

    @app_commands.command(name="userinfo", description="Provides information about a user.")
    @app_commands.describe(member="The member to get the info for",)
    async def direct_userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        await self.userinfo(interaction, member)
    
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        try:
            member = member or interaction.user
            embed = discord.Embed(title="User Info", color=0x808080)
            embed.set_thumbnail(url=member.avatar.url)
            embed.add_field(name="Username", value=member.display_name)
            embed.add_field(name="User ID", value=member.id)
            embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"))
            embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"))
            embed.add_field(name="Roles", value=", ".join([role.name for role in member.roles]))
            embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    @app_commands.command(name="status", description="Check the status of a website.")
    @app_commands.describe(website="Link to the website.")
    async def status(self, interaction: discord.Interaction, website: str):
        await interaction.response.defer()

        if not website.startswith(("http://", "https://")):
            website = "http://" + website

        async with ClientSession() as session:
            try:
                async with session.get(website, timeout=5) as response:
                    status_code = response.status
                    if 200 <= status_code < 300:
                        message = f"<:check:1292269189536682004> The website `{website}` is **up**! Status Code: `{status_code}`."
                    else:
                        message = f"⚠️ The website `{website}` returned a **problematic** status. Status Code: `{status_code}`."
            except ClientError as e:
                message = f"❌ The website `{website}` is **down** or unreachable. Error: `{e}`"
            except asyncio.TimeoutError:
                message = f"❌ The request to `{website}` timed out after 5 seconds."

        await interaction.followup.send(message)

    @app_commands.command(name="define", description="Define a word")
    @app_commands.describe(word="The word you want to define")
    async def define(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with ClientSession() as session:
                async with session.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as response:
                    if response.status != 200:
                        await interaction.followup.send("Could not find the definition.")
                        return
                    
                    data = await response.json()
            
            entry = data[0]
            phonetic = entry.get('phonetics', [{}])[0].get('text', 'N/A')
            origin = entry.get('origin', 'N/A')
            meanings = entry.get('meanings', [])
            
            embed = discord.Embed(title=f"Definition for **{word}** ({phonetic})", color=discord.Color.blue())

            if origin != "N/A":
                embed.add_field(name="Origin", value=origin, inline=False)

            for meaning in meanings:
                part_of_speech = meaning.get("partOfSpeech", "N/A")
                definitions = meaning.get("definitions", [])

                for definition in definitions:
                    field_value = f"**Definition**: {definition.get('definition', '') or 'Nothing'}\n"
                    field_value += f"**Example**: {definition.get('example', 'Nothing')}\n"

                    synonyms = definition.get("synonyms", [])
                    antonyms = definition.get("antonyms", [])
                    if synonyms:
                        field_value += f"**Synonyms**: {', '.join(synonyms)}\n"
                    if antonyms:
                        field_value += f"**Antonyms**: {', '.join(antonyms)}\n"

                    embed.add_field(name=part_of_speech.capitalize(), value=field_value, inline=False)

            audio_urls = [phonetic.get("audio", "") for phonetic in entry.get("phonetics", []) if phonetic.get("audio")]

            if audio_urls:
                audio_url = audio_urls[0].lstrip("//")
                audio_file_name = f"{word}_pronunciation.mp3"

                async with ClientSession() as session:
                    async with session.get(audio_url) as audio_response:
                        if audio_response.status == 200:
                            with open(audio_file_name, 'wb') as f:
                                f.write(await audio_response.read())
                
                await interaction.followup.send(embed=embed, file=discord.File(audio_file_name))
                os.remove(audio_file_name)
            else:
                await interaction.followup.send(embed=embed)
        except Exception as error:
            await handle_logs(interaction, error)

    async def context_filedata(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message("This message doesn't contain any attachments!", ephemeral=True)
            return
        
        file = message.attachments[0]

        if not file:
            await interaction.response.send_message("No valid attachment found!")
            return
        
        await self.filedata(interaction, file)
        
    @app_commands.command(name="filedata", description="Display metadata for an uploaded file")
    @app_commands.describe(file="The uploaded file to analyze.")
    async def direct_filedata(self, interaction: discord.Interaction, file: discord.Attachment):
        await self.filedata(interaction, file)

    async def filedata(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer()
        try:
            file_data = await file.read()
            file_type = file.content_type
            file_size_kb = len(file_data) / 1024
            file_size_mb = file_size_kb / 1024

            file_info = (
                f"**File Name:** {file.filename}\n"
                f"**File Type:** {file_type}\n"
                f"**File Size:** {file_size_kb:.2f} KB ({file_size_mb:.2f} MB)\n"
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as temp_input:
                temp_input.write(file_data)
                temp_input_path = temp_input.name

            if "video" in file_type:
                clip = VideoFileClip(temp_input_path)
                frame_rate = clip.fps
                duration = clip.duration
                bitrate = (file_size_mb * 8 * 1024) / duration if duration > 0 else "Unknown"
                resolution = f"{clip.w}x{clip.h} pixels"
                file_info += (
                    f"**Duration:** {duration:.2f} seconds\n"
                    f"**Frame Rate:** {frame_rate:.2f} fps\n"
                    f"**Bitrate:** {bitrate:.2f} kbps\n"
                    f"**Resolution:** {resolution}\n"
                )
                clip.close()

            elif "audio" in file_type:
                clip = AudioFileClip(temp_input_path)
                duration = clip.duration
                bitrate = (file_size_mb * 8 * 1024) / duration if duration > 0 else "Unknown"
                file_info += (
                    f"**Duration:** {duration:.2f} seconds\n"
                    f"**Bitrate:** {bitrate:.2f} kbps\n"
                )
                clip.close()

            elif "image" in file_type:
                with Image.open(temp_input_path) as img:
                    resolution = f"{img.width}x{img.height} pixels"
                    file_info += f"**Resolution:** {resolution}\n"

            elif "text" in file_type:
                with open(temp_input_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                file_info += (
                    f"**Encoding:** UTF-8\n"
                    f"**Line Count:** {len(lines)}\n"
                )

            else:
                file_info += "No additional metadata available for this file type.\n"

            await interaction.followup.send(content=file_info)

            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
        except Exception as error:
            await handle_logs(interaction, error)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
