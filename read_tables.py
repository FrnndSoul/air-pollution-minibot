# read_tables.py
import sqlite3
from pathlib import Path

DB_PATH = Path("resources/sensor.db")


def main():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]

    print("\n=== Tables Found ===")
    for t in tables:
        print(" -", t)

    print("\n=== Row Counts ===")
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"{table}: {count} rows")
        except Exception as e:
            print(f"{table}: ERROR -> {e}")

    conn.close()


if __name__ == "__main__":
    main()
