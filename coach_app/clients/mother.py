import os, requests

BASE = os.getenv("MOTHER_BASE_URL", "http://mother:8080")

def predict(model: str, features: dict) -> dict:
    r = requests.post(f"{BASE}/api/models/predict", json={"model": model, "features": features}, timeout=10)
    r.raise_for_status()
    return r.json()

def create_reminder(rec: dict) -> dict:
    r = requests.post(f"{BASE}/api/reminders", json=rec, timeout=10)
    r.raise_for_status()
    return r.json()
