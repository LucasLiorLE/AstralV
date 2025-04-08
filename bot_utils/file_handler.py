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
    try:
        with open(filename, "r", encoding="utf-8") as f:
            file_data = json.load(f)
        return file_data
    except Exception as e:
        print(e)
        return None

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