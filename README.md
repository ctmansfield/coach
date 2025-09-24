# Coach Stack (Design Docs Only) — v0.1.0

This repository contains **design documents and configuration templates** for your private, on-device coaching system.
It is intended to live at `/mnt/nas_storage/repos/coach/` and be kept **separate** from other projects.
Your normal flow: download this bundle → save it to `/mnt/nas_storage/incoming/` → extract into `/mnt/nas_storage/repos/coach/`.

**Scope of this bundle (no code yet):**
- Requirements and finalized architecture/design draft
- VM deployment plan (pros/cons, suggestions)
- File layout, ops guidance, change control
- Configuration templates (YAML) for profiles, playbooks, nutrition, study deck

> LLMs and Postgres stay at the **system level** as per your design. The VM will host all other layers.

