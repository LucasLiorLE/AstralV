from ast import alias
from bot_utils import (
    get_member_color,
    load_commands,
    open_json,
    handle_logs,
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
        load_commands(self.__cog_app_commands__, "fun")

    
    def check_moderation_info(self, ctx_or_interaction, permission_name: str, minimum_role: str) -> tuple[bool, discord.Embed]:
        try:
            if isinstance(ctx_or_interaction, discord.Interaction):
                user = ctx_or_interaction.user
                guild = ctx_or_interaction.guild
            else:
                user = ctx_or_interaction.author
                guild = ctx_or_interaction.guild

            if not guild:
                return False, discord.Embed(
                    title="Error",
                    description="This command can only be used in a server.",
                    color=discord.Color.red()
                )

            if user.id == guild.owner_id:
                return True, None

            member = guild.get_member(user.id)
            if not member:
                return False, discord.Embed(
                    title="Error",
                    description="Could not verify your server membership.",
                    color=discord.Color.red()
                )

            if getattr(member.guild_permissions, permission_name, False):
                return True, None

            server_info = open_json("storage/server_info.json")
            guild_prefs = server_info.get("preferences", {}).get(str(guild.id), {})
            required_role_id = guild_prefs.get(minimum_role)

            if not required_role_id:
                return False, discord.Embed(
                    title="Error",
                    description=f"No {minimum_role} role has been set for this server.",
                    color=discord.Color.red()
                )

            required_role = guild.get_role(required_role_id)
            if not required_role:
                return False, discord.Embed(
                    title="Error",
                    description=f"The configured {minimum_role} role could not be found.",
                    color=discord.Color.red()
                )

            if required_role in member.roles:
                return True, None

            return False, discord.Embed(
                title="Missing Permissions",
                description=f"You need the `{required_role.name}` role or `{permission_name}` permission to use this command.",
                color=discord.Color.red()
            )

        except Exception as e:
            return False, discord.Embed(
                title="Error",
                description=f"An error occurred while checking permissions: {str(e)}",
                color=discord.Color.red()
            )

    @app_commands.command(name="say")
    async def say(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str = None, 
                  attachment: discord.Attachment = None, reply: str = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            has_mod, embed = self.check_moderation_info(interaction, "manage_messages", "moderator")
            if not has_mod:
                return await interaction.followup.send(embed=embed)

            if not channel.permissions_for(channel.guild.me).send_messages:
                return await interaction.followup.send(f"I don't have permission to send messages in {channel.mention}")
            
            if not message and not attachment:
                return await interaction.followup.send("You must provide either a message or an attachment!")

            reference_message = None

            if reply:
                try:
                    reference_message = await channel.fetch_message(int(reply))
                except discord.NotFound:
                    return await interaction.followup.send(f"Message with ID {reply} not found in {channel.mention}.")

                except discord.HTTPException as e:
                    return await interaction.followup.send(f"An error occurred while fetching the message: {e}")

            await channel.send(content=message, file=await attachment.to_file() if attachment else None, reference=reference_message)

            await interaction.followup.send(f"Message sent to {channel.mention}")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dm")
    async def dm(self, interaction: discord.Interaction, member: discord.Member, message: str = None,
                attachment: discord.Attachment = None, ephemeral: bool = True):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            if not message and not attachment:
                return await interaction.followup.send("You must provide either a message or an attachment!")

            try:
                await member.send(content=message, file=await attachment.to_file() if attachment else None)
                await interaction.followup.send(f"Message sent to {member}")
            except discord.Forbidden:
                await interaction.followup.send(f"I cannot send messages to {member.mention}. They might have their DMs closed.")
            except Exception as e:
                await interaction.followup.send(f"Failed to send message: {str(e)}")

        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="dice")
    async def dice(self, interaction: discord.Interaction, sides: int = 6, amount: int = 1):
        try:
            await interaction.response.send_message(f"Rolling {amount} {sides}-sided dice...", ephemeral=True)
            rolls = [random.randint(1, sides) for _ in range(amount)]
            total = sum(rolls)
            embed = discord.Embed(
                title=f"{amount} {sides}-sided dice roll",
                description=f"Rolls: {', '.join(map(str, rolls))}\nTotal: {total}",
                color=get_member_color(interaction, 0x00FF00)
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="fact")
    async def fact(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/random.json?language=en") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title="Random Fact 🤓", 
                            description=data["text"], 
                            color=get_member_color(interaction, 0xe04ac7), 
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the fact.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="joke")
    async def joke(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/jokes/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "setup" in data and "punchline" in data:
                            embed = discord.Embed(
                                title=data['setup'], 
                                description=f"||{data['punchline']}||", 
                                color=get_member_color(interaction, 0xad3d4c),
                                timestamp=datetime.now(timezone.utc)
                            )
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
    @app_commands.command(name="cat")
    async def cat(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title="Here's a cute cat for you!", 
                            color=get_member_color(interaction, 0x553a69), 
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        embed.set_image(url=data[0]["url"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the cat picture.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="dog")
    async def dog(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title="Here's a cute dog for you!", 
                            color=get_member_color(interaction, 0x52452a), 
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                        embed.set_image(url=data["message"])
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the dog picture.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="duck")
    async def duck(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://random-d.uk/api/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "url" in data:
                            embed = discord.Embed(
                                title="Random Duck GIF", 
                                color=get_member_color(interaction, 0xfbff8a),
                                timestamp=datetime.now(timezone.utc))
                            embed.set_image(url=data["url"])
                            embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
                            await interaction.followup.send(embed=embed)
                        else:
                            await interaction.followup.send("Sorry, I couldn't fetch a duck GIF right now. Try again later!")
                    else:
                        await interaction.followup.send("An error occurred while fetching the duck GIF.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="quote")
    async def quote(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://zenquotes.io/api/random") as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title="Super inspiring title",
                            description=f"```{data[0]['q']}```\n*― {data[0]['a']}*", 
                            color=get_member_color(interaction, 0x9932CC),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_footer(text=f"Requested by {interaction.user.display_name}", 
                                    icon_url=interaction.user.avatar.url)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("An error occurred while fetching the quote.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="meme")
    async def meme(self, interaction: discord.Interaction, # allow_nsfw: bool = False, Removing allow_nsfw since people don't want it, you can easily add it back.
                  allow_spoilers: bool = False, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                max_retries = 5
                for _ in range(max_retries):
                    async with session.get("https://meme-api.com/gimme") as response:
                        if response.status == 200:  
                            meme_data = await response.json()
                            
                            if not False and meme_data.get('nsfw', False):
                                continue
                                
                            if not allow_spoilers and meme_data.get('spoiler', False):
                                continue

                            embed = discord.Embed(
                                title=meme_data['title'],
                                url=meme_data['postLink'],
                                color=get_member_color(interaction, 0xffef40),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_image(url=meme_data["url"])
                            
                            footer_text = f"👍 {meme_data['ups']} | Posted by u/{meme_data['author']}"
                            # if meme_data.get('nsfw'):
                            #     footer_text += " | 🔞 NSFW"
                            if meme_data.get('spoiler'):
                                footer_text += " | ⚠️ Spoiler"
                            footer_text += f" | Requested by {interaction.user.display_name}"
                            
                            embed.set_footer(
                                text=footer_text,
                                icon_url=interaction.user.avatar.url
                            )
                            
                            return await interaction.followup.send(embed=embed)
                            
                await interaction.followup.send("Couldn't find a suitable meme matching your criteria. Please try again!")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name='8ball')
    async def eight_ball(self, interaction: discord.Interaction, question: str, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
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
                color=get_member_color(interaction, 0x4169E1)
            )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="xkcd")
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

                                embed = discord.Embed(
                                    title=comic_data["title"], 
                                    description=comic_data["alt"], 
                                    color=get_member_color(interaction, 0xFFFFFF),
                                    timestamp=datetime.now(timezone.utc)
                                )
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