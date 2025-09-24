# Node-RED Flow (Minimal)

Files
- flows_clean.json: Minimal flow with HTTP endpoint /events, no CGM. It computes a small risk and posts a notification to Home Assistant via REST. Includes /health and two test injects. This is the canonical flow; flows.json will mirror this.

Configuration
- Set environment variables for the Node-RED container:
  - HA_BASE_URL=http://homeassistant:8123
  - HA_TOKEN=<long-lived HA token>
  - HA_NOTIFY_SERVICE=notify.mobile_app_<your_device>

Import
- Use Node-RED editor -> menu -> Import -> select flows_clean.json -> Deploy.

Endpoints
- POST /events (JSON): { type: "MEAL_MISSED"|"TIMEBOX_END", ... }
- GET /health: returns 200 OK
- Inject nodes: "Test TIMEBOX_END" and "Test MEAL_MISSED" for quick tests.
