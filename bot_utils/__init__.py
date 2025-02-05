from .economy import *
from .file_handler import *
from .game_apis import *
from .logger import *
from .moderation import *
from .utils import *

# Version info

VERSION = {
    'major': 2,
    'minor': 1,
    'patch': 3
}

__version__ = f"{VERSION['major']}.{VERSION['minor']}.{VERSION['patch']}"
__status__ = "Alpha"
__author__ = "LucasLiorLE"