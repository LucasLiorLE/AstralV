import discord
import re, io, json, time

from datetime import timedelta
from typing import Optional, TypeVar, Generic
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
        - Input: "1d2h30m15s"
        - Output: timedelta(days=1, hours=2, minutes=30, seconds=15)
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
        - 50m -> 50000000
        - 1b -> 1000000000
        - 10k -> 10000
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
    """
    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            return member.top_role.color
    return 0xDA8EE7 if color is None else color

async def get_dominant_color(url: str = None, buffer: io.BytesIO = None) -> discord.Color:
    """
    Retrieves the dominant color from an image.

    Parameters:
        url (str): The URL of the image to analyze.
        buffer (io.BytesIO): A buffer containing the image data.

    Returns:
        discord.Color: The dominant color in the image as a Discord color object.
    """
    try:
        if buffer:
            image = Image.open(buffer)
        else:
            async with ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return 0x808080
                    
                    image_data = await response.read()
                    image = Image.open(io.BytesIO(image_data))
        
        image = image.resize((50, 50))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        pixels = image.getcolors(2500)

        if not pixels:
            return 0x808080
        sorted_pixels = sorted(pixels, key=lambda x: x[0], reverse=True)
        dominant_color = sorted_pixels[0][1]
        return int('%02x%02x%02x' % dominant_color, 16)
    except:
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
    """

    def save_file():
        with open("storage/member_info.json", "w") as f:
            json.dump(member_info, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)

    current_time = int(time.time())
    user_id = str(user_id)
    
    try:
        with open("storage/member_info.json", "r") as f:
            member_info = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        member_info = {}

    user_data = member_info.setdefault(user_id, {})
    if exp:
        user_exp = user_data.setdefault("EXP", {})
        exp_cooldown = user_exp.setdefault("cooldown", 0)
        save_file()

        return current_time - exp_cooldown
    
    if command:
        commands = user_data.setdefault("commands", {})
        command_data = commands.setdefault(command, {"cooldown": 0})
        save_file()
        
        return current_time - command_data["cooldown"]
    
async def get_command_help_embed(command_name: str) -> discord.Embed:
    with open("storage/command_help.json", "r") as f:
        command_help = json.load(f)
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