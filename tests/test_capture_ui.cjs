"use strict";

const assert = require("node:assert/strict");
const {createHash, webcrypto} = require("node:crypto");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const capture = require("../coach_app/physiology/capture_ui.js");

const fixedCrypto = {
  randomUUID() {
    return "00000000-0000-4000-8000-000000000001";
  },
  subtle: webcrypto.subtle
};
const fixedNow = new Date("2026-11-07T04:12:00.000Z");

function input(kind = "user_marker", overrides = {}) {
  return {
    subject_id: "synthetic-subject",
    event_kind: kind,
    text: "Contact adjusted, no symptoms reported",
    occurrence_start: "2026-11-07T14:05:00+10:00",
    occurrence_end: "",
    known_at: "",
    session_id: "",
    parent_id: "",
    parent_kind: "",
    ...overrides
  };
}
function draft(kind = "user_marker", overrides = {}) {
  return capture.createDraft(input(kind, overrides), fixedCrypto, fixedNow);
}

test("reported marker preserves original timezone, unknown knowledge, distinct recording time", () => {
  const value = draft();
  assert.equal(value.id, "coach-manual:00000000-0000-4000-8000-000000000001");
  assert.equal(value.occurrence_start, "2026-11-07T14:05:00+10:00");
  assert.equal(value.recorded_at, "2026-11-07T04:12:00.000Z");
  assert.equal(value.known_at, null);
  assert.equal(value.source_revision_id, null);
  assert.equal(value.epistemic_type, "reported");
  assert.deepEqual(value.related_ids, []);
  assert.deepEqual(value.payload, {text: "Contact adjusted, no symptoms reported"});
});

test("valid zero is distinct from missing outcome and optional timestamps remain null", () => {
  const value = draft("user_marker", {
    text: "Zero devices disconnected", occurrence_start: "", occurrence_end: ""
  });
  assert.equal(value.occurrence_start, null);
  assert.equal(value.occurrence_end, null);
  assert.match(value.payload.text, /Zero/);
  assert.equal(value.event_kind, "user_marker");
});

test("acknowledgment cannot become an action", () => {
  const value = draft("acknowledgment", {
    parent_kind: "recommendation", parent_id: "recommendation:1"
  });
  assert.equal(value.event_kind, "acknowledgment");
  assert.deepEqual(value.related_ids, ["recommendation:1"]);
  assert.throws(() => draft("acknowledgment", {
    parent_kind: "reported_action", parent_id: "action:1"
  }), /Parent event kind/);
});

test("answer, outcome and optional action links use compatible typed parents", () => {
  assert.deepEqual(draft("answer", {
    parent_kind: "question", parent_id: "question:1"
  }).related_ids, ["question:1"]);
  assert.deepEqual(draft("outcome", {
    parent_kind: "observed_action", parent_id: "action:1"
  }).related_ids, ["action:1"]);
  assert.deepEqual(draft("reported_action", {
    parent_kind: "acknowledgment", parent_id: "ack:1"
  }).related_ids, ["ack:1"]);
  assert.deepEqual(draft("reported_action").related_ids, []);
  for (const kind of ["answer", "outcome", "acknowledgment"]) {
    assert.throws(() => draft(kind), /requires a previously recorded parent/);
  }
  assert.throws(() => draft("context", {
    parent_kind: "question", parent_id: "question:1"
  }), /Parent event kind/);
});

test("negative or inconsistent time intervals are not accepted", () => {
  assert.throws(() => draft("context", {
    occurrence_start: "", occurrence_end: "2026-11-07T04:10:00Z"
  }), /Occurrence end requires/);
  assert.throws(() => draft("context", {
    occurrence_start: "2026-11-07T14:05:00+10:00",
    occurrence_end: "2026-11-07T04:04:59Z"
  }), /cannot precede/);
  assert.doesNotThrow(() => draft("context", {
    occurrence_start: "2026-11-07T14:05:00+10:00",
    occurrence_end: "2026-11-07T04:05:00Z"
  }));
});

test("invalid calendar dates and ambiguous times are rejected", () => {
  for (const value of [
    "2026-02-30T12:00:00Z", "2026-02-29T12:00:00Z",
    "2026-11-07T04:00:00", "2026-13-07T04:00:00Z",
    "2026-11-07T24:00:00Z", "2026-11-07T04:00:60Z"
  ]) {
    assert.throws(() => draft("context", {occurrence_start: value}), Error);
  }
  assert.equal(capture.validTimestamp("2024-02-29T12:00:00Z", true),
    "2024-02-29T12:00:00Z");
});

test("oversize, invalid identity and non-factual empty descriptions rejected", () => {
  assert.throws(() => draft("user_marker", {text: " "}), /description/);
  assert.throws(() => draft("user_marker", {subject_id: " "}), /identifier/);
  assert.throws(() => draft("user_marker", {text: "x".repeat(4001)}), /description/);
  assert.throws(() => draft("observed_action"), /Unsupported event kind/);
  assert.throws(() => capture.createDraft(input(), null), /Secure random/);
});

test("Unicode envelope preserves exact event bytes and SHA-256 integrity", async () => {
  const value = draft("context", {
    text: "Intense exercise 🏃; 身体感觉变化, no scoring"
  });
  const packaged = await capture.makeEnvelope(value, fixedCrypto);
  const parsed = JSON.parse(new TextDecoder().decode(packaged.bytes));
  assert.deepEqual(Object.keys(parsed).sort(), [
    "content_type", "encoding", "envelope_version", "event_base64", "event_sha256"
  ]);
  assert.equal(parsed.content_type, "application/vnd.coach.manual-event+json");
  assert.equal(parsed.envelope_version, "1.0.0");
  const actualBytes = Buffer.from(parsed.event_base64, "base64");
  assert.deepEqual(actualBytes, Buffer.from(packaged.original));
  assert.deepEqual(JSON.parse(actualBytes.toString("utf8")), value);
  assert.equal(parsed.event_sha256, createHash("sha256").update(actualBytes).digest("hex"));
  assert.equal(packaged.filename,
    createHash("sha256").update(packaged.bytes).digest("hex") + ".coach-event.json");
});

test("same event yields identical packet, distinct event identity yields distinct packet", async () => {
  const one = await capture.makeEnvelope(draft(), fixedCrypto);
  const same = await capture.makeEnvelope(draft(), fixedCrypto);
  assert.deepEqual(one.bytes, same.bytes);
  assert.equal(one.filename, same.filename);
  const changed = await capture.makeEnvelope(draft("context"), fixedCrypto);
  assert.notEqual(changed.filename, one.filename);
});

test("browser form is explicitly offline and prevents silent state persistence", () => {
  const html = readFileSync(path.join(__dirname, "../coach_app/physiology/manual_capture.html"), "utf8");
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.match(html, /autocomplete="off"/);
  assert.match(html, /capture_ui\.js/);
  assert.match(html, /name="subject_id"/);
  assert.match(html, /name="event_kind"/);
  assert.match(html, /name="known_at"/);
  assert.match(html, /name="parent_id"/);
  assert.match(html, /not saved to the physiology archive/i);
  const code = readFileSync(path.join(__dirname, "../coach_app/physiology/capture_ui.js"), "utf8");
  assert.doesNotMatch(code, /\blocalStorage\b|\bsessionStorage\b|\bfetch\s*\(|XMLHttpRequest|WebSocket/);
});

test("unknown known_at does not become report time, even when occurrence is unknown", () => {
  const value = draft("context", {occurrence_start: "", known_at: ""});
  assert.equal(value.known_at, null);
  assert.equal(value.occurrence_start, null);
  assert.ok(value.recorded_at);
});
