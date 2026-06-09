import os

log_path = "jarvis.log"
if os.path.exists(log_path):
    print(f"Log file size: {os.path.getsize(log_path)} bytes")
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print("--- LAST 50 LINES OF JARVIS.LOG ---")
        for line in lines[-50:]:
            print(line.strip())
else:
    print("jarvis.log does not exist")
