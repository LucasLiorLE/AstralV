from .file_handler import (
    open_json,
    save_json
)

import discord
from discord import app_commands
from discord.ext import commands
import re, io, time
import asyncio

from datetime import timedelta
from typing import Optional, TypeVar, Generic, Union, Dict, Any, Tuple, List
from aiohttp import ClientSession
from PIL import Image

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parses a duration string in the format 'XdYhZmWs' into a timedelta object.

    Parameters:
        duration_str (str): The duration string to parse, where:
            'd' represents days,
            'h' represents hours,
            'm' represents minutes,
            's' represents seconds.

    Returns:
        Optional[timedelta]: A `timedelta` object representing the total duration if the format is valid, otherwise `None`.

    Example:
        ```
        parse_duration("1d2h30m15s") # Output: timedelta(days=1, hours=2, minutes=30, seconds=15)
        ```
    """
    duration_regex = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = duration_regex.match(duration_str)

    if not match:
        return None

    days, hours, minutes, seconds = match.groups()
    total_duration = timedelta()

    if days:
        total_duration += timedelta(days=int(days))
    if hours:
        total_duration += timedelta(hours=int(hours))
    if minutes:
        total_duration += timedelta(minutes=int(minutes))
    if seconds:
        total_duration += timedelta(seconds=int(seconds))

    return total_duration

def check_user(interaction: discord.Interaction, original_user: discord.User) -> bool:
    """
    Checks if the interaction is performed by the original user.

    Parameters:
        interaction (discord.Interaction): The interaction object triggered by the user.
        original_user (discord.User): The user who is allowed to interact.

    Returns:
        bool: True if the interaction user matches the original user, otherwise False.

    Examples:
        ```
        @app_commands.command(name="test")
        async def test(interaction: discord.Interaction):
            view = discord.ui.View()

            view.add_item(discord.ui.Button(label="Test", style=discord.ButtonStyle.primary))

            @view.item(label="Test", style=discord.ButtonStyle.primary)
            async def test_button(interaction: discord.Interaction):
                if check_user(interaction, original_user):
                    await interaction.response.send_message("You are allowed to interact with this command.")
                else:
                    await interaction.response.send_message("You are not allowed to interact with this command.")

            await interaction.response.send_message("You are allowed to interact with this command.", view=view)
        ```
    """
    return interaction.user.id == original_user.id


def convert_number(number: str) -> int:
    """
    Converts shorthand notations like 50m, 1b, 10k to full numbers.

    Args:
        number (str): The shorthand number as a string.

    Returns:
        int: The full numeric value.

    Example:
        ```
        convert_number("50m") # Output: 50000000
        convert_number("1b") # Output: 1000000000
        convert_number("10k") # Output: 10000
        ```
    """
    suffixes = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000, 't': 1_000_000_000_000}
    if not number:
        raise ValueError("No number provided.")

    number = number.lower().strip()
    if number[-1] in suffixes:
        multiplier = suffixes[number[-1]]
        return int(float(number[:-1]) * multiplier)
    return int(number)

T = TypeVar('T')

class RestrictedView(discord.ui.View, Generic[T]):
    """
    A custom Discord UI View that restricts interactions to a specific user.
    
    Type Parameters:
        T: The type of data this view handles
    
    Attributes:
        original_user (discord.User): The user allowed to interact with this view
        data (T): Optional data associated with this view
    """
    def __init__(self, user: discord.User, timeout: float = 180, data: Optional[T] = None):
        super().__init__(timeout=timeout)
        self.original_user: discord.User = user
        self.data: Optional[T] = data

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verifies if the interaction user matches the original user."""
        return check_user(interaction, self.original_user)

async def create_interaction(ctx):
    """Creates a pseudo-interaction from a command context.

    This function simulates a Discord interaction using the provided command context.
    It creates a pseudo-interaction object that mimics the behavior of a real interaction,
    allowing for deferred responses and follow-up messages.

    Args:
        ctx: The command context from which to create the pseudo-interaction.

    Returns:
        PseudoInteraction: An object that simulates a Discord interaction.

    Example:
        ```
        @commands.command(name="test")
        async def test(interaction: discord.Interaction):
            interaction = await create_interaction(interaction)
        ```
    """
    async with ctx.typing():
        class Response:
            def __init__(self, ctx):
                self.ctx = ctx
                self._deferred = False
                self._responded = False

            async def defer(self, ephemeral=False):
                """Marks the interaction as deferred.

                Args:
                    ephemeral (bool): Whether the deferred response should be ephemeral (default is False).
                """
                self._deferred = True

            async def send_message(self, *args, **kwargs):
                """Sends a message in response to the interaction.

                Args:
                    *args: Positional arguments to pass to the send method.
                    **kwargs: Keyword arguments to pass to the send method.

                Returns:
                    The message that was sent.
                """
                self._responded = True
                return await self.ctx.send(*args, **kwargs)

            def is_done(self):
                """Checks if the interaction has been deferred.

                Returns:
                    bool: True if the interaction has been deferred, otherwise False.
                """
                return self._deferred

        class Followup:
            def __init__(self, ctx):
                self.ctx = ctx
                self._last_message = None

            async def send(self, content=None, **kwargs):
                """Sends a follow-up message, deleting the previous one if it exists.

                Args:
                    content: The content of the follow-up message.
                    **kwargs: Additional keyword arguments to pass to the send method.

                Returns:
                    The follow-up message that was sent.
                """
                if self._last_message:
                    try:
                        await self._last_message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass

                if isinstance(content, discord.Embed):
                    self._last_message = await self.ctx.send(embed=content, **kwargs)
                else:
                    self._last_message = await self.ctx.send(content, **kwargs)
                
                return self._last_message
            
        class PseudoInteraction:
            def __init__(self, ctx):
                self.user = ctx.author
                self.author = ctx.author
                self.guild = ctx.guild
                self.guild_id = ctx.guild.id
                self.channel = ctx.channel
                self.response = Response(ctx)
                self.followup = Followup(ctx)
                self.message = ctx.message

        return PseudoInteraction(ctx)

def get_member_color(interaction: discord.Interaction, color: str = None) -> discord.Color:
    """Retrieves the color of the member's highest role in the guild.

    Args:
        interaction (discord.Interaction): The interaction object containing user and guild information.
        color (str): The default color to return if the member is not found or the color is None.

    Returns:
        discord.Color: The color of the member's highest role.
                      Returns 0xDA8EE7 if the member is not found or the color is None.

    Examples:
        ```
        @app_commands.command(name="test")
        async def test(interaction: discord.Interaction):
            color = get_member_color(interaction)
            await interaction.response.send_message(f"The color of the member's highest role is {color}.")
        ```
    """
    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            return member.top_role.color
    return 0xDA8EE7 if color is None else color

async def _process_image(image: Image.Image) -> int:
    """
    Helper function to process image and get dominant color.
    """
    image = image.resize((50, 50))
    if image.mode != 'RGB':
        image = image.convert('RGB')
    pixels = image.getcolors(2500)

    if not pixels:
        return 0x808080
    sorted_pixels = sorted(pixels, key=lambda x: x[0], reverse=True)
    dominant_color = sorted_pixels[0][1]
    return int('%02x%02x%02x' % dominant_color, 16)

