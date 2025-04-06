import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands

from bot_utils import (
	get_dominant_color,
	__version__,
	__status__,
	open_json,
	handle_logs,
)

import time, asyncio, os, tempfile
from aiohttp import ClientSession, ClientError
from datetime import datetime, timezone
from moviepy.editor import VideoFileClip, AudioFileClip
from PIL import Image

class AvatarGroup(app_commands.Group):
	def __init__(self):
		super().__init__(name="avatar")

	@app_commands.command(name="get")
	async def get(self, interaction: discord.Interaction, user: discord.User = None):
		await interaction.response.defer()
		try:
			user = user or interaction.user
			avatar_url = user.avatar.url if user.avatar else None
			
			if avatar_url:
				embed_color = await get_dominant_color(avatar_url)
			else:
				embed_color = 0x808080
				
			embed = discord.Embed(
				title=f"{user.display_name}'s Avatar",
				color=embed_color
			)
			embed.set_image(url=avatar_url)
			embed.set_footer(
				text=f"Requested by {interaction.user}",
				icon_url=(interaction.user.avatar.url if interaction.user.avatar else None)
			)
			await interaction.followup.send(embed=embed)
		except Exception as error:
			await handle_logs(interaction, error)

	@app_commands.command(name="server")
	async def server(self, interaction: discord.Interaction, user: discord.User = None):
		await interaction.response.defer()
		try:
			user = user or interaction.user
			avatar_url = user.display_avatar.url if user.display_avatar else None
			
			if avatar_url:
				embed_color = await get_dominant_color(avatar_url)
			else:
				embed_color = 0x808080
				
			embed = discord.Embed(
				title=f"{user.display_name}'s Server Avatar",
				color=embed_color
			)
			embed.set_image(url=avatar_url)
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
		self.start_time = datetime.now(timezone.utc)
				
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

	@app_commands.command(name="help")
	async def help(self, interaction: discord.Interaction, command: str, ephemeral: bool = True):
		try:
			command_help = open_json("storage/commands.json")
			
			command_parts = command.lower().split()
			current_level = command_help
			
			for part in command_parts:
				if part in current_level:
					current_level = current_level[part]
				else:
					await interaction.response.send_message(f"Command `{command}` not found.", ephemeral=True)
					return
			
			embed = discord.Embed(
				title=f"Help: {command}",
				color=interaction.user.color if interaction.user.color.value else discord.Color.blue()
			)
			
			if isinstance(current_level, dict):
				if "description" in current_level:
					embed.description = current_level["description"]
				
				if "parameters" in current_level:
					params = []
					for param_name, param_desc in current_level["parameters"].items():
						params.append(f"**{param_name}**: {param_desc}")
					
					if params:
						embed.add_field(
							name="Parameters",
							value="\n".join(params),
							inline=False
						)
			else:
				embed.description = current_level

			await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="level")
	@app_commands.choices(
		where=[app_commands.Choice(name="Local (Server)", value="guild"), app_commands.Choice(name="Global", value="global")]
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
			server_info = open_json("storage/server_info.json")
				
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

	@app_commands.allowed_installs(guilds=True, users=True)
	@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
	@app_commands.command(name="ping")
	async def ping(self, interaction: discord.Interaction):
		start_time = time.perf_counter()
		command_start = time.time()
		
		bot_latency = round(self.bot.latency * 1000)
		ws_latency = round((time.perf_counter() - start_time) * 1000)
		
		api_start = time.perf_counter()
		await interaction.response.send_message("Measuring...", ephemeral=True)
		api_end = time.perf_counter()
		api_latency = round((api_end - api_start) * 1000)
		
		response_time = round((time.time() - command_start) * 1000)
		
		worst_latency = max(bot_latency, ws_latency, api_latency)
		color = (0x00FF00 if worst_latency < 150 
				else 0xFFFF00 if worst_latency < 300 
				else 0xFF0000)
		
		def get_status(latency):
			return f"{latency}ms ({"Low" if latency < 150 else "Medium" if latency < 300 else "High"})"
		
		latency_info = (
			f"```\n"
			f"Bot Latency:     {get_status(bot_latency)}\n"
			f"WebSocket:       {get_status(ws_latency)}\n"
			f"API Latency:     {get_status(api_latency)}\n"
			f"Response Time:   {get_status(response_time)}\n"
			f"```"
		)
		
		embed = discord.Embed(
			title="🏓 Pong!",
			description=latency_info,
			color=color
		)
		
		await interaction.edit_original_response(content=None, embed=embed)

	@app_commands.allowed_installs(guilds=True, users=True)
	@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
	@app_commands.command(name="info")
	async def info(self, interaction: discord.Interaction):
		try:
			current_time = datetime.now(timezone.utc)
			uptime = current_time - self.start_time
			days = uptime.days
			hours, remainder = divmod(uptime.seconds, 3600)
			minutes, seconds = divmod(remainder, 60)
			uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

			embed = discord.Embed(title="Bot Info", description="This bot is developed by LucasLiorLE.", color=0x808080)
			embed.add_field(name="Version", value=f"v{__version__} ({__status__})")
			embed.add_field(name="Server Count", value=len(self.bot.guilds))
			embed.add_field(name="Library", value="Discord.py (Python)")
			embed.add_field(name="Uptime", value=uptime_str)
			embed.add_field(name="Other", value="Made by LucasLiorLE\nEstimated time: 400+ hours")
			embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

			view = View()

			website = Button(label="Visit Website", url="https://lucasliorle.github.io")
			view.add_item(website)
			github = Button(label="GitHub Repo", url="https://github.com/LucasLiorLE/AstralV")
			view.add_item(github)
			add = Button(label="Add Bot", url="https://discord.com/oauth2/authorize?client_id=733021769073557604")
			view.add_item(add)

			await interaction.response.send_message(embed=embed, view=view)
		except Exception as error:
			await handle_logs(interaction, error)

	@app_commands.command(name="serverinfo")
	async def serverinfo(self, interaction: discord.Interaction):
		try:
			guild = interaction.guild
			if not guild:
				await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
				return

			embed = discord.Embed(title="Server Info", color=0x808080)
			embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "N/A")
			embed.add_field(name="Members", value=guild.member_count)
			embed.add_field(name="Roles", value=len([role.name for role in guild.roles]))
			embed.add_field(name="Category Channels", value=len(guild.categories))
			embed.add_field(name="Text Channels", value=len([channel for channel in guild.text_channels]))
			embed.add_field(name="Voice Channels", value=len([channel for channel in guild.voice_channels]))
			embed.add_field(name="Role List", value=", ".join([role.name for role in guild.roles]), inline=False)
			embed.add_field(name="Server ID", value=guild.id)
			embed.add_field(name="Server Created", value=f"{guild.created_at.strftime('%m/%d/%Y %I:%M %p')}")
			embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

			await interaction.response.send_message(embed=embed)
		except Exception as error:
			await handle_logs(interaction, error)

	@app_commands.command(name="emojiinfo")
	async def emojiinfo(self, interaction: discord.Interaction, emoji: str):
		await interaction.response.defer()
		try:
			emoji_obj = discord.utils.get(interaction.guild.emojis, name=emoji)
			if emoji_obj is None:
				return await interaction.followup.send("Emoji not found.", ephemeral=True)

			color = await get_dominant_color(emoji_obj.url, timeout=5)

			embed = discord.Embed(title=f"Emoji info for {emoji_obj.name}", color=color)
			embed.add_field(name="Name", value=emoji_obj.name)
			embed.add_field(name="URL", value=emoji_obj.url)
			embed.add_field(name="Emoji ID", value=emoji_obj.id)
			embed.add_field(
				name="Emoji Created",
				value=f"{emoji_obj.created_at.strftime('%m/%d/%Y %H:%M')} ({(datetime.now(timezone.utc) - emoji_obj.created_at).days} days ago)"
			)

			embed.set_thumbnail(url=emoji_obj.url)

			await interaction.followup.send(embed=embed)
		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="roleinfo")
	async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
		try:
			permissions = role.permissions
			permissions_list = [perm for perm, value in permissions if value]

			embed = discord.Embed(title=f"Role info for {role.name}", color=role.color)
			embed.add_field(name="Role ID", value=role.id)
			embed.add_field(name="Color", value=str(role.color))
			embed.add_field(name="Mentionable", value=str(role.mentionable))
			embed.add_field(name="Hoist", value=str(role.hoist))
			embed.add_field(name="Position",value=f"{role.position}/{len(interaction.guild.roles)}",)
			embed.add_field(name="Member Count", value=len(role.members))
			embed.add_field(name="Role Created",value=f"{role.created_at.strftime("%m/%d/%Y %H:%M")} ({(datetime.now(timezone.utc) - role.created_at).days} days ago)")
			embed.add_field(name="Permissions",value=", ".join(permissions_list) if permissions_list else "No permissions", inline=False)

			if role.icon:
				embed.set_thumbnail(url=role.icon.url)

			embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)
			await interaction.response.send_message(embed=embed)
		except Exception as error:
			await handle_logs(interaction, error)

	async def context_userinfo_callback(self, interaction: discord.Interaction, user: discord.Member):
		await self.userinfo(interaction, user)

	@app_commands.command(name="userinfo")
	async def direct_userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
		await self.userinfo(interaction, member)
	
	async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
		try:
			member = member or interaction.user
			if not member:
				await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
				return

			embed = discord.Embed(title="User Info", color=0x808080)
			embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
			embed.add_field(name="Username", value=member.display_name)
			embed.add_field(name="User ID", value=member.id)
			embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"))
			embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "N/A")
			if member.roles:
				embed.add_field(name="Roles", value=", ".join([role.name for role in member.roles]))
			embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

			await interaction.response.send_message(embed=embed)
		except Exception as error:
			await handle_logs(interaction, error)

	@app_commands.command(name="status")
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

	@app_commands.command(name="define")
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
		
	@app_commands.command(name="filedata")
	async def direct_filedata(self, interaction: discord.Interaction, file: discord.Attachment):
		await interaction.response.defer()
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

	@app_commands.command(name="pokemon")
	async def pokemon(self, interaction: discord.Interaction, pokemon: str):
		await interaction.response.defer()
		try:
			async with ClientSession() as session:
				async with session.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon.lower()}") as response:
					if response.status != 200:
						await interaction.followup.send(f"Pokemon '{pokemon}' not found.", ephemeral=True)
						return
					data = await response.json()

			pokemon_name = data['name'].capitalize()
			pokemon_id = data['id']
			types = [t['type']['name'].capitalize() for t in data['types']]
			abilities = [f"[{a['ability']['name'].replace('-', ' ').title()}]({a['ability']['url']})" for a in data['abilities']]
			height = data['height'] / 10
			weight = data['weight'] / 10
			stats = {}
			for stat in data['stats']:
				stat_name = stat['stat']['name'].replace('-', ' ').title()
				stats[stat_name] = stat['base_stat']
			
			color = {
				'Normal': 0xA8A878,
				'Fire': 0xF08030,
				'Water': 0x6890F0,
				'Electric': 0xF8D030,
				'Grass': 0x78C850,
				'Ice': 0x98D8D8,
				'Fighting': 0xC03028,
				'Poison': 0xA040A0,
				'Ground': 0xE0C068,
				'Flying': 0xA890F0,
				'Psychic': 0xF85888,
				'Bug': 0xA8B820,
				'Rock': 0xB8A038,
				'Ghost': 0x705898,
				'Dragon': 0x7038F8,
				'Dark': 0x705848,
				'Steel': 0xB8B8D0,
				'Fairy': 0xEE99AC
			}

			embed = discord.Embed(
				title=f"#{pokemon_id} - {pokemon_name}",
				color=color.get(types[0], 0xAAAAAA)
			)

			embed.set_thumbnail(url=data['sprites']['other']['official-artwork']['front_default'])

			embed.add_field(name="Types", value=" | ".join(types), inline=False)
			embed.add_field(name="Abilities", value=" | ".join(abilities), inline=False)
			embed.add_field(name="Height", value=f"{height}m", inline=True)
			embed.add_field(name="Weight", value=f"{weight}kg", inline=True)
			
			stats_text = "\n".join([f"{name}: {value}" for name, value in stats.items()])
			embed.add_field(name="Base Stats", value=f"```\n{stats_text}\n```", inline=False)

			await interaction.followup.send(embed=embed)

		except Exception as error:
			await handle_logs(interaction, error)

async def setup(bot):
	await bot.add_cog(InfoCog(bot))