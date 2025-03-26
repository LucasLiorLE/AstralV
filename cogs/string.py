import discord
from discord.ext import commands
from discord import app_commands



class StringCommandGroup(commands.Group):
    def __init__():
        super().__init__(name="string", description="String manipulation commands")

    @commands.hybrid_command(name="reverse")
    async def reverse(self, ctx: commands.Context, *, text: str):
        await ctx.send(text[::-1])

    @commands.hybrid_command(name="upper")
    async def upper(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.upper())

    @commands.hybrid_command(name="lower")
    async def lower(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.lower())

    @commands.hybrid_command(name="title")
    async def title(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.title())

    @commands.hybrid_command(name="swapcase")
    async def swapcase(self, ctx: commands.Context, *, text: str):
        await ctx.send(text.swapcase())

    @commands.hybrid_command(name="char")
    async def char(self, ctx: commands.Context, *chars: str):
        await ctx.send("".join(chr(int(char)) for char in chars))

    @commands.hybrid_command(name="length")
    async def length(self, ctx: commands.Context, *, text: str):
        await ctx.send(len(text))

    @commands.hybrid_command(name="replace")
    async def replace(self, ctx: commands.Context, text: str, old: str, new: str):
        await ctx.send(text.replace(old, new))

    @commands.hybrid_command(name="split")
    async def split(self, ctx: commands.Context, text: str, sep: str = " "):
        await ctx.send(text.split(sep))

    @commands.hybrid_command(name="ascii")
    async def ascii(self, ctx: commands.Context, *, text: str):
        await ctx.send(" ".join(str(ord(char)) for char in text))

    @commands.hybrid_command(name="binary")
    async def binary(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "08b") for char in text))

    @commands.hybrid_command(name="hex")
    async def hex(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "02x") for char in text))

    @commands.hybrid_command(name="octal")
    async def octal(self, ctx: commands.Context, text: str):
        await ctx.send(" ".join(format(ord(char), "03o") for char in text))

    @commands.hybrid_command(name="encode")
    @app_commands.choices([
        app_commands.OptionChoice(name="utf-8", value="utf-8"),
        app_commands.OptionChoice(name="utf-16", value="utf-16"),
        app_commands.OptionChoice(name="utf-32", value="utf-32"),
        app_commands.OptionChoice(name="ascii", value="ascii"),
        app_commands.OptionChoice(name="latin-1", value="latin-1"),
        app_commands.OptionChoice(name="cp037", value="cp037"),
        app_commands.OptionChoice(name="cp424", value="cp424"),
        app_commands.OptionChoice(name="cp437", value="cp437")]
    )
    async def encode(self, ctx: commands.Context, text: str, encoding: str):
        try:
            await ctx.send(text.encode(encoding))
        except LookupError:
            await ctx.send("Invalid encoding.")