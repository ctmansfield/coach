"""Offline, source-aware replay of contract 1.0.0 records.

The renderer reads an exported bundle. It does not acquire measurements, infer
recovery, send notifications, or turn annotations into performed actions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import math
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_VERSION = "1.0.0"
RENDERER_VERSION = "coach-replay/1.0.0"
DEFAULT_SCHEMA = Path(__file__).with_name("schemas") / "v1.schema.json"
RECORD_COLLECTIONS = {
    "observations": "observation",
    "events": "event",
    "sessions": "session",
    "source_revisions": "source_revision",
}
EPISTEMIC_LABELS = {
    "measured": "Measured",
    "vendor_derived": "Vendor derived",
    "derived": "Derived",
    "imputed": "Imputed",
    "inferred": "Inferred",
    "clinical_interpretation": "Clinical interpretation",
    "reported": "Reported",
}
METADATA_KEYS = ("evidence_level", "timing_policy", "processing_version", "assumptions")


class ReplayInputError(ValueError):
    """The bundle cannot be displayed without losing its stated meaning."""


def _time(value: Any, label: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ReplayInputError(f"{label} must be an offset-aware timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReplayInputError(f"{label} is not a valid timestamp") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ReplayInputError(f"{label} has no timezone offset")
    return result.astimezone(timezone.utc)


def _interval(start: Any, end: Any, label: str, *, start_nullable: bool = False):
    first = _time(start, f"{label}.start", nullable=start_nullable)
    last = _time(end, f"{label}.end", nullable=True)
    if first is not None and last is not None and last < first:
        raise ReplayInputError(f"{label} ends before it starts")
    return first, last


def _reject_constant(value: str):
    raise ReplayInputError(f"Non-finite JSON number {value} is unsupported")


def _metadata(bundle: dict) -> dict:
    metadata = bundle.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ReplayInputError("metadata must be an object")
    result = dict(metadata)
    for key in METADATA_KEYS:
        if key in bundle:
            if key in result and result[key] != bundle[key]:
                raise ReplayInputError(f"Conflicting bundle metadata: {key}")
            result[key] = bundle[key]
    import_summaries = result.get("import_summaries", [])
    if not isinstance(import_summaries, list) or not all(
        isinstance(x, dict) for x in import_summaries
    ):
        raise ReplayInputError("import_summaries must be an array of objects")
    assumptions = result.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(
        isinstance(x, str) for x in assumptions
    ):
        raise ReplayInputError("assumptions must be an array of strings")
    return result


def _validator(schema_path: str | Path | None = None):
    path = Path(
        schema_path or os.getenv("COACH_PHYSIOLOGY_SCHEMA_PATH") or DEFAULT_SCHEMA
    )
    try:
        schema = json.loads(path.read_text(), parse_constant=_reject_constant)
    except OSError as error:
        raise ReplayInputError(
            "Contract schema is unavailable; install the compatible schema or pass --schema"
        ) from error
    if schema.get("$id") != "urn:coach-mother:physiology:1.0.0":
        raise ReplayInputError("The supplied contract schema is not version 1.0.0")
    return {
        kind: Draft202012Validator(
            {"$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"},
            format_checker=FormatChecker(),
        )
        for kind in RECORD_COLLECTIONS.values()
    }


def validate_bundle(bundle: dict, *, schema_path: str | Path | None = None) -> None:
    """Validate canonical records and the references required by this view.

    The shared schema owns record fields and enums. The checks here concern
    replay intervals, complete references, and coverage-display integrity.
    """
    if not isinstance(bundle, dict) or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ReplayInputError("Replay requires schema_version 1.0.0")
    if not isinstance(bundle.get("subject_id"), str) or not bundle["subject_id"]:
        raise ReplayInputError("Replay requires a subject_id")
    if bundle.get("streams"):
        raise ReplayInputError(
            "This scalar replay cannot display nonempty stream segments; a stream-capable viewer is required"
        )
    start, end = _interval(bundle.get("start"), bundle.get("end"), "bundle")
    if end is None or end <= start:
        raise ReplayInputError("Replay end must be later than start")
    _metadata(bundle)
    validators = _validator(schema_path)
    ids: set[str] = set()
    for collection, kind in RECORD_COLLECTIONS.items():
        records = bundle.get(collection)
        if not isinstance(records, list):
            raise ReplayInputError(
                f"{collection} must be an array, including when empty"
            )
        for index, record in enumerate(records):
            errors = list(validators[kind].iter_errors(record))
            if errors:
                error = errors[0]
                field = ".".join(str(x) for x in error.absolute_path) or "record"
                # Do not echo the raw source record in an exception or CLI log.
                raise ReplayInputError(
                    f"{collection}[{index}].{field} violates contract assertion {error.validator}"
                )
            if record["subject_id"] != bundle["subject_id"]:
                raise ReplayInputError(
                    f"{collection}[{index}] belongs to another subject"
                )
            if record["id"] in ids:
                raise ReplayInputError("Duplicate record ID in replay bundle")
            ids.add(record["id"])
    revisions = {r["id"] for r in bundle["source_revisions"]}
    sessions = {r["id"] for r in bundle["sessions"]}

    def require_revision(reference):
        if reference is not None and reference not in revisions:
            raise ReplayInputError(
                "A source revision referenced by a displayed record is missing"
            )

    for record in bundle["observations"]:
        require_revision(record["source_revision_id"])
        for reference in record["lineage"]:
            require_revision(reference)
        if record["session_id"] is not None and record["session_id"] not in sessions:
            raise ReplayInputError(
                "An observation references a session missing from the bundle"
            )
        _interval(record["measurement_start"], record["measurement_end"], "observation")
        for field in ("value", "original_value"):
            value = record[field]
            if isinstance(value, float) and not math.isfinite(value):
                raise ReplayInputError(f"Observation {field} is non-finite")
    for record in bundle["events"]:
        require_revision(record["source_revision_id"])
        if record["session_id"] is not None and record["session_id"] not in sessions:
            raise ReplayInputError(
                "An event references a session missing from the bundle"
            )
        _interval(
            record["occurrence_start"],
            record["occurrence_end"],
            "event",
            start_nullable=True,
        )
    for record in bundle["sessions"]:
        _interval(record["start"], record["end"], "session")
        for reference in record["source_revision_ids"]:
            require_revision(reference)
    coverage = bundle.get("coverage")
    if not isinstance(coverage, list):
        raise ReplayInputError("coverage must be an array, including when unknown")
    for index, row in enumerate(coverage):
        label = f"coverage[{index}]"
        if not isinstance(row, dict):
            raise ReplayInputError(f"{label} must be an object")
        required = {
            "channel",
            "source_instance",
            "start",
            "end",
            "count",
            "valid_count",
            "expected_cadence_seconds",
            "gaps",
            "quality_flags",
            "status",
        }
        if not required.issubset(row):
            raise ReplayInputError(f"{label} is missing required coverage fields")
        for name in ("channel", "source_instance"):
            if not isinstance(row.get(name), str) or not row[name]:
                raise ReplayInputError(f"{label}.{name} must be a nonempty string")
        if row.get("status") not in {"observed", "partial", "absent", "unknown"}:
            raise ReplayInputError(f"{label}.status is unsupported")
        first, last = _interval(row.get("start"), row.get("end"), label)
        if last is None or last <= first:
            raise ReplayInputError(f"{label} must cover a positive interval")
        for name in ("count", "valid_count"):
            if type(row.get(name)) is not int or row[name] < 0:
                raise ReplayInputError(f"{label}.{name} must be a nonnegative integer")
        if row["valid_count"] > row["count"]:
            raise ReplayInputError(f"{label}.valid_count exceeds count")
        if row["status"] == "absent" and row["count"] != 0:
            raise ReplayInputError(f"{label} cannot be absent with records")
        cadence = row.get("expected_cadence_seconds")
        if cadence is not None and (
            type(cadence) not in (float, int)
            or (isinstance(cadence, float) and not math.isfinite(cadence))
            or cadence <= 0
        ):
            raise ReplayInputError(
                f"{label}.expected_cadence_seconds must be positive or null"
            )
        if not isinstance(row.get("quality_flags"), list) or not all(
            isinstance(x, str) for x in row["quality_flags"]
        ):
            raise ReplayInputError(f"{label}.quality_flags must be an array of strings")
        if not isinstance(row.get("gaps"), list):
            raise ReplayInputError(f"{label}.gaps must be an array")
        for gap in row["gaps"]:
            if not isinstance(gap, dict) or not isinstance(gap.get("reason"), str):
                raise ReplayInputError(f"{label} has a malformed gap")
            gap_start, gap_end = _interval(gap.get("start"), gap.get("end"), "gap")
            if (
                gap_end is None
                or gap_end <= gap_start
                or gap_start < first
                or gap_end > last
            ):
                raise ReplayInputError(f"{label} has a gap outside its interval")


def _text(value: Any) -> str:
    if value is None:
        return '<span class="unknown">Unknown</span>'
    if isinstance(value, bool):
        return "true" if value else "false"
    return escape(str(value), quote=True)


def _json(value: Any) -> str:
    return escape(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), quote=True
    )


def _anchor(kind: str, record_id: str) -> str:
    return kind + "-" + hashlib.sha256(record_id.encode()).hexdigest()[:24]


def _flags(values: list[str]) -> str:
    return (
        " ".join(f'<span class="flag">{_text(value)}</span>' for value in values)
        or '<span class="muted">None recorded</span>'
    )


def _source_link(reference: str | None) -> str:
    if reference is None:
        return '<span class="unknown">No source revision linked</span>'
    return (
        f'<a href="#{_anchor("source", reference)}"><code>{_text(reference)}</code></a>'
    )


def _value(record: dict) -> str:
    if record["value_status"] != "valid":
        return (
            f'<strong class="unknown">{_text(record["value_status"].title())}</strong>'
        )
    unit = _text(record["unit"]) if record["unit"] is not None else "unit unknown"
    return (
        f'<strong>{_text(record["value"])}</strong> <span class="muted">{unit}</span>'
    )


def _table(headings: list[str], rows: list[str], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{escape(empty)}</p>'
    head = "".join(f'<th scope="col">{escape(h)}</th>' for h in headings)
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _timeline(bundle: dict, revision_index: dict) -> str:
    start = _time(bundle["start"], "start")
    end = _time(bundle["end"], "end")
    span = (end - start).total_seconds()
    lanes: dict[tuple, list] = {}
    for record in bundle["observations"]:
        source = revision_index[record["source_revision_id"]]["source_instance"]
        key = (
            record["channel"],
            source,
            record["epistemic_type"],
            record["unit"] or "unit unknown",
        )
        lanes.setdefault(key, []).append(record)
    for row in bundle["coverage"]:
        if not any(
            key[:2] == (row["channel"], row["source_instance"]) for key in lanes
        ):
            lanes[(row["channel"], row["source_instance"], "coverage_only", "")] = []

    def position(instant):
        return max(0.0, min(100.0, (instant - start).total_seconds() / span * 100))

    rows = []
    for key in sorted(lanes):
        channel, source, epistemic, unit = key
        records = lanes[key]
        marks = []
        coverage = [
            r
            for r in bundle["coverage"]
            if (r["channel"], r["source_instance"]) == key[:2]
        ]
        for coverage_row in coverage:
            for gap in coverage_row["gaps"]:
                first, last = _interval(gap["start"], gap["end"], "gap")
                if last <= start or first >= end:
                    continue
                left, right = position(first), position(last)
                label = f"Gap: {gap['start']} to {gap['end']} — {gap['reason']}"
                marks.append(
                    f'<span class="gap" style="left:{left:.6f}%;width:{right-left:.6f}%" title="{escape(label, quote=True)}"></span>'
                )
        for record in sorted(
            records, key=lambda r: _time(r["measurement_start"], "measurement_start")
        ):
            first, last = _interval(
                record["measurement_start"], record["measurement_end"], "observation"
            )
            if (last or first) < start or first > end:
                continue
            left = position(first)
            value = (
                record["value"]
                if record["value_status"] == "valid"
                else record["value_status"]
            )
            label = f"{channel}: {value} {record['unit'] or '(unit unknown)'}; {record['measurement_start']}; {epistemic}; source revision {record['source_revision_id']}"
            css = (
                "mark "
                + ("valid " if record["value_status"] == "valid" else "not-valid ")
                + ("flagged " if record["quality_flags"] else "")
                + epistemic
            )
            if last is not None and last > first:
                css += " interval"
                style = f"left:{left:.6f}%;width:{position(last)-left:.6f}%"
                symbol = ""
            else:
                style = f"left:{left:.6f}%"
                symbol = "●" if record["value_status"] == "valid" else "×"
            marks.append(
                f'<a class="{css}" href="#{_anchor("observation", record["id"])}" style="{style}" title="{escape(label, quote=True)}" aria-label="{escape(label, quote=True)}">{symbol}</a>'
            )
        if not records:
            states = ", ".join(sorted({r["status"] for r in coverage})) or "unknown"
            marks.append(
                f'<span class="lane-empty">{escape(states)} — no observations supplied</span>'
            )
        label = EPISTEMIC_LABELS.get(epistemic, "Coverage")
        rows.append(
            f'<div class="timeline-row"><div class="lane-label"><strong>{_text(channel)}</strong><small>{_text(source)} · {escape(label)}{(" · " + _text(unit)) if unit else ""}</small></div><div class="track">{"".join(marks)}</div></div>'
        )
    # Event kinds receive independent lanes. Unknown occurrence times are not
    # silently substituted with recorded_at on the occurrence-time axis.
    for kind in sorted({r["event_kind"] for r in bundle["events"]}):
        marks = []
        for record in bundle["events"]:
            if record["event_kind"] != kind or record["occurrence_start"] is None:
                continue
            first, last = _interval(
                record["occurrence_start"], record["occurrence_end"], "event"
            )
            if (last or first) < start or first > end:
                continue
            left = position(first)
            style = f"left:{left:.6f}%"
            css = "event-mark"
            if last is not None and last > first:
                style += f";width:{position(last)-left:.6f}%"
                css += " interval"
            label = f"{kind}; occurrence {record['occurrence_start']}; known {record['known_at'] or 'unknown'}"
            marks.append(
                f'<a class="{css}" style="{style}" href="#{_anchor("event", record["id"])}" title="{escape(label, quote=True)}" aria-label="{escape(label, quote=True)}">◆</a>'
            )
        if marks:
            rows.append(
                f'<div class="timeline-row"><div class="lane-label"><strong>{_text(kind)}</strong><small>Event occurrence</small></div><div class="track">{"".join(marks)}</div></div>'
            )
    if not rows:
        return '<p class="empty">No observations or expected-channel coverage supplied. Coverage is unknown.</p>'
    midpoint = start + (end - start) / 2
    stamps = [point.strftime("%d %b %H:%M UTC") for point in (start, midpoint, end)]
    axis = f'<div class="timeline-row axis"><div class="lane-label">Measurement / occurrence time</div><div class="axis-labels"><span>{stamps[0]}</span><span>{stamps[1]}</span><span>{stamps[2]}</span></div></div>'
    return (
        '<div class="timeline-scroll"><div class="timeline">'
        + axis
        + "".join(rows)
        + '</div></div><p class="muted">Points remain discrete. Bars show recorded intervals only; no interpolation is drawn. Hatched regions are supplied coverage gaps. Events with unknown occurrence times remain in the event table.</p>'
    )


CSS = """
:root{color-scheme:light;--ink:#163243;--muted:#566975;--line:#d9e2e8;--blue:#146c94;--paper:#f5f8fa}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1500px;margin:0 auto;padding:28px}header{border-top:5px solid var(--blue);background:white;padding:24px 28px;border-radius:8px}
h1{font-size:30px;margin:3px 0 8px;letter-spacing:-.025em}h2{font-size:21px;margin:0 0 10px}h3{font-size:16px;margin:12px 0 6px}p{margin:8px 0}.eyebrow{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
section{background:white;margin:20px 0;padding:24px;border:1px solid var(--line);border-radius:8px}a{color:#0b638e;text-decoration-thickness:1px;text-underline-offset:2px}code{font-size:12px;overflow-wrap:anywhere}
.muted,small{color:var(--muted)}small{display:block}.unknown{color:#775513}.flag,.badge{display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;border-radius:5px;background:#edf2f6;font-size:12px;overflow-wrap:anywhere}.flag{background:#fff1d7;color:#705011}.badge{background:#e6f2f7;color:#15516c}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:14px;margin-top:18px}.metric{padding:12px 15px;background:#f5f8fa;border-radius:5px}.metric strong{display:block;font-size:24px}.metric span{font-size:12px;color:var(--muted)}
.table-scroll,.timeline-scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;background:#f1f5f7}th,td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}td{min-width:105px}tr:target{background:#fff4d9}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;margin:6px 0;max-width:720px}details{margin-top:5px}summary{cursor:pointer;color:var(--blue)}.empty{padding:16px;background:#f7f8fa;border-left:3px solid #a6b8c2}
.timeline{min-width:850px;padding-right:10px}.timeline-row{display:grid;grid-template-columns:250px 1fr;min-height:61px;border-bottom:1px solid #e8eef1}.lane-label{padding:10px 14px 10px 0;font-size:13px;overflow-wrap:anywhere}.lane-label small{font-size:11px}.track{position:relative;min-height:60px;background:repeating-linear-gradient(90deg,transparent,transparent calc(25% - 1px),#e9eff3 calc(25% - 1px),#e9eff3 25%)}
.axis{min-height:38px;border:0}.axis-labels{display:flex;justify-content:space-between;align-items:center;font-size:10px;color:var(--muted)}.mark,.event-mark{position:absolute;top:22px;text-decoration:none;line-height:18px;transform:translateX(-50%);color:var(--blue);z-index:2;font-size:17px}.mark:hover,.event-mark:hover{outline:2px solid #d1a143;outline-offset:3px}.mark.interval,.event-mark.interval{top:27px;height:9px;min-width:1px;background:var(--blue);transform:none;border-radius:2px;color:transparent}.mark.imputed{color:#8552a0}.mark.imputed.interval{background:#8552a0}.mark.inferred,.mark.clinical_interpretation{color:#92673f}.mark.inferred.interval,.mark.clinical_interpretation.interval{background:#92673f}.mark.vendor_derived{color:#287e77}.mark.vendor_derived.interval{background:#287e77}.mark.not-valid{color:#9b5d35}.mark.flagged{outline:1px solid #cf991e;outline-offset:2px}.event-mark{color:#777165}.event-mark.interval{background:#777165}
.gap{position:absolute;top:7px;bottom:7px;background:repeating-linear-gradient(135deg,#fff5e5,#fff5e5 4px,#eedfca 4px,#eedfca 6px);z-index:0}.lane-empty{position:absolute;left:12px;top:20px;font-size:12px;color:#775513;z-index:1}.status-absent,.status-unknown{color:#775513}footer{padding:8px 4px;color:var(--muted);font-size:12px}
@media(max-width:650px){main{padding:12px}header,section{padding:16px}h1{font-size:25px}.metrics{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:white}main{padding:0}section{break-inside:avoid}.table-scroll,.timeline-scroll{overflow:visible}.timeline{min-width:0}.timeline-row{grid-template-columns:180px 1fr}details{display:block}th,td{padding:6px;font-size:10px}}
"""


def render_replay(
    bundle: dict,
    *,
    schema_path: str | Path | None = None,
    title: str = "Physiology replay",
) -> str:
    """Return self-contained HTML without modifying the input or embedding raw artifacts."""
    validate_bundle(bundle, schema_path=schema_path)
    metadata = _metadata(bundle)
    revisions = {r["id"]: r for r in bundle["source_revisions"]}
    unknown_availability = sum(
        r["source_available_at"] is None for r in bundle["observations"]
    )
    source_count = len({r["source_instance"] for r in bundle["source_revisions"]})
    flagged_count = sum(bool(r["quality_flags"]) for r in bundle["observations"])
    evidence = metadata.get("evidence_level", "unspecified")
    parts = [
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{_text(title)}</title><style>{CSS}</style></head><body><main>'
    ]
    parts.append(
        f'<header><div class="eyebrow">Coach · synchronized evidence</div><h1>{_text(title)}</h1><p>Subject <code>{_text(bundle["subject_id"])}</code> · <span class="badge">Evidence: {_text(evidence)}</span></p><p>{_text(bundle["start"])} → {_text(bundle["end"])}</p><div class="metrics">'
    )
    for count, label in [
        (len(bundle["observations"]), "Observation records"),
        (source_count, "Source instances"),
        (flagged_count, "Records with quality flags"),
        (unknown_availability, "Unknown source availability"),
    ]:
        parts.append(
            f'<div class="metric"><strong>{count}</strong><span>{label}</span></div>'
        )
    parts.append(
        '</div><p class="muted">Counts describe records in this bundle. Relayed copies and repeated revisions are not evidence of independent sensors or independent episodes.</p></header>'
    )
    parts.append(
        "<section><h2>Synchronized timeline</h2>"
        + _timeline(bundle, revisions)
        + "</section>"
    )
    coverage_rows = []
    for row in bundle["coverage"]:
        gaps = "".join(
            f'<li>{_text(gap["start"])} → {_text(gap["end"])}: {_text(gap["reason"])}</li>'
            for gap in row["gaps"]
        )
        gap_text = (
            f"<ul>{gaps}</ul>"
            if gaps
            else '<span class="muted">No gaps supplied</span>'
        )
        cadence = (
            f'{_text(row["expected_cadence_seconds"])} s'
            if row["expected_cadence_seconds"] is not None
            else '<span class="unknown">Unknown / not specified</span>'
        )
        coverage_rows.append(
            f'<tr><td><strong>{_text(row["channel"])}</strong><small>{_text(row["source_instance"])}</small></td><td class="status-{row["status"]}">{row["status"]}</td><td>{row["count"]} / {row["valid_count"]}</td><td>{_text(row["start"])}<br>{_text(row["end"])}</td><td>{cadence}</td><td>{gap_text}{_flags(row["quality_flags"])}</td></tr>'
        )
    parts.append(
        '<section><h2>Coverage and gaps</h2><p class="muted">Counts and expected cadence are supplied by the bundle producer. An empty gap list does not establish uninterrupted sampling. Expected channels remain visible when absent.</p>'
        + _table(
            [
                "Channel / source",
                "Status",
                "Records / valid",
                "Interval",
                "Expected cadence",
                "Gaps / quality",
            ],
            coverage_rows,
            "Coverage was not supplied; continuity and expected-channel completeness are unknown.",
        )
        + "</section>"
    )
    observation_rows = []
    for record in sorted(
        bundle["observations"],
        key=lambda r: (_time(r["measurement_start"], "measurement_start"), r["id"]),
    ):
        source = revisions[record["source_revision_id"]]
        end = record["measurement_end"]
        measurement = _text(record["measurement_start"]) + (
            "<br>→ " + _text(end)
            if end
            else "<small>Discrete time; no interval end supplied</small>"
        )
        timing = f'<small>Available: {_text(record["source_available_at"])}</small><small>First seen: {_text(record["first_seen_at"])}</small><small>Ingested: {_text(record["ingested_at"])}</small>'
        detail_fields = {
            k: record[k]
            for k in (
                "native_type",
                "method",
                "device_id",
                "recording_app",
                "body_site",
                "specimen",
                "session_id",
                "measurement_group_id",
                "processing_version",
                "clock",
                "metadata",
            )
        }
        detail = (
            "<details><summary>Method, clock and processing</summary><pre>"
            + _json(detail_fields)
            + "</pre></details>"
        )
        lineage = "".join(
            "<small>Lineage: " + _source_link(reference) + "</small>"
            for reference in record["lineage"]
            if reference != record["source_revision_id"]
        )
        observation_rows.append(
            f'<tr id="{_anchor("observation", record["id"])}"><td><code>{_text(record["id"])}</code><small>{_text(record["channel"])}</small></td><td>{measurement}{timing}</td><td>{_value(record)}<small>Original: {_text(record["original_value"])} {_text(record["original_unit"])}</small></td><td><span class="badge">{EPISTEMIC_LABELS[record["epistemic_type"]]}</span><small>Status: {_text(record["value_status"])}</small>{_flags(record["quality_flags"])}</td><td>{_text(source["source_instance"])}<br>{_source_link(record["source_revision_id"])}{lineage}{detail}</td></tr>'
        )
    parts.append(
        '<section><h2>Observations</h2><p class="muted">Every supplied record is listed, including records outside the selected timeline interval. Unknown, invalid and unobserved values stay distinct from zero.</p>'
        + _table(
            [
                "Record / channel",
                "Measurement and knowledge times",
                "Value",
                "Evidence / quality",
                "Source revision / processing",
            ],
            observation_rows,
            "No observation records supplied.",
        )
        + "</section>"
    )
    event_rows = []
    for record in sorted(
        bundle["events"],
        key=lambda r: (
            _time(r["occurrence_start"] or r["recorded_at"], "event sort time"),
            r["id"],
        ),
    ):
        occurrence = _text(record["occurrence_start"]) + (
            "<br>→ " + _text(record["occurrence_end"])
            if record["occurrence_end"]
            else ""
        )
        event_rows.append(
            f'<tr id="{_anchor("event", record["id"])}"><td><strong>{_text(record["event_kind"])}</strong><small>{_text(record["id"])}</small><span class="badge">{EPISTEMIC_LABELS[record["epistemic_type"]]}</span></td><td>{occurrence}<small>Known: {_text(record["known_at"])}</small><small>Recorded: {_text(record["recorded_at"])}</small></td><td><pre>{_json(record["payload"])}</pre>{_flags(record["quality_flags"])}</td><td>{_text(record["source"])}<br>{_source_link(record["source_revision_id"])}<small>Session: {_text(record["session_id"])}</small><small>Related IDs: {_text(", ".join(record["related_ids"]) or None)}</small><small>Processing: {_text(record["processing_version"])}</small></td></tr>'
        )
    parts.append(
        '<section><h2>Context, recommendations, actions and outcomes</h2><p class="muted">Each event kind is retained separately. Acknowledgment does not establish action. Missing answers and missing outcomes remain unknown. Events with unknown occurrence times are listed by recorded time without placing them on the occurrence timeline.</p>'
        + _table(
            [
                "Event kind / evidence",
                "Occurrence and knowledge times",
                "Recorded payload / quality",
                "Source / relationships",
            ],
            event_rows,
            "No context or action events supplied.",
        )
        + "</section>"
    )
    session_rows = []
    for record in sorted(
        bundle["sessions"], key=lambda r: _time(r["start"], "session start")
    ):
        details = {
            k: record[k]
            for k in (
                "recording_app",
                "firmware",
                "configuration",
                "body_site",
                "clock",
                "garment",
                "processing_version",
            )
        }
        session_rows.append(
            f'<tr><td><code>{_text(record["id"])}</code></td><td>{_text(record["start"])}<br>→ {_text(record["end"])}</td><td>{_text(", ".join(record["device_ids"]) or None)}<details><summary>Configuration / clock / garment</summary><pre>{_json(details)}</pre></details></td><td>{"<br>".join(_source_link(x) for x in record["source_revision_ids"]) or _text(None)}</td></tr>'
        )
    parts.append(
        "<section><h2>Recording sessions</h2>"
        + _table(
            ["Session", "Interval", "Devices / configuration", "Source revisions"],
            session_rows,
            "No recording sessions supplied.",
        )
        + "</section>"
    )
    source_rows = []
    for record in sorted(
        bundle["source_revisions"],
        key=lambda r: (r["source_instance"], r["collection"], r["id"]),
    ):
        source_rows.append(
            f'<tr id="{_anchor("source", record["id"])}"><td><code>{_text(record["id"])}</code><small>{_text(record["source_instance"])} / {_text(record["collection"])}</small><small>Native ID: {_text(record["native_id"])}</small><small>Identity basis: {_text(record["identity_basis"])}</small></td><td><code>{_text(record["revision_hash"])}</code><small>Artifact SHA-256: <code>{_text(record["artifact_sha256"])}</code></small></td><td>Available: {_text(record["source_available_at"])}<small>Modified: {_text(record["source_modified_at"])}</small><small>First seen: {_text(record["first_seen_at"])}</small><small>Ingested: {_text(record["ingested_at"])}</small></td><td>{_flags(record["quality_flags"])}<small>Import run: {_text(record["import_run_id"])}</small><small>Processing: {_text(record["processing_version"])}</small></td></tr>'
        )
    parts.append(
        '<section><h2>Source revision manifest</h2><p class="muted">These references identify the preserved source revisions. Original raw records and source artifacts are not embedded in this HTML.</p>'
        + _table(
            [
                "Revision / source",
                "Content hashes",
                "Source and system times",
                "Quality / import",
            ],
            source_rows,
            "No source revisions supplied.",
        )
        + "</section>"
    )
    summary_rows = [
        "<tr><td>"
        + _text(item.get("source_instance"))
        + "<small>"
        + _text(item.get("collection"))
        + "</small></td><td>"
        + _text(item.get("status"))
        + "<small>"
        + _text(item.get("run_id"))
        + "</small></td><td><pre>"
        + _json(item.get("counts", {}))
        + "</pre></td><td>"
        + _text(item.get("adapter_version"))
        + "<small>"
        + _text(item.get("error"))
        + "</small></td></tr>"
        for item in metadata.get("import_summaries", [])
    ]
    parts.append(
        '<section><h2>Import accounting</h2><p class="muted">These are whole-import counts, not counts limited to the displayed interval. Repeated sightings, rejected and unsupported records, and incomplete imports remain visible.</p>'
        + _table(
            ["Source / collection", "State / run", "Accounting", "Adapter / error"],
            summary_rows,
            "No import summaries supplied.",
        )
        + "</section>"
    )
    assumptions = metadata.get("assumptions", [])
    assumption_html = (
        "<ul>" + "".join(f"<li>{_text(item)}</li>" for item in assumptions) + "</ul>"
        if assumptions
        else '<p class="unknown">No timing or processing assumptions were supplied.</p>'
    )
    parts.append(
        "<section><h2>Timing policy and reproducibility</h2><p>Measurement time, source-supported availability, first observation by this system, and ingestion remain distinct. Unknown historical availability is shown as unknown.</p><h3>Timing policy</h3><pre>"
        + _json(metadata.get("timing_policy", "Not supplied"))
        + "</pre><h3>Declared assumptions</h3>"
        + assumption_html
        + f'<p>Bundle processing: <code>{_text(metadata.get("processing_version"))}</code><br>Contract: <code>{SCHEMA_VERSION}</code> · Renderer: <code>{RENDERER_VERSION}</code></p></section>'
    )
    parts.append(
        "<footer>This replay presents the supplied evidence and its provenance. It does not compute readiness, classify dysfunction, or establish a physiological recovery outcome.</footer></main></body></html>"
    )
    return "\n".join(parts)


def create_user_marker(
    *,
    subject_id: str,
    text: str,
    recorded_at: str,
    occurrence_start: str | None = None,
    occurrence_end: str | None = None,
    known_at: str | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
    related_ids: list[str] | None = None,
    schema_path: str | Path | None = None,
) -> dict:
    """Construct a reported factual marker; the caller must archive it separately."""
    if not isinstance(text, str) or not text.strip():
        raise ReplayInputError("A user marker requires nonempty factual text")
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "event",
        "id": event_id or f"user-marker:{uuid4()}",
        "subject_id": subject_id,
        "event_kind": "user_marker",
        "occurrence_start": occurrence_start,
        "occurrence_end": occurrence_end,
        "known_at": known_at,
        "recorded_at": recorded_at,
        "source": "coach:user_marker",
        "source_revision_id": None,
        "session_id": session_id,
        "related_ids": list(related_ids or []),
        "payload": {"text": text},
        "epistemic_type": "reported",
        "quality_flags": [],
        "processing_version": RENDERER_VERSION,
    }
    if list(_validator(schema_path)["event"].iter_errors(record)):
        raise ReplayInputError("User marker does not satisfy the shared event contract")
    _interval(occurrence_start, occurrence_end, "user marker", start_nullable=True)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render an offline contract 1.0.0 physiology replay"
    )
    parser.add_argument(
        "--input", required=True, type=Path, help="Versioned JSON replay bundle"
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New standalone HTML file; existing files are preserved",
    )
    parser.add_argument(
        "--schema", type=Path, default=None, help="Shared contract schema path"
    )
    parser.add_argument("--title", default="Physiology replay")
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(args.input.read_text(), parse_constant=_reject_constant)
        html = render_replay(bundle, schema_path=args.schema, title=args.title)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(html)
    except (OSError, ValueError) as error:
        print(f"Replay not written: {error}", file=sys.stderr)
        return 2
    print(
        f"Wrote {args.output}: {len(bundle['observations'])} observation records, {len(bundle['events'])} events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
