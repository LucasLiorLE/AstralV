import discord
from discord.ext import commands
from discord import app_commands

from bot_utils import (
    handle_logs
)

class StringCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group()
    async def string(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")

    @string.command(name="reverse")
    async def reverse(self, ctx: commands.Context, *, text: str):
        await ctx.send(text[::-1])

    @string.command(name="upper")
    async def upper(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.upper())

    @string.command(name="lower")
    async def lower(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.lower())

    @string.command(name="title")
    async def title(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.title())

    @string.command(name="swapcase")
    async def swapcase(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.swapcase())

    @string.command(name="char")
    async def char(self, ctx: commands.Context, numbers: str):
        try:
            chars = [chr(int(num)) for num in numbers.split()]
            await ctx.send("".join(chars))
        except ValueError:
            await ctx.send("Invalid input. Please provide space-separated numbers.")

    @string.command(name="length")
    async def length(self, ctx: commands.Context, *, text: str):
        await ctx.send(len(text))

    @string.command(name="replace")
    async def replace(self, ctx: commands.Context, text: str, old: str, new: str):
        await ctx.send(text.replace(old, new))

    @string.command(name="split")
    async def split(self, ctx: commands.Context, text: str, sep: str = " "):
        await ctx.send(text.split(sep))

    @string.command(name="ascii")
    async def ascii(self, ctx: commands.Context, *, text: str):
        await ctx.send(" ".join(str(ord(char)) for char in text))

    @string.command(name="binary")
    async def binary(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "08b") for char in text))

    @string.command(name="hex")
    async def hex(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "02x") for char in text))

    @string.command(name="octal")
    async def octal(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "03o") for char in text))

    @string.command(name="encode")
    @app_commands.choices(
        encoding = [
            app_commands.Choice(name="utf-8", value="utf-8"),
            app_commands.Choice(name="utf-16", value="utf-16"),
            app_commands.Choice(name="utf-32", value="utf-32"),
            app_commands.Choice(name="ascii", value="ascii"),
            app_commands.Choice(name="latin-1", value="latin-1"),
            app_commands.Choice(name="cp037", value="cp037"),
            app_commands.Choice(name="cp424", value="cp424"),
            app_commands.Choice(name="cp437", value="cp437")
        ]
    )
    async def encode(self, ctx: commands.Context, text: str, encoding: str):
        try:
            await ctx.send(text.encode(encoding))
        except LookupError:
            await ctx.send("Invalid encoding.")

async def setup(bot):
    await bot.add_cog(StringCog(bot))