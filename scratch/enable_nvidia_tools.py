import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint

db = SessionLocal()

nvidia_id = "nvidia-nemotron"
nvidia_ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == nvidia_id).first()

if nvidia_ep:
    nvidia_ep.supports_tools = True
    db.commit()
    print("Successfully enabled native tool support (supports_tools = True) for NVIDIA endpoint.")
else:
    print("Error: nvidia-nemotron endpoint not found in database.")

db.close()
