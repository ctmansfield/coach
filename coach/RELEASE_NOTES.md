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
- Packer/cloud‑init manifest for the VM image
- Docker Compose for HA, Node‑RED, proxy, Nightscout/xDrip path
- Minimal Rules Engine skeleton and event schema
- Basic RAG service stub and patient‑facing proxy
- Operational VERIFY steps (watch cue, Alexa whisper, synthetic CGM spike)
