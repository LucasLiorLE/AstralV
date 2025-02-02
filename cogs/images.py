from bot_utils import (
    handle_logs,
    open_file
)

import discord

from discord.ext import commands
from discord import app_commands

import asyncio, tempfile, io, random

from PIL import Image, ImageSequence, ImageOps, ImageFilter, ImageEnhance
from moviepy.editor import VideoFileClip, AudioFileClip
from aiohttp import ClientSession
from urllib.parse import urlparse

class ImageGroup(app_commands.Group): # This originally was named "Image" but it was conflicting with the PIL Image module and I got confused for a long time lol.
    def __init__(self):
        super().__init__(name="image", description="Image manipulation commands")
        
        self.command_help = open_file("storage/command_help.json").get("image", {})
        
        for command in self.commands:
            if command.name in self.command_help:
                command_data = self.command_help[command.name]
                command.description = command_data["description"]
                if "parameters" in command_data:
                    for param_name, param_desc in command_data["parameters"].items():
                        if param_name in command._params:
                            command._params[param_name].description = param_desc

    async def togif(self, image_buffer: io.BytesIO) -> io.BytesIO:
        image = Image.open(image_buffer)
        output_buffer = io.BytesIO()
        image.save(output_buffer, format="GIF")
        output_buffer.seek(0)
        return output_buffer

    async def image_resize(self, image_buffer: io.BytesIO, width: int = None, height: int = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if width is None and height is None:
            width = random.randint(100, 500)
            height = random.randint(100, 500)

        resized_image = image.resize((width, height))
        output_buffer = io.BytesIO()
        resized_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
        
    async def image_flip(self, image_buffer: io.BytesIO) -> io.BytesIO:
        image = Image.open(image_buffer)
        flipped_image = image.transpose(Image.FLIP_TOP_BOTTOM)
        output_buffer = io.BytesIO()
        flipped_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_invert(self, image_buffer: io.BytesIO) -> io.BytesIO:
        image = Image.open(image_buffer).convert("RGBA")
        r, g, b, a = image.split()
        
        rgb = Image.merge("RGB", (r, g, b))
        inverted_rgb = ImageOps.invert(rgb)
        
        inverted_image = Image.merge("RGBA", (*inverted_rgb.split(), a))
        
        output_buffer = io.BytesIO()
        inverted_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_blur(self, image_buffer: io.BytesIO, radius: int = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if radius is None:
            radius = random.randint(2, 20)
        blurred_image = image.filter(ImageFilter.GaussianBlur(radius))
        output_buffer = io.BytesIO()
        blurred_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer

    async def image_brightness(self, image_buffer: io.BytesIO, factor: float = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if factor is None:
            factor = random.uniform(0.5, 2.0)
        enhancer = ImageEnhance.Brightness(image)
        brightened_image = enhancer.enhance(factor)
        output_buffer = io.BytesIO()
        brightened_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)    
        return output_buffer
    
    async def image_contrast(self, image_buffer: io.BytesIO, factor: float = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if factor is None:
            factor = random.uniform(0.5, 2.0)
        enhancer = ImageEnhance.Contrast(image)
        contrasted_image = enhancer.enhance(factor)
        output_buffer = io.BytesIO()
        contrasted_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_grayscale(self, image_buffer: io.BytesIO) -> io.BytesIO:
        image = Image.open(image_buffer)
        grayscale_image = image.convert("L")
        output_buffer = io.BytesIO()
        grayscale_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_sepia(self, image_buffer: io.BytesIO) -> io.BytesIO:
        image = Image.open(image_buffer)
        sepia_image = ImageOps.colorize(image.convert("L"), "#704214", "#C0A080")
        output_buffer = io.BytesIO()
        sepia_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_sharpen(self, image_buffer: io.BytesIO, factor: int = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if factor is None:
            factor = random.randint(50, 200) 

        sharpened_image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=factor))
        output_buffer = io.BytesIO()
        sharpened_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def image_pixelate(self, image_buffer: io.BytesIO, factor: int = None) -> io.BytesIO:
        image = Image.open(image_buffer)
        if factor is None:
            factor = random.randint(5, 20)
        pixelated_image = image.resize((image.width // factor, image.height // factor), Image.NEAREST).resize((image.width, image.height), Image.NEAREST)
        output_buffer = io.BytesIO()
        pixelated_image.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        return output_buffer
    
    async def process_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None):
        if image is None and link is None:
                    await interaction.followup.send("Please provide an image attachment or a link to an image.", ephemeral=True)
                    return
                
        if link is not None:
            async with ClientSession() as session:
                async with session.get(link) as response:
                    if response.status != 200:
                        await interaction.followup.send("Failed to fetch the image from the provided URL.", ephemeral=True)
                        return
                    
                    image_data = await response.read()

            parsed_url = urlparse(link)
            filename = parsed_url.path.split("/")[-1] or "image.png"

        else:
            if not image.content_type.startswith("image/"):
                await interaction.followup.send("Please upload a valid image file.", ephemeral=True)
                return

            image_data = await image.read()
            filename = image.filename

        return image_data, filename

    @app_commands.command(name="resize", description="Resize an uploaded image to a specified size")
    async def resize_image(self, interaction: discord.Interaction, width: int, height: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)
            image_buffer = io.BytesIO(image_data)

            resize_image_buffer = await self.image_resize(image_buffer, width, height)

            await interaction.followup.send(
                content=f"Here is your resized image to {width}x{height}:",
                file=discord.File(fp=resize_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )           
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="crop", description="Crop an uploaded image to a specified size")
    async def crop_image(self, interaction: discord.Interaction, width: int, height: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_pil = Image.open(io.BytesIO(image_data))
            cropped_image = image_pil.crop((0, 0, width, height))

            output_buffer = io.BytesIO()
            cropped_image.save(output_buffer, format="PNG")

            output_buffer.seek(0)

            await interaction.followup.send(
                content=f"Here is your cropped image to {width}x{height}:",
                file=discord.File(fp=output_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)


    @app_commands.command(name="rotate", description="Rotate an uploaded image by a specified angle")
    async def rotate_image(self, interaction: discord.Interaction, angle: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            image = Image.open(image_buffer)
            rotated_image = image.rotate(angle, expand=True)
            rotate_image_buffer = io.BytesIO()
            rotated_image.save(rotate_image_buffer, format="PNG")
            rotate_image_buffer.seek(0)

            await interaction.followup.send(
                content=f"Here is your rotated image:",
                file=discord.File(fp=rotate_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="flip", description="Flip an uploaded image vertically")
    async def flip_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            flip_image_buffer = await self.image_flip(image_buffer)

            await interaction.followup.send(
                content=f"Here is your flipped image:",
                file=discord.File(fp=flip_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="invert", description="Invert the colors of an uploaded image")
    async def invert_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            invert_image_buffer = await self.image_invert(image_buffer)

            await interaction.followup.send(
                content="Here is your inverted image:",
                file=discord.File(fp=invert_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="blur", description="Blur an uploaded image")
    async def blur_image(self, interaction: discord.Interaction, radius: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            blur_image_buffer = await self.image_blur(image_buffer, radius)

            await interaction.followup.send(
                content=f"Here is your blurred image with a radius of {radius}:",
                file=discord.File(fp=blur_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="brightness", description="Adjust the brightness of an uploaded image")
    async def brightness_image(self, interaction: discord.Interaction, factor: float, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            bright_image_buffer = await self.image_brightness(image_buffer, factor)

            await interaction.followup.send(
                content=f"Here is your image with the brightness adjusted by a factor of {factor}:",
                file=discord.File(fp=bright_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="contrast", description="Adjust the contrast of an uploaded image")
    async def contrast_image(self, interaction: discord.Interaction, factor: float, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            contrast_image_buffer = await self.image_contrast(image_buffer, factor)

            await interaction.followup.send(
                content=f"Here is your image with the contrast adjusted by a factor of {factor}:",
                file=discord.File(fp=contrast_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="grayscale", description="Convert an uploaded image to grayscale")
    async def grayscale_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            grayscale_image_buffer = await self.image_grayscale(image_buffer)

            await interaction.followup.send(
                content="Here is your image converted to grayscale:",
                file=discord.File(fp=grayscale_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="sepia", description="Convert an uploaded image to sepia")
    async def sepia_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            sepia_image_buffer = await self.image_sepia(image_buffer)

            await interaction.followup.send(
                content="Here is your image converted to sepia:",
                file=discord.File(fp=sepia_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="sharpen", description="Sharpen an uploaded image")
    async def sharpen_image(self, interaction: discord.Interaction, factor: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            sharpen_image_buffer = await self.image_sharpen(image_buffer, factor)

            await interaction.followup.send(
                content=f"Here is your sharpened image with a factor of {int(factor)}:",
                file=discord.File(fp=sharpen_image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="pixelate", description="Pixelate an uploaded image")
    async def pixelate_image(self, interaction: discord.Interaction, factor: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_buffer = io.BytesIO(image_data)
            pixelate_image_buffer = await self.image_pixelate(image_buffer, factor)

            await interaction.followup.send(
                content=f"Here is your pixelated image with a factor of {factor}:",
                file=discord.File(fp=pixelate_image_buffer, filename=f"{image.filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="changeres", description="Change the resolution of an uploaded image")
    async def change_resolution_image(self, interaction: discord.Interaction, factor: int, image: discord.Attachment = None, link: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            image_data, filename = await self.process_image(interaction, image, link)

            image_pil = Image.open(io.BytesIO(image_data))
            reduced_resolution = image_pil.resize((image_pil.width // factor, image_pil.height // factor), Image.NEAREST)

            output_buffer = io.BytesIO()
            reduced_resolution.save(output_buffer, format="PNG")

            output_buffer.seek(0)

            await interaction.followup.send(
                content=f"Here is your image with the resolution reduced by a factor of {factor}:",
                file=discord.File(fp=output_buffer, filename=f"{image.filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    async def context_randomize_callback(self, interaction: discord.Interaction, message: discord.Message):
        if not message.attachments:
            await interaction.response.send_message("This message doesn't contain any images!", ephemeral=True)
            return
            
        image = next((attachment for attachment in message.attachments 
                    if attachment.content_type and attachment.content_type.startswith('image/')), None)
                    
        if not image:
            await interaction.response.send_message("No valid image found in this message!", ephemeral=True)
            return
            
        await self.randomize_image(interaction, image=image, amount=3, ephemeral=False)

    @app_commands.command(name="random", description="Apply random effects to an uploaded image")
    async def direct_randomize_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, amount: int = 3, ephemeral: bool = True):
        await self.randomize_image(interaction, image, link, amount, ephemeral)

    async def randomize_image(self, interaction: discord.Interaction, image: discord.Attachment = None, link: str = None, amount: int = 3, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            random_effects = [
                self.image_flip, self.image_invert, self.image_blur, self.image_brightness, self.image_contrast,
                self.image_grayscale, self.image_sepia, self.image_sharpen, self.image_pixelate
            ]

            image_data, filename = await self.process_image(interaction, image, link)
            image_buffer = io.BytesIO(image_data)
            applied_effects = []
            random.shuffle(random_effects)
            for i in range(amount):
                random_effect = random_effects[i]
                image_buffer = await random_effect(image_buffer)
                applied_effects.append(random_effect.__name__.split("_")[1].capitalize())
            await interaction.followup.send(
                content=f"Applied effects: " + ", ".join(applied_effects),
                file=discord.File(fp=image_buffer, filename=f"{filename.rsplit('.', 1)[0]}.png")
            )
        except Exception as e:
            await handle_logs(interaction, e)    

class ConvertGroup(app_commands.Group): # Keep this here for now.
    def __init__(self):
        super().__init__(name="convert", description="Image conversion commands")
        
        # Load command descriptions from JSON
        self.command_help = open_file("storage/command_help.json").get("convert", {})
        
        # Set descriptions for commands
        for command in self.commands:
            if command.name in self.command_help:
                command_data = self.command_help[command.name]
                command.description = command_data["description"]
                if "parameters" in command_data:
                    for param_name, param_desc in command_data["parameters"].items():
                        if param_name in command._params:
                            command._params[param_name].description = param_desc

    @app_commands.command(name="image")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="JPEG", value="jpeg"),
            app_commands.Choice(name="PNG", value="png"),
            app_commands.Choice(name="WEBP", value="webp"),
            app_commands.Choice(name="GIF", value="gif"),
            app_commands.Choice(name="BMP", value="bmp"),
            app_commands.Choice(name="TIFF", value="tiff"),
        ]
    )
    async def convert_image(self, interaction: discord.Interaction, image: discord.Attachment, format: str, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if not image.content_type.startswith("image/"):
                await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
                return

            image_data = await image.read()
            image_pil = Image.open(io.BytesIO(image_data))

            if format == "jpeg" and image_pil.mode == "RGBA":
                image_pil = image_pil.convert("RGB")

            output_buffer = io.BytesIO()

            if format == "gif" and image_pil.is_animated:
                frames = []
                for frame in ImageSequence.Iterator(image_pil):
                    frame = frame.convert("RGBA")
                    frames.append(frame)

                frames[0].save(output_buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0)
            else:
                output_filename = f"{image.filename.rsplit('.', 1)[0]}.{format.lower()}"
                image_pil.save(output_buffer, format=format.upper())

            output_buffer.seek(0)

            await interaction.followup.send(
                content=f"Here is your converted image in {format.upper()} format:",
                file=discord.File(fp=output_buffer, filename=f"{output_filename}")
            )
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="video")
    @app_commands.choices(
        format=[
            app_commands.Choice(name="MP4", value="mp4"),
            app_commands.Choice(name="MP3", value="mp3"),
            app_commands.Choice(name="WMV", value="wmv"),
            app_commands.Choice(name="MOV", value="mov"),
            app_commands.Choice(name="MKV", value="mkv"),
            app_commands.Choice(name="AVI", value="avi"),
            app_commands.Choice(name="GIF", value="gif")
        ]
    )
    async def convert_video(self, interaction: discord.Interaction, video: discord.Attachment, format: str, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            video_data = await video.read()
            output_filename = await asyncio.to_thread(self.process_video, video_data, video.filename, format)

            await interaction.followup.send(
                content=f"Here is your converted file in {format.upper()} format:",
                file=discord.File(fp=output_filename, filename=output_filename.split('/')[-1])
            )

        except Exception as e:
            await handle_logs(interaction, e)

    def process_video(self, video_data, original_filename, target_format):
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{original_filename.split('.')[-1]}") as temp_input:
            temp_input.write(video_data)
            temp_input_path = temp_input.name

        output_filename = f"{tempfile.gettempdir()}/{original_filename.rsplit('.', 1)[0]}.{target_format.lower()}"

        if target_format.lower() == "mp3":
            input_audio = AudioFileClip(temp_input_path)
            input_audio.write_audiofile(output_filename)
        else:
            input_video = VideoFileClip(temp_input_path)
            input_video.write_videofile(output_filename, codec="libx264", audio_codec="aac", remove_temp=True)

        return output_filename

class FileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(ConvertGroup())
        self.bot.tree.add_command(ImageGroup())

        self.context_randomize = app_commands.ContextMenu(
            name="Randomize Image",
            callback=ImageGroup().context_randomize_callback
        )

        self.bot.tree.add_command(self.context_randomize)

async def setup(bot):
    await bot.add_cog(FileCog(bot))