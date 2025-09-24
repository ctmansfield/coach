from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import yaml

# Minimal, self-contained scoring stub
# Loads weights from configs/coach/nutrition/risk_model.yaml if available

class Event(BaseModel):
    type: str
    glucose: Optional[float] = None
    trend: Optional[str] = None
    minutes_late: Optional[int] = None
    next_task: Optional[str] = None

class ScoreResponse(BaseModel):
    risk: float
    message: str

app = FastAPI()

DEFAULT_WEIGHTS = {
    "meal_timing_penalty_per_min": 0.2,
}

weights = DEFAULT_WEIGHTS.copy()

try:
    with open("configs/coach/nutrition/risk_model.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        if isinstance(data, dict) and isinstance(data.get("weights"), dict):
            weights.update(data["weights"])
except FileNotFoundError:
    pass

@app.post("/score", response_model=ScoreResponse)
async def score(event: Event):
    t = event.type.upper()
    risk = 0.0
    msg = "Event"

    if t == "CGM_SPIKE":
        g = float(event.glucose or 0)
        trend = (event.trend or "").lower()
        risk = (20.0 if g >= 180 else 10.0) + (10.0 if trend == "rising" else 0.0)
        msg = f"Glucose {int(g)} and {trend or 'unknown'}. Short walk + water?"

    elif t == "MEAL_MISSED":
        mins = int(event.minutes_late or 0)
        per = float(weights.get("meal_timing_penalty_per_min", 0.2))
        risk = min(30.0, mins * per)
        msg = f"Meal is {mins} min late. Quick protein snack or start meal window?"

    elif t == "TIMEBOX_END":
        nxt = event.next_task or "next block"
        risk = 5.0
        msg = f"Block complete. Switch to: {nxt}."

    else:
        msg = f"Event: {t}"

    return ScoreResponse(risk=risk, message=msg)

# To run locally: uvicorn app:app --reload --port 8081
