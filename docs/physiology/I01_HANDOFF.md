# I01-T — Offline Coach → Mother event handoff

## Purpose and ownership

Coach owns event draft preparation and **local outbound packaging**, while
Mother owns contract validation, archival ingestion and source-revision
identity. The envelope wire format is pinned to version 1.0.0; the receiver
owns acceptance rules. This step is an offline *file* handoff, not an HTTP
API, authenticated session, notifications, or a live connector.

Base: Coach manual event drafts, PR #2.
The paired Mother receiver targets Mother manual ingest, PR #5.

## Wire contract

A UTF-8 JSON object with exactly these keys:

- `envelope_version`: `1.0.0`
- `content_type`: `application/vnd.coach.manual-event+json`
- `encoding`: `base64`
- `event_sha256`: lowercase SHA-256 of original submitted event bytes
- `event_base64`: strict base64 representation of those exact bytes

Coach serializes the manual draft deterministically to finite UTF-8 JSON
before packaging. Mother must verify the digest *before* invoking its own
contract validator and immutable archive. The source bytes, not the
envelope's declaration, are the record of what was received.

## INSTALL / usage

Install the isolated Coach branch in a separate review worktree; do not
replace the restored NAS application or running flows. The module uses
Python's standard library and needs no new runtime dependency.

```python
from coach_app.physiology.manual_events import create_manual_event
from coach_app.physiology.handoff import pack_manual_event, save_to_outbox

event = create_manual_event(
    subject_id="synthetic",
    event_kind="user_marker",
    payload={"description": "test annotation"},
    recorded_at="2026-11-07T04:10:00Z",
)
bundle = pack_manual_event(event)
path = save_to_outbox("/path/to/disposable/outbox", bundle)
```

Use only synthetic inputs until the user has authorized a concrete data path.
The writer publishes a private, content-addressed file without overwriting
existing files; interrupted temporary files are not treated as ready.
An independently authorized operator copies that immutable file to an
explicitly chosen Mother input path. There is no automatic polling or
network transfer in this increment.

## VERIFY

```bash
python -m unittest discover -s tests -p test_event_handoff.py -v
```

The isolated test suite uses a temporary directory and synthetic events only.
No actual data, services, notifications or credentials are accessed.

## Safety / limitations / rollback

The SHA-256 digest establishes byte integrity, **not sender authentication**.
A file with a valid hash might still be untrusted. Mother's receiver must
reject unrelated content, wrong versions, duplicate JSON keys and nonfinite
numbers, and then validate event authorization and references at a later
authenticated integration gate.

A local spool may contain private event contents encoded in base64.
Protect/retain it as personal data; do not upload it to a public repository.
No live deployment is attempted, and deleting an unused disposable test
outbox does not delete source records from an existing archive.
