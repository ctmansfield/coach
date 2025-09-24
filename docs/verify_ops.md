# VERIFY (Operational, v0.2 draft)

Goal: Prove end-to-end notifications via HA mobile app from Node-RED, using the /events endpoint and a direct HA service call smoke test.

Prereqs
- HA mobile app registered; obtain notify service name (e.g., notify.mobile_app_pixel_7).
- In Node-RED, set environment variables: HA_BASE_URL, HA_TOKEN, HA_NOTIFY_SERVICE.
  - HA token: long-lived access token from HA user profile.

Steps
1) Node-RED flow import
   - Import vm/coach/docker/nodered/events.json (tab: Coach /events), vm/coach/docker/nodered/buttons.json (tab: Coach Quick Actions), and vm/coach/docker/nodered/playbooks.json (tab: Coach Playbooks).
   - Set env vars in the Node-RED container (see Notes).
   - Deploy → Full.

2) Direct HA service smoke test (from inside Node-RED container)
   - docker exec -it nodered bash -lc 'curl -sS -o /tmp/out -w "HTTP:%{http_code}\n" -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" -d "{\"message\":\"Smoke test\",\"title\":\"Coach\"}" "$HA_BASE_URL/api/services/notify/mobile_app_masterblaster" ; echo ; cat /tmp/out'
   - Expected: HTTP:200 and [] response; a push on the phone.

3) HTTP ingest test (/events)
   - Send a POST to Node-RED:
     curl -X POST \
       http://localhost:1880/events \
       -H 'Content-Type: application/json' \
       -d '{"type":"TIMEBOX_END","next_task":"Stand, water, 1 flashcard"}'
   - Expected: HA mobile notification with switch prompt.

4) MEAL_MISSED test
   - Same endpoint:
     curl -X POST \
       http://localhost:1880/events \
       -H 'Content-Type: application/json' \
       -d '{"type":"MEAL_MISSED","minutes_late":25}'
   - Expected: HA mobile notification suggesting protein-forward snack or start meal window.

5) Playbook tests
   - GET /playbook/:name → pushes the playbook steps as a bulleted message, and returns a JSON body:
     - curl -s http://localhost:1880/playbook/morning_boot | jq
     - curl -s http://localhost:1880/playbook/deep_work_block | jq
     - curl -s http://localhost:1880/playbook/bedtime_winddown | jq
   - Unknown playbook returns 404 JSON:
     - curl -i http://localhost:1880/playbook/does_not_exist

Notes
- Node-RED env vars come from compose env/env_file (nodered.env). Inside Function nodes, use env.get("HA_TOKEN") etc.
- HA_BASE_URL should be http://homeassistant:8123 from inside the container network.
- HA_NOTIFY_SERVICE should normally be the bare slug (mobile_app_<device>), not prefixed with notify. The REST path is /api/services/notify/<slug>.
- For external testing via Caddy, use https://flows.lab.lan/flows/ (once DNS/TLS are in place). For now, localhost:1880 is fine.
