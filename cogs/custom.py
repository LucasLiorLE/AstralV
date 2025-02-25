# Custom commands for me and my friends.
# These will not be bug checked. 
# And will not be included in the change logs.

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import random

from bot_utils import (
    open_file,
    save_file
)

class QuizView(View):
    def __init__(self, correct_answer, question, timeout):
        super().__init__(timeout=timeout)
        self.correct_answer = correct_answer
        self.used = []
        self.question = question
        self.winner_found = False
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="Error",
            description=f"No one answered the question in time. The answer was {self.correct_answer}.",
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

        if button.label.lower() == str(self.correct_answer).lower():
            self.winner_found = True
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="Trivia Question Answered",
                description=self.question,
                color=discord.Color.green()
            )
            embed.add_field(name="Answer", value=f"{self.correct_answer}", inline=False)
            embed.add_field(name="Winner", value=interaction.user.mention, inline=False)
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message("Wrong lmfao.", ephemeral=True)

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.tree.add_command(OppList())

    @app_commands.command(name="quiz", description="Create a quiz question")
    @app_commands.describe(
        question="The question to ask",
        correct_answer="The correct answer",
        wrong_answers="Comma-separated list of wrong answers (e.g. 'London,Berlin,Madrid')",
        time_limit="Time limit in seconds (default: 60)"
    )
    async def quiz(
        self, 
        interaction: discord.Interaction, 
        question: str,
        correct_answer: str,
        wrong_answers: str,
        time_limit: float = 60.0
    ):
        wrong_answers_list = []

        for ans in wrong_answers.split(","):
            ans = ans.strip()
            if ans in wrong_answers_list:
                return await interaction.response.send_message("You cannot have duplicate answers!", ephemeral=True)
            else:
                wrong_answers_list.append(ans)

        if not wrong_answers_list:
            return await interaction.response.send_message("Please provide at least one wrong answer!", ephemeral=True)

        if len(wrong_answers_list) + 1 > 10:
            return await interaction.response.send_message("Please provide with less than 10 answers.", ephemeral=True)

        if (correct_answer in wrong_answers_list):
            return await interaction.response.send_message("You cannot have duplicate answers!", ephemeral=True)

        embed = discord.Embed(title="Trivia Question", color=discord.Color.green())
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Time to answer", value=f"{time_limit} seconds", inline=False)

        view = QuizView(correct_answer, question, time_limit)
        
        options = [correct_answer] + wrong_answers_list
        random.shuffle(options)
        
        for i, option in enumerate(options, 1):
            button = Button(label=str(option), style=discord.ButtonStyle.primary, custom_id=f"option_{i}")
            button.callback = lambda i=interaction, b=button: view.handle_click(i, b)
            view.add_item(button)

        response = await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

class OppList(app_commands.Group):
    def __init__(self):
        super().__init__(name="opp")
        self.file_path = "storage/customs/opp_list.json"
        self.opp_editors = [721151215010054165, 776139231583010846, 872706663474429993]

    @app_commands.command(name="list", description="List all users in the opp list")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = open_file(self.file_path)
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
        if interaction.user.id not in self.opp_editors:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_file(self.file_path)
        if user in data:
            await interaction.response.send_message(f"{user} is already in the opp list!", ephemeral=True)
            return

        data[user] = {"reason": reason, "added_by": str(interaction.user)}
        save_file(self.file_path, data)
        await interaction.response.send_message(f"Added {user} to the opp list.")

    @app_commands.command(name="remove", description="Remove someone from the opp list")
    @app_commands.describe(user="The user to remove")
    async def remove(self, interaction: discord.Interaction, user: str):
        if interaction.user.id not in self.opp_editors:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_file(self.file_path)
        if user not in data:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        del data[user]
        save_file(self.file_path, data)
        await interaction.response.send_message(f"Removed {user} from the opp list.")

    @app_commands.command(name="edit", description="Edit someone's reason in the opp list")
    @app_commands.describe(user="The user to edit", reason="New reason")
    async def edit(self, interaction: discord.Interaction, user: str, reason: str):
        if interaction.user.id not in self.opp_editors:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_file(self.file_path)
        if user not in data:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        data[user]["reason"] = reason
        save_file(self.file_path, data)
        await interaction.response.send_message(f"Updated reason for {user}.")

    @app_commands.command(name="view", description="View someone's opp list entry")
    @app_commands.describe(user="The user to view")
    async def view(self, interaction: discord.Interaction, user: str):
        data = open_file(self.file_path)
        if user not in data:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        embed = discord.Embed(title=f"Opp List Entry - {user}", color=discord.Color.red())
        embed.add_field(name="Reason", value=data[user]["reason"], inline=False)
        embed.add_field(name="Added by", value=data[user]["added_by"], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reorder", description="Reorder someone in the opp list")
    @app_commands.describe(user="The user to reorder", position="New position (1-based)")
    async def reorder(self, interaction: discord.Interaction, user: str, position: int):
        if interaction.user.id not in self.opp_editors:
            await interaction.response.send_message("You don't have permission to modify the opp list!", ephemeral=True)
            return

        data = open_file(self.file_path)
        if user not in data:
            await interaction.response.send_message(f"{user} is not in the opp list!", ephemeral=True)
            return

        items = list(data.items())
        total_items = len(items)

        if position < 1 or position > total_items:
            await interaction.response.send_message(f"Position must be between 1 and {total_items}!", ephemeral=True)
            return

        current_pos = next(i for i, (name, _) in enumerate(items) if name == user)
        
        item = items.pop(current_pos)
        
        items.insert(position-1, item)
        
        new_data = dict(items)
        save_file(self.file_path, new_data)

        embed = discord.Embed(title="Opp List Updated", color=discord.Color.green())
        opp_list = "\n".join(f"{i+1}. {name}" for i, (name, _) in enumerate(items))
        embed.description = opp_list
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Quiz(bot))