import json, os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, TypeVar, Union, List
from typing_extensions import deprecated

import mysql.connector

class DB:
    def __init__(self, env_file: str = "storage/secrets.env"):
        """
        Initializes the DB class and loads credentials from a .env file.
        """
        root_dir = Path(__file__).parent.parent
        secrets_path = root_dir / env_file

        if not secrets_path.exists():
            raise FileNotFoundError(f"secrets.env not found at {secrets_path}")

        load_dotenv(secrets_path)

        self.db_host = os.getenv("DB_HOST")
        self.db_user = os.getenv("DB_USER")
        self.db_pass = os.getenv("DB_PASS")
        self.db_name = os.getenv("DB_NAME")

        if not all([self.db_host, self.db_user, self.db_pass, self.db_name]):
            raise ValueError("Missing one or more database credentials in the .env file")

    def get_db_connection(self):
        """Establishes and returns a connection to the MySQL database."""
        return mysql.connector.connect(
            host=self.db_host,
            user=self.db_user,
            password=self.db_pass,
            database=self.db_name
        )

    def query_db(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Executes a SELECT query and returns the results as a list of dictionaries.
        
        Parameters:
            query (str): SQL query to execute
            params (tuple): Parameters to pass into the query (default is empty)
            
        Returns:
            List[Dict[str, Any]]: List of results, each represented as a dictionary
        """
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return []
        finally:
            cursor.close()
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> int:
        """
        Executes an INSERT, UPDATE, or DELETE query.
        
        Parameters:
            query (str): SQL query to execute
            params (tuple): Parameters to pass into the query (default is empty)
            
        Returns:
            int: The number of rows affected by the query
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()

    def fetch_one(self, query: str, params: tuple = ()) -> Dict[str, Any]:
        """
        Fetch a single result from the database.
        
        Parameters:
            query (str): SQL query to execute
            params (tuple): Parameters to pass into the query (default is empty)
            
        Returns:
            Dict[str, Any]: Single row result as a dictionary
        """
        results = self.query_db(query, params)
        return results[0] if results else {}

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Fetch all results from the database.
        
        Parameters:
            query (str): SQL query to execute
            params (tuple): Parameters to pass into the query (default is empty)
            
        Returns:
            List[Dict[str, Any]]: All results as a list of dictionaries
        """
        return self.query_db(query, params)

    def insert_record(self, query: str, params: tuple = ()) -> int:
        """
        Insert a new record into the database and return the last inserted ID.
        
        Parameters:
            query (str): SQL insert query
            params (tuple): Parameters for the query
            
        Returns:
            int: The ID of the last inserted record
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()

T = TypeVar('T')
JsonData = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

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