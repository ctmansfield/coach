#!/usr/bin/env bash
set -euo pipefail
echo "[coach/VERIFY] Generating suggestions via plan_now (container run recommended)."
python -m coach_app.cli.plan_now --user 00000000-0000-0000-0000-000000000001 --hours 4 --goals deep_work,hydration,walk || true
