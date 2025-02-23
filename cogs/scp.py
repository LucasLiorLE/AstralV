import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import random

class QuizView(View):
    def __init__(self, correct_answer, num1, num2):
        super().__init__(timeout=60.0)
        self.correct_answer = correct_answer
        self.used = []
        self.question = f"What is {num1} + {num2}?"

    async def handle_click(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in self.used:
            await interaction.response.send_message("You have already answered this question.", ephemeral=True)
            return
        
        self.used.append(user_id)

        if button.label == str(self.correct_answer):
            embed = discord.Embed(
                title="Trivia Question Answered",
                description=self.question,
                color=discord.Color.green()
            )
            embed.add_field(name="Reward", value="air")
            embed.add_field(name="Answer", value=f"{self.correct_answer}", inline=False)
            embed.add_field(name="Winner", value=interaction.user.mention, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Aiko sucks", ephemeral=True)

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quiz", description="pls work holger")
    async def quiz(self, interaction: discord.Interaction):
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        correct_answer = num1 + num2
        
        wrong_answers = []
        while len(wrong_answers) < 3:
            wrong = random.randint(1, 50)
            if wrong != correct_answer and wrong not in wrong_answers:
                wrong_answers.append(wrong)

        embed = discord.Embed(title="Trivia Question", color=discord.Color.green())
        embed.add_field(name="Question", value=f"What is {num1} + {num2}?", inline=False)
        embed.add_field(name="Reward", value="14 Social Credit Points", inline=False)
        embed.add_field(name="Time to answer", value="60.0 seconds", inline=False)

        view = QuizView(correct_answer, num1, num2)
        
        options = [correct_answer] + wrong_answers
        random.shuffle(options)
        
        for i, option in enumerate(options, 1):
            button = Button(label=str(option), style=discord.ButtonStyle.primary, custom_id=f"option_{i}")
            button.callback = lambda i=interaction, b=button: view.handle_click(i, b)
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Quiz(bot))