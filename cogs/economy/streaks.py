import discord
from datetime import datetime, timezone, timedelta
from discord import app_commands
from discord.ext import commands
from bot_utils import (
    open_json, 
    save_json,
    handle_logs
)
from .utils import (
    check_user_stat
)

class StreaksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def update_streak(self, streak: str, user_id: str):
        check_user_stat(["streaks"], user_id)
        current_streak = check_user_stat(["streaks", streak, "streak"], user_id, 0)
        last_claimed = check_user_stat(["streaks", streak, "last_claimed"], user_id, "2000-01-01 00:00:00.000000+00:00")
        
        now = datetime.now(timezone.utc)
        last_claimed = datetime.fromisoformat(last_claimed)
        since_last_claimed = now - last_claimed

        days = since_last_claimed.days
        eco = open_json("storage/economy/economy.json")
        next_streak = int(datetime.timestamp(
                    last_claimed + timedelta(days=1) if streak == "daily"
                    else last_claimed + timedelta(days=7) if streak == "weekly"
                    else last_claimed + timedelta(days=30)
                ))
        
        if (streak == "daily" and (days < 1) or \
            streak == "weekly" and (days < 7) or \
            streak == "monthly" and (days < 30)):
            return None, None, next_streak

        if (streak == "daily" and (days > 2) or \
            streak == "weekly" and (days > 8) or \
            streak == "monthly" and (days > 32)):
            eco[user_id]["streaks"][streak]["streak"] = 0
            current_streak = 0

        if streak == "daily": 
            amount = 5000 * ((current_streak * 0.05) + 1)

        if streak == "weekly": 
            amount = 40000 * ((current_streak * 0.1) + 1)

        if streak == "monthly": 
            amount = 200000 * ((current_streak * 0.16) + 1)

        check_user_stat(["balance", "purse"], user_id, 0)
        check_user_stat(["balance", "bank"], user_id, 5000)
        check_user_stat(["balance", "maxBank"], user_id, 25000)
        eco = open_json("storage/economy/economy.json")

        eco[user_id]["balance"]["purse"] += int(amount)
        eco[user_id]["streaks"][streak]["streak"] += 1
        eco[user_id]["streaks"][streak]["last_claimed"] = now.isoformat()
        save_json("storage/economy/economy.json", eco)

        return amount, current_streak, next_streak

    @commands.hybrid_command(name="daily")
    async def daily(self, ctx: commands.Context):
        try:
            amount, current, next_streak = self.update_streak("daily", str(ctx.author.id))
            if not amount or current:
                return await ctx.send(f"You already claimed your daily reward. Please try again after <t:{next_streak}:F>")

            embed = discord.Embed(
                title="Daily Reward",
                description=f"Amount: {amount}",
                color=discord.Color.green(),
                timestamp=datetime.fromtimestamp(next_streak)
            )

            await ctx.send(embed=embed)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="weekly")
    async def weekly(self, ctx: commands.Context):
        try:
            amount, current, next_streak = self.update_streak("weekly", str(ctx.author.id))
            if not amount or current:
                return await ctx.send(f"You already claimed your weekly reward. Please try again after <t:{next_streak}:F>")

            embed = discord.Embed(
                title="Weekly Reward",
                description=f"Amount: {amount}",
                color=discord.Color.green(),
                timestamp=datetime.fromtimestamp(next_streak)
            )

            await ctx.send(embed=embed)
        except Exception as e:
            await handle_logs(ctx, e)

    @commands.hybrid_command(name="monthly")
    async def monthly(self, ctx: commands.Context):
        try:
            amount, current, next_streak = self.update_streak("monthly", str(ctx.author.id))
            if not amount or current:
                return await ctx.send(f"You already claimed your monthly reward. Please try again after <t:{next_streak}:F>")

            embed = discord.Embed(
                title="Monthly Reward",
                description=f"Amount: {amount}",
                color=discord.Color.green(),
                timestamp=datetime.fromtimestamp(next_streak)
            )

            await ctx.send(embed=embed)
        except Exception as e:
            await handle_logs(ctx, e)

async def setup(bot):
    await bot.add_cog(StreaksCog(bot))