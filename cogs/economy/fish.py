import discord
from discord import app_commands
from discord.ext import commands
import random
from bot_utils import (
    open_json, 
    save_json
)
from .utils import (
    display_item_name,
    check_user_stat
)

class FishingCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="fish", description="Economy fishing commands")
        self.eco_path = "storage/economy/economy.json"
        self.items = "storage/economy/items.json"

    class AllView(discord.ui.View):
        def __init__(self, page):
            super().__init__(timeout=None)
            self.page = page

        @discord.ui.button(label="Catch")
        async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ...

        @discord.ui.button(label="Upgrade")
        async def upgrade_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ...

        @discord.ui.button(label="Sell")
        async def sell_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ...

    async def fish(self, interaction: discord.Interaction, page: str):
        view = self.AllView(page)
        await interaction.response.send_message(view=view)

    @app_commands.command(name="shop")
    async def fish_shop(self, interaction: discord.Interaction):
        await self.fish(interaction, "shop")

    @app_commands.command(name="catch")
    async def fish_catch(self, interaction: discord.Interaction):
        await self.fish(interaction, "catch")

    @app_commands.command(name="sell")
    async def fish_sell(self, interaction: discord.Interaction):
        await self.fish(interaction, "sell")

    @app_commands.command(name="leaderboard")
    async def fish_leaderboard(self, interaction: discord.Interaction):
        await self.fish(interaction, "leaderboard")

class FishingCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fishing = FishingCommands()
        self.bot.tree.add_command(self.fishing)

async def setup(bot):
    await bot.add_cog(FishingCommandCog(bot))