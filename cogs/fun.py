from bot_utils import (
    handle_logs,
    check_mod
)

import discord
from discord.ext import commands
from discord import app_commands

import random
from datetime import datetime, timezone
from aiohttp import ClientSession

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Say a message in a channel.")
    @app_commands.describe(
        channel="The channel to send the message to.",
        message="The message to send",
        attachment="An optional attachment to include.",
        message_id="An optional message to reply to.",
        ephemeral="Whether the interaction will be ephemeral or not."
    )
    async def say(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = None,
        attachment: discord.Attachment = None,
        message_id: str = None,
        ephemeral: bool = True 
    ):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if not await check_mod(interaction, "manage_messages"):
                return

            if not channel.permissions_for(channel.guild.me).send_messages:
                await interaction.followup.send(f"I don't have permission to send messages in {channel.mention}")
                return

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
                
            await channel.send(content=message, file=await attachment.to_file() if attachment else None, reference=reference_message)

            await interaction.followup.send(f"Sent '{message}' to {channel.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dm", description="Directly message a person.")
    @app_commands.describe(
        member="The member to DM.",
        message="The message to send to them.",
        attachment="An optional attachment to include.",
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
            try:
                await member.send()
            except discord.Forbidden:
                await interaction.followup.send(f"I cannot send messages to {member.mention}. They might have their DMs closed.")
                return
            except:
                pass
            
            await member.send(content=message, file=await attachment.to_file() if attachment else None)
            await interaction.followup.send(f"Sent '{message}' to {member}")   

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="fact", description="Fetches a random fact.")
    async def fact(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/random.json?language=en") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Random Fact 🤓", description=data["text"], color=0x9370DB, timestamp=datetime.now(timezone.utc))
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the fact.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="joke", description="Fetches a random joke.")
    async def joke(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/jokes/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "setup" in data and "punchline" in data:
                            embed = discord.Embed(title=data['setup'], description=f"||{data['punchline']}||", timestamp=datetime.now(timezone.utc))
                            embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send("Sorry, I couldn't fetch a joke right now. Try again later!")
                    else:
                        await interaction.followup.send("An error occurred while fetching the joke.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="cat", description="Fetches a cute cat picture.")
    async def cat(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Here's a cute cat for you!", color=0xFFA07A, timestamp=datetime.now(timezone.utc))
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        embed.set_image(url=data[0]["url"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the cat picture.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="dog", description="Fetches an adorable dog picture.")
    async def dog(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title="Here's a cute dog for you!", color=0xADD8E6, timestamp=datetime.now(timezone.utc))
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        embed.set_image(url=data["message"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the dog picture.")
        except Exception as e:
            await handle_logs(interaction, e)
            
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="duck", description="Fetches a random duck GIF.")
    async def duck(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://random-d.uk/api/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "url" in data:
                            embed = discord.Embed(title="Random Duck GIF", timestamp=datetime.now(timezone.utc))
                            embed.set_image(url=data["url"])
                            embed.set_footer(f"Powered by random-d.uk\nRequested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send("Sorry, I couldn't fetch a duck GIF right now. Try again later!")
                    else:
                        await interaction.followup.send("An error occurred while fetching the duck GIF.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
    @app_commands.command(name="quote", description="Fetches an inspirational quote.")
    async def quote(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://zenquotes.io/api/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(title=data[0]["q"], description=f"- {data[0]['a']}", color=0x66CDAA, timestamp=datetime.now(timezone.utc))
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the quote.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
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
    @app_commands.describe(question="Ask it a question!")
    @app_commands.command(name='8ball', description='Ask the magic 8-ball a question')
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        try:
            responses = [
                "Yes, definitely.",
                "No, not at all.",
                "Maybe, try again later.",
                "It is certain.",
                "Cannot predict now.",
                "Outlook not so good.",
                "Yes, but with caution.",
                "I don't know, ask again."
            ]
            
            response = random.choice(responses)
            
            embed = discord.Embed(
                title="Magic 8-ball",
                description=f'**Question:** {question}\n**Answer:** {response}',
                color=discord.Color.blurple()
            )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(ephemeral="If the message is hidden (Useful if no perms).")
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
                                comic_url = f"https://xkcd.com/{comic_data['num']}/"
                                year = int(comic_data['year'])
                                posted_date = datetime(year, 1, 1).date()

                                embed = discord.Embed(title=comic_data["title"], description=comic_data["alt"], color=0x6A5ACD, timestamp=datetime.now(timezone.utc))
                                embed.url = comic_url
                                embed.set_footer(text=f"Posted on {posted_date}", icon_url="https://xkcd.com/favicon.ico")
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