async def get_dominant_color(url: str = None, buffer: io.BytesIO = None, timeout: int = 5) -> discord.Color:
    """
    Retrieves the dominant color from an image with timeout handling.

    Parameters:
        url (str): The URL of the image to analyze.
        buffer (io.BytesIO): A buffer containing the image data.
        timeout (int): The amount of time to attempt to process the color.

    Returns:
        discord.Color: The dominant color in the image as a Discord color object.
                      Returns 0x808080 (gray) if processing fails or times out.

    Example:
        ```
        @app_commands.command(name="test")
        async def test(interaction: discord.Interaction):
            color = get_dominant_color(url="https://example.com/image.png")
            await interaction.response.send_message(f"The dominant color in the image is {color}.")
        ```
    """
    try:
        async def process():
            if buffer:
                image = Image.open(buffer)
            else:
                async with ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            return 0x808080
                        image_data = await response.read()
                        image = Image.open(io.BytesIO(image_data))
            
            return await _process_image(image)

        return await asyncio.wait_for(process(), timeout=timeout)
    except (asyncio.TimeoutError, Exception):
        return 0x808080

def get_member_cooldown(user_id: discord.User, command: str = None, exp: bool = False) -> int:
    """
    Retrieves the time elapsed since the last command usage/message sent for a specific user.

    Parameters:
        user_id (discord.User): The user to check the cooldown for.
        command (str): The name of the command to check.
        exp (bool): Whether or not you want to check the exp cooldown.

    Returns:
        int: The number of seconds elapsed since the last command usage/message sent.

             Returns 0 if the command has never been used.

    Example:
        ```
        @app_commands.command(name="test")
        async def test(interaction: discord.Interaction):
            cooldown = get_member_cooldown(interaction.user, "test")
            await interaction.response.send_message(f"The cooldown for the command is {cooldown} seconds.")
        ```
    """

    current_time = int(time.time())
    user_id = str(user_id)
    
    member_info = open_json("storage/member_info.json")


    user_data = member_info.setdefault(user_id, {})
    if exp:
        user_exp = user_data.setdefault("EXP", {})
        exp_cooldown = user_exp.setdefault("cooldown", 0)
        save_json("storage/member_info.json", member_info)

        return current_time - exp_cooldown
    
    if command:
        commands = user_data.setdefault("commands", {})
        command_data = commands.setdefault(command, {"cooldown": 0})
        save_json("storage/member_info.json", member_info)
        
        return current_time - command_data["cooldown"]

def check_command_cooldown(user_id: str, command_name: str, cooldown_seconds: int) -> Tuple[bool, int]:
    """
    Checks if a command is on cooldown.

    Args:
        user_id (str): The ID of the user to check the cooldown for.
        command_name (str): The name of the command to check the cooldown for.
        cooldown_seconds (int): The cooldown time in seconds.   

    Returns:
        Tuple[bool, int]: A tuple containing a boolean indicating if the command is on cooldown and the remaining time in seconds.

    Example:
        ```
        @app_commands.command(name="test")
        async def test(interaction: discord.Interaction):
            is_on_cooldown, remaining_time = check_command_cooldown(interaction.user.id, "test", 10)
        ```
    """
    member_info = open_json("storage/member_info.json")
    current_time = int(time.time())
    
    if str(user_id) not in member_info:
        member_info[str(user_id)] = {"commands": {}}
    
    user_data = member_info[str(user_id)]
    if "commands" not in user_data:
        user_data["commands"] = {}
        
    cmd_data = user_data["commands"].get(command_name, {"uses": 0, "cooldown": 0})
    
    if current_time - cmd_data["cooldown"] < cooldown_seconds:
        remaining = cooldown_seconds - (current_time - cmd_data["cooldown"])
        return True, remaining
        
    return False, 0

def update_command_cooldown(user_id: str, command_name: str):
    """Update the command cooldown timestamp"""
    member_info = open_json("storage/member_info.json")
    current_time = int(time.time())
    
    if str(user_id) not in member_info:
        member_info[str(user_id)] = {"commands": {}}
    
    user_data = member_info[str(user_id)]
    if "commands" not in user_data:
        user_data["commands"] = {}
        
    if command_name not in user_data["commands"]:
        user_data["commands"][command_name] = {"uses": 0, "cooldown": 0}
        
    user_data["commands"][command_name]["uses"] += 1
    user_data["commands"][command_name]["cooldown"] = current_time
    
    save_json("storage/member_info.json", member_info)
    
