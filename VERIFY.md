# VERIFY — v0.2 (Functionality-first)

Design presence
- Confirm files exist:
  - `/mnt/nas_storage/repos/coach/README.md`
  - `/mnt/nas_storage/repos/coach/docs/requirements.md`
  - `/mnt/nas_storage/repos/coach/design/design_draft.md`
  - `/mnt/nas_storage/repos/coach/configs/coach/profile/pop.yaml`

Operational
- Import Node-RED flow: `vm/coach/docker/nodered/flows.json`
- Set Node-RED env vars:
  - `HA_BASE_URL=http://homeassistant:8123`
  - `HA_TOKEN=<HA long-lived token>`
  - `HA_NOTIFY_SERVICE=notify.mobile_app_<your_device>`
- Deploy flow and run tests (see `docs/verify_ops.md`).

Expectations
- Synthetic CGM inject produces a HA mobile notification
- HTTP POST /events for TIMEBOX_END and MEAL_MISSED produces appropriate notifications
