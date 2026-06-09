import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint
from src.settings import load_settings, save_settings

db = SessionLocal()

# Enable all endpoints
endpoints = db.query(ModelEndpoint).all()
for ep in endpoints:
    ep.is_enabled = True
    print(f"Enabled endpoint: {ep.name} (URL: {ep.base_url})")

# Check if local Ollama exists, if not create it
ollama_url = "http://127.0.0.1:11434/v1"
ollama_ep = db.query(ModelEndpoint).filter(ModelEndpoint.base_url == ollama_url).first()
if not ollama_ep:
    ollama_ep = ModelEndpoint(
        id="local-ollama",
        name="localhost:11434",
        base_url=ollama_url,
        is_enabled=True,
        model_type="llm"
    )
    db.add(ollama_ep)
    print("Added local Ollama endpoint.")
else:
    ollama_ep.is_enabled = True

db.commit()

# Print active endpoints
print("\n--- Active Endpoints ---")
for ep in db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True).all():
    print(f"ID: {ep.id}, Name: {ep.name}, URL: {ep.base_url}")

db.close()
