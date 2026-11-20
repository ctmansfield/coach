"""No-network acceptance for manual physiology event drafts."""

import unittest

from coach_app.physiology.manual_events import (
    ManualEventError,
    create_manual_event,
)

NOW = "2026-11-07T04:00:00Z"
SUBJECT = "synthetic-subject"


def make(kind="user_marker", **kwargs):
    defaults = {
        "subject_id": SUBJECT,
        "event_kind": kind,
        "payload": {"text": "synthetic factual statement"},
        "recorded_at": NOW,
        "event_id": "event:test",
    }
    defaults.update(kwargs)
    return create_manual_event(**defaults)


def reference(kind, ident):
    return {
        "record_type": "event",
        "subject_id": SUBJECT,
        "event_kind": kind,
        "id": ident,
    }


class ManualDraftTests(unittest.TestCase):
    def test_marker_preserves_unknown_occurrence_and_knowledge(self):
        result = make()
        self.assertIsNone(result["occurrence_start"])
        self.assertIsNone(result["known_at"])
        self.assertEqual(result["epistemic_type"], "reported")
        self.assertIsNone(result["source_revision_id"])
        self.assertEqual(result["payload"], {"text": "synthetic factual statement"})

    def test_answer_links_to_question_not_action(self):
        result = make("answer", reference_event=reference("question", "q1"))
        self.assertEqual(result["related_ids"], ["q1"])
        self.assertEqual(result["event_kind"], "answer")
        with self.assertRaises(ManualEventError):
            make("answer", reference_event=reference("recommendation", "r1"))

    def test_acknowledgment_does_not_create_an_action(self):
        result = make("acknowledgment", reference_event=reference("recommendation", "r1"))
        self.assertEqual(result["related_ids"], ["r1"])
        self.assertEqual(result["event_kind"], "acknowledgment")
        self.assertNotIn("action", result["payload"])

    def test_action_and_outcome_are_separate(self):
        action = make("reported_action", event_id="a1")
        self.assertEqual(action["event_kind"], "reported_action")
        self.assertEqual(action["related_ids"], [])
        outcome = make(
            "outcome",
            event_id="o1",
            payload={"value": 0, "unit": "reported scale"},
            reference_event=action,
        )
        self.assertEqual(outcome["related_ids"], ["a1"])
        self.assertEqual(outcome["payload"]["value"], 0)
        self.assertNotEqual(action["id"], outcome["id"])

    def test_missing_outcome_is_not_synthesized(self):
        action = make("reported_action")
        self.assertNotIn("outcome", action["payload"])
        self.assertEqual(action["event_kind"], "reported_action")
        with self.assertRaises(ManualEventError):
            make("outcome")

    def test_invalid_parent_linkage_rejected(self):
        with self.assertRaises(ManualEventError):
            make("answer", reference_event=reference("question", ""))
        wrong = reference("question", "q1")
        wrong["subject_id"] = "different-subject"
        with self.assertRaises(ManualEventError):
            make("answer", reference_event=wrong)
        with self.assertRaises(ManualEventError):
            make("outcome", reference_event=reference("acknowledgment", "ack1"))

    def test_time_offsets_are_accepted_without_rewriting(self):
        output = make(
            occurrence_start="2026-11-07T14:00:00+10:00",
            occurrence_end="2026-11-07T14:05:00+10:00",
            known_at=None,
        )
        self.assertEqual(output["occurrence_start"], "2026-11-07T14:00:00+10:00")
        self.assertIsNone(output["known_at"])

    def test_naive_and_reversed_times_rejected(self):
        with self.assertRaises(ManualEventError):
            make(recorded_at="2026-11-07T04:00:00")
        with self.assertRaises(ManualEventError):
            make(occurrence_end=NOW)
        with self.assertRaises(ManualEventError):
            make(
                occurrence_start="2026-11-07T04:00:00Z",
                occurrence_end="2026-11-07T03:59:59Z",
            )

    def test_no_automatic_recommendation_or_observed_action(self):
        for kind in ("recommendation", "question", "observed_action", "sleep"):
            with self.assertRaises(ManualEventError):
                make(kind)

    def test_payload_requires_object_and_session_is_optional(self):
        with self.assertRaises(ManualEventError):
            make(payload="text")
        with self.assertRaises(ManualEventError):
            make(session_id="")
        self.assertEqual(make(session_id="session-1")["session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()
