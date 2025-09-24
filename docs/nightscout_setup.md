# Nightscout Setup (Functionality-first)

This sets up a local Nightscout in the coach VM using Docker Compose, suitable for Node-RED polling.

What you get
- MongoDB 5 and Nightscout container, exposed at http://<VM-IP>:1337 (and via Caddy at https://ns.lab.lan/ns/ if you use the provided Caddyfile).

Steps
1) Bring up services
   - On the VM: docker compose -f /repos/coach/vm/coach/docker/compose/docker-compose.yml up -d nightscout-mongo nightscout
   - First boot can take ~1–2 minutes.

2) Confirm Nightscout is up
   - curl -sI http://localhost:1337 | head -n1
   - Browse to http://<VM-IP>:1337 and set up basics in the UI.

3) Configure API secret (already set via env)
   - Default in compose: API_SECRET=CHANGE_THIS_very_secret_123
   - For a real setup, change this in compose and restart.

4) Node-RED polling (simple)
   - In Node-RED, add an inject node every 1 min -> http request node:
     - GET http://nightscout:1337/api/v1/entries.json?count=1
   - Function node to map to CGM events per docs/event_schema.md
   - POST to /events (the flow provided already accepts CGM_SPIKE and will notify HA)

5) Verify
   - Once an entry exists (or simulate by editing admin UI), the poller should create a notification if glucose is high and rising.

Notes
- This is a local functional setup, not hardened. Credentials are placeholders.
- You can also configure xDrip+ to point to your Nightscout instance if desired.
