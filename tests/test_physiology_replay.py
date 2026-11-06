"""Synthetic-only replay tests; no device or network access is used."""

import copy
from html.parser import HTMLParser
import json
import os
from pathlib import Path

import pytest

from coach_app.physiology.replay import (
    DEFAULT_SCHEMA,
    ReplayInputError,
    create_user_marker,
    main,
    render_replay,
    validate_bundle,
)


STAMP = "2026-11-07T00:00:00Z"
SEEN = "2026-11-07T01:00:00Z"


@pytest.fixture
def schema_path():
    path = Path(os.getenv("COACH_PHYSIOLOGY_SCHEMA_PATH") or DEFAULT_SCHEMA)
    assert (
        path.is_file()
    ), "Install the shared schema or set COACH_PHYSIOLOGY_SCHEMA_PATH for isolated checks"
    return path


def source(record_id="source-cgm", source_instance="nightscout-fixture"):
    return {
        "schema_version": "1.0.0",
        "record_type": "source_revision",
        "id": record_id,
        "subject_id": "synthetic-subject",
        "processing_version": "fixture/1",
        "source_instance": source_instance,
        "collection": "entries",
        "source_key": record_id,
        "native_id": "native-fixture-1",
        "revision_hash": "a" * 64,
        "artifact_sha256": "b" * 64,
        "original_record": {"private_raw_only": "DO_NOT_EMBED_RAW_ARTIFACT"},
        "first_seen_at": SEEN,
        "ingested_at": SEEN,
        "source_available_at": None,
        "source_modified_at": None,
        "import_run_id": "fixture-import",
        "identity_basis": "native_id",
        "quality_flags": [],
    }


def observation(**changes):
    record = {
        "schema_version": "1.0.0",
        "record_type": "observation",
        "id": "observation-zero",
        "subject_id": "synthetic-subject",
        "source_revision_id": "source-cgm",
        "channel": "glucose",
        "native_type": "sgv",
        "measurement_start": "2026-11-07T10:00:00+10:00",
        "measurement_end": None,
        "source_available_at": None,
        "first_seen_at": SEEN,
        "ingested_at": SEEN,
        "original_value": 0,
        "original_unit": "mg/dL",
        "value": 0,
        "unit": "mg/dL",
        "value_status": "valid",
        "epistemic_type": "measured",
        "method": "fixture",
        "device_id": "fixture-sensor",
        "recording_app": "fixture-app",
        "body_site": None,
        "specimen": None,
        "session_id": None,
        "measurement_group_id": None,
        "quality_flags": [],
        "processing_version": "fixture/1",
        "lineage": ["source-cgm"],
        "metadata": {},
        "clock": {"timezone_basis": "explicit_offset"},
    }
    record.update(changes)
    return record


def event(event_id="event-question", kind="question", **changes):
    record = {
        "schema_version": "1.0.0",
        "record_type": "event",
        "id": event_id,
        "subject_id": "synthetic-subject",
        "event_kind": kind,
        "occurrence_start": "2026-11-07T00:10:00Z",
        "occurrence_end": None,
        "known_at": "2026-11-07T00:30:00Z",
        "recorded_at": SEEN,
        "source": "fixture",
        "source_revision_id": None,
        "session_id": None,
        "related_ids": [],
        "payload": {"text": "Was a workout recorded at this time?", "answer": None},
        "epistemic_type": "reported",
        "quality_flags": [],
        "processing_version": "fixture/1",
    }
    record.update(changes)
    return record


@pytest.fixture
def bundle():
    return {
        "schema_version": "1.0.0",
        "subject_id": "synthetic-subject",
        "start": STAMP,
        "end": SEEN,
        "observations": [
            observation(),
            observation(
                id="observation-missing",
                measurement_start="2026-11-07T00:05:00Z",
                value=None,
                original_value="",
                value_status="missing",
                quality_flags=["source_value_missing"],
            ),
        ],
        "events": [event()],
        "sessions": [],
        "source_revisions": [source()],
        "coverage": [
            {
                "channel": "glucose",
                "source_instance": "nightscout-fixture",
                "start": STAMP,
                "end": SEEN,
                "count": 2,
                "valid_count": 1,
                "expected_cadence_seconds": 300,
                "status": "partial",
                "quality_flags": ["incomplete_fixture"],
                "gaps": [
                    {
                        "start": "2026-11-07T00:10:00Z",
                        "end": SEEN,
                        "reason": "No supplied samples",
                    }
                ],
            },
            {
                "channel": "h10.ecg",
                "source_instance": "polar-fixture",
                "start": STAMP,
                "end": SEEN,
                "count": 0,
                "valid_count": 0,
                "expected_cadence_seconds": None,
                "status": "absent",
                "quality_flags": ["not_recorded"],
                "gaps": [],
            },
        ],
        "metadata": {
            "evidence_level": "synthetic_integration",
            "timing_policy": "Historical availability unknown",
            "processing_version": "synthetic-fixture/1",
            "assumptions": ["Synthetic records only; no wearer performance inference"],
        },
    }


