import discord
import re

from datetime import timedelta
from typing import Optional, TypeVar, Generic

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parses a duration string in the format 'XdYhZmWs' into a timedelta object.

    Parameters:
    - duration_str (str): The duration string to parse, where:
      - 'd' represents days,
      - 'h' represents hours,
      - 'm' represents minutes,
      - 's' represents seconds.

    Returns:
    - Optional[timedelta]: A `timedelta` object representing the total duration if the format is valid, otherwise `None`.

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
    - interaction (discord.Interaction): The interaction object triggered by the user.
    - original_user (discord.User): The user who is allowed to interact.

    Returns:
    - bool: True if the interaction user matches the original user, otherwise False.
    """
    return interaction.user.id == original_user.id


def convert_number(number: str) -> int:
    """
    Converts shorthand notations like 50m, 1b, 10k to full numbers.
    Ex. 
    50m -> 50000000
    1b -> 1000000000
    10k -> 10000

    Args:
        number (str): The shorthand number as a string.

    Returns:
        int: The full numeric value.
    """
    suffixes = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000, 't': 1_000_000_000_000}
    if not number:
        raise ValueError("No number provided.")

    number = number.lower().strip()
    if number[-1] in suffixes:
        multiplier = suffixes[number[-1]]
        return int(float(number[:-1]) * multiplier)
    return int(number)

T = TypeVar('T')  # Generic type for RestrictedView

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
