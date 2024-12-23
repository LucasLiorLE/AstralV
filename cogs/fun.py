from main import handle_logs

import discord
from discord.ext import commands
from discord import app_commands

import random
from io import BytesIO
from petpetgif import petpet # pip install petpetgif
from aiohttp import ClientSession

class MemeifyGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="memeify", description="Generate memes!")

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
                image_data = await interaction.member.display_avatar.read()

            source = BytesIO(image_data)
            dest = BytesIO()
            petpet.make(source, dest)
            dest.seek(0)

            await interaction.followup.send(file=discord.File(dest, filename="petpet.gif"))
        except Exception as e:
            await handle_logs(interaction, e)

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(MemeifyGroup())

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="ccp", description="Ping a user and send a message.")
    @app_commands.describe(choice="Select whether to increase or decrease the Social Credit Score", user_id="The ID of the user to mention",)
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Increase", value="increase"),
            app_commands.Choice(name="Decrease", value="decrease"),
        ]
    )
    async def ccp(self, interaction: discord.Interaction, choice: str, user_id: str):
        await interaction.response.defer()
        try:
            if choice == "increase":
                message = f"<@{user_id}> (我们的) Good work citizen, and glory to the CCP! Remember to redeem your food units after 12:00 P.M."
            elif choice == "decrease":
                message = (
                    f"<@{user_id}> (我们的) :arrow_double_down: Your Social Credit Score has decreased "
                    ":arrow_double_down:. Please refrain from making more of these comments or we will have "
                    "to send a Reeducation Squad to your location. Thank you! Glory to the CCP! :flag_cn: (我们的)"
                )

            await interaction.followup.send(message)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="say", description="Say a message in a channel")
    @app_commands.describe(
        channel="The user to talk in",
        message="The message to send",
        attachment="An optional attachment to include",
        message_id="An optional message to reply to",
        ephemeral="Whether the message will be ephemeral for others or not"
    )
    @commands.has_permissions(manage_messages=True)
    async def say(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = None,
        attachment: discord.Attachment = None,
        message_id: str = None,
        ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            reference_message = None

            if message_id:
                try:
                    reference_message = await channel.fetch_message(int(message_id))
                except discord.NotFound:
                    await interaction.followup.send(f"Message with ID {message_id} not found in {channel.mention}.")
                    return
                except discord.HTTPException as e:
                    await interaction.followup.send(f"An error occurred while fetching the message: {e}")
                    return
                
            # Testing if file=None will return an error or not.
            await channel.send(content=message, file=await attachment.to_file(), reference=reference_message)

            '''
            if attachment:
                await channel.send(content=message, file=await attachment.to_file(), reference=reference_message)
            else:
                await channel.send(content=message, reference=reference_message)
            '''

            await interaction.followup.send(f"Sent '{message}' to {channel.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dm", description="Directly message a person.")
    @app_commands.describe(
        member="The user to DM",
        message="The message to send to them",
        attachment="An optional attachment to include",
    )
    async def dm(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str = None,
        attachment: discord.Attachment = None,
    ):
        await interaction.response.defer()
        try:
            await member.send(content=message, file=await attachment.to_file())
            await interaction.followup.send(f"Sent '{message}' to {member}")              
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="fact", description="Fetches a random fact.")
    async def fact(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/random.json?language=en") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Random Fact 🤓", description=data["text"], color=0x9370DB)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the fact.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="joke", description="Fetches a random joke.")
    async def joke(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/jokes/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "setup" in data and "punchline" in data:
                            await interaction.followup.send(content=f"**{data['setup']}**\n\n*||{data['punchline']}||*")
                        else:
                            await interaction.followup.send("Sorry, I couldn't fetch a joke right now. Try again later!")
                    else:
                        await interaction.followup.send("An error occurred while fetching the joke.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="cat", description="Fetches a cute cat picture.")
    async def cat(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Here's a cute cat for you!", color=0xFFA07A)
                        embed.set_image(url=data[0]["url"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the cat picture.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="dog", description="Fetches an adorable dog picture.")
    async def dog(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Here's a cute dog for you!", color=0xADD8E6)
                        embed.set_image(url=data["message"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the dog picture.")
        except Exception as e:
            await handle_logs(interaction, e)
            
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="quote", description="Fetches an inspirational quote.")
    async def quote(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://zenquotes.io/api/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=data[0]["q"], 
                            description=f"- {data[0]['a']}", 
                            color=0x66CDAA
                        )
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the quote.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="meme", description="Fetches a funny meme!")
    async def meme(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as response:
                    if response.status == 200:  
                        data = await response.json()
                        meme_data = data[0]

                        embed = discord.Embed(title=f"({meme_data['title']})[{meme_data['postLink']}]", color=0x66CDAA)
                        embed.set_image(url=meme_data["url"])
                        embed.set_footer(text=f"{meme_data['ups']} Upvotes | By: {meme_data['author']} | Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred when trying to fetch the meme")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms)")
    @app_commands.command(name="xkcd", description="Fetches a random xkcd comic.")
    async def xkcd(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://xkcd.com/info.0.json") as latest_response:
                    if latest_response.status == 200:
                        latest_data = await latest_response.json()
                        max_comic = latest_data["num"]
                        async with session.get(f"https://xkcd.com/{random.randint(1, max_comic)}/info.0.json") as random_response:
                            if random_response.status == 200:
                                comic_data = await random_response.json()
                                embed = discord.Embed(title=comic_data["title"], description=comic_data["alt"], color=0x6A5ACD)
                                embed.set_image(url=comic_data["img"])
                                await interaction.followup.send(embed=embed)
                            else:
                                await interaction.followup.send("An error occurred while fetching the xkcd comic.")
                    else:
                        await interaction.followup.send("An error occurred while fetching the latest xkcd comic.")
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(FunCog(bot))
