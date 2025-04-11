# Custom commands for me and my friends.
# These will not be bug checked. 
# And will not be included in the change logs.

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
from datetime import datetime, timezone
import random

from bot_utils import (
    open_json,
    save_json,
    handle_logs,
    logs
)
from main import botTesters, botAdmins

class Editors(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="editors",
            description="Manage editors for opp list and ratings",
            guild_only=False
        )
        self.file_path = "storage/customs/editors.json"

    @app_commands.command(name="toggle", description="Toggle a user's ability to add to opp list or ratings")
    @app_commands.describe(
        type="The type of editor to toggle (Opp or Ratings)",
        user="The user to toggle"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Opp", value="opp"),
            app_commands.Choice(name="Ratings", value="ratings"),
        ]
    )
    async def toggle(self, interaction: discord.Interaction, type: str, user: discord.User):
        if interaction.user.id not in botAdmins:
            await interaction.response.send_message("Only bot admins can manage editors!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data:
            data = {"opp": [], "ratings": []}

        user_id = str(user.id)
        editor_type = type.lower()

        if user_id in data[editor_type]:
            data[editor_type].remove(user_id)
            action = "removed from"
        else:
            data[editor_type].append(user_id)
            action = "added to"

        save_json(self.file_path, data)
        await interaction.response.send_message(f"{user.mention} has been {action} the {editor_type} editors list.")

class QuizView(View):
    def __init__(self, correct_answers, question, timeout):
        super().__init__(timeout=timeout)
        self.correct_answers = [str(ans).lower() for ans in correct_answers]
        self.used = []
        self.question = question
        self.winner_found = False
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="Error",
            description=f"No one answered the question in time. The answers were: {', '.join(self.correct_answers)}.",
            color=discord.Color.red()
        )
        
        await self.message.edit(view=self)
        await self.message.reply(embed=embed)

    async def handle_click(self, interaction: discord.Interaction, button: Button):
        if self.winner_found:
            await interaction.response.send_message("This question has already been answered correctly!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in self.used:
            await interaction.response.send_message("You have already answered this question.", ephemeral=True)
            return
        
        self.used.append(user_id)

        if button.label.lower() in self.correct_answers:
            self.winner_found = True
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="Trivia Question Answered",
                description=self.question,
                color=discord.Color.green()
            )
            embed.add_field(name="Answer Given", value=f"{button.label}", inline=False)
            embed.add_field(name="All Correct Answers", value=f"{', '.join(self.correct_answers)}", inline=False)
            embed.add_field(name="Winner", value=interaction.user.mention, inline=False)
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=embed)
            self.stop()
        else:
            await interaction.response.send_message("Wrong lmfao.", ephemeral=True)

class RevealView(View):
    def __init__(self, quiz_data):
        super().__init__()
        self.quiz_data = quiz_data

    @discord.ui.button(label="Reveal Quiz", style=discord.ButtonStyle.primary)
    async def reveal_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Trivia Question", color=discord.Color.green())
        embed.add_field(name="Question", value=self.quiz_data["question"], inline=False)
        embed.add_field(name="Time to answer", value=f"{self.quiz_data['time_limit']} seconds", inline=False)

        view = QuizView(self.quiz_data["correct_answer"], self.quiz_data["question"], self.quiz_data["time_limit"])
        
        options = []
        options.extend(self.quiz_data["correct_answer"])
        options.extend(self.quiz_data["wrong_answers"])
        random.shuffle(options)
        
        for i, option in enumerate(options, 1):
            button = Button(label=str(option), style=discord.ButtonStyle.primary, custom_id=f"option_{i}")
            button.callback = lambda i=interaction, b=button: view.handle_click(i, b)
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        self.stop()

class CustomCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(OppList())
        self.bot.tree.add_command(Rating())
        self.bot.tree.add_command(Editors())

    @app_commands.command(name="error_test", description="Demonstrates intentional error generation")
    async def error_test(self, interaction: discord.Interaction):
        error_list = []
        try:
            print(error_list[0]) 
        except Exception as e:
            await handle_logs(interaction, e)

    @app_commands.command(name="error", description="Allows you to view a certain error.")
    async def view_error(self, interaction: discord.Interaction, error_id: int):
        await interaction.response.defer()

        if interaction.user.id not in botTesters:
            await interaction.followup.send("You do not have permission to use this command.")
            return

        for log_type, log_entries in logs.items():
            for entry in log_entries:
                if entry["ID"] == error_id:
                    error_message = entry.get("Message", "No error message available.")
                    
                    embed = discord.Embed(
                        title=f"Error ID: {error_id}",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name="Type", value=log_type.capitalize(), inline=False)
                    
                    chunks = [error_message[i:i + 1024] for i in range(0, len(error_message), 1024)]
                    for idx, chunk in enumerate(chunks):
                        embed.add_field(
                            name=f"Error (Part {idx + 1})" if len(chunks) > 1 else "Error",
                            value=chunk,
                            inline=False
                        )
                    
                    await interaction.followup.send(embed=embed)
                    return

        await interaction.followup.send(f"No error found with ID {error_id}", ephemeral=True)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="quiz", description="Create a quiz question")
    @app_commands.describe(
        question="The question to ask",
        correct_answers="Comma-separated list of correct answers (e.g. 'Paris,France,République française')",
        wrong_answers="Optional: Comma-separated list of wrong answers",
        time_limit="Time limit in seconds (default: 60)"
    )
    async def quiz(
        self, 
        interaction: discord.Interaction, 
        question: str,
        correct_answers: str,
        wrong_answers: str = None,
        time_limit: float = 60.0
    ):
        correct_answers_list = [ans.strip() for ans in correct_answers.split(",")]
        wrong_answers_list = []

        if wrong_answers:
            for ans in wrong_answers.split(","):
                ans = ans.strip()
                if ans in wrong_answers_list or ans in correct_answers_list:
                    return await interaction.response.send_message("You cannot have duplicate answers!", ephemeral=True)
                else:
                    wrong_answers_list.append(ans)

        if len(correct_answers_list) + len(wrong_answers_list) > 10:
            return await interaction.response.send_message("Please provide less than 10 answers total.", ephemeral=True)

        quiz_data = {
            "question": question,
            "correct_answer": correct_answers_list,
            "wrong_answers": wrong_answers_list,
            "time_limit": time_limit
        }

        view = RevealView(quiz_data)
        await interaction.response.send_message("Click the button below to reveal the quiz:", view=view, ephemeral=True)

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="ccp", description="Ping a user and send a message.")
    @app_commands.describe(choice="Select whether to increase or decrease the Social Credit Score", user="The user to mention",)
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Increase", value="increase"),
            app_commands.Choice(name="Decrease", value="decrease"),
        ]
    )
    async def ccp(self, interaction: discord.Interaction, choice: str, user: discord.User):
        if choice == "increase":
            message = f"{user.mention} (我们的) Good work citizen, and glory to the CCP! Remember to redeem your food units after 12:00 P.M."
        elif choice == "decrease":
            message = (
                f"{user.mention} (我们的) :arrow_double_down: Your Social Credit Score has decreased "
                ":arrow_double_down:. Please refrain from making more of these comments or we will have "
                "to send a Reeducation Squad to your location. Thank you! Glory to the CCP! :flag_cn: (我们的)"
            )

        await interaction.response.send_message(message)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class Rating(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="ratings",
            description="Ratings of users or games",
            guild_only=False
        )
        self.file_path = "storage/customs/ratings.json"
        self.editors_path = "storage/customs/editors.json"

    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        data = open_json(self.file_path)
        if not data:
            return []
        
        items = list(data.keys())
        return [
            app_commands.Choice(name=item, value=item)
            for item in items
            if current.lower() in item.lower()
        ][:25]

    @app_commands.command(name="rate", description="Rate an item")
    @app_commands.describe(
        item="The item to rate, can be a game, user, etc",
        stars="The stars you would give it on a 0-10 scale (can use decimals like 5.5)",
        rating="The rating, max of 2k characters",
        extra_rating_1="Extra rating, max of 2k characters",
        extra_rating_2="Extra rating, max of 2k characters",
        extra_rating_3="Extra rating, max of 2k characters",
        extra_rating_4="Extra rating, max of 2k characters",
        extra_rating_5="Extra rating, max of 2k characters",
        extra_rating_6="Extra rating, max of 2k characters",
        extra_rating_7="Extra rating, max of 2k characters",
        extra_rating_8="Extra rating, max of 2k characters",
        extra_rating_9="Extra rating, max of 2k characters"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def rate(self, interaction: discord.Interaction, item: str, stars: float, rating: str,
                    extra_rating_1: str = None, extra_rating_2: str = None, extra_rating_3: str = None,
                    extra_rating_4: str = None, extra_rating_5: str = None, extra_rating_6: str = None, 
                    extra_rating_7: str = None, extra_rating_8: str = None, extra_rating_9: str = None):
        
        editors_data = open_json(self.editors_path)
        if not editors_data or "ratings" not in editors_data:
            editors_data = {"ratings": []}
            save_json(self.editors_path, editors_data)
        
        if str(interaction.user.id) not in editors_data["ratings"] and interaction.user.id not in botAdmins:
            await interaction.response.send_message("You don't have permission to rate items!", ephemeral=True)
            return

        if not 0 <= stars <= 10:
            await interaction.response.send_message("Stars must be between 0 and 10!", ephemeral=True)
            return

        if len(str(stars).split('.')[-1]) > 1:
            await interaction.response.send_message("Stars can only have 1 decimal place (e.g. 5.5)!", ephemeral=True)
            return
        
        rating = ''.join(part for part in [rating, extra_rating_1, extra_rating_2, extra_rating_3, extra_rating_4,
               extra_rating_5, extra_rating_6, extra_rating_7, extra_rating_8, extra_rating_9] if part)

        if len(rating) > 20000:
            await interaction.response.send_message("Rating text must be 20000 characters or less!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data:
            data = {}

        if item not in data:
            data[item] = {}

        user_id = str(interaction.user.id)
        if user_id in data[item]:
            await interaction.response.send_message(f"You have already rated this item! Please use `/ratings edit` to edit it or `/ratings delete` to delete it!", ephemeral=True)
            return

        data[item][user_id] = {
            "versions": [],
            "current_version": 0
        }

        new_version = data[item][user_id]["current_version"] + 1
        data[item][user_id]["versions"].append({
            "stars": stars,
            "rating": rating,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": new_version
        })
        data[item][user_id]["current_version"] = new_version

        save_json(self.file_path, data)

        total_stars = 0
        count = 0
        for user_ratings in data[item].values():
            latest_version = next(v for v in user_ratings["versions"] if v["version"] == user_ratings["current_version"])
            total_stars += latest_version["stars"]
            count += 1
        average_rating = total_stars / count if count > 0 else 0

        embed = discord.Embed(
            title=f"Rating Added - {item}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Stars", value=f"{stars}/10", inline=True)
        embed.add_field(name="Average Rating", value=f"{average_rating:.1f}/10", inline=True)
        
        chunks = [rating[i:i + 1000] for i in range(0, len(rating), 1000)]
        for i, chunk in enumerate(chunks, 1):
            embed.add_field(name=f"{"Rating" if i == 1 else "\u2800"}", value=chunk, inline=False)

        embed.set_footer(text=f"By {interaction.user}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="edit", description="Edit your rating for an item")
    @app_commands.describe(
        item="The item to edit your rating for",
        stars="The new star rating (0-10, can use decimals like 5.5)",
        rating="The new rating text (max 20k characters, split into 10 parts)",
        extra_rating_1="Extra rating, max of 2k characters",
        extra_rating_2="Extra rating, max of 2k characters",
        extra_rating_3="Extra rating, max of 2k characters",
        extra_rating_4="Extra rating, max of 2k characters",
        extra_rating_5="Extra rating, max of 2k characters",
        extra_rating_6="Extra rating, max of 2k characters",
        extra_rating_7="Extra rating, max of 2k characters",
        extra_rating_8="Extra rating, max of 2k characters",
        extra_rating_9="Extra rating, max of 2k characters"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def edit(self, interaction: discord.Interaction, item: str, stars: float, rating: str,
                    extra_rating_1: str = None, extra_rating_2: str = None, extra_rating_3: str = None,
                    extra_rating_4: str = None, extra_rating_5: str = None, extra_rating_6: str = None, 
                    extra_rating_7: str = None, extra_rating_8: str = None, extra_rating_9: str = None):
        
        if not 0 <= stars <= 10:
            await interaction.response.send_message("Stars must be between 0 and 10!", ephemeral=True)
            return

        if len(str(stars).split('.')[-1]) > 1:
            await interaction.response.send_message("Stars can only have 1 decimal place (e.g. 5.5)!", ephemeral=True)
            return
        
        rating = ''.join(part for part in [rating, extra_rating_1, extra_rating_2, extra_rating_3, extra_rating_4,
               extra_rating_5, extra_rating_6, extra_rating_7, extra_rating_8, extra_rating_9] if part)

        if len(rating) > 20000:
            await interaction.response.send_message("Rating text must be 20000 characters or less!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if user_id not in data[item]:
            await interaction.response.send_message("You haven't rated this item yet!", ephemeral=True)
            return

        new_version = data[item][user_id]["current_version"] + 1
        data[item][user_id]["versions"].append({
            "stars": stars,
            "rating": rating,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": new_version
        })
        data[item][user_id]["current_version"] = new_version

        save_json(self.file_path, data)

        total_stars = 0
        count = 0
        for user_ratings in data[item].values():
            latest_version = next(v for v in user_ratings["versions"] if v["version"] == user_ratings["current_version"])
            total_stars += latest_version["stars"]
            count += 1
        average_rating = total_stars / count if count > 0 else 0

        embed = discord.Embed(
            title=f"Rating Updated - {item}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="New Stars", value=f"{stars}/10", inline=True)
        embed.add_field(name="Average Rating", value=f"{average_rating:.1f}/10", inline=True)
        
        chunks = [rating[i:i + 1000] for i in range(0, len(rating), 1000)]
        for i, chunk in enumerate(chunks, 1):
            embed.add_field(name=f"{"Rating" if i == 1 else "\u2800"}", value=chunk, inline=False)

        embed.set_footer(text=f"By {interaction.user}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="admin_edit", description="[Admin] Edit someone's rating or rename an item")
    @app_commands.describe(
        item="The item to edit",
        new_name="New name for the item (optional)",
        user="User whose rating to edit (optional)",
        stars="New star rating (0-10, can use decimals like 5.5)",
        rating="New rating text"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_edit(
        self, 
        interaction: discord.Interaction, 
        item: str, 
        new_name: str = None,
        user: discord.User = None,
        stars: float = None,
        rating: str = None
    ):
        if interaction.user.id not in botAdmins:
            await interaction.response.send_message("Only bot admins can use this command!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        if new_name:
            if new_name in data:
                await interaction.response.send_message(f"An item named '{new_name}' already exists!", ephemeral=True)
                return
            data[new_name] = data[item]
            del data[item]
            item = new_name

        if user:
            user_id = str(user.id)
            if user_id not in data[item]:
                await interaction.response.send_message(f"{user} hasn't rated this item!", ephemeral=True)
                return

            if stars is not None:
                if not 0 <= stars <= 10:
                    await interaction.response.send_message("Stars must be between 0 and 10!", ephemeral=True)
                    return
                if len(str(stars).split('.')[-1]) > 1:
                    await interaction.response.send_message("Stars can only have 1 decimal place (e.g. 5.5)!", ephemeral=True)
                    return

            if not stars and not rating:
                await interaction.response.send_message("Please provide either stars or rating to edit!", ephemeral=True)
                return

            current_version = data[item][user_id]["current_version"]
            current_data = next(v for v in data[item][user_id]["versions"] if v["version"] == current_version)

            new_version = current_version + 1
            new_data = {
                "stars": stars if stars is not None else current_data["stars"],
                "rating": rating if rating is not None else current_data["rating"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": new_version,
                "edited_by": str(interaction.user)
            }

            data[item][user_id]["versions"].append(new_data)
            data[item][user_id]["current_version"] = new_version

        save_json(self.file_path, data)

        embed = discord.Embed(
            title="Admin Edit Complete",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        if new_name:
            embed.add_field(name="Item Renamed", value=f"'{item}' (previously '{new_name}')", inline=False)

        if user:
            embed.add_field(name="User Rating Updated", value=f"Updated {user}'s rating:", inline=False)
            if stars is not None:
                embed.add_field(name="New Stars", value=f"{stars}/10", inline=True)
            if rating is not None:
                embed.add_field(name="New Rating", value=rating, inline=False)

        embed.set_footer(text=f"Edited by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="admin_delete_rating", description="[Admin] Delete a specific user's rating")
    @app_commands.describe(
        item="The item to delete the rating from",
        user="The user whose rating to delete"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_delete_rating(self, interaction: discord.Interaction, item: str, user: discord.User):
        if interaction.user.id not in botAdmins:
            await interaction.response.send_message("Only bot admins can use this command!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        user_id = str(user.id)
        if user_id not in data[item]:
            await interaction.response.send_message(f"{user} hasn't rated this item!", ephemeral=True)
            return

        del data[item][user_id]

        if not data[item]:
            del data[item]

        save_json(self.file_path, data)

        embed = discord.Embed(
            title="Rating Deleted",
            description=f"Deleted {user}'s rating for {item}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        if item in data:
            total_stars = 0
            count = 0
            for user_ratings in data[item].values():
                latest_version = next(v for v in user_ratings["versions"] if v["version"] == user_ratings["current_version"])
                total_stars += latest_version["stars"]
                count += 1
            average_rating = total_stars / count if count > 0 else 0
            embed.add_field(name="New Average Rating", value=f"{average_rating:.1f}/10", inline=True)
        else:
            embed.add_field(name="Item Status", value="Item removed (no more ratings)", inline=True)

        embed.set_footer(text=f"Deleted by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="view", description="View ratings for an item")
    @app_commands.describe(
        item="The item to view ratings for",
        user="Filter ratings by a specific user",
        version="View a specific version of a rating"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def view(self, interaction: discord.Interaction, item: str, user: discord.User = None, version: int = None):
        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Ratings for {item}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        if user:
            user_id = str(user.id)
            if user_id not in data[item]:
                await interaction.response.send_message(f"{user} hasn't rated this item!", ephemeral=True)
                return

            user_data = data[item][user_id]
            if version is None:
                embed.add_field(name="Stars", value=f"{version_data['stars']}/10", inline=True)
                embed.add_field(name="Version", value=str(version), inline=True)
                
                chunks = [version_data['rating'][i:i + 2000] for i in range(0, len(version_data['rating']), 2000)]
                for i, chunk in enumerate(chunks, 1):
                    embed.add_field(name=f"{"Rating" if i == 1 else "\u2800"}", value=chunk, inline=False)

            else:
                version_data = None
                for v in user_data["versions"]:
                    if v["version"] == version:
                        version_data = v
                        break

                if not version_data:
                    await interaction.response.send_message(f"Version {version} not found!", ephemeral=True)
                    return

                embed.add_field(name="Stars", value=f"{version_data['stars']}/10", inline=True)
                embed.add_field(name="Version", value=str(version), inline=True)
                
                chunks = [version_data['rating'][i:i + 2000] for i in range(0, len(version_data['rating']), 2000)]
                for i, chunk in enumerate(chunks, 1):
                    embed.add_field(name=f"{"Rating" if i == 1 else "\u2800"}", value=chunk, inline=False)

        else:
            total_stars = 0
            count = 0
            ratings_text = []

            for user_id, user_ratings in data[item].items():
                latest_version = next(v for v in user_ratings["versions"] if v["version"] == user_ratings["current_version"])
                total_stars += latest_version["stars"]
                count += 1
                
                try:
                    user = await interaction.client.fetch_user(int(user_id))
                    user_name = user.display_name if user else "Unknown User"
                except:
                    discord_user = interaction.guild.get_member(int(user_id)) if interaction.guild else None
                    user_name = discord_user.display_name if discord_user else "Unknown User"
                
                ratings_text.append(f"{user_name}: {latest_version['stars']}/10 - {latest_version['rating'][:100]}{"..." if len(latest_version['rating']) > 100 else None}")

            average_rating = total_stars / count if count > 0 else 0
            embed.add_field(name="Average Rating", value=f"{average_rating:.1f}/10", inline=False)

            if ratings_text:
                ratings_chunks = []
                current_chunk = ""
                for rating in ratings_text[:10]:
                    if len(current_chunk) + len(rating) + 2 > 1000:
                        ratings_chunks.append(current_chunk)
                        current_chunk = rating
                    else:
                        current_chunk += ("\n\n" if current_chunk else "") + rating
                if current_chunk:
                    ratings_chunks.append(current_chunk)

                for i, chunk in enumerate(ratings_chunks, 1):
                    embed.add_field(name=f"All Ratings", value=chunk, inline=False)

                if len(ratings_text) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(ratings_text)} ratings")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete", description="Delete your rating for an item")
    @app_commands.describe(item="The item to delete your rating for")
    @app_commands.autocomplete(item=item_autocomplete)
    async def delete(self, interaction: discord.Interaction, item: str):
        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        if user_id not in data[item]:
            await interaction.response.send_message("You haven't rated this item!", ephemeral=True)
            return

        del data[item][user_id]

        if not data[item]:
            del data[item]

        save_json(self.file_path, data)

        embed = discord.Embed(
            title="Rating Deleted",
            description=f"Your rating for {item} has been deleted.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )

        if item in data:
            total_stars = 0
            count = 0
            for user_ratings in data[item].values():
                latest_version = next(v for v in user_ratings["versions"] if v["version"] == user_ratings["current_version"])
                total_stars += latest_version["stars"]
                count += 1
            average_rating = total_stars / count if count > 0 else 0
            embed.add_field(name="New Average Rating", value=f"{average_rating:.1f}/10", inline=True)
        else:
            embed.add_field(name="Item Status", value="Item removed (no more ratings)", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete_item", description="[Admin] Delete an item and all its ratings")
    @app_commands.describe(item="The item to completely delete")
    @app_commands.autocomplete(item=item_autocomplete)
    async def delete_item(self, interaction: discord.Interaction, item: str):
        if interaction.user.id not in botAdmins:
            await interaction.response.send_message("Only bot admins can delete items!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data or item not in data:
            await interaction.response.send_message("This item doesn't exist!", ephemeral=True)
            return

        rating_count = len(data[item])

        del data[item]
        save_json(self.file_path, data)

        embed = discord.Embed(
            title="Item Deleted",
            description=f"The item '{item}' has been completely deleted.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Ratings Removed", value=str(rating_count), inline=True)
        embed.set_footer(text=f"Deleted by {interaction.user}")

        await interaction.response.send_message(embed=embed)

@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class OppList(app_commands.Group):
    def __init__(self):
        super().__init__(
            name="opp",
            description="Manage the opp list",
            guild_only=False
        )
        self.file_path = "storage/customs/opp_list.json"
        self.editors_path = "storage/customs/editors.json"

    async def user_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        data = open_json(self.file_path)
        if not data:
            return []
        
        users = list(data.keys())
        return [
            app_commands.Choice(name=user, value=user)
            for user in users
            if current.lower() in user.lower()
        ][:25]

    def find_user(self, search_user: str, data: dict) -> str:
        """Find user with case-insensitive search"""
        for user in data:
            if user.lower() == search_user.lower():
                return user
        return None

    @app_commands.command(name="list", description="List all users in the opp list")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = open_json(self.file_path)
        if not data:
            await interaction.followup.send("The opp list is empty!", ephemeral=True)
            return

        embed = discord.Embed(title="Opp List", color=discord.Color.red())
        opp_list = "\n".join(f"{i+1}. {user}" for i, user in enumerate(data.keys()))
        embed.description = opp_list
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="add", description="Add someone to the opp list")
    @app_commands.describe(user="The user to add", reason="Reason for adding")
    async def add(self, interaction: discord.Interaction, user: str, reason: str):
        editors_data = open_json(self.editors_path)
        if not editors_data or "opp" not in editors_data:
            editors_data = {"opp": []}
            save_json(self.editors_path, editors_data)
        
        if str(interaction.user.id) not in editors_data["opp"] and interaction.user.id not in botAdmins:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_json(self.file_path)
        existing_user = self.find_user(user, data)
        if existing_user:
            await interaction.response.send_message(f"{existing_user} is already in the opp list!", ephemeral=True)
            return

        data[user] = {
            "versions": [
                {
                    "reason": reason,
                    "edited_by": str(interaction.user),
                    "version": 1
                }
            ],
            "current_version": 1
        }
        save_json(self.file_path, data)
        await interaction.response.send_message(f"Added {user} to the opp list.")

    @app_commands.command(name="remove", description="Remove someone from the opp list")
    @app_commands.describe(user="The user to remove")
    @app_commands.autocomplete(user=user_autocomplete)
    async def remove(self, interaction: discord.Interaction, user: str):
        if interaction.user.id not in botTesters:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_json(self.file_path)
        existing_user = self.find_user(user, data)
        if not existing_user:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        del data[existing_user]
        save_json(self.file_path, data)
        await interaction.response.send_message(f"Removed {existing_user} from the opp list.")

    @app_commands.command(name="edit", description="Edit someone's reason in the opp list")
    @app_commands.describe(user="The user to edit", reason="New reason")
    @app_commands.autocomplete(user=user_autocomplete)
    async def edit(self, interaction: discord.Interaction, user: str, reason: str):
        if interaction.user.id not in botTesters:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_json(self.file_path)
        existing_user = self.find_user(user, data)
        if not existing_user:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        user_data = data[existing_user]
        new_version = user_data["current_version"] + 1
        user_data["versions"].append({
            "reason": reason,
            "edited_by": str(interaction.user),
            "version": new_version
        })
        user_data["current_version"] = new_version
        save_json(self.file_path, data)
        await interaction.response.send_message(f"Updated reason for {existing_user}.")

    @app_commands.command(name="view", description="View someone's opp list entry")
    @app_commands.describe(
        user="The user to view",
        version="Version number to view (optional, defaults to latest)"
    )
    @app_commands.autocomplete(user=user_autocomplete)
    async def view(self, interaction: discord.Interaction, user: str, version: int = None):
        data = open_json(self.file_path)
        existing_user = self.find_user(user, data)
        if not existing_user:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        user_data = data[existing_user]
        if version is None:
            version = user_data["current_version"]
        
        version_data = None
        for v in user_data["versions"]:
            if v["version"] == version:
                version_data = v
                break

        if not version_data:
            await interaction.response.send_message(f"Version {version} not found for {existing_user}!", ephemeral=True)
            return

        embed = discord.Embed(title=f"Opp List Entry - {existing_user}", color=discord.Color.red())
        embed.add_field(name="Version", value=str(version), inline=False)
        embed.add_field(name="Reason", value=version_data["reason"], inline=False)
        editor_field = "Added by" if version == 1 else "Edited by"
        embed.add_field(name=editor_field, value=version_data["edited_by"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reorder", description="Reorder someone in the opp list")
    @app_commands.describe(user="The user to reorder", position="New position (1-based)")
    @app_commands.autocomplete(user=user_autocomplete)
    async def reorder(self, interaction: discord.Interaction, user: str, position: int):
        if interaction.user.id not in botTesters:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_json(self.file_path)
        existing_user = self.find_user(user, data)
        if not existing_user:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        items = list(data.items())
        total_items = len(items)

        if position < 1 or position > total_items:
            await interaction.response.send_message(f"Position must be between 1 and {total_items}!", ephemeral=True)
            return

        current_pos = next(i for i, (name, _) in enumerate(items) if name == existing_user)
        
        item = items.pop(current_pos)
        
        items.insert(position-1, item)
        
        new_data = dict(items)
        save_json(self.file_path, new_data)

        embed = discord.Embed(title="Opp List Updated", color=discord.Color.green())
        opp_list = "\n".join(f"{i+1}. {name}" for i, (name, _) in enumerate(items))
        embed.description = opp_list
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomCommandCog(bot))