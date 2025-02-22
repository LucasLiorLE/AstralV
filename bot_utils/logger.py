import time
import discord
import traceback
from typing import Dict, List, Any, Union
from discord.ext import commands

LogEntry = Dict[str, Any]
LogStore = Dict[str, List[LogEntry]]

logs: LogStore = {}
log_id_counter: int = 1

def store_log(log_type: str, message: str) -> int:
    """
    Stores a log entry and returns its ID.
    
    Parameters:
        log_type (str): Category of the log entry (e.g., "error", "warning", "info")
        message (str): Content of the log message
        
    Returns:
        int: Unique identifier for the stored log entry
        
    Raises:
        ValueError: If message is not a string
    """
    global log_id_counter

    log_type = log_type.title()

    if log_type not in logs:
        logs[log_type] = []

    if not isinstance(message, str):
        raise ValueError("Message must be a string.")

    log_entry = {
        "Message": message,
        "ID": log_id_counter,
        "Time": int(time.time()),
    }

    logs[log_type].append(log_entry)
    print(f"[{log_type}]: {message}")

    current_id = log_id_counter
    log_id_counter += 1

    return current_id

def warn(
        *values: object,
    ) -> None:
    """
    Prints a warning message to the console.
    
    Parameters:
        *values (object): The values to be printed
    """
    print("[WARNING]", *values)

def debug(
        *values: object,
    ) -> None:
    """
    Prints a debug message to the console.
    
    Parameters:
        *values (object): The values to be printed
    """
    print("[DEBUG]", *values)

def error(
        *values: object,
    ) -> None:
    """
    Prints an error message to the console.
    
    Parameters:
        *values (object): The values to be printed
    """
    print("[ERROR]", *values)
    
async def handle_logs(
        ctx_or_interaction: Union[discord.Interaction, commands.Context], 
        error: Exception, 
        log_type: str = "error"
    ) -> None:
    """
    Processes and stores error logs while notifying users.
    
    Parameters:
        ctx_or_interaction (Union[discord.Interaction, commands.Context]): The interaction or context
        error (Exception): The error to be logged
        log_type (str): Category of log, defaults to "error"
    """
    global log_id_counter
    log_type = log_type.title()

    if log_type == "Error" and isinstance(error, Exception):
        embed = discord.Embed(title=f"An error occurred ({log_id_counter})", color=discord.Color.red())
        embed.add_field(name="Error", value=str(error), inline=False)

        if isinstance(ctx_or_interaction, discord.Interaction):
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx_or_interaction.send(embed=embed)

        full_error = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        log_id = store_log(log_type, full_error)
        print(f"Logged error with ID: {log_id}")
    else:
        log_id = store_log(log_type, str(error))
        print(f"Logged '{log_type}' with ID: {log_id}")