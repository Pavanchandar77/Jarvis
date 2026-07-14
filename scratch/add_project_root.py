import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.settings import load_settings, save_settings
from src.constants import SETTINGS_FILE

try:
    settings = load_settings()
except Exception as e:
    settings = {}

project_root = r"C:\Users\pavan\spark"
extra_roots = settings.get("tool_path_extra_roots", [])
if not isinstance(extra_roots, list):
    extra_roots = []

if project_root not in extra_roots:
    extra_roots.append(project_root)
    # Also add user home directory or user workspace folders if needed, but let's start with project root
    settings["tool_path_extra_roots"] = extra_roots
    save_settings(settings)
    print(f"Added {project_root} to tool_path_extra_roots in settings.json.")
else:
    print(f"{project_root} is already in tool_path_extra_roots.")
