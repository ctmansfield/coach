# v0.2 Roadmap (Functionality-first)

Out of scope (deferred)
- Hardening compose/networking and secret management (SOPS) per user request.

Included
1) Minimal Node-RED flow and HA mobile notification
   - HTTP ingest for events
   - Synthetic CGM spike injector
   - REST call to HA notify service using env vars
2) Event schema doc (TIMEBOX_END, MEAL_MISSED, CGM_SPIKE, CGM_DROP)
3) VERIFY ops for end-to-end notification
4) Rules Engine skeleton plan
5) Future Nightscout/xDrip integration placeholder

Next increments after v0.2
- Implement rules engine service (FastAPI) with unit tests
- Add Nightscout ingestion (poll REST) with basic transforms to events
- Add persistence (simple SQLite or Postgres events table) and ack/snooze handling
- Introduce basic RAG proxy stub wired to local small model for phrasing
