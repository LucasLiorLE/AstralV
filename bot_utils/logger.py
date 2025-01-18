import time
import discord
import traceback
from typing import Dict, List, Any

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
    print(f"[{log_type}] {message}")

    current_id = log_id_counter
    log_id_counter += 1

    return current_id

async def handle_logs(
        interaction: discord.Interaction, 
        error: Exception, 
        log_type: str = "error"
    ) -> None:
    """
    Processes and stores error logs while notifying users.
    
    Parameters:
        interaction (discord.Interaction): The interaction context
        error (Exception): The error to be logged
        log_type (str): Category of log, defaults to "error"
        
    Notes:
        - Sends an ephemeral message to the user with error details
        - Stores full traceback in logs for debugging
        - Prints log ID for reference
    """
    global log_id_counter
    log_type = log_type.title()

    if log_type == "Error" and isinstance(error, Exception):
        embed = discord.Embed(title="An error occurred", color=discord.Color.red())
        embed.add_field(name="Error", value=str(error), inline=False)
        embed.add_field(name="ID", value=log_id_counter)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

        full_error = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        log_id = store_log(log_type, full_error)
        print(f"Logged error with ID: {log_id}")
    else:
        log_id = store_log(log_type, str(error))
        print(f"Logged '{log_type}' with ID: {log_id}")