# Coach flows and physiological replay

## Flow authority and compatibility

| File | Purpose | Current boundary |
| --- | --- | --- |
| `flows_clean.json` | Canonical minimal `/events` and `/health` flow | Existing meal/timebox notifications; unchanged by the physiology increment |
| `flows.json` | Exact mirror of `flows_clean.json` | Reconciled to the source README's existing canonical-file instruction |
| `playbooks.json` | Existing playbook endpoints and notification construction | JSON and JavaScript regular-expression escaping repaired; no new playbook policy |
| `flows_nightscout_poll.json` | Optional latest-entry observation preview | Disabled by default; disconnected output; no notification route or archival guarantee |

The previous malformed `flows.json` contained a CGM-specific recommendation
branch. It has been replaced with the documented canonical flow. The separate
legacy poller no longer labels every reading `CGM_SPIKE` or calls `/events`.
Physiological source acquisition and durable history belong to Mother.

These are source changes. The active Node-RED export and deployed repository
revision must be reconciled before any flow import or deployment. Offline JSON
and function tests do not establish the behavior of an existing running flow.

## Existing minimal notification flow

The unchanged canonical flow uses:

- `HA_BASE_URL`: Home Assistant base URL.
- `HA_TOKEN`: existing Home Assistant authentication configuration.
- `HA_NOTIFY_SERVICE`: existing notification service.

Its endpoints remain `POST /events` for `MEAL_MISSED` and `TIMEBOX_END`, and
`GET /health`. Manual test injects can send real notifications. This increment
does not change credentials, deployed flows, or notification policies.

## Disabled legacy Nightscout preview

Mother's importer is the authoritative ingestion path. It preserves source
records, revisions, import runs and archived history before producing replay
bundles. The legacy Node-RED poller is a bounded observation preview:

1. The flow tab is disabled and its inject node does not run on deployment.
2. A function gate additionally requires
   `COACH_ENABLE_LEGACY_NIGHTSCOUT_POLL=1`, a nonempty
   `NIGHTSCOUT_SOURCE_INSTANCE`, and `NIGHTSCOUT_URL` before it permits a request.
3. It asks for only the latest SGV entry. It has no pagination, catch-up or
   deletion detection, and it cannot preserve a six-month history.
4. A valid response produces a `CGM_OBSERVATION_CANDIDATE` transport envelope
   with native ID, original JSON, original timestamp fields, measurement time,
   original value/unit, provenance and quality flags. Unknown units remain
   unknown. Source availability and archival ingestion remain null.
5. Its link output has no configured links. It never POSTs to `/events` or a
   notification service. Connecting it to any consumer is a separate integration
   change; no Mother endpoint is assumed here.

The transport envelope uses `transport_version: "1.0.0"`. It is **not** a
canonical archived Observation and does not invent a durable source revision ID.
`archival_status: "not_persisted"` makes that distinction explicit. A downstream
authoritative importer must preserve and reconcile source evidence before
creating canonical observations.

Repeated native-ID/content revisions are suppressed using a bounded Node-RED
context cache of the last 1,000 previewed revisions. Changed payloads remain
visible. This cache is neither a durable-receipt acknowledgment nor an import
checkpoint; its restart behavior depends on the Node-RED context configuration.
Retries and restarts must be reconciled by the archive. Equal readings with
different native IDs are not merged.

Missing IDs, malformed responses, invalid values/timestamps and empty results
produce explicit acquisition-status output. The diagnostic debug node is
inactive by default. Stale observations remain timestamped candidates with
`stale_preview`; they are not converted into alerts. The preview's default
freshness interval is 900 seconds, configurable through
`COACH_NIGHTSCOUT_PREVIEW_MAX_AGE_SECONDS`. This is a display-quality parameter,
not a physiological threshold. Original timestamps are retained, timezone-free
fallback timestamps and calendar rollovers are rejected, and no original
availability time is inferred from server modification fields.

Authentication and instance-specific source semantics have not been verified
against the user's Nightscout deployment. No live poll was executed for this
increment.

## Offline replay

`coach_app.physiology.replay` reads a versioned export bundle and writes one
self-contained HTML file. It performs no acquisition, background request,
notification or model inference. It uses the canonical schema at
`coach_app/physiology/schemas/v1.schema.json`; the schema owner maintains the
compatible copy in both applications. Python's `jsonschema` package is required.

From the Coach repository:

```bash
python -m coach_app.physiology.replay \
  --input replay-bundle.json \
  --output replay.html
```

The output must be a new filename; an existing file is preserved. `--schema`
can specify the exact shared schema for an isolated compatibility check.
`COACH_PHYSIOLOGY_SCHEMA_PATH` provides the equivalent testing override.

The bundle contains `schema_version: "1.0.0"`, `subject_id`, an offset-aware
`start`/`end`, and arrays named `observations`, `events`, `sessions`,
`source_revisions`, and `coverage`. Empty arrays remain explicit. The first four
arrays use the shared record definitions. Referenced source revisions and
sessions must be included; ambiguous or broken references are rejected.

Each coverage row contains `channel`, `source_instance`, `start`, `end`, `count`,
`valid_count`, `expected_cadence_seconds` (positive or null), `gaps` (objects with
`start`, `end`, `reason`), `quality_flags`, and `status` (`observed`, `partial`,
`absent`, or `unknown`). Expected channels should be emitted even when absent.
The renderer does not infer uninterrupted coverage from the presence of records
or an empty gap list.

Bundle metadata contains `evidence_level`, `timing_policy`, `processing_version`
and `assumptions`. It can be supplied in `metadata` or as consistent top-level
fields. Conflicting copies are rejected. Synthetic fixtures should use an
explicit evidence level such as `synthetic_integration`.

The view provides:

- Separate source/channel/evidence lanes, supplied gaps, and a complete
  observation table. Points remain discrete; bars represent recorded intervals.
- Original and normalized values/units, quality, channel/method information,
  original offsets, measurement time, source availability, first seen time and
  ingestion time. Missing values remain distinct from valid zero.
- Source-revision links and content hashes for every observation. Raw source
  artifacts are not embedded in the HTML.
- Separate event kinds for recommendations, acknowledgments, reported actions,
  observed actions, questions, answers and outcomes. Unknown event occurrence
  times are not silently replaced with recorded time on the timeline.
- Recording/session context, processing versions and explicit replay timing
  assumptions. All untrusted text is HTML-escaped and source links stay local.

This increment displays scalar observations and recorded intervals. A nonempty
`streams` collection is rejected explicitly; waveform/beat-series playback
requires a subsequent stream viewer. No ECG/RR history, readiness score,
clinical state, or recovery result is reconstructed from HR summaries.

The `create_user_marker` Python helper constructs a `reported` `user_marker`
event with factual text. Occurrence and knowledge times remain null unless
provided. It does not persist the event, select a question, or convert a marker
into a recommendation, performed action or outcome.

## Verification

Run the offline checks from the Coach repository using the release's compatible
environment and shared schema:

```bash
python -m pytest -q \
  tests/test_physiology_flows.py \
  tests/test_physiology_replay.py \
  tests/test_end_to_end.py
```

The flow checks parse all JSON, compile every function using Node.js, and execute
selected function bodies with mocked context, environment and time. They never
run HTTP nodes. Replay checks use synthetic fixtures and temporary files.

All existing `test_end_to_end.py` tests are skipped unless
`COACH_RUN_NETWORK_TESTS=1` is explicitly set. Some GET routes in that suite send
notifications, so the gate covers the entire module, not just POST tests. Use
that opt-in only after selecting a controlled test target or obtaining specific
authorization for externally visible notification tests. Tokens in the
environment do not enable these tests by themselves.

Record JSON/function tests, replay integration, actual deployment, and verified
live behavior as separate evidence levels. Existing playbook wiring and a
deployed Node-RED environment still require integration verification.
