import json, os
from dotenv import load_dotenv
from pathlib import Path
from discord import app_commands
from typing import Dict, Any, TypeVar, Union, List
from typing_extensions import deprecated

"""
import mysql.connector 

root_dir = Path(__file__).parent.parent
secrets_path = root_dir / "storage" / "secrets.env"

if not secrets_path.exists():
    raise FileNotFoundError(f"secrets.env not found at {secrets_path}")

load_dotenv(secrets_path)

AstralV_DB = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database=os.getenv("DB_NAME")
)

cursor = AstralV_DB.cursor()
"""

T = TypeVar('T')
JsonData = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

@deprecated("Scheduled for removal in a future version. Use open_json() instead.")
def open_file(filename: str) -> Dict[str, Any]:
    """
    Opens and parses a JSON file.
    
    Parameters:
        filename (str): Path to the JSON file
        
    Returns:
        Dict(str, Any): Parsed JSON data as dictionary
    """
    with open(filename, "r") as f:
        file_data = json.load(f)
    return file_data

def open_json(filename: str) -> Dict[str, Any]:
    """
    Opens and parses a JSON file.
    
    Parameters:
        filename (str): Path to the JSON file
        
    Returns:
        Dict(str, Any): Parsed JSON data as dictionary
    """
    with open(filename, "r") as f:
        file_data = json.load(f)
    return file_data

@deprecated("Scheduled for removal in a future version. Use save_json() instead.")
def save_file(filename: str, data: JsonData) -> None:
    """
    Saves data to a JSON file with proper formatting.
    
    Parameters:
        filename (str): Path where to save the file
        data (JsonData): Data to be saved, must be JSON-serializable
        
    Raises:
        Exception: If file cannot be written or data cannot be serialized
    """
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)
    except Exception as e:
        raise Exception(f"Error: Could not save data to '{filename}'. {e}")

def save_json(filename: str, data: JsonData) -> None:
    """
    Saves data to a JSON file with proper formatting.
    
    Parameters:
        filename (str): Path where to save the file
        data (JsonData): Data to be saved, must be JSON-serializable
        
    Raises:
        Exception: If file cannot be written or data cannot be serialized
    """
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, default=lambda o: o.to_dict() if hasattr(o, "to_dict") else o)
    except Exception as e:
        raise Exception(f"Error: Could not save data to '{filename}'. {e}")

def load_commands(commands: Union[List[app_commands.Command], app_commands.Group], group: str) -> None:
    """
    Loads command descriptions and parameter help from command_help.json
    
    Parameters:
        commands (list): List of commands or a command Group
        group (str): Group name in command_help.json
    """
    command_help = open_file("storage/command_help.json").get(group, {})
    
    if isinstance(commands, app_commands.Group):
        group_data = command_help.get(commands.name, {})
        
        if group_data:
            if "description" in group_data:
                commands.description = group_data["description"]
            
            for cmd in commands.commands:
                if cmd.name in group_data:
                    cmd_data = group_data[cmd.name]
                    cmd.description = cmd_data.get("description", cmd.description)
                    
                    if "parameters" in cmd_data:
                        for param_name, param_desc in cmd_data["parameters"].items():
                            if param_name in cmd._params:
                                cmd._params[param_name].description = param_desc
        
        else:
            for cmd in commands.commands:
                if cmd.name in command_help:
                    cmd_data = command_help[cmd.name]
                    cmd.description = cmd_data.get("description", cmd.description)
                    
                    if "parameters" in cmd_data:
                        for param_name, param_desc in cmd_data["parameters"].items():
                            if param_name in cmd._params:
                                cmd._params[param_name].description = param_desc
    else:
        command_list = commands.commands if hasattr(commands, 'commands') else commands
        for command in command_list:
            if command.name in command_help:
                cmd_data = command_help[command.name]
                command.description = cmd_data.get("description", command.description)
                
                if "parameters" in cmd_data:
                    for param_name, param_desc in cmd_data["parameters"].items():
                        if param_name in command._params:
                            command._params[param_name].description = param_desc