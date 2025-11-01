from pydantic import BaseModel
from typing import List, Dict, Any
import math

def score(value: float, expectancy: float, impulsiveness: float, delay_min: float) -> float:
    delay = max(1.0, delay_min)
    return (value * expectancy) / (impulsiveness * delay)

def tiny_step(title: str) -> str:
    return {
        "Start focus session": "Open editor and write a 3-item TODO (2 min).",
        "Hydrate": "Drink 8oz water now (2 min).",
        "Walk": "Stand and walk for 3 minutes."
    }.get(title, "Do a 2‑minute starter action.")

def suggestions(features: Dict[str, Any]) -> List[Dict[str, Any]]:
    # naive fixed candidates + expectancy from predict later
    candidates = [
        {"title":"Start focus session","value":0.9,"impulsiveness":1.5,"delay_min":10},
        {"title":"Hydrate","value":0.5,"impulsiveness":1.2,"delay_min":0},
        {"title":"Walk","value":0.6,"impulsiveness":1.3,"delay_min":30},
    ]
    exp = float(features.get("expectancy", 0.6))
    for c in candidates:
        c["expectancy"] = exp
        c["priority_score"] = round(score(c["value"], exp, c["impulsiveness"], c["delay_min"]), 4)
        c["tiny_step"] = tiny_step(c["title"])
    return sorted(candidates, key=lambda x: x["priority_score"], reverse=True)
