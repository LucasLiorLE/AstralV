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
        item="The thing to rate, can be a game, user, etc",
        stars="The stars you would give it on a 1-10 scale",
        rating="The rating, max of 1k characters"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def rate(self, interaction: discord.Interaction, item: str, stars: int, rating: str):
        if not 1 <= stars <= 10:
            await interaction.response.send_message("Stars must be between 1 and 10!", ephemeral=True)
            return

        if len(rating) > 1000:
            await interaction.response.send_message("Rating text must be 1000 characters or less!", ephemeral=True)
            return

        data = open_json(self.file_path)
        if not data:
            data = {}

        if item not in data:
            if interaction.user.id not in botTesters:
                await interaction.response.send_message("This item hasn't been rated yet. Only bot testers can add new items!", ephemeral=True)
                return
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
        embed.add_field(name="Your Rating", value=rating, inline=False)
        embed.set_footer(text=f"By {interaction.user}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="edit", description="Edit your rating for an item")
    @app_commands.describe(
        item="The item to edit your rating for",
        stars="The new star rating (1-10)",
        rating="The new rating text"
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def edit(self, interaction: discord.Interaction, item: str, stars: int, rating: str):
        if not 1 <= stars <= 10:
            await interaction.response.send_message("Stars must be between 1 and 10!", ephemeral=True)
            return

        if len(rating) > 5000:
            await interaction.response.send_message("Rating text must be 5000 characters or less!", ephemeral=True)
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
        embed.add_field(name="Your New Rating", value=rating, inline=False)
        embed.set_footer(text=f"By {interaction.user}")

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
                version = user_data["current_version"]

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
            embed.add_field(name="Rating", value=version_data["rating"], inline=False)
            embed.set_footer(text=f"By {user}")

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
                
                ratings_text.append(f"{user_name}: {latest_version['stars']}/10 - {latest_version['rating'][:100]}...")

            average_rating = total_stars / count if count > 0 else 0
            embed.add_field(name="Average Rating", value=f"{average_rating:.1f}/10", inline=False)
            
            if ratings_text:
                embed.add_field(name="All Ratings", value="\n\n".join(ratings_text[:10]), inline=False)
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
        if interaction.user.id not in botTesters:
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