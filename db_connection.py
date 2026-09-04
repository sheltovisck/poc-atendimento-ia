import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

SERVER = os.environ["AZURE_SQL_SERVER"]
DATABASE = os.environ["AZURE_SQL_DATABASE"]
USER = os.environ["AZURE_SQL_USER"]
PASSWORD = os.environ["AZURE_SQL_PASSWORD"]

DRIVER = "{ODBC Driver 18 for SQL Server}"

CONN_STRING = (
    f"DRIVER={DRIVER};"
    f"SERVER=tcp:{SERVER},1433;"
    f"DATABASE={DATABASE};"
    f"UID={USER};"
    f"PWD={PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)


def get_connection():
    return pyodbc.connect(CONN_STRING)


if __name__ == "__main__":
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        print(cursor.fetchone()[0])
