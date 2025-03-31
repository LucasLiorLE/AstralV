from bot_utils import (
    get_member_color,
    open_json,
    handle_logs,
)

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View

import random
from datetime import datetime, timezone
from aiohttp import ClientSession

class TriviaView(View):
    def __init__(self, correct_answer: str, question: str):
        super().__init__(timeout=60)
        self.correct_answer = correct_answer
        self.question = question
        self.used = []
        self.winner_found = False
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="Time's Up!",
            description=f"No one answered in time. The correct answer was: {self.correct_answer}",
            color=discord.Color.red()
        )
        
        await self.message.edit(view=self)
        await self.message.reply(embed=embed)

    async def handle_click(self, interaction: discord.Interaction, button: Button):
        if self.winner_found:
            await interaction.response.send_message("This question has already been answered!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in self.used:
            await interaction.response.send_message("You already answered this question.", ephemeral=True)
            return
        
        self.used.append(user_id)

        if button.label == self.correct_answer:
            self.winner_found = True
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="Correct Answer!",
                description=self.question,
                color=discord.Color.green()
            )
            embed.add_field(name="Answer", value=self.correct_answer)
            embed.add_field(name="Winner", value=interaction.user.mention)
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=embed)
            self.stop()
        else:
            await interaction.response.send_message("Wrong answer!", ephemeral=True)