async def get_command_help_embed(command_name: str) -> discord.Embed:
    command_help = open_json("storage/command_help.json")

    command_data = command_help.get("moderation", {}).get(command_name)
    if not command_data:
        return None

    embed = discord.Embed(
        title=f"Command: {command_name}",
        description=command_data.get("description", "No description available."),
        color=discord.Color.blue()
    )

    if "parameters" in command_data:
        parameters = []
        for param_name, param_desc in command_data["parameters"].items():
            parameters.append(f"• **{param_name}**: {param_desc}")
        
        if parameters:
            embed.add_field(
                name="Parameters",
                value="\n".join(parameters),
                inline=False
            )

    return embed

def get_role_hierarchy(main: discord.Member, check: discord.Member | discord.Role):
    if isinstance(check, discord.Member):
        return main.top_role.position > check.top_role.position
    else:
        return main.top_role.position > check.position
    
async def get_member(ctx: commands.Context, member_str: str) -> discord.Member | None:
	"""Find a member by mention, username, nickname, or ID."""
	member_str = member_str.strip("<@!>")
	
	if member_str.isdigit():
		try:
			return await ctx.guild.fetch_member(int(member_str))
		except discord.NotFound:
			return None
	else:
		return discord.utils.get(ctx.guild.members, name=member_str) or \
			   discord.utils.get(ctx.guild.members, display_name=member_str)

async def get_channel(ctx: commands.Context, channel_str: str) -> discord.TextChannel | None:
    """Find a text channel by mention, name, or ID."""
    if channel_str == None: return None
    channel_str = channel_str.strip("<#>")
    
    if channel_str.isdigit():
        try:
            return await ctx.guild.fetch_channel(int(channel_str))
        
        except discord.NotFound:
            return None
        
    else:
        return discord.utils.get(ctx.guild.text_channels, name=channel_str) or \
               discord.utils.get(ctx.guild.text_channels, mention=channel_str)
    
async def get_role(ctx: commands.Context, role_str: str | discord.Role) -> discord.Role | None:
    """Find a role by mention, name, or ID."""
    if role_str == None: return None
    role_str = role_str.strip("<@&>")
    
    if role_str.isdigit():
        try:
            return ctx.guild.get_role(int(role_str))
        except discord.NotFound:
            return None
        
    else:
        return discord.utils.get(ctx.guild.roles, name=role_str) or \
               discord.utils.get(ctx.guild.roles, mention=role_str)
    
def get_context_object(ctx_or_interaction: Union[commands.Context, discord.Interaction]) -> Dict[str, Any]:
	"""Returns a dictionary with unified access to common attributes."""
	is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
	return {
		"interaction": ctx_or_interaction if is_interaction else None,
		"ctx": ctx_or_interaction if not is_interaction else None,
		"user": ctx_or_interaction.user if is_interaction else ctx_or_interaction.author,
		"guild": ctx_or_interaction.guild,
		"guild_id": ctx_or_interaction.guild.id,
		"send": ctx_or_interaction.followup.send if is_interaction else ctx_or_interaction.send
	}

async def autocomplete_choices(
        choices: list,
        interaction: discord.Interaction,
        current: str,
) -> List[app_commands.Choice[str]]:
    choices = [choice for choice in choices if current.lower() in choice.lower()]
    return [
        app_commands.Choice(name=choice, value=choice)
        for choice in choices[:25]
    ]

async def send_cooldown(ctx_or_interaction: Union[commands.Context, discord.Interaction], cooldown: int):
    embed = discord.Embed(
        title="Slow down there buddy!",
        description=f"This command is on cooldown, please try again <t:{cooldown}:R>",
        color=discord.Color.red()
    )
    
    if isinstance(ctx_or_interaction, discord.Interaction):
        if ctx_or_interaction.response.is_done():
            await ctx_or_interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await ctx_or_interaction.send(embed=embed)