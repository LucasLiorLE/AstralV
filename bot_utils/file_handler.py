import json
from discord import app_commands
from typing import Dict, Any, TypeVar, Union, List
from typing_extensions import deprecated

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
        command_list = [commands]
    else:
        command_list = commands.commands if hasattr(commands, 'commands') else commands
    
    for command in command_list:
        if command.name in command_help:
            cmd_data = command_help[command.name]
            command.description = cmd_data.get("description", command.description)
            
            if "parameters" in cmd_data:
                param_count = 0
                for param_name, param_desc in cmd_data["parameters"].items():
                    if param_name in command._params:
                        command._params[param_name].description = param_desc
                        param_count += 1
            
            if "subcommands" in cmd_data:
                subcmd_data = cmd_data["subcommands"]
                if isinstance(command, app_commands.Group):
                    for subcmd in command.walk_commands():
                        if subcmd.name in subcmd_data:
                            subcmd_info = subcmd_data[subcmd.name]
                            subcmd.description = subcmd_info.get("description", subcmd.description)
                            
                            if "parameters" in subcmd_info:
                                sub_param_count = 0
                                for param_name, param_desc in subcmd_info["parameters"].items():
                                    if param_name in subcmd._params:
                                        subcmd._params[param_name].description = param_desc
                                        sub_param_count += 1
                        else:
                            pass

                elif hasattr(command, "children"):
                    for subcmd_name, subcmd_info in subcmd_data.items():
                        if subcmd_name in command.children:
                            subcmd = command.children[subcmd_name]
                            subcmd.description = subcmd_info.get("description", subcmd.description)
                            
                            if "parameters" in subcmd_info:
                                sub_param_count = 0
                                for param_name, param_desc in subcmd_info["parameters"].items():
                                    if param_name in subcmd._params:
                                        subcmd._params[param_name].description = param_desc
                                        sub_param_count += 1
        else:
            print(f"[ERROR]: No help data found for command: {command.name}")