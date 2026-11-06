"""Offline Node-RED checks: no HTTP request or notification is executed."""

import json
from pathlib import Path
import runpy
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FLOW_DIR = ROOT / "vm" / "coach" / "docker" / "nodered"
NOW = "2026-11-07T00:05:00.000Z"
ENV = {
    "COACH_ENABLE_LEGACY_NIGHTSCOUT_POLL": "1",
    "NIGHTSCOUT_SOURCE_INSTANCE": "nightscout-fixture",
    "NIGHTSCOUT_URL": "https://nightscout.invalid",
}


def _flow(filename):
    return json.loads((FLOW_DIR / filename).read_text())


def _node(node_id, filename="flows_nightscout_poll.json"):
    return next(n for n in _flow(filename) if n["id"] == node_id)


def _run_function(code, messages, environment=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for offline function execution")
    # Only the function body executes inside a VM with fake clock/env/context.
    # The HTTP nodes themselves are never executed.
    harness = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const state = new Map();
const statuses = [];
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [input.now])); }
  static now() { return Date.parse(input.now); }
}
const result = [];
for (const message of input.messages) {
  const context = {
    msg: message,
    Date: FixedDate,
    env: {get: name => input.environment[name]},
    flow: {get: key => state.get(key), set: (key, value) => state.set(key, value)},
    node: {status: value => statuses.push(value)}
  };
  const script = new vm.Script('(function() {\n' + input.code + '\n})()');
  result.push(script.runInNewContext(context, {timeout: 1000}));
}
process.stdout.write(JSON.stringify({result, statuses}));
"""
    process = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "code": code,
                "messages": messages,
                "environment": environment or {},
                "now": NOW,
            }
        ),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)["result"]


def _entry(**changes):
    value = {
        "_id": "sample-1",
        "date": 1794009600000,
        "dateString": "2026-11-07T00:00:00.000Z",
        "sgv": 103,
        "units": "mg/dL",
        "type": "sgv",
        "direction": "Flat",
        "device": "fixture-sensor",
    }
    value.update(changes)
    return value


def test_all_flow_json_parses_and_canonical_mirror_matches():
    for path in FLOW_DIR.glob("*.json"):
        assert isinstance(json.loads(path.read_text()), list), path.name
    assert (FLOW_DIR / "flows.json").read_bytes() == (
        FLOW_DIR / "flows_clean.json"
    ).read_bytes()


def test_all_function_nodes_compile_offline():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for offline function syntax checks")
    functions = [
        {"name": f"{path.name}:{n['id']}", "code": n["func"]}
        for path in FLOW_DIR.glob("*.json")
        for n in json.loads(path.read_text())
        if n.get("type") == "function"
    ]
    process = subprocess.run(
        [
            node,
            "-e",
            "const fs=require('fs'); for(const f of JSON.parse(fs.readFileSync(0,'utf8'))) "
            "{ try { new Function('msg','node','env','flow','context',f.code); } "
            "catch(e) { throw new Error(f.name+': '+e.message); } }",
        ],
        input=json.dumps(functions),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr


def test_legacy_preview_is_disabled_and_has_no_notification_route():
    nodes = _flow("flows_nightscout_poll.json")
    assert next(n for n in nodes if n["type"] == "tab")["disabled"] is True
    assert _node("inj1")["once"] is False
    assert _node("observation_preview_out")["links"] == []
    assert not any("POST" in n.get("name", "") for n in nodes)
    assert "CGM_SPIKE" not in _node("fn_map")["func"]
    assert "/events" not in _node("fn_map")["func"]
    assert not any(
        n.get("type") == "http request" and n["id"] != "http_ns" for n in nodes
    )


def test_preview_network_gate_requires_explicit_opt_in_and_source():
    code = _node("fn_enable_poll")["func"]
    assert _run_function(code, [{}]) == [None]
    assert _run_function(code, [{}], {"COACH_ENABLE_LEGACY_NIGHTSCOUT_POLL": "1"}) == [
        None
    ]
    result = _run_function(code, [{}], ENV)[0]
    assert result["method"] == "GET"
    assert result["url"] == "https://nightscout.invalid/api/v1/entries/sgv.json?count=1"


def test_preview_retains_identity_measurement_and_unknown_availability():
    entry = _entry()
    result, issue = _run_function(
        _node("fn_map")["func"], [{"payload": [entry], "statusCode": 200}], ENV
    )[0]
    assert issue is None
    payload = result["payload"]
    assert payload["type"] == "CGM_OBSERVATION_CANDIDATE"
    assert payload["native_record_id"] == "sample-1"
    assert payload["raw_record"] == entry
    assert payload["measurement_start"] == entry["dateString"]
    assert payload["first_seen_at"] == NOW
    assert payload["source_available_at"] is None
    assert payload["ingested_at"] is None
    assert payload["archival_status"] == "not_persisted"
    assert payload["quality_flags"] == []
    assert "url" not in result and "headers" not in result
    assert "recommendation" not in payload and "risk" not in payload


def test_preview_deduplicates_revisions_without_discarding_corrections():
    original = _entry()
    reordered = dict(reversed(list(original.items())))
    changed = _entry(sgv=104)
    messages = [{"payload": [e]} for e in [original, reordered, changed, original]]
    results = _run_function(_node("fn_map")["func"], messages, ENV)
    assert results[0][0]["payload"]["revision_status"] == "first_observed"
    assert results[1][0] is None
    assert results[1][1]["payload"]["code"] == "duplicate_revision"
    assert results[2][0]["payload"]["revision_status"] == "changed"
    assert results[2][0]["payload"]["original_value"] == 104
    assert results[3][0] is None
    assert results[3][1]["payload"]["code"] == "duplicate_revision"


def test_stale_preview_remains_a_timestamped_observation_candidate():
    entry = _entry(date=1793836800000, dateString="2026-11-05T00:00:00.000Z")
    result, issue = _run_function(_node("fn_map")["func"], [{"payload": [entry]}], ENV)[
        0
    ]
    assert issue is None
    assert result["payload"]["measurement_start"] == entry["dateString"]
    assert result["payload"]["quality_flags"] == ["stale_preview"]
    assert result["payload"]["type"] == "CGM_OBSERVATION_CANDIDATE"
    assert result["payload"]["source_available_at"] is None


def test_zero_is_retained_and_unknown_units_remain_unknown():
    entry = _entry(sgv=0)
    del entry["units"]
    result, issue = _run_function(_node("fn_map")["func"], [{"payload": [entry]}], ENV)[
        0
    ]
    assert issue is None
    assert result["payload"]["original_value"] == 0
    assert result["payload"]["original_unit"] is None


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({}, "malformed_response"),
        ([], "no_entry"),
        ([None], "malformed_entry"),
        ([_entry(), _entry(_id="second")], "unexpected_result_count"),
        ([_entry(_id="")], "missing_native_id"),
        ([_entry(sgv=None)], "invalid_sgv"),
        ([_entry(sgv="")], "invalid_sgv"),
        ([_entry(sgv=True)], "invalid_sgv"),
        ([_entry(date="bad")], "invalid_date_ms"),
        (
            [_entry(date=None, dateString="2026-11-07T00:00:00")],
            "missing_or_ambiguous_measurement_time",
        ),
        ([_entry(date=None, dateString="2026-02-30T00:00:00Z")], "invalid_dateString"),
        ([_entry(type="mbg")], "unsupported_entry_type"),
    ],
)
def test_malformed_entries_emit_explicit_status_without_measurements_or_alerts(
    payload, code
):
    observation, issue = _run_function(
        _node("fn_map")["func"], [{"payload": payload}], ENV
    )[0]
    assert observation is None
    assert issue["payload"]["type"] == "observation_preview_status"
    assert issue["payload"]["code"] == code
    assert "risk" not in issue["payload"]


def test_playbook_regex_repairs_preserve_intended_yaml_parsing():
    code = _node("fn-parse-yaml-lite", "playbooks.json")["func"]
    result = _run_function(
        code,
        [
            {
                "pbname": "deep_work_block",
                "payload": 'steps:\r\n  - "Save work"\r\n  - Stand up\r\n',
            }
        ],
    )[0]
    assert result["parsed"] == {
        "title": "Deep Work Block",
        "steps": ["Save work", "Stand up"],
    }


def test_playbook_service_prefix_is_stripped_without_sending_request():
    code = _node("fn-build-ha-from-parsed", "playbooks.json")["func"]
    result = _run_function(
        code,
        [{"pbname": "fixture", "parsed": {"title": "Fixture", "steps": ["A", "B"]}}],
        {
            "HA_BASE_URL": "https://fixture.invalid",
            "HA_NOTIFY_SERVICE": "notify.fixture",
            "HA_TOKEN": "fixture-token",
        },
    )[0]
    assert result["url"] == "https://fixture.invalid/api/services/notify/fixture"
    assert result["payload"]["message"] == "• A\n• B"


def test_network_suite_is_gated_even_when_notification_credentials_exist(monkeypatch):
    monkeypatch.delenv("COACH_RUN_NETWORK_TESTS", raising=False)
    monkeypatch.setenv("HA_TOKEN", "fixture-token")
    module = runpy.run_path(str(ROOT / "tests" / "test_end_to_end.py"))
    assert module["pytestmark"].name == "skipif"
    assert module["pytestmark"].args == (True,)
    assert "COACH_RUN_NETWORK_TESTS=1" in module["pytestmark"].kwargs["reason"]
