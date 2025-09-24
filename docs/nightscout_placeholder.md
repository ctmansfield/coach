# Nightscout/xDrip Integration (placeholder)

Plan
- Poll Nightscout API every 1 min for latest SGV and trend.
- Transform to CGM_* events per docs/event_schema.md and POST to Node-RED /events.

Example (pseudo)
- GET http://nightscout.local/api/v1/entries.json?count=1
- Transform: { type: "CGM_SPIKE", glucose: <sgv>, trend: <direction> }
- Post to: http://nodered:1880/events

Security
- For now, no auth. Later, add token and move traffic to internal network.
