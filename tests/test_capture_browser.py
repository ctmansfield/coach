"""Real Chromium browser acceptance for the offline Coach manual capture page.

Only synthetic values and file:// resources are used. No server or NAS access.
Requires playwright and a separately installed Chromium browser.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright

PAGE = Path(__file__).resolve().parents[1] / "coach_app" / "physiology" / "manual_capture.html"
OUTPUT = Path(os.getenv("CAPTURE_BROWSER_EVIDENCE", "")) if os.getenv("CAPTURE_BROWSER_EVIDENCE") else None
EVENT_TYPE = "application/vnd.coach.manual-event+json"
SUBJECT = "synthetic-browser-subject"


def decode_download(download):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / download.suggested_filename
        download.save_as(path)
        data = path.read_bytes()
    envelope = json.loads(data)
    assert set(envelope) == {
        "envelope_version",
        "content_type",
        "encoding",
        "event_sha256",
        "event_base64",
    }
    assert envelope["envelope_version"] == "1.0.0"
    assert envelope["content_type"] == EVENT_TYPE
    assert envelope["encoding"] == "base64"
    original = base64.b64decode(envelope["event_base64"], validate=True)
    assert hashlib.sha256(original).hexdigest() == envelope["event_sha256"]
    assert download.suggested_filename == (
        hashlib.sha256(data).hexdigest() + ".coach-event.json"
    )
    return json.loads(original)


class CaptureBrowserAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(headless=True, args=["--no-sandbox"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.context = self.browser.new_context(
            accept_downloads=True,
            viewport={"width": 1365, "height": 900},
        )
        self.page = self.context.new_page()
        self.errors = []
        self.remote = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on(
            "request",
            lambda req: self.remote.append(req.url)
            if req.url.startswith(("http://", "https://"))
            else None,
        )
        self.page.goto(PAGE.as_uri())
        self.assertTrue(self.page.get_by_role("heading", name="Manual factual event").is_visible())

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.remote, [])
        self.context.close()

    def fill_marker(self):
        self.page.get_by_label("Subject identifier").fill(SUBJECT)
        self.page.get_by_label("Factual description").fill(
            "Electrode was repositioned; observed value was zero"
        )
        self.page.get_by_label("Event start (optional)").fill(
            "2026-11-07T14:05:00+10:00"
        )

    def test_rendered_desktop_and_mobile_without_horizontal_overflow(self):
        self.assertTrue(self.page.get_by_role("button", name="Export offline event file").is_visible())
        self.assertTrue(self.page.get_by_role("status").is_visible())
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        if OUTPUT:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(OUTPUT / "capture-desktop.png"), full_page=True)
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(self.page.get_by_label("Subject identifier").is_visible())
        self.assertLessEqual(
            self.page.evaluate("document.documentElement.scrollWidth"),
            self.page.evaluate("window.innerWidth"),
        )
        if OUTPUT:
            self.page.screenshot(path=str(OUTPUT / "capture-mobile.png"), full_page=True)

    def test_keyboard_focus_and_accessible_name(self):
        self.page.keyboard.press("Tab")
        self.assertEqual(
            self.page.evaluate("document.activeElement.id"),
            "subject_id",
        )
        self.page.keyboard.press("Tab")
        self.assertEqual(
            self.page.evaluate("document.activeElement.id"),
            "event_kind",
        )
        self.page.keyboard.press("Tab")
        self.assertEqual(
            self.page.evaluate("document.activeElement.id"),
            "text",
        )
        self.assertTrue(self.page.get_by_label("Subject identifier").is_visible())
        self.assertTrue(self.page.get_by_label("Event type", exact=True).is_visible())

    def test_real_browser_download_is_integrity_checked_and_offline(self):
        self.fill_marker()
        with self.page.expect_download(timeout=15000) as pending:
            self.page.get_by_role("button", name="Export offline event file").click()
        original = decode_download(pending.value)
        self.assertEqual(original["subject_id"], SUBJECT)
        self.assertEqual(original["event_kind"], "user_marker")
        self.assertEqual(original["epistemic_type"], "reported")
        self.assertEqual(original["occurrence_start"], "2026-11-07T14:05:00+10:00")
        self.assertIsNone(original["known_at"])
        self.assertIsNone(original["source_revision_id"])
        self.assertEqual(original["payload"]["text"], "Electrode was repositioned; observed value was zero")
        self.assertIn("Nothing was uploaded or archived", self.page.get_by_role("status").inner_text())

    def test_required_parent_blocks_export_until_reference_is_supplied(self):
        self.page.get_by_label("Subject identifier").fill(SUBJECT)
        self.page.get_by_label("Event type", exact=True).select_option("outcome")
        self.assertTrue(self.page.get_by_label("Earlier event ID").is_visible())
        self.assertTrue(self.page.get_by_label("Earlier event type").is_visible())
        self.assertTrue(self.page.get_by_label("Earlier event ID").get_attribute("required") is not None)
        self.assertTrue(self.page.get_by_label("Earlier event type").get_attribute("required") is not None)
        self.page.locator("#text").fill("Reported zero change, no measured outcome")
        self.page.get_by_role("button", name="Export offline event file").click()
        self.assertFalse(
            self.page.locator("form").evaluate("(form) => form.checkValidity()")
        )
        self.page.get_by_label("Earlier event type").select_option("reported_action")
        self.page.get_by_label("Earlier event ID").fill("action:synthetic")
        self.assertTrue(self.page.locator("form").evaluate("(form) => form.checkValidity()"))
        with self.page.expect_download(timeout=15000) as pending:
            self.page.get_by_role("button", name="Export offline event file").click()
        original = decode_download(pending.value)
        self.assertEqual(original["event_kind"], "outcome")
        self.assertEqual(original["related_ids"], ["action:synthetic"])
        self.assertEqual(original["epistemic_type"], "reported")

    def test_switching_from_linked_event_to_marker_clears_parent(self):
        self.page.get_by_label("Event type", exact=True).select_option("answer")
        self.page.get_by_label("Earlier event type").select_option("question")
        self.page.get_by_label("Earlier event ID").fill("question:old")
        self.page.get_by_label("Event type", exact=True).select_option("user_marker")
        self.assertTrue(self.page.locator("#parent-fields").is_hidden())
        self.assertEqual(self.page.locator("#parent_id").input_value(), "")
        self.assertFalse(self.page.locator("#parent_id").evaluate("(el) => el.required"))
        self.assertFalse(self.page.locator("#parent_kind").evaluate("(el) => el.required"))

    def test_bad_calendar_date_does_not_download_and_gives_message(self):
        self.fill_marker()
        self.page.get_by_label("Event start (optional)").fill("2026-02-30T14:05:00+10:00")
        self.page.get_by_role("button", name="Export offline event file").click()
        self.assertIn("Invalid calendar date", self.page.get_by_role("status").inner_text())
        self.assertTrue(self.page.get_by_role("button", name="Export offline event file").is_enabled())

    def test_no_external_requests_and_no_browser_storage_on_reload(self):
        self.fill_marker()
        self.page.reload()
        self.assertEqual(self.page.get_by_label("Subject identifier").input_value(), "")
        self.assertEqual(self.page.get_by_label("Factual description").input_value(), "")
        self.assertEqual(self.page.evaluate("Object.keys(localStorage).length"), 0)
        self.assertEqual(self.page.evaluate("Object.keys(sessionStorage).length"), 0)


if __name__ == "__main__":
    unittest.main()
