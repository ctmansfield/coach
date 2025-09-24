# Home Assistant Mobile App (Quick Setup)

Purpose
- Use HA mobile app notifications for early functionality verification.

Steps
1) Install HA mobile app on your iPhone and log in to your HA instance (use a URL reachable from your phone).
2) In HA web UI, Settings -> Devices & Services -> Integrations -> Mobile App, confirm your iPhone shows up.
3) Find your notify service under Developer Tools -> Actions (formerly "Services"). It will be named like `notify.mobile_app_<device_name>` (e.g., notify.mobile_app_chads_iphone).
4) Create a long-lived access token (Profile -> Security -> Long-Lived Access Tokens).
5) Provide the following to Node-RED (container env vars):
   - HA_BASE_URL=http://homeassistant:8123
   - HA_TOKEN=<token>
   - HA_NOTIFY_SERVICE=notify.mobile_app_<device_name>

Test
- In the iOS app: App Configuration -> Notifications -> Troubleshooting -> Send Test Notification.
- Or in HA: Developer Tools -> Actions -> YAML:
  service: notify.mobile_app_<device>
  data:
    title: Coach
    message: Test from HA
- You should receive a mobile notification.
