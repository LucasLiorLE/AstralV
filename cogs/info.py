from shapely import is_valid
from bot_utils import (
	get_dominant_color,
	__version__,
	__status__,
	load_commands,
	open_file,
	handle_logs,
)

import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands

import time, asyncio, os, tempfile, math
from aiohttp import ClientSession, ClientError
from datetime import datetime, timezone, timedelta
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

	def setup_commands(self):
		load_commands(self, "info")

class InfoCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.start_time = datetime.now(timezone.utc)
		
		load_commands(self.__cog_app_commands__, "info")
		
		avatar_group = AvatarGroup()
		avatar_group.setup_commands()
		self.bot.tree.add_command(avatar_group)

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

	def exp_required(self, level: int) -> int:
		total_exp = 0
		for l in range(1, level + 1):
			total_exp += 5 * (l ** 2) + 50 * l + 100
		return total_exp

	def is_valid_value(self, value: int, min_val: int, max_val: int) -> bool:
		if value is None:
			return True
		try:
			return min_val < value <= max_val
		except TypeError:
			return False

	def exp_required_tower(self, level: int) -> int:
		if level <= 10:
			return 45 + (level * 3.5)
		elif level <= 40:
			return level * 8
		else:
			return 260 + (level * 1.5)

	@app_commands.command(name="help")
	async def help(self, interaction: discord.Interaction, command: str, ephemeral: bool = True):
		try:
			command_help = open_file("storage/command_help.json")

			if command:
				for category, commands in command_help.items():
					if isinstance(commands, dict):
						if command in commands:
							cmd_data = commands[command]
							embed = discord.Embed(
								title=f"Help: {command}",
								description=cmd_data.get("description", "No description available."),
								color=discord.Color.blue()
							)
							
							if "parameters" in cmd_data:
								params = []
								for param_name, param_desc in cmd_data["parameters"].items():
									params.append(f"• **{param_name}**: {param_desc}")
								if params:
									embed.add_field(
										name="Parameters",
										value="\n".join(params),
										inline=False
									)
							
							if "subcommands" in cmd_data:
								subcmds = []
								for subcmd_name, subcmd_data in cmd_data["subcommands"].items():
									subcmds.append(f"• **{subcmd_name}**: {subcmd_data['description']}")
								if subcmds:
									embed.add_field(
										name="Subcommands",
										value="\n".join(subcmds),
										inline=False
									)
							
							await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
							return
						
				await interaction.response.send_message(f"No help found for command: {command}", ephemeral=ephemeral)
				return

			embed = discord.Embed(
				title="Command Categories",
				description="Here are all available command categories.\nUse `/help <command>` for detailed help on a command.",
				color=discord.Color.blue()
			)

			for category, commands in command_help.items():
				if isinstance(commands, dict) and category not in ["modlogs", "warn", "mute"]:
					cmd_list = [f"`{cmd}`" for cmd in commands.keys() if not isinstance(commands[cmd], dict)]
					if cmd_list:
						embed.add_field(
							name=category.title(),
							value=", ".join(cmd_list),
							inline=False
						)

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

	@app_commands.command(name="mlevel")
	async def mlevel(self, interaction: discord.Interaction, current_level: int, current_exp: int, 
					target_level: int = None, target_exp: int = None, target_date: str = None,
					exp_per_day: int = None, mee6_pro: bool = False, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)
		try:
			old_target_exp = target_exp

			if (
				self.is_valid_value(current_level, 1, 500) and 
				self.is_valid_value(target_level, 2, 500) and 
				self.is_valid_value(current_exp, 0, 1000000) and 
				self.is_valid_value(target_exp, 1, 1000000)
			):
				return await interaction.followup.send("Invalid level or EXP values!", ephemeral=True)

			if target_level is None and target_exp is None:
				return await interaction.followup.send("You must provide either a target level or target EXP!", ephemeral=True)
			
			total_current_exp = self.exp_required(current_level) + current_exp
			
			if target_exp is not None:
				target_level = target_level or current_level
				total_target_exp = self.exp_required(target_level) + target_exp
				
				if total_target_exp <= total_current_exp:
					await interaction.followup.send("Target EXP must be higher than current total EXP!", ephemeral=True)
					return
				required_exp = total_target_exp - total_current_exp
			else:
				target_exp = self.exp_required(target_level)
				if target_exp <= total_current_exp:
					await interaction.followup.send("Target level must result in higher EXP than current!", ephemeral=True)
					return
				required_exp = target_exp - total_current_exp

			if required_exp == 0:
				await interaction.followup.send("You have already reached or exceeded this target!", ephemeral=True)
				return
			
			if mee6_pro:
				required_exp = int(required_exp / 1.5)

			if target_date:
				try:
					target = datetime.strptime(target_date, "%m/%d/%Y")
					now = datetime.now()
					days_until = (target - now).days + 1
					
					if days_until <= 0:
						await interaction.followup.send("Target date must be in the future!")
						return
					
					required_daily_exp = required_exp / days_until
					completion_date = target
				except ValueError:
					await interaction.followup.send("Invalid date format! Use MM/DD/YYYY")
					return
			else:
				if not exp_per_day:
					await interaction.followup.send("Either target_date or exp_per_day must be provided!")
					return
				
				days_needed = round(required_exp / exp_per_day)
				try:
					completion_date = datetime.now() + timedelta(days=days_needed)
				except OverflowError:
					return await interaction.followup.send("Pleae provide smaller target/current level/exp!")
				required_daily_exp = exp_per_day

			embed = discord.Embed(
				title="Mee6 Level Calculator",
				color=discord.Color.blue()
			)

			main_info = (
				f"Total Required EXP: {required_exp:,}\n"
				f"Minimum Messages: {int(required_exp / 20 * 1.8):,}\n"
			)

			if target_date:
				target_timestamp = int(target.timestamp())
				main_info += f"Estimated Days: {days_until:,}\n"
				main_info += f"Estimated completion: <t:{target_timestamp}:F>"
			else:
				completion_timestamp = int(completion_date.timestamp())
				main_info += f"Estimated Days: {days_needed:,}\n"
				main_info += f"Estimated completion: <t:{completion_timestamp}:F>"

			embed.add_field(name="Main Info", value=main_info, inline=False)

			daily_chat_info = ""
			chat_hours_needed = (exp_per_day if exp_per_day else required_daily_exp) / 1200
			hours = int(chat_hours_needed)
			minutes = int((chat_hours_needed - hours) * 60)
			
			daily_chat_info += f"Time: {hours} hours {minutes} minutes\n"
			daily_chat_info += f"Messages: {int((exp_per_day if exp_per_day else required_daily_exp) / 20):,} minimum messages per day\n"
			daily_chat_info += f"EXP: {int(exp_per_day if exp_per_day else required_daily_exp):,} exp per day"
			
			embed.add_field(name="Est. Daily Chat Info", value=daily_chat_info, inline=False)

			other_info = (
				f"Current Level/EXP: {current_level}/{current_exp:,}\n"
				f"Target Level/EXP: {target_level}/{old_target_exp if old_target_exp else 0:,}\n"
				f"Total current level EXP: {total_current_exp:,}\n"
				f"Total target level EXP: {target_exp if target_exp else self.exp_required(target_level):,}"
			)
			
			embed.add_field(name="Other Info", value=other_info, inline=False)

			embed.set_footer(text=f"Estimates based on 1.2k EXP per hour of chatting", icon_url=interaction.user.avatar.url)

			await interaction.followup.send(embed=embed)
		except Exception as error:
			await handle_logs(interaction, error)

	@app_commands.command(name="tlevel")
	@app_commands.choices(
			mode=[
				app_commands.Choice(name="Easy", value="easy"),
				app_commands.Choice(name="Casual", value="casual"),
				app_commands.Choice(name="Intermediate", value="intermediate"),
				app_commands.Choice(name="Molten", value="molten"),
				app_commands.Choice(name="Fallen", value="fallen"),
				app_commands.Choice(name="Hardcore", value="hardcore")
			]
		)
	async def tlevel(self, interaction: discord.Interaction, current_level: int, current_exp: float, 
					target_level: int = None, target_exp: float = None, target_date: str = None,
					games_per_day: int = None, mode: str = "fallen", vip: bool = False, 
					vip_plus: bool = False, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)
		try:
			if target_level is None and target_exp is None:
				return await interaction.followup.send("You must provide either a target level or target EXP!", ephemeral=True)
			
			if (
				self.is_valid_value(current_level, 1, 25000) and 
				self.is_valid_value(target_level, 2, 25000) and 
				self.is_valid_value(current_exp, 0, 100000) and 
				self.is_valid_value(target_exp, 1, 100000)
			):
				return await interaction.followup.send("Invalid level or EXP values!", ephemeral=True)

			mode_config = {
				"easy": {"exp": 50, "time": 20, "reward": "250 coins", "reward_amount": 250, "type": "coins"},
				"casual": {"exp": 90, "time": 20, "reward": "400 coins", "reward_amount": 400, "type": "coins"},
				"intermediate": {"exp": 120, "time": 20, "reward": "500 coins", "reward_amount": 500, "type": "coins"},
				"molten": {"exp": 185, "time": 25, "reward": "750 coins", "reward_amount": 750, "type": "coins"},
				"fallen": {"exp": 250, "time": 35, "reward": "1000 coins", "reward_amount": 1000, "type": "coins"},
				"hardcore": {"exp": 400, "time": 35, "reward": "300 gems", "reward_amount": 300, "type": "gems"}
			}

			selected_mode = mode_config[mode]
			base_exp_per_game = selected_mode["exp"]

			exp_multiplier = 1.0
			coin_multiplier = 1.0
			
			if vip_plus:
				exp_multiplier += 0.50
				coin_multiplier += 0.20
			elif vip:
				exp_multiplier += 0.25

			if selected_mode["type"] == "coins":
				reward_amount = math.floor(selected_mode["reward_amount"] * coin_multiplier)
			else:
				reward_amount = selected_mode["reward_amount"]

			total_current_exp = sum(self.exp_required_tower(i) for i in range(current_level)) + current_exp
			
			if target_exp is not None:
				target_level = target_level or current_level
				total_target_exp = sum(self.exp_required_tower(i) for i in range(target_level)) + target_exp
			else:
				total_target_exp = sum(self.exp_required_tower(i) for i in range(target_level + 1))

			if total_target_exp <= total_current_exp:
				await interaction.followup.send("Target must be higher than current progress!", ephemeral=True)
				return

			required_exp = total_target_exp - total_current_exp
			days_needed = 0

			total_exp_needed = required_exp / exp_multiplier

			if target_date:
				try:
					target = datetime.strptime(target_date, "%m/%d/%Y")
					now = datetime.now()
					days_until = (target - now).days + 1
					
					if days_until <= 0:
						await interaction.followup.send("Target date must be in the future!")
						return

					weekend_days = sum(1 for i in range(days_until) if (now + timedelta(days=i)).weekday() >= 5)
					regular_days = days_until - weekend_days
					
					if games_per_day is None:
						daily_games = math.ceil(total_exp_needed / (base_exp_per_game * (regular_days + weekend_days * 2)))
					else:
						daily_games = games_per_day
					
					completion_date = target
					days_needed = days_until
				except ValueError:
					await interaction.followup.send("Invalid date format! Use MM/DD/YYYY")
					return
			else:
				if not games_per_day:
					await interaction.followup.send("Either target_date or games_per_day must be provided!")
					return
				
				daily_games = games_per_day
				avg_daily_exp = daily_games * base_exp_per_game * (5 + 4) / 7
				days_needed = math.ceil(total_exp_needed / avg_daily_exp)
				try:
					completion_date = datetime.now() + timedelta(days=days_needed)
				except OverflowError:
					return await interaction.followup.send("Pleae provide smaller target/current level/exp!")

			if target_date:
				total_games = daily_games * days_until
			else:
				total_games = daily_games * days_needed

			total_rewards = total_games * reward_amount
			total_time = (total_games * selected_mode["time"]) / 60

			embed = discord.Embed(
				title="Tower Defense Level Calculator",
				color=discord.Color.blue()
			)

			main_info = (
				f"Total Required EXP: {required_exp:,.2f}\n"
				f"Estimated Games: {total_games:,}\n"
				f"Total {selected_mode['type']}: {total_rewards:,}\n"
				f"Total Time: {total_time:,.1f} hours\n"
			)

			if target_date:
				target_timestamp = int(target.timestamp())
				main_info += f"Days until target: {days_until:,}\n"
				main_info += f"Target completion: <t:{target_timestamp}:F>"
			else:
				completion_timestamp = int(completion_date.timestamp())
				main_info += f"Estimated days: {days_needed:,}\n"
				main_info += f"Estimated completion: <t:{completion_timestamp}:F>"

			embed.add_field(name="Main Info", value=main_info, inline=False)

			daily_info = (
				f"Games per day: {daily_games:,}\n"
				f"Time per day: {(daily_games * selected_mode["time"] / 60):,.1f} hours\n"
				f"{selected_mode['type'].title()} per day: {(daily_games * reward_amount):,}"
			)
			embed.add_field(name="Daily Requirements", value=daily_info, inline=False)

			status_info = (
				f"Current Level/EXP: {current_level}/{current_exp:,.2f}\n"
				f"Target Level/EXP: {target_level}/{target_exp if target_exp else 0:,.2f}\n"
				f"Mode: {mode.title()} ({selected_mode['exp']} EXP)\n"
				f"EXP Multiplier: {exp_multiplier}x"
			)
			if selected_mode["type"] == "coins" and coin_multiplier > 1:
				status_info += f"\nCoin Multiplier: {coin_multiplier}x"
			
			embed.add_field(name="Status Info", value=status_info, inline=False)

			footer_text = "Weekend days (2x EXP) are included in calculations"

			embed.set_footer(text=footer_text, icon_url=interaction.user.avatar.url)

			await interaction.followup.send(embed=embed)

		except Exception as error:
			await handle_logs(interaction, error)

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
			embed.add_field(name="Library", value="Discord.py")
			embed.add_field(name="Uptime", value=uptime_str)
			embed.add_field(name="Other", value="Made by LucasLiorLE\nEstimated time: 310+ hours")
			embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url)

			view = View()

			website = Button(label="Visit Website", url="https://lucasliorle.github.io")
			view.add_item(website)
			github = Button(label="GitHub Repo", url="https://github.com/LucasLiorLE/APEYE")
			view.add_item(github)

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
		try:
			emoji_obj = discord.utils.get(interaction.guild.emojis, name=emoji)
			if emoji_obj is None:
				return await interaction.followup.send("Emoji not found.", ephemeral=True)

			color = await get_dominant_color(emoji_obj.url, timeout=5)

			embed = discord.Embed(title=f"Emoji info for {emoji_obj.name}", color=color)
			embed.add_field(name="Name", value=emoji_obj.name)
			if emoji_obj.user:
				embed.add_field(name="Created By", value=emoji_obj.user.mention)
			embed.add_field(name="URL", value=emoji_obj.url)
			embed.add_field(name="Emoji ID", value=emoji_obj.id)
			embed.add_field(
				name="Emoji Created",
				value=f"{emoji_obj.created_at.strftime('%m/%d/%Y %H:%M')} ({(datetime.now(timezone.utc) - emoji_obj.created_at).days} days ago)"
			)

			await interaction.response.send_message(embed=embed)
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

async def setup(bot):
	await bot.add_cog(InfoCog(bot))