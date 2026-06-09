import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint
from src.settings import load_settings, save_settings
from src.constants import SETTINGS_FILE

# 1. Update Database
db = SessionLocal()

# Disable other endpoints to make sure NVIDIA is used as the primary/active one
for ep in db.query(ModelEndpoint).all():
    ep.is_enabled = False

# Upsert NVIDIA endpoint
nvidia_id = "nvidia-nemotron"
nvidia_ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == nvidia_id).first()

if not nvidia_ep:
    nvidia_ep = ModelEndpoint(id=nvidia_id)
    db.add(nvidia_ep)

nvidia_ep.name = "NVIDIA Nemotron"
nvidia_ep.base_url = "https://integrate.api.nvidia.com/v1"
nvidia_ep.api_key = "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"
nvidia_ep.is_enabled = True
nvidia_ep.cached_models = json.dumps(["nvidia/nemotron-3-ultra-550b-a55b"])
nvidia_ep.pinned_models = json.dumps(["nvidia/nemotron-3-ultra-550b-a55b"])
nvidia_ep.model_type = "llm"
nvidia_ep.supports_tools = False

db.commit()
print("Successfully configured NVIDIA endpoint in the database.")

# Check the endpoints again
endpoints = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all()
for ep in endpoints:
    print(f"Active EP -> ID: {ep.id}, Name: {ep.name}, URL: {ep.base_url}, Enabled: {ep.is_enabled}")

db.close()

# 2. Update settings.json
try:
    settings = load_settings()
except Exception as e:
    settings = {}

settings["default_chat_model"] = "nvidia/nemotron-3-ultra-550b-a55b"
settings["default_model"] = "nvidia/nemotron-3-ultra-550b-a55b"
settings["default_endpoint_id"] = nvidia_id

save_settings(settings)
print(f"Successfully configured default model to nvidia/nemotron-3-ultra-550b-a55b in settings.json ({SETTINGS_FILE}).")
