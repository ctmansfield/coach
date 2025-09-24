# Run the Rules Engine (dev)

Using Python venv
- python -m venv .venv
- source .venv/bin/activate
- pip install -r requirements.txt
- uvicorn app:app --reload --port 8081

Test
- curl -s -X POST localhost:8081/score -H 'Content-Type: application/json' -d '{"type":"CGM_SPIKE","glucose":190,"trend":"rising"}' | jq
- curl -s -X POST localhost:8081/score -H 'Content-Type: application/json' -d '{"type":"MEAL_MISSED","minutes_late":30}' | jq
- curl -s -X POST localhost:8081/score -H 'Content-Type: application/json' -d '{"type":"TIMEBOX_END","next_task":"Stretch + 1 flashcard"}' | jq
