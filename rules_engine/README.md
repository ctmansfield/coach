# Rules Engine (skeleton plan)

Purpose
- Consume normalized events, compute a transparent risk score using configs/coach/nutrition/risk_model.yaml, and emit a message + actions for Node-RED to send via HA.

MVP scope
- Stateless function: (event, POP, risk_weights) -> {risk, message}
- Expose a simple HTTP endpoint /score for Node-RED to call.

Interfaces
- POST /score { type, ... } -> { risk, message }

Next steps
- Implement a minimal Python FastAPI or Node service.
- Add unit tests for CGM_SPIKE, MEAL_MISSED, TIMEBOX_END.
- Later: maintain short-term context (recent meals, sleep) and escalate based on ack/snooze signals.
