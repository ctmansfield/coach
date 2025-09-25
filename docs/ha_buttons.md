# Home Assistant Buttons / Scripts for Coach

Call Node-RED endpoints from HA with one tap in the app.

Option A: Scripts + REST commands (YAML)
script:
  coach_playbook_morning_boot:
    alias: Coach: Morning Boot
    sequence:
      - service: rest_command.coach_playbook_morning_boot
  coach_playbook_deep_work:
    alias: Coach: Deep Work End Ritual
    sequence:
      - service: rest_command.coach_playbook_deep_work

rest_command:
  coach_playbook_morning_boot:
    url: "http://nodered:1880/playbook/morning_boot"
    method: GET
    timeout: 10
  coach_playbook_deep_work:
    url: "http://nodered:1880/playbook/deep_work_block"
    method: GET
    timeout: 10

Add to Dashboard (Lovelace)
- Create Button cards that call script.coach_playbook_morning_boot and script.coach_playbook_deep_work.
- Or add a Web Link card pointing at http://<VM_LAN_IP>:1880/playbook/<name> for direct calls.

Notes
- Use http://homeassistant:8123 as a base only inside containers. In HA UI, use nodered’s hostname/IP reachable from HA.
- You can add more scripts for other playbooks or for /coach/quick endpoints (e.g., /coach/quick/walk_3min).
