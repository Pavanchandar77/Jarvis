import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.settings import load_settings, save_settings
from src.constants import SETTINGS_FILE

# Set the default model to llama-3.1-70b-instruct which we verified is working
try:
    settings = load_settings()
except Exception as e:
    settings = {}

settings["default_chat_model"] = "meta/llama-3.1-70b-instruct"
settings["default_model"] = "meta/llama-3.1-70b-instruct"
settings["default_endpoint_id"] = "nvidia-nemotron"

save_settings(settings)
print(f"Final default model set to meta/llama-3.1-70b-instruct in settings.json ({SETTINGS_FILE}).")
