import os
import time
import socket
import requests
import pytest
from urllib.parse import urlsplit

HA_BASE = os.getenv("HA_BASE", "http://homeassistant:8123")
NR_BASE = os.getenv("NR_BASE", "http://localhost:1880")
HA_TOKEN = os.getenv("HA_TOKEN", "")
HA_NOTIFY = os.getenv("HA_NOTIFY", "mobile_app_masterblaster")

_NR = urlsplit(NR_BASE)
NR_HOST = _NR.hostname or "localhost"
NR_PORT = _NR.port or (443 if _NR.scheme == "https" else 80)

@pytest.mark.skipif(not HA_TOKEN, reason="HA_TOKEN env not set for tests")
def test_ha_smoke_notify():
    url = f"{HA_BASE}/api/services/notify/{HA_NOTIFY}"
    r = requests.post(url,
                      headers={
                          "Authorization": f"Bearer {HA_TOKEN}",
                          "Content-Type": "application/json",
                      },
                      json={"title": "Coach", "message": "pytest smoke"},
                      timeout=10)
    assert r.status_code in (200, 201), r.text


def wait_port(host, port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def test_nodered_health_and_events():
    # Ensure Node-RED is up at NR_BASE host:port
    assert wait_port(NR_HOST, NR_PORT, 20), f"Node-RED port not reachable at {NR_HOST}:{NR_PORT}" 

    # Health endpoint (if present)
    r = requests.get(f"{NR_BASE}/health", timeout=5)
    assert r.status_code in (200, 404)

    # TIMEBOX_END event should return JSON body of the HA message envelope
    r = requests.post(f"{NR_BASE}/events",
                      headers={"Content-Type": "application/json"},
                      json={"type": "TIMEBOX_END", "next_task": "Stand, water, 1 flashcard"},
                      timeout=10)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("title") == "Coach"
    assert "Switch to:" in j.get("message", "")


def test_playbook_json_and_push():
    # Accepts JSON body and returns JSON structure
    names = [
        "morning_boot",
        "deep_work_block",
        "bedtime_winddown",
    ]
    for name in names:
        r = requests.get(f"{NR_BASE}/playbook/{name}", timeout=10)
        assert r.status_code == 200, (name, r.text)
        data = r.json()
        assert data.get("ok") is True
        assert data.get("name") == name
        assert isinstance(data.get("steps"), list) and len(data["steps"]) > 0

    # Unknown returns 404 JSON
    r = requests.get(f"{NR_BASE}/playbook/does_not_exist", timeout=10)
    assert r.status_code == 404


@pytest.mark.parametrize("endpoint", [
    "/coach/quick/stand_water",
    "/coach/quick/walk_3min",
    "/coach/quick/flashcard",
    "/coach/quick?next=Test%20Next",
])
def test_quick_buttons(endpoint):
    r = requests.get(f"{NR_BASE}{endpoint}", timeout=10)
    # These endpoints return text bodies; status should still be 200
    assert r.status_code == 200
