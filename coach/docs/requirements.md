# Requirements (User-Derived)

1. **Structured routines** for meals and sleep with reminders; cues facilitate task switching and reduce perseveration.
2. **Gentle reminders with escalation:** watch haptics → second watch cue + single-room Alexa whisper → SMS/Signal; include **time anchoring**.
3. **Medication & supplement compliance** with practical consequence framing; no dosing advice.
4. **Nutrition integration:** meal/snack timing windows, reinforcement via a transparent **Risk/Impairment Score**; editable rules in YAML.
5. **Health data integration:** vitals, sleep, activity, and **CGM** live data for real-time nudging and next-day adjustments.
6. **Study & flashcards:** micro-prompts with spaced repetition; used as context switchers.
7. **Deep personalization:** local LLM coach w/ RAG memory (profile, playbooks, diary), learning from feedback signals; entirely offline.
8. **Models & privacy:** small model for patient-facing nudges; larger model for offline analysis. All data and logic remain local.
9. **Isolation:** Run the stack inside a **VM**; only LLM services and Postgres remain at the system level.
10. **Repo layout & ops:** this project lives under `/mnt/nas_storage/repos/coach/`; patches delivered via `/mnt/nas_storage/incoming/` with INSTALL/VERIFY and release notes.
