from pathlib import Path
from db_connection import get_connection

SQL_FILE = Path(__file__).parent / "create_tables.sql"


def run():
    script = SQL_FILE.read_text(encoding="utf-8")
    with get_connection() as conn:
        cursor = conn.cursor()
        for statement in script.split(";\n\n"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        conn.commit()
    print("Tabelas criadas/verificadas com sucesso.")


if __name__ == "__main__":
    run()
