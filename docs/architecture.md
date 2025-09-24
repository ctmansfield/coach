# Architecture Overview

**Outside the VM (system level):**
- Local LLM endpoints (small patient-facing, larger analysis).
- Postgres at `192.168.1.225:55432`.

**Inside the VM:**
- Home Assistant (HA) for notification routing to phone/watch and Alexa.
- Node-RED for escalation ladder and orchestration flows.
- Rules Engine (deterministic) computing Risk/Impairment Score and emitting events.
- RAG/Memory service aggregating POP/playbooks/diary/context.
- Patient-facing coach proxy calling the small LLM with strict guardrails.
- Analysis scheduler for AM/PM runs against the large LLM; writes plans/summaries.
- CGM ingest (Nightscout or xDrip+/HA) translating live glucose into DB events.
- Study/flashcard service with spaced repetition scheduler.

**Networking:**
- Reverse proxy exposes only 443 (and 22 for admin).
- Internal-only ports for HA, Node-RED, Rules Engine, RAG, Nightscout.
