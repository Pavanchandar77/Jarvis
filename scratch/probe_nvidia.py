import sys
import os
import json
import asyncio
import httpx
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal, ModelEndpoint
from src.secret_storage import decrypt

async def probe_model(client, base_url, api_key, model_id):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "hello"}
        ],
        "max_tokens": 5
    }
    try:
        t0 = time.time()
        response = await client.post(url, headers=headers, json=payload, timeout=6.0)
        latency = round((time.time() - t0) * 1000)
        if response.status_code == 200:
            return model_id, True, latency, None
        else:
            # Check if it was a 404 (model not found / no permission)
            try:
                err_detail = response.json().get("detail", "") or response.json().get("error", {}).get("message", "")
            except Exception:
                err_detail = response.text[:100]
            return model_id, False, latency, f"HTTP {response.status_code}: {err_detail}"
    except Exception as e:
        return model_id, False, 0, str(e)[:100]

async def main():
    db = SessionLocal()
    nvidia_id = "nvidia-nemotron"
    ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == nvidia_id).first()
    
    if not ep:
        print("NVIDIA endpoint not found.")
        db.close()
        return
        
    base_url = ep.base_url
    api_key = decrypt(ep.api_key) if ep.api_key else ""
    cached_models = json.loads(ep.cached_models) if ep.cached_models else []
    
    if not cached_models:
        print("No cached models to probe.")
        db.close()
        return
        
    print(f"Probing {len(cached_models)} models concurrently...")
    
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [probe_model(client, base_url, api_key, m) for m in cached_models]
        results = await asyncio.gather(*tasks)
        
    working = []
    failed = []
    
    for model_id, ok, latency, err in results:
        if ok:
            working.append(model_id)
            print(f"[OK] {model_id} ({latency}ms)")
        else:
            failed.append(model_id)
            # print(f"[FAIL] {model_id}: {err}")
            
    print(f"\nResults: {len(working)} working, {len(failed)} failed.")
    
    # Save the failed models as hidden_models in the database
    ep.hidden_models = json.dumps(failed) if failed else None
    
    # Let's also set the default model to one of the verified working models
    # if the current default isn't in the working list.
    from src.settings import load_settings, save_settings
    settings = load_settings()
    current_default = settings.get("default_chat_model", "")
    
    if current_default not in working and working:
        # Pick the best working model.
        # Prefer llama-3.1-nemotron-70b-instruct or llama-3.3-70b-instruct or similar if available
        preferred = [
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "meta/llama-3.3-70b-instruct",
            "google/gemma-3-4b-it",
            "google/gemma-3-12b-it"
        ]
        chosen = None
        for p in preferred:
            if p in working:
                chosen = p
                break
        if not chosen:
            chosen = working[0]
            
        settings["default_chat_model"] = chosen
        settings["default_model"] = chosen
        save_settings(settings)
        print(f"Updated default model in settings.json to verified working model: {chosen}")
        
    db.commit()
    print("Database updated with hidden_models.")
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