class Tags(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.elements = []
        self.feed(document)

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))


def test_renderer_preserves_zero_missing_time_offsets_and_evidence(bundle, schema_path):
    untouched = copy.deepcopy(bundle)
    html = render_replay(bundle, schema_path=schema_path)
    assert bundle == untouched
    assert "synthetic_integration" in html
    assert "2026-11-07T10:00:00+10:00" in html
    assert "<strong>0</strong>" in html
    assert '<strong class="unknown">Missing</strong>' in html
    assert 'Available: <span class="unknown">Unknown</span>' in html
    assert "First seen:" in html and "Ingested:" in html
    assert "No supplied samples" in html
    assert "DO_NOT_EMBED_RAW_ARTIFACT" not in html


def test_every_observation_source_link_resolves_and_absent_channels_stay_visible(
    bundle, schema_path
):
    html = render_replay(bundle, schema_path=schema_path)
    tags = Tags(html).elements
    targets = {attrs["id"] for _, attrs in tags if "id" in attrs}
    links = [
        attrs["href"][1:]
        for tag, attrs in tags
        if tag == "a" and attrs.get("href", "").startswith("#")
    ]
    assert links
    assert all(link in targets for link in links)
    assert "h10.ecg" in html
    assert "absent — no observations supplied" in html
    assert "Unknown / not specified" in html
    # There are no generated connected curves or script-based interpolation.
    assert not {"script", "polyline", "path", "iframe"}.intersection(
        tag for tag, _ in tags
    )


def test_untrusted_strings_cannot_create_html_or_external_links(bundle, schema_path):
    attack = '<img src=x onerror="alert(1)"><script>bad()</script>'
    bundle["observations"][0].update(
        channel=attack, original_value=attack, quality_flags=[attack]
    )
    bundle["events"][0]["payload"] = {"text": attack}
    bundle["source_revisions"][0]["native_id"] = attack
    bundle["metadata"]["assumptions"].append(attack)
    html = render_replay(bundle, schema_path=schema_path, title=attack)
    tags = Tags(html).elements
    assert not {"img", "script", "iframe"}.intersection(tag for tag, _ in tags)
    assert not any("onerror" in attrs or "onclick" in attrs for _, attrs in tags)
    assert "&lt;img" in html and "&lt;script&gt;" in html
    assert all(
        attrs.get("href", "#").startswith("#") for tag, attrs in tags if tag == "a"
    )


@pytest.mark.parametrize(
    "epistemic,label",
    [
        ("measured", "Measured"),
        ("vendor_derived", "Vendor derived"),
        ("derived", "Derived"),
        ("imputed", "Imputed"),
        ("inferred", "Inferred"),
        ("clinical_interpretation", "Clinical interpretation"),
        ("reported", "Reported"),
    ],
)
def test_epistemic_categories_remain_explicit(bundle, schema_path, epistemic, label):
    bundle["observations"][0]["epistemic_type"] = epistemic
    html = render_replay(bundle, schema_path=schema_path)
    assert f'<span class="badge">{label}</span>' in html


def test_recommendations_acknowledgments_actions_and_unobserved_outcomes_are_separate(
    bundle, schema_path
):
    kinds = [
        "recommendation",
        "acknowledgment",
        "reported_action",
        "observed_action",
        "outcome",
    ]
    bundle["events"] = [
        event("event-" + kind, kind, payload={"fixture_kind": kind}) for kind in kinds
    ]
    bundle["events"][-1]["payload"] = {"value": None, "status": "unobserved"}
    html = render_replay(bundle, schema_path=schema_path)
    for kind in kinds:
        assert f"<strong>{kind}</strong>" in html
    assert "unobserved" in html
    assert "Acknowledgment does not establish action" in html
    assert len(bundle["events"]) == 5


def test_unknown_event_occurrence_is_not_positioned_at_recorded_time(
    bundle, schema_path
):
    bundle["events"] = [event(occurrence_start=None, known_at=None)]
    tags = Tags(render_replay(bundle, schema_path=schema_path)).elements
    assert not any("event-mark" in attrs.get("class", "").split() for _, attrs in tags)


def test_actual_utc_order_is_used_without_rewriting_original_offsets(
    bundle, schema_path
):
    bundle["observations"] = [
        observation(id="later-record", measurement_start="2026-11-07T00:15:00Z"),
        observation(id="earlier-record", measurement_start="2026-11-07T10:00:00+10:00"),
    ]
    html = render_replay(bundle, schema_path=schema_path)
    assert html.index("<code>earlier-record</code>") < html.index(
        "<code>later-record</code>"
    )
    assert "2026-11-07T10:00:00+10:00" in html


