import sqlite3
import os
import sys

# Reconfigure stdout to handle UTF-8 properly
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

db_path = os.path.abspath('data/app.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- LAST 5 CHAT SESSIONS ---")
sessions = cur.execute("SELECT id, name, model, mode, created_at FROM sessions ORDER BY created_at DESC LIMIT 5").fetchall()
for s in sessions:
    print(dict(s))
    
    print("--- MESSAGES FOR THIS SESSION ---")
    messages = cur.execute("SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC", (s['id'],)).fetchall()
    for m in messages:
        content = m['content']
        if len(content) > 300:
            content = content[:300] + "... [TRUNCATED]"
        print(f"  [{m['role']}]: {content}")
    print()

conn.close()
