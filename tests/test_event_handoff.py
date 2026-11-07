"""No-network acceptance tests for deterministic Coach event envelopes."""

import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from coach_app.physiology.handoff import (
    HandoffError,
    CONTENT_TYPE,
    pack_manual_event,
    save_to_outbox,
)
from coach_app.physiology.manual_events import create_manual_event


def marker():
    return create_manual_event(
        subject_id="synthetic",
        event_kind="user_marker",
        payload={"description": "adjusted electrode contact", "score": 0},
        recorded_at="2026-11-07T04:10:00Z",
        occurrence_start="2026-11-07T14:00:00+10:00",
        event_id="marker:fixture",
    )


class HandoffTests(unittest.TestCase):
    def test_exact_event_bytes_and_digest(self):
        event = marker()
        wire = pack_manual_event(event)
        obj = json.loads(wire)
        self.assertEqual(obj["envelope_version"], "1.0.0")
        self.assertEqual(obj["content_type"], CONTENT_TYPE)
        self.assertEqual(obj["encoding"], "base64")
        original = base64.b64decode(obj["event_base64"], validate=True)
        self.assertEqual(json.loads(original), event)
        self.assertEqual(hashlib.sha256(original).hexdigest(), obj["event_sha256"])
        self.assertEqual(pack_manual_event(event), wire)
        self.assertIsNone(event["source_revision_id"])

    def test_missing_and_zero_values_preserved(self):
        event = marker()
        original = json.loads(
            base64.b64decode(json.loads(pack_manual_event(event))["event_base64"])
        )
        self.assertEqual(original["payload"]["score"], 0)
        self.assertIsNone(original["known_at"])
        self.assertEqual(
            original["occurrence_start"], "2026-11-07T14:00:00+10:00"
        )

    def test_invalid_event_drafts_rejected(self):
        for changes in (
            {"source": "coach:auto"},
            {"schema_version": "2.0"},
            {"processing_version": "different/1"},
            {"record_type": "observation"},
            {"payload": {"value": float("nan")}},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(HandoffError):
                    pack_manual_event(dict(marker(), **changes))

    def test_size_limit_rejects_oversized_payload(self):
        event = marker()
        event["payload"] = {"text": "x" * (256 * 1024)}
        with self.assertRaises(HandoffError):
            pack_manual_event(event)

    def test_private_outbox_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "outbox"
            payload = pack_manual_event(marker())
            first = save_to_outbox(directory, payload)
            original_stat = first.stat()
            second = save_to_outbox(directory, payload)
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), payload)
            self.assertEqual(len(list(directory.glob("*.coach-event.json"))), 1)
            self.assertEqual(first.stat().st_ino, original_stat.st_ino)
            if os.name == "posix":
                self.assertEqual(first.stat().st_mode & 0o777, 0o600)
                self.assertEqual(directory.stat().st_mode & 0o077, 0)

    def test_different_content_does_not_replace_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            original = save_to_outbox(directory, pack_manual_event(marker()))
            changed = marker()
            changed["payload"] = {"description": "new observation"}
            altered = save_to_outbox(directory, pack_manual_event(changed))
            self.assertNotEqual(original, altered)
            self.assertEqual(len(list(directory.glob("*.coach-event.json"))), 2)

    def test_symlinked_outbox_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            actual = base / "actual"
            actual.mkdir()
            shortcut = base / "shortcut"
            shortcut.symlink_to(actual, target_is_directory=True)
            with self.assertRaises(HandoffError):
                save_to_outbox(shortcut, pack_manual_event(marker()))

    def test_existing_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = pack_manual_event(marker())
            name = hashlib.sha256(payload).hexdigest() + ".coach-event.json"
            target = base / "outside.json"
            target.write_bytes(b"original")
            (base / name).symlink_to(target)
            with self.assertRaises(HandoffError):
                save_to_outbox(base, payload)
            self.assertEqual(target.read_bytes(), b"original")

    def test_same_subject_does_not_require_parent_for_marker(self):
        payload = pack_manual_event(marker())
        self.assertTrue(payload.endswith(b"\n"))
        self.assertLess(len(payload), 400 * 1024)


if __name__ == "__main__":
    unittest.main()
