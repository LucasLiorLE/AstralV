import os
from dotenv import load_dotenv
import mysql.connector
from pathlib import Path

def test_mysql_connection():
    # Load environment variables from secrets.env
    root_dir = Path(__file__).parent.parent
    secrets_path = root_dir / "storage" / "secrets.env"
    load_dotenv(secrets_path)

    # Connection configuration
    config = {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASS'),
        'database': os.getenv('DB_NAME')
    }

    try:
        # Attempt connection
        connection = mysql.connector.connect(**config)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            cursor = connection.cursor()
            
            # Get database info
            cursor.execute("SELECT DATABASE();")
            db_name = cursor.fetchone()[0]
            
            print("="*50)
            print(f"Connected to MySQL Server version {db_info}")
            print(f"Database name: {db_name}")
            print(f"Host: {config['host']}")
            print(f"User: {config['user']}")
            print("="*50)
            
            # Test creating a simple table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_connection (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    test_column VARCHAR(255)
                )
            """)
            print("Test table created successfully!")
            
    except mysql.connector.Error as e:
        print("="*50)
        print("Connection Error:")
        print(f"Error: {e}")
        print("="*50)
        
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")

if __name__ == "__main__":
    test_mysql_connection()