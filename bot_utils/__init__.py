from discord import Interaction, User, TextChannel, Role, Embed, Client
from typing import Optional, Tuple, Dict, Any, Union

from .file_handler import (
    open_file,
    save_file
)

from .logger import (
    store_log,
    handle_logs
)

from .utils import (
    parse_duration,
    check_user,
    convert_number,
    RestrictedView
)

from .game_apis import (
    get_player_data,
    get_clan_data,
    fetch_roblox_bio,
    GetRobloxID,
    getUUID
)

from .economy import (
    create_account,
    check_user_stat,
    process_transaction,
    gambling_stats,
    update_stats,
    eco_path
)

from .moderation import (
    dmbed,
    check_mod,
    store_modlog,
    send_modlog_embed
)

__all__ = [
    # File handling
    'open_file',
    'save_file',
    
    # Logging
    'store_log',
    'handle_logs',
    
    # Utility functions
    'parse_duration',
    'check_user',
    'convert_number',
    'check_user_stat',
    'RestrictedView',

    # Game APIs
    'get_player_data',
    'get_clan_data',
    'fetch_roblox_bio',
    'GetRobloxID',
    'getUUID',
    
    # Economy
    'create_account',
    'process_transaction',
    'gambling_stats', 
    'update_stats',
    'eco_path'
    
    # Moderation
    'dmbed',
    'check_mod',
    'store_modlog',
    'send_modlog_embed'
]

ModLogResult = Tuple[Optional[Embed], int, int]
ServerData = Dict[str, Any]
UserStats = Dict[str, Union[int, str, Dict[str, Any]]]

# Version info
__version__ = "2.0.7"
__author__ = "LucasLiorLE"
