import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.action_intents import classify_tool_intent

queries = [
    "List files in the current repository and show the git status.",
    "run git status please",
    "git diff app.py",
    "read main.js",
    "edit routes/chat_routes.py",
    "what does git status do?", # explanatory, should not escalate
    "hello how are you" # normal chat, should not escalate
]

for q in queries:
    res = classify_tool_intent(q)
    print(f"Query: '{q}'")
    print(f"  needs_tools: {res.needs_tools}, category: {res.category}, reason: {res.reason}")
    print()
