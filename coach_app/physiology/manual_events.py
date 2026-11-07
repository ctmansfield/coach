"""Create explicit, offline Coach event drafts without persistence or notifications.

Event constructors do not infer an action from an acknowledgment or a missing
outcome from silence. Persistence belongs to Mother's immutable archive.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

CONTRACT_VERSION = "1.0.0"
PROCESSING_VERSION = "coach-manual-events/0.1.0"

KINDS = {
    "user_marker",
    "context",
    "answer",
    "acknowledgment",
    "reported_action",
    "outcome",
}
REFERENCE_TYPES = {
    "answer": {"question"},
    "acknowledgment": {"recommendation"},
    "outcome": {"reported_action", "observed_action"},
}


class ManualEventError(ValueError):
    """A proposed event conflicts with the manual evidence contract."""


def _timestamp(value: str | None, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value:
        raise ManualEventError("Time requires an explicit offset-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManualEventError("Malformed event timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManualEventError("Naive event timestamp")
    return parsed.astimezone(timezone.utc)


def create_manual_event(
    *,
    subject_id: str,
    event_kind: str,
    payload: dict[str, Any],
    recorded_at: str,
    occurrence_start: str | None = None,
    occurrence_end: str | None = None,
    known_at: str | None = None,
    reference_event: dict | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
) -> dict:
    """Build a draft for a caller to validate and persist separately.

    Answers, acknowledgments and outcomes require an explicit typed parent.
    Actions may occur without a preceding recommendation. An outcome is not
    synthesized merely because an action was recorded.
    """
    if event_kind not in KINDS:
        raise ManualEventError("Unsupported manual event kind")
    if not isinstance(subject_id, str) or not subject_id:
        raise ManualEventError("A subject identifier is required")
    if type(payload) is not dict:
        raise ManualEventError("Event payload must be an object")
    if not isinstance(event_id, (str, type(None))) or event_id == "":
        raise ManualEventError("Event identity is invalid")
    if session_id is not None and (not isinstance(session_id, str) or not session_id):
        raise ManualEventError("Invalid optional session reference")
    _timestamp(recorded_at)
    start = _timestamp(occurrence_start, optional=True)
    end = _timestamp(occurrence_end, optional=True)
    _timestamp(known_at, optional=True)
    if end is not None and start is None:
        raise ManualEventError("An occurrence end requires an occurrence start")
    if end is not None and end < start:
        raise ManualEventError("An event cannot end before it begins")

    required = REFERENCE_TYPES.get(event_kind)
    if required is not None and reference_event is None:
        raise ManualEventError("A typed parent event is required")
    related_ids = []
    if reference_event is not None:
        if not isinstance(reference_event, dict):
            raise ManualEventError("Reference event must be an object")
        if reference_event.get("record_type") != "event":
            raise ManualEventError("Reference is not an event")
        if reference_event.get("subject_id") != subject_id:
            raise ManualEventError("Cross-subject event linkage is forbidden")
        if required is not None and reference_event.get("event_kind") not in required:
            raise ManualEventError("The parent event has an incompatible kind")
        ref_id = reference_event.get("id")
        if not isinstance(ref_id, str) or not ref_id:
            raise ManualEventError("Parent event identity is missing")
        related_ids.append(ref_id)
    if event_kind in {"user_marker", "context"} and reference_event is not None:
        raise ManualEventError("Standalone context and marker drafts do not take a parent")

    # Manual action is a reported fact, never a sensor-observed action.
    # No automatic prompts, recommendations or interventions are created.
    return {
        "schema_version": CONTRACT_VERSION,
        "record_type": "event",
        "id": event_id or f"coach-manual:{uuid4()}",
        "subject_id": subject_id,
        "processing_version": PROCESSING_VERSION,
        "event_kind": event_kind,
        "occurrence_start": occurrence_start,
        "occurrence_end": occurrence_end,
        "known_at": known_at,
        "recorded_at": recorded_at,
        "source": "coach:manual",
        "source_revision_id": None,
        "session_id": session_id,
        "related_ids": related_ids,
        "payload": dict(payload),
        "epistemic_type": "reported",
        "quality_flags": [],
    }
