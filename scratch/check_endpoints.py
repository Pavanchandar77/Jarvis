import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint

db = SessionLocal()
endpoints = db.query(ModelEndpoint).all()
print(f"Total endpoints: {len(endpoints)}")
for ep in endpoints:
    print(f"ID: {ep.id}, Name: {ep.name}, URL: {ep.base_url}, Enabled: {ep.is_enabled}, Cached: {ep.cached_models}, Pinned: {ep.pinned_models}")
db.close()
