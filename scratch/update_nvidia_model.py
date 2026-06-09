import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint
from src.settings import load_settings, save_settings
from src.constants import SETTINGS_FILE

# 1. Update Database ModelEndpoint pinned/cached models to include modern models
db = SessionLocal()

nvidia_id = "nvidia-nemotron"
nvidia_ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == nvidia_id).first()

if nvidia_ep:
    # Set pinned models to llama-3.1-nemotron-70b-instruct
    modern_model = "nvidia/llama-3.1-nemotron-70b-instruct"
    nvidia_ep.pinned_models = json.dumps([modern_model])
    db.commit()
    print("Successfully updated database ModelEndpoint pinned_models.")
else:
    print("Error: nvidia-nemotron endpoint not found in database.")

db.close()

# 2. Update settings.json to use the modern model
try:
    settings = load_settings()
except Exception as e:
    settings = {}

settings["default_chat_model"] = "nvidia/llama-3.1-nemotron-70b-instruct"
settings["default_model"] = "nvidia/llama-3.1-nemotron-70b-instruct"
settings["default_endpoint_id"] = nvidia_id

save_settings(settings)
print(f"Successfully configured default model to nvidia/llama-3.1-nemotron-70b-instruct in settings.json ({SETTINGS_FILE}).")
