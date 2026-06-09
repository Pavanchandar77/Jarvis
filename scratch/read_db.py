import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

keywords = ['model', 'endpoint', 'setting', 'api', 'config', 'key', 'pref']
for tname in tables:
    if any(x in tname.lower() for x in keywords):
        try:
            rows = cur.execute(f'SELECT * FROM "{tname}" LIMIT 10').fetchall()
            if rows:
                print(f'\n--- {tname} ---')
                for r in rows:
                    print(dict(r))
        except Exception as e:
            print(f'Error reading {tname}: {e}')

conn.close()
