import sqlite3
import os

db_path = os.path.abspath('data/app.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

for table in ['sessions', 'chat_messages']:
    print(f"Schema for {table}:")
    cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    print()

conn.close()
