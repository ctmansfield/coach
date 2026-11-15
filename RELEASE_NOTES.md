# RELEASE_NOTES — v0.1.0 (2025-09-21)

**Type:** Design-only drop (no services deployed)

**Why:** Establish a stable specification and configuration templates before building the VM image and container stack.

**What’s included:**
- Finalized requirements and architecture
- VM deployment pros/cons and suggestions
- Files layout and ops guidance
- Templates for POP, playbooks, nutrition, supplements, risk model, flashcards
- Install & Verify instructions

**Next planned patch (v0.2.x):**
- Functionality-first minimal flow (Node-RED + HA mobile app notification)
- Event schema and operational VERIFY docs
- Rules Engine skeleton plan
- Nightscout/xDrip placeholder
- Hardening (compose/networking, secrets) deferred per decision

## v0.1.1 — 2026-11-15: context reader adoption

Install the shared context reader bundle 1.0.0 and context-v1 ordered intake,
with project-local policy, an empty task index, synthetic tests, and a read-only
SessionStart reminder adapter. See `.codex/WORKFLOW.md` for intake and handoff.
This is repository tooling release accounting; no application deployment or
target hook callback is asserted by this entry. No release tag is created.
