from bot_utils.logger import (
	handle_logs
)

import discord
from discord.ext import commands 
from discord import app_commands

import asyncio, tempfile, io, random, os
import moviepy.editor as mp

from aiohttp import ClientSession
from moviepy.editor import VideoFileClip, AudioFileClip, vfx, CompositeVideoClip
from urllib.parse import urlparse

class VideoGroup(app_commands.Group):
	def __init__(self):
		super().__init__(name="video", description="Video manipulation commands")

	async def process_video(self, interaction: discord.Interaction, video: discord.Attachment = None, link: str = None):
		if video is None and link is None:
			await interaction.response.send_message("You need to provide a video file or a link to a video file.", ephemeral=True)
			return

		if link is not None:
			async with ClientSession() as session:
				async with session.get(link) as response:
					if response.status != 200:
						await interaction.response.send_message("The link you provided is invalid.", ephemeral=True)
						return

					video_data = await response.read()
			
			parsed_url = urlparse(link)
			filename = parsed_url.path.split('/')[-1]

		else:
			if not video.content_type.startswith("video/"):
				await interaction.response.send_message("The file you provided is not a video file.", ephemeral=True)
				return
			
			video_data = await video.read()
			filename = video.filename

		return video_data, filename

	async def video_speed(self, video_data: io.BytesIO, factor: float = None) -> io.BytesIO:
		with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
			temp_file.write(video_data.getvalue())
			temp_filename = temp_file.name

		try:
			video = VideoFileClip(temp_filename)

			if factor is None:
				factor = random.uniform(0.5, 5.0)

			video = video.fx(vfx.speedx, factor)
			output_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
			output_filename = output_temp.name
			output_temp.close()

			video.write_videofile(output_filename, codec="libx264", audio_codec="aac", fps=24, threads=4)
			video.close()

			with open(output_filename, 'rb') as f:
				video_buffer = io.BytesIO(f.read())

			return video_buffer

		finally:
			try:
				os.unlink(temp_filename)
				os.unlink(output_filename)
			except:
				pass

	async def video_reverse(self, video_data: io.BytesIO) -> io.BytesIO:
		
		temp_input = None
		temp_output = None
		
		try:
			with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as input_file:
				video_data.seek(0)
				input_file.write(video_data.getvalue())
				input_file.flush()
				temp_input = input_file.name
				
			temp_output = tempfile.mktemp(suffix='.mp4')
			
			cmd = [
				'ffmpeg',
				'-i', temp_input,
				'-vf', 'reverse',
				'-af', 'areverse',
				'-preset', 'ultrafast',
				'-y',
				temp_output
			]
			
			process = await asyncio.create_subprocess_exec(
				*cmd,
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.PIPE
			)
			
			await process.communicate()
			
			if process.returncode != 0:
				raise RuntimeError(f"FFmpeg failed with return code {process.returncode}")
				
			with open(temp_output, 'rb') as f:
				result = io.BytesIO(f.read())
				result.seek(0)
				return result
				
		finally:
			for temp_file in (temp_input, temp_output):
				if temp_file and os.path.exists(temp_file):
					try:
						os.unlink(temp_file)
					except Exception:
						pass
					
	async def video_mute(self, video_data: io.BytesIO) -> io.BytesIO:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_input:
			temp_input.write(video_data.read())
			temp_input_path = temp_input.name

		try:
			output_buffer = io.BytesIO()
			with VideoFileClip(temp_input_path) as video:
				video_no_audio = video.without_audio()

				with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
					video_no_audio.write_videofile(temp_output.name, codec="libx264", audio_codec="aac")
					temp_output_path = temp_output.name

				with open(temp_output_path, "rb") as output_file:
					output_buffer.write(output_file.read())

			output_buffer.seek(0)
			return output_buffer

		finally:
			if os.path.exists(temp_input_path):
				os.remove(temp_input_path)
			if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
				os.remove(temp_output_path)

	async def video_sharpen(self, video_data: io.BytesIO, factor: float = None) -> io.BytesIO:
		if factor is None:
			factor = random.uniform(0.5, 5.0)

		if factor > 5:
			return False
		
		temp_input = None
		temp_output = None
		
		try:
			with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as input_file:
				video_data.seek(0)
				input_file.write(video_data.read())
				input_file.flush()
				temp_input = input_file.name
			
			temp_output = tempfile.mktemp(suffix='.mp4')
			
			cmd = [
				'ffmpeg',
				'-i', temp_input,
				'-vf', f'unsharp=5:5:{factor}',
				'-c:v', 'libx264',
				'-preset', 'fast',
				'-crf', '23',
				'-c:a', 'aac', 
				'-movflags', '+faststart',
				'-f', 'mp4',
				'-y',
				temp_output
			]
			
			process = await asyncio.create_subprocess_exec(
				*cmd,
				stdout=asyncio.subprocess.PIPE,
				stderr=asyncio.subprocess.PIPE
			)
			
			stdout, stderr = await process.communicate()
			
			if process.returncode != 0:
				raise RuntimeError(f"FFmpeg failed with return code {process.returncode}\nError: {stderr.decode()}")
			
			with open(temp_output, 'rb') as f:
				result = io.BytesIO(f.read())
				result.seek(0)
				return result
				
		finally:
			for temp_file in (temp_input, temp_output):
				if temp_file and os.path.exists(temp_file):
					try:
						os.unlink(temp_file)
					except Exception:
						pass
				
	@app_commands.command(name="speed", description="Change the speed of an uploaded video")
	@app_commands.describe(
		video="The video file you want to change the speed of.",
		link="The link to the video you want to change the speed of.",
		factor="The factor you want to change the speed by.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def speed_video(self, interaction: discord.Interaction, factor: float, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)
		
		try:
			video_data, filename = await self.process_video(interaction, video, link)

			video_buffer = io.BytesIO(video_data)
			video_buffer = await self.video_speed(factor, video_buffer)

			await interaction.followup.send(
				f"Here is the video with the speed changed by {factor}x", 
				files=[discord.File(video_buffer, filename=filename)]
			)

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="reverse", description="Reverse an uploaded video")
	@app_commands.describe(
		video="The video file you want to reverse.",
		link="The link to the video you want to reverse.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def reverse_video(self, interaction: discord.Interaction, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)

		try:
			video_data, filename = await self.process_video(interaction, video, link)

			video_buffer = io.BytesIO(video_data)
			video_buffer = await self.video_reverse(video_buffer)

			await interaction.followup.send(
				"Here is the video reversed", 
				files=[discord.File(video_buffer, filename=filename)]
			)
		
		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="mute", description="Mute an uploaded video")
	@app_commands.describe(
		video="The video file you want to mute.",
		link="The link to the video you want to mute.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def mute_video(self, interaction: discord.Interaction, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)

		try:
			video_data, filename = await self.process_video(interaction, video, link)

			video_buffer = io.BytesIO(video_data)
			video_buffer = await self.video_mute(video_buffer)

			await interaction.followup.send(
				"Here is the video muted",
				files=[discord.File(video_buffer, filename=filename)]
			)

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="sharpness", description="Sharpen an uploaded video")
	@app_commands.describe(
		video="The video file you want to sharpen.",
		link="The link to the video you want to sharpen.",
		factor="The factor you want to sharpen the video by. (Max: 5)",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def sharpen_video(self, interaction: discord.Interaction, factor: float, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)

		try:
			video_data, filename = await self.process_video(interaction, video, link)

			video_buffer = io.BytesIO(video_data)
			video_buffer = await self.video_sharpen(video_buffer, factor)

			if video_buffer:
				await interaction.followup.send(
					f"Here is the video sharpened by a factor of {factor}",
					files=[discord.File(video_buffer, filename=filename)]
				)
			else:
				await interaction.followup.send(f"Please choose a sharpness between 1-10!")

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="random", description="Apply random effects to an uploaded video")
	@app_commands.describe(
		video="The video file you want to apply random effects to.",
		link="The link to the video you want to apply random effects to.",
		amount="The amount of random effects to apply.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def random_video(self, interaction: discord.Interaction, video: discord.Attachment = None, link: str = None, amount: int = 3, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)
		try:
			random_effects = [
				self.video_speed, self.video_reverse, self.video_mute, self.video_sharpen
			]

			video_data, filename = await self.process_video(interaction, video, link)
			video_buffer = io.BytesIO(video_data)

			applied_effects = []

			for _ in range(amount):
				effect = random.choice(random_effects)
				video_buffer = await effect(video_buffer)
				applied_effects.append(effect.__name__.split('_')[-1])

			await interaction.followup.send(
				f"Here is the video with the following effects applied: {', '.join(applied_effects)}",
				files=[discord.File(video_buffer, filename=filename)]
			)

		except Exception as e:
			await handle_logs(interaction, e)

	# Singular/Nonrandom commands:

	@app_commands.command(name="crop", description="Crop an uploaded video")
	@app_commands.describe(
		video="The video file you want to crop.",
		link="The link to the video you want to crop.",
		x="The x coordinate to start cropping from.",
		y="The y coordinate to start cropping from.",
		width="The width of the cropped video.",
		height="The height of the cropped video.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def crop_video(self, interaction: discord.Interaction, x: int, y: int,  width: int, height: int, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)

		try:
			video_data, filename = await self.process_video(interaction, video, link)

			with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
				temp_file.write(video_data)
				temp_filename = temp_file.name

			try:
				video = VideoFileClip(temp_filename)
				video = video.crop(x1=x, y1=y, x2=x+width, y2=y+height)
				output_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
				output_filename = output_temp.name
				output_temp.close()

				video.write_videofile(output_filename, codec="libx264", audio_codec="aac", fps=24, threads=4)
				video.close()

				with open(output_filename, 'rb') as f:
					video_buffer = io.BytesIO(f.read())

				await interaction.followup.send(
					"Here is the cropped video", 
					files=[discord.File(video_buffer, filename=filename)]
				)

			finally:
				try:
					os.unlink(temp_filename)
					os.unlink(output_filename)
				except:
					pass

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="trim", description="Trim an uploaded video")
	@app_commands.describe(
		video="The video file you want to trim.",
		link="The link to the video you want to trim.",
		start="The start time to trim from.",
		end="The end time to trim to.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def trim_video(self, interaction: discord.Interaction, start: int, end: int, video: discord.Attachment = None, link: str = None, ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)

		try:
			video_data, filename = await self.process_video(interaction, video, link)

			with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
				temp_file.write(video_data)
				temp_filename = temp_file.name

			try:
				video = VideoFileClip(temp_filename)
				video = video.subclip(start, end)
				output_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
				output_filename = output_temp.name
				output_temp.close()

				video.write_videofile(output_filename, codec="libx264", audio_codec="aac", fps=24, threads=4)
				video.close()

				with open(output_filename, 'rb') as f:
					video_buffer = io.BytesIO(f.read())

				await interaction.followup.send(
					"Here is the trimmed video", 
					files=[discord.File(video_buffer, filename=filename)]
				)

			finally:
				try:
					os.unlink(temp_filename)
					os.unlink(output_filename)
				except:
					pass

		except Exception as e:
			await handle_logs(interaction, e)

	@app_commands.command(name="concat", description="Concatenate two uploaded videos")
	@app_commands.describe(
		video1="The first video file you want to concatenate.",
		video2="The second video file you want to concatenate.",
		link1="The link to the first video you want to concatenate.",
		link2="The link to the second video you want to concatenate.",
		ephemeral="If the message is hidden (Useful if no perms)"
	)
	async def concat_video(self, interaction: discord.Interaction, video1: discord.Attachment = None, 
						video2: discord.Attachment = None, link1: str = None, link2: str = None, 
						ephemeral: bool = True):
		await interaction.response.defer(ephemeral=ephemeral)
		
		try:
			if not ((video1 or link1) and (video2 or link2)):
				await interaction.followup.send(
					"You must provide either two videos, two links, or a combination of a video and a link.",
					ephemeral=True
				)
				return

			video_data1, filename1 = await self.process_video(interaction, video1, link1)
			video_data2, _ = await self.process_video(interaction, video2, link2)
			
			temp_file1 = None
			temp_file2 = None
			list_filename = None
			output_filename = None
			
			try:
				with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp1:
					if isinstance(video_data1, io.BytesIO):
						temp1.write(video_data1.getvalue())
					else:
						temp1.write(video_data1)
					temp1.flush()
					temp_file1 = temp1.name
					
				with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp2:
					if isinstance(video_data2, io.BytesIO):
						temp2.write(video_data2.getvalue())
					else:
						temp2.write(video_data2)
					temp2.flush()
					temp_file2 = temp2.name
				
				with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as list_file:
					list_file.write(f"file '{temp_file1}'\nfile '{temp_file2}'")
					list_filename = list_file.name
				
				output_filename = tempfile.mktemp(suffix='.mp4')
				
				cmd = [
					'ffmpeg',
					'-f', 'concat',
					'-safe', '0',
					'-i', list_filename,
					'-c:v', 'libx264',
					'-c:a', 'aac',
					'-preset', 'fast',
					'-movflags', '+faststart',
					'-y',
					output_filename
				]
				
				process = await asyncio.create_subprocess_exec(
					*cmd,
					stdout=asyncio.subprocess.PIPE,
					stderr=asyncio.subprocess.PIPE
				)
				
				_, stderr = await process.communicate()
				
				if process.returncode != 0:
					raise RuntimeError(f"FFmpeg concatenation failed: {stderr.decode()}")
				
				with open(output_filename, 'rb') as f:
					video_buffer = io.BytesIO(f.read())
					video_buffer.seek(0)
				
				await interaction.followup.send(
					"Here is the concatenated video",
					files=[discord.File(video_buffer, filename=filename1)]
				)
				
			finally:
				for temp_file in (temp_file1, temp_file2, list_filename, output_filename):
					if temp_file and os.path.exists(temp_file):
						try:
							os.unlink(temp_file)
						except Exception:
							pass
							
		except Exception as e:
			await handle_logs(interaction, e)
			
class VideoCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

		self.bot.tree.add_command(VideoGroup())

async def setup(bot):
	await bot.add_cog(VideoCog(bot))