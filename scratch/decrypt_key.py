import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint
from src.secret_storage import decrypt

db = SessionLocal()

nvidia_id = "nvidia-nemotron"
nvidia_ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == nvidia_id).first()

if nvidia_ep:
    raw_key = nvidia_ep.api_key
    try:
        # If it's already decrypted by SQLAlchemy because of process_result_value, it'll print here
        # or we might need raw decryption if fetched directly.
        # SQLAlchemy ModelEndpoint might decrypt automatically when we access the field.
        print("SQLAlchemy-fetched key:", raw_key)
    except Exception as e:
        print("Direct access failed:", e)
else:
    print("NVIDIA endpoint not found in database.")

db.close()
