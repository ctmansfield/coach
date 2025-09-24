# Event Schema (v0.2 draft)

Minimal events to drive early functionality and VERIFY.

Common fields
- id: string (client-assigned or server-generated)
- type: enum
- ts: ISO 8601 timestamp
- source: e.g., "node-red", "nightscout", "test"
- ctx: object (optional)

Event types
- TIMEBOX_END
  - next_task: string
- MEAL_MISSED
  - minutes_late: number
- CGM_SPIKE
  - glucose: number (mg/dL)
  - trend: enum [rising, flat, falling]
- CGM_DROP
  - glucose: number (mg/dL)
  - trend: enum [falling, rising, flat]

Response envelope (from rules/flows)
- risk: number (0-100)
- message: string (user-facing)
- actions: string[] (optional)

Notes
- Risk weights are human-readable and come from configs/coach/nutrition/risk_model.yaml.
- Pop/playbooks adjust phrasing and escalation, not dosing.