class QuestionView(View):
    def __init__(self, question_type: str = None, rating: str = "pg13"):
        super().__init__()
        self.question_type = question_type
        self.rating = rating

    async def get_question(self, type_override: str = None):
        question_type = type_override or self.question_type
        if not question_type:
            question_type = random.choice(["truth", "dare", "wyr", "nhie", "paranoia"])
        
        url = f"https://api.truthordarebot.xyz/v1/{question_type.lower()}?rating={self.rating}"
        async with ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None

    async def handle_response(self, interaction: discord.Interaction, question_type: str = None):
        data = await self.get_question(question_type)
        if data:
            colors = {
                "TRUTH": discord.Color.blue(),
                "DARE": discord.Color.red(),
                "WYR": discord.Color.purple(),
                "NHIE": discord.Color.gold(),
                "PARANOIA": discord.Color.orange()
            }
            titles = {
                "TRUTH": "Truth",
                "DARE": "Dare",
                "WYR": "Would You Rather",
                "NHIE": "Never Have I Ever",
                "PARANOIA": "Paranoia"
            }
            embed = discord.Embed(
                title=f"{titles[data['type']]} ({data['rating']})",
                description=data['question'],
                color=colors[data['type']]
            )
            embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
            new_view = QuestionView(self.question_type, self.rating)
            await interaction.followup.send(embed=embed, view=new_view)
        else:
            await interaction.response.send_message("Failed to fetch a question.", ephemeral=True)

    @discord.ui.button(label="Truth", style=discord.ButtonStyle.primary)
    async def truth_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction, "truth")

    @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger)
    async def dare_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction, "dare")

    @discord.ui.button(label="Would You Rather", style=discord.ButtonStyle.secondary)
    async def wyr_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction, "wyr")

    @discord.ui.button(label="Never Have I Ever", style=discord.ButtonStyle.secondary)
    async def nhie_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction, "nhie")

    @discord.ui.button(label="Paranoia", style=discord.ButtonStyle.secondary)
    async def paranoia_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction, "paranoia")

    @discord.ui.button(label="Random", style=discord.ButtonStyle.success)
    async def random_button(self, interaction: discord.Interaction, button: Button):
        await self.handle_response(interaction)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class FunCommandGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="fun", description="Fun commands to mess around with!", guild_only=False)

    rating_choices = [
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ]

    @app_commands.command(name="trivia")
    async def trivia(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            async with ClientSession() as session:
                async with session.get("https://opentdb.com/api.php?amount=1") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["response_code"] == 0:
                            result = data["results"][0]
                            
                            def clean_text(text):
                                replacements = {
                                    "&quot;": '"',
                                    "&#039;": "'",
                                    "&amp;": "&",
                                    "&lt;": "<",
                                    "&gt;": ">",
                                    "&apos;": "'",
                                }
                                for old, new in replacements.items():
                                    text = text.replace(old, new)
                                return text
                            
                            question = clean_text(result["question"])
                            correct = clean_text(result["correct_answer"])
                            incorrect = [clean_text(ans) for ans in result["incorrect_answers"]]
                            
                            embed = discord.Embed(
                                title=f"Trivia Question ({result['category']})",
                                description=question,
                                color=get_member_color(interaction, 0x3498db)
                            )
                            embed.add_field(name="Difficulty", value=result["difficulty"].capitalize())
                            embed.set_footer(text=f"Time limit: 60 seconds | Requested by {interaction.user.display_name}")
                            
                            view = TriviaView(correct, question)
                            
                            all_answers = [correct] + incorrect
                            random.shuffle(all_answers)
                            
                            for answer in all_answers:
                                button = Button(label=answer, style=discord.ButtonStyle.primary)
                                button.callback = lambda i=interaction, b=button: view.handle_click(i, b)
                                view.add_item(button)
                            
                            await interaction.followup.send(embed=embed, view=view)
                            view.message = await interaction.original_response()
                        else:
                            await interaction.followup.send("Failed to fetch trivia question. Try again later.")
                    else:
                        await interaction.followup.send("Failed to connect to trivia API. Try again later.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="truth")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def truth(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            url = f"https://api.truthordarebot.xyz/v1/truth?rating={rating}"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=f"Truth ({data['rating']})",
                            description=data['question'],
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView("TRUTH", rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a truth question.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="dare")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def dare(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            url = f"https://api.truthordarebot.xyz/v1/dare?rating={rating}"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=f"Dare ({data['rating']})",
                            description=data['question'],
                            color=discord.Color.red()
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView("DARE", rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a dare question.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="tod")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def truth_or_dare(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            endpoint = "truth" if random.random() < 0.5 else "dare"
            url = f"https://api.truthordarebot.xyz/v1/{endpoint}?rating={rating}"
            
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        color = discord.Color.blue() if data['type'] == "TRUTH" else discord.Color.red()
                        embed = discord.Embed(
                            title=f"{data['type'].capitalize()} ({data['rating']})",
                            description=data['question'],
                            color=color
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView(None, rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a question.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="wyr")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def would_you_rather(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            url = f"https://api.truthordarebot.xyz/v1/wyr?rating={rating}"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=f"Would You Rather ({data['rating']})",
                            description=data['question'],
                            color=discord.Color.purple()
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView("WYR", rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a question.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="nhie")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def never_have_i_ever(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            url = f"https://api.truthordarebot.xyz/v1/nhie?rating={rating}"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=f"Never Have I Ever ({data['rating']})",
                            description=data['question'],
                            color=discord.Color.gold()
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView("NHIE", rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a question.")
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="paranoia")
    @app_commands.choices(rating=[
        app_commands.Choice(name="PG (Family Friendly)", value="pg"),
        app_commands.Choice(name="PG-13 (Teen)", value="pg13")
    ])
    async def paranoia(self, interaction: discord.Interaction, rating: str = "pg13"):
        await interaction.response.defer()
        try:
            url = f"https://api.truthordarebot.xyz/v1/paranoia?rating={rating}"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = discord.Embed(
                            title=f"Paranoia ({data['rating']})",
                            description=data['question'],
                            color=discord.Color.orange()
                        )
                        embed.set_footer(text=f"ID: {data['id']} | Requested by {interaction.user.display_name}")
                        view = QuestionView("PARANOIA", rating)
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("Failed to fetch a question.")
        except Exception as e:
            await handle_logs(interaction, e)

class FunCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(FunCommandGroup())
    
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
    async def xkcd(self, interaction: discord.Interaction, comic_id: int = None, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        try:
            async with ClientSession() as session:
                async with session.get("https://xkcd.com/info.0.json") as latest_response:
                    if latest_response.status != 200:
                        return await interaction.followup.send("An error occurred while fetching the latest xkcd comic.")
                    latest_data = await latest_response.json()
                    max_comic = latest_data["num"]

                comic_num = comic_id if comic_id is not None else random.randint(1, max_comic)
                
                async with session.get(f"https://xkcd.com/{comic_num}/info.0.json") as comic_response:
                    if comic_response.status == 200:
                        comic_data = await comic_response.json()
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
        except Exception as e:
            await handle_logs(interaction, e)

async def setup(bot):
    await bot.add_cog(FunCog(bot))