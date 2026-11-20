"""Headless Chromium acceptance of the offline delivery-state viewer.

Synthetic files only, no NAS, no network service, no output deletion.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import unittest

from playwright.sync_api import expect, sync_playwright

PAGE = (
    Path(__file__).resolve().parents[1]
    / "coach_app"
    / "physiology"
    / "delivery_status.html"
)


def synthetic_packet():
    raw = {
        "schema_version": "1.0.0",
        "record_type": "event",
        "id": "coach-manual:browser-fixture",
        "source": "coach:manual",
        "subject_id": "synthetic",
        "event_kind": "user_marker",
        "occurrence_start": None,
        "known_at": None,
        "payload": {"text": "No personal data"},
    }
    original = json.dumps(raw, separators=(",", ":")).encode()
    envelope = {
        "envelope_version": "1.0.0",
        "content_type": "application/vnd.coach.manual-event+json",
        "encoding": "base64",
        "event_sha256": hashlib.sha256(original).hexdigest(),
        "event_base64": base64.b64encode(original).decode("ascii"),
    }
    return (json.dumps(envelope) + "\n").encode()


def synthetic_report(packet, state):
    return {
        "report_version": "1.0.0",
        "event_id": "coach-manual:browser-fixture",
        "envelope_sha256": hashlib.sha256(packet).hexdigest(),
        "state": state,
        "archive_checked": state.startswith("archive_"),
        "receipt_present": state.endswith("valid"),
        "receipt_checked": state.endswith("valid"),
        "safe_to_delete_original": False,
        "authenticated_sender": False,
    }


class DeliveryStatusBrowserQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-sandbox"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 850})
        self.page = self.context.new_page()
        self.errors = []
        self.remote = []
        self.page.on("pageerror", lambda exc: self.errors.append(str(exc)))
        self.page.on(
            "request",
            lambda req: self.remote.append(req.url)
            if req.url.startswith(("http://", "https://"))
            else None,
        )
        self.page.goto(PAGE.as_uri())
        self.assertTrue(
            self.page.get_by_role("heading", name="Event delivery status").is_visible()
        )

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.remote, [])
        self.context.close()

    def put_packet(self, data=None):
        value = data if data is not None else synthetic_packet()
        self.page.locator("#event-envelope").set_input_files(
            {"name": "fixture.coach-event.json", "mimeType": "application/json", "buffer": value}
        )
        return value

    def put_report(self, packet, state, changes=None):
        report = synthetic_report(packet, state)
        report.update(changes or {})
        self.page.locator("#mother-report").set_input_files(
            {
                "name": "fixture-status.json",
                "mimeType": "application/json",
                "buffer": json.dumps(report).encode(),
            }
        )

    def test_keyboard_and_mobile_layout(self):
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "event-envelope")
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "mother-report")
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        self.assertTrue(self.page.get_by_label("Coach event envelope").is_visible())

    def test_prepared_and_attempted_unknown_are_separate(self):
        self.put_packet()
        self.page.get_by_role("button", name="Review local delivery evidence").click()
        expect(self.page.locator("#state-title")).to_contain_text("Prepared")
        self.page.get_by_label("I attempted to transfer this event").check()
        self.page.get_by_role("button", name="Review local delivery evidence").click()
        expect(self.page.locator("#state-title")).to_contain_text("Delivery unknown")
        expect(self.page.locator("#state-warning")).to_contain_text("Keep the original envelope")

    def test_copied_report_is_never_authenticated(self):
        packet = self.put_packet()
        self.put_report(packet, "archive_verified_receipt_valid")
        self.page.get_by_role("button", name="Review local delivery evidence").click()
        expect(self.page.locator("#state-title")).to_contain_text("match reported")
        expect(self.page.locator("#state-warning")).to_contain_text("cannot authenticate")

    def test_forged_digest_refuses_to_render_archived_state(self):
        packet = self.put_packet()
        self.put_report(
            packet, "archive_verified_receipt_valid",
            {"envelope_sha256": "f" * 64},
        )
        self.page.get_by_role("button", name="Review local delivery evidence").click()
        expect(self.page.locator("#state-title")).to_contain_text("Verification unavailable")
        self.assertIn("Keep the original envelope", self.page.locator("#state-warning").inner_text())

    def test_no_storage_and_reload_discards_files(self):
        self.put_packet()
        self.page.reload()
        self.assertEqual(self.page.locator("#event-envelope").evaluate("(e)=>e.files.length"), 0)
        self.assertEqual(self.page.evaluate("localStorage.length"), 0)
        self.assertEqual(self.page.evaluate("sessionStorage.length"), 0)


if __name__ == "__main__":
    unittest.main()