@pytest.mark.parametrize(
    "failure",
    [
        "missing_revision",
        "missing_lineage",
        "missing_session",
        "duplicate",
        "wrong_subject",
        "naive_time",
        "reversed_interval",
        "nonfinite",
        "missing_clock",
        "missing_value_as_zero",
    ],
)
def test_corrupt_or_incomplete_records_are_refused(bundle, schema_path, failure):
    record = bundle["observations"][0]
    if failure == "missing_revision":
        record["source_revision_id"] = "absent-revision"
    elif failure == "missing_lineage":
        record["lineage"] = ["absent-revision"]
    elif failure == "missing_session":
        record["session_id"] = "absent-session"
    elif failure == "duplicate":
        bundle["observations"].append(copy.deepcopy(record))
    elif failure == "wrong_subject":
        record["subject_id"] = "another-subject"
    elif failure == "naive_time":
        record["measurement_start"] = "2026-11-07T00:00:00"
    elif failure == "reversed_interval":
        record["measurement_end"] = "2026-11-06T23:00:00Z"
    elif failure == "nonfinite":
        record["value"] = float("nan")
    elif failure == "missing_clock":
        del record["clock"]
    else:
        record["value_status"] = "missing"
    with pytest.raises(ReplayInputError):
        render_replay(bundle, schema_path=schema_path)


def test_invalid_coverage_is_refused(bundle, schema_path):
    bundle["coverage"][0]["gaps"][0]["end"] = "2026-11-07T02:00:00Z"
    with pytest.raises(ReplayInputError, match="gap outside"):
        validate_bundle(bundle, schema_path=schema_path)


def test_missing_coverage_fields_and_unsupported_streams_are_not_silently_omitted(
    bundle, schema_path
):
    del bundle["coverage"][0]["expected_cadence_seconds"]
    with pytest.raises(ReplayInputError, match="missing required coverage"):
        validate_bundle(bundle, schema_path=schema_path)
    bundle["coverage"] = []
    bundle["streams"] = [{"id": "waveform-fixture"}]
    with pytest.raises(ReplayInputError, match="stream-capable"):
        validate_bundle(bundle, schema_path=schema_path)


def test_metadata_top_level_is_supported_but_conflicts_are_refused(bundle, schema_path):
    bundle.update(bundle.pop("metadata"))
    assert "synthetic_integration" in render_replay(bundle, schema_path=schema_path)
    bundle["metadata"] = {"evidence_level": "different"}
    with pytest.raises(ReplayInputError, match="Conflicting"):
        render_replay(bundle, schema_path=schema_path)


def test_empty_bundle_has_unknown_coverage_instead_of_a_normal_result(
    bundle, schema_path
):
    for collection in [
        "observations",
        "events",
        "sessions",
        "source_revisions",
        "coverage",
    ]:
        bundle[collection] = []
    html = render_replay(bundle, schema_path=schema_path)
    assert "Coverage is unknown" in html
    assert "continuity and expected-channel completeness are unknown" in html
    assert "No observation records supplied" in html


def test_reported_user_marker_keeps_unknown_occurrence_and_knowledge_times(schema_path):
    marker = create_user_marker(
        subject_id="synthetic-subject",
        text="Garment adjusted",
        recorded_at=SEEN,
        event_id="marker-fixture",
        schema_path=schema_path,
    )
    assert marker["event_kind"] == "user_marker"
    assert marker["epistemic_type"] == "reported"
    assert marker["occurrence_start"] is None and marker["known_at"] is None
    assert marker["source_revision_id"] is None
    assert marker["recorded_at"] == SEEN
    assert marker["payload"] == {"text": "Garment adjusted"}


def test_user_marker_rejects_naive_time_and_empty_text(schema_path):
    with pytest.raises(ReplayInputError):
        create_user_marker(
            subject_id="synthetic-subject",
            text="Marker",
            recorded_at="2026-11-07T00:00:00",
            schema_path=schema_path,
        )
    with pytest.raises(ReplayInputError):
        create_user_marker(
            subject_id="synthetic-subject",
            text=" ",
            recorded_at=SEEN,
            schema_path=schema_path,
        )


def test_cli_writes_a_reviewable_file_and_preserves_existing_output(
    bundle, schema_path, tmp_path
):
    input_path = tmp_path / "synthetic-bundle.json"
    output_path = tmp_path / "replay.html"
    input_path.write_text(json.dumps(bundle))
    argv = [
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--schema",
        str(schema_path),
    ]
    assert main(argv) == 0
    original = output_path.read_bytes()
    assert b"synthetic_integration" in original
    assert main(argv) == 2
    assert output_path.read_bytes() == original


def test_cli_invalid_input_does_not_leave_output(bundle, schema_path, tmp_path):
    bundle["schema_version"] = "unknown-version"
    input_path = tmp_path / "bad.json"
    input_path.write_text(json.dumps(bundle))
    output_path = tmp_path / "replay.html"
    assert (
        main(
            [
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--schema",
                str(schema_path),
            ]
        )
        == 2
    )
    assert not output_path.exists()
