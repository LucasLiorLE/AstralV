import json
from typing import Dict, Any, TypeVar, Union, List

T = TypeVar('T')
JsonData = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

def open_file(filename: str) -> Dict[str, Any]:
    """
    Opens and parses a JSON file.
    
    Parameters:
        filename (str): Path to the JSON file
        
    Returns:
        Dict[str, Any]: Parsed JSON data as dictionary
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    try:
        with open(filename, "r") as f:
            file_data = json.load(f)
        return file_data
    except FileNotFoundError:
        print(f"[ERROR]: The file '{filename}' was not found.")
        return {}
    except json.JSONDecodeError:
        print(f"[ERROR]: The file '{filename}' contains invalid JSON.")
        return {}

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