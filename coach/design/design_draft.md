# Personalized Coaching System – Finalized Design Draft (v0.1.0)

This document consolidates requirements and the finalized design for your private, VM-isolated coaching system with nutrition, CGM, study prompts, and escalation nudges.

## 1) Requirements
See `docs/requirements.md`.

## 2) System Architecture
See `docs/architecture.md`. Key points:
- VM hosts coach layers; host runs LLM + Postgres.
- RAG pulls profile, playbooks, diary; small LLM writes nudges; large LLM writes plans.

## 3) Data Model (high level)
- **Events**: MEAL_MISSED, FASTING_RISK, CGM_SPIKE, CGM_DROP, SLEEP_HYGIENE_RISK, SUPP_TIMING_VIOLATION, TIMEBOX_END.
- **Risk Score (0–100)**: additive, transparent; meal timing, fasting, CGM volatility, sleep hygiene, supp/med timing; mitigations subtract risk.
- **Signals**: ack/snooze/ignore, thumbs up/down; latency.

## 4) Coaching Policies
- Watch-first escalation ladder (two steps before strong).
- Quiet hours: haptics only.
- Task switching: time-anchored nudges at block ends.
- Nutrition: protect lunch window; snack rules; caffeine cutoff.
- CGM: small walks on rising slope; snack/water on drops.
- Study: 1–2 flashcards at natural transitions; spaced repetition intervals.

## 5) Personalization
- POP (profile) + playbooks in YAML; daily diary; weekly style adapter update (LoRA/DPO).
- Guardrails: no medical dosing; cite rule sources; transparency on “why this cue”.

## 6) VM Deployment
See `docs/vm_deployment.md` for pros/cons and practical suggestions.

## 7) Next Steps
- Confirm hypervisor, CGM path (Nightscout vs xDrip+), notifier (Signal vs Twilio), Echo device, escalation timings, and meal windows.
- Prepare INSTALL/VERIFY bundle for the first operational patch (v0.2.x) with containers and minimal flows.
