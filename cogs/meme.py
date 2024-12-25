from main import handle_logs

import discord
from discord.ext import commands
from discord import app_commands

import io, os

from aiohttp import ClientSession
from petpetgif import petpet 
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from urllib.parse import quote

class MemeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="spongebob", description="Generates a Spongebob meme")
    @app_commands.describe(text="The text you want to show on the paper")
    async def spongebob(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with ClientSession() as session:
                async with session.get(f"https://memeado.vercel.app/api/spongebob?text={text}") as response:
                    if response.status == 200:
                        meme_url = str(response.url)
                        await interaction.followup.send(content=meme_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="drakelikehate", description="Generates a Drake Like Hate meme")
    @app_commands.describe(text1="The text for the 'Like' part", text2="The text for the 'Hate' part")
    async def drakelikehate(self, interaction: discord.Interaction, text1: str, text2: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with ClientSession() as session:
                url = f"https://memeado.vercel.app/api/drakelikehate?text1={text1}&text2={text2}"
                async with session.get(url) as response:
                    if response.status == 200:
                        meme_url = str(response.url)
                        await interaction.followup.send(content=meme_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as e:
            await handle_logs(interaction, e)
            
    @app_commands.command(name="petpet", description="Creates a pet-pet gif from a user's avatar, emoji, custom image URL, or uploaded file")
    @app_commands.describe(
        member="Use a member's avatar",
        url="URL to an image to create a pet-pet gif (optional)",
        attachment="File attachment to use for the pet-pet gif (optional)"
    )
    async def petpet(self, interaction: discord.Interaction, member: discord.Member = None, url: str = None, attachment: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        try:
            if attachment:
                image_data = await attachment.read()

            elif url:
                async with ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            await interaction.followup.send("Failed to retrieve the image from the URL.")
                            return
                        image_data = await response.read()

            elif isinstance(member, discord.Member):
                image_data = await member.display_avatar.read()
            else:
                image_data = await interaction.user.display_avatar.read()

            source = BytesIO(image_data)
            dest = BytesIO()
            petpet.make(source, dest)
            dest.seek(0)

            await interaction.followup.send(file=discord.File(dest, filename="petpet.gif"))
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dailystruggle", description="Generates a Daily Struggle meme")
    @app_commands.describe(text1="The text for the right", text2="The text for the left")
    async def dailystruggle(self, interaction: discord.Interaction, text1: str, text2: str):
        await interaction.response.defer(ephemeral=True)
        try:
            text1 = quote(text1, "~")
            text2 = quote(text2, "~")
            async with ClientSession() as session:
                url = f"https://api.memegen.link/images/ds/{text1}/{text2}.png"
                async with session.get(url) as response:
                    if response.status == 200:
                        meme_url = str(response.url)
                        await interaction.followup.send(content=meme_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="isthis", description="Generates an 'Is this' meme")
    @app_commands.describe(
        question="The bottom text (Question)", 
        person="The top text (Person)",
        image="The image URL to use (optional)",
        attachment="Upload an image to use (optional)"
    )
    async def isthis(self, interaction: discord.Interaction, question: str, person: str, image: str = None, attachment: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        try:
            question = quote(question, safe="~")
            person = quote(person, safe="~")

            if attachment:
                image_data = await attachment.read()
                image = "attachment"
            elif image:
                async with ClientSession() as session:
                    async with session.get(image) as response:
                        if response.status != 200:
                            await interaction.followup.send("Failed to retrieve the image from the URL.")
                            return
            else:
                await interaction.followup.send("Please provide an image URL or upload an image.")
                return

            base_url = "https://api.memegen.link/images/pigeon"
            meme_url = f"{base_url}/{question}/{person}.png"
            if image:
                meme_url += f"?background={quote(image, safe='')}"

            async with ClientSession() as session:
                async with session.get(meme_url) as response:
                    if response.status == 200:
                        meme_image_url = str(response.url)
                        await interaction.followup.send(content=meme_image_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Please try again later.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="custom", description="Generates a caption via a custom image")
    @app_commands.describe(
        text="The caption",
        link="The image URL to use",
        attachment="Upload an image to use",
        ephemeral="Whether to hide the response (default: true)"
    )
    async def custom(self, interaction: discord.Interaction, text: str, link: str = None, attachment: discord.Attachment = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            text = quote(text, safe="~")

            if attachment:
                image_url = attachment.url
            elif link:
                image_url = link
            else:
                await interaction.followup.send("Please provide an image URL or upload an image.")
                return

            base_url = "https://api.memegen.link/images/custom"
            meme_url = f"{base_url}/_/{text}.png?background={quote(image_url, safe='')}"

            async with ClientSession() as session:
                async with session.get(meme_url) as response:
                    if response.status == 200:
                        meme_image_url = str(response.url)
                        await interaction.followup.send(content=meme_image_url)
                    else:
                        await interaction.followup.send("Failed to generate the meme. Either the API is down or it's an invalid file type.")
        except Exception as e:
            await handle_logs(interaction, e)
            
    @app_commands.command(name="caption", description="Generates a caption on an image")
    @app_commands.describe(
        text="The caption",
        link="The image URL to use",
        attachment="Upload an image to use",
        layout="The caption layout (top or default)",
        ephemeral="Whether to hide the response (default: true)"
    )
    @app_commands.choices(layout=[app_commands.Choice(name="Top", value="top"), app_commands.Choice(name="Default", value="default")])
    async def caption(self, interaction: discord.Interaction, text: str, link: str = None, attachment: discord.Attachment = None, layout: str = "top", ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if attachment:
                image_data = await attachment.read()
                image = Image.open(io.BytesIO(image_data))
            elif link:
                async with ClientSession() as session:
                    async with session.get(link) as response:
                        if response.status != 200:
                            await interaction.followup.send("Failed to retrieve the image from the URL.")
                            return
                        image_data = await response.read()
                image = Image.open(io.BytesIO(image_data))
            else:
                await interaction.followup.send("Please provide an image URL or upload an image.")
                return

            try:
                font_path = os.path.join(os.path.dirname(__file__), "..", "storage", "fonts", "Futura-Condensed-Extra-Bold.otf")
                font_path = os.path.abspath(font_path)

                if not os.path.exists(font_path):
                    raise FileNotFoundError(f"Font file not found: {font_path}")

                with open(font_path, "rb") as font_file:
                    font_bytes = font_file.read()

                font_size = int(image.height * 0.1)
                font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)

            except OSError as e:
                raise e("Failed to load font file. If you are the owner, please make sure the font file exists in the storage/fonts directory.")
            except FileNotFoundError as fnf_error:
                raise fnf_error("Font file not found. If you are the owner, please make sure the font file exists in the storage/fonts directory.")
            
            words = text.split()
            lines = []
            current_line = []
            current_length = 0

            for word in words:
                word_length = len(word)
                if current_length + word_length + len(current_line) <= 30:
                    current_line.append(word)
                    current_length += word_length
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = word_length
            if current_line:
                lines.append(" ".join(current_line))

            if layout == "top":
                max_line_width = 0
                total_height = 0
                for line in lines:
                    bbox = ImageDraw.Draw(image).textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    line_height = bbox[3] - bbox[1]
                    max_line_width = max(max_line_width, line_width)
                    total_height += line_height

                border_padding = int(image.height * 0.05)
                new_height = image.height + total_height + (border_padding * 2)
                new_image = Image.new("RGB", (image.width, new_height), "white")
                new_image.paste(image, (0, total_height + (border_padding * 2)))

                draw = ImageDraw.Draw(new_image)
                y = border_padding
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    x = (image.width - line_width) // 2
                    draw.text((x, y), line, font=font, fill="black")
                    y += bbox[3] - bbox[1]

                image = new_image
            else:
                total_height = 0
                for line in lines:
                    bbox = ImageDraw.Draw(image).textbbox((0, 0), line, font=font)
                    total_height += bbox[3] - bbox[1]

                draw = ImageDraw.Draw(image)
                y = image.height - total_height - int(image.height * 0.05)

                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    x = (image.width - line_width) // 2
                    draw.text((x, y), line, font=font, fill="black")
                    y += bbox[3] - bbox[1]

            dest = io.BytesIO()
            image.save(dest, format="PNG")
            dest.seek(0)
            await interaction.followup.send(file=discord.File(dest, filename="caption.png"))

        except Exception as e:
            await handle_logs(interaction, e)
            
async def setup(bot):
    await bot.add_cog(MemeCog(bot))