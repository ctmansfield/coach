"use strict";

const assert = require("node:assert/strict");
const {test} = require("node:test");
const {readFileSync} = require("node:fs");
const {webcrypto} = require("node:crypto");
const path = require("node:path");
const status = require("../coach_app/physiology/delivery_status.js");
const capture = require("../coach_app/physiology/capture_ui.js");

const runtime = {
  randomUUID: () => "00000000-0000-4000-8000-000000000021",
  subtle: webcrypto.subtle
};

async function example() {
  const event = capture.createDraft({
    subject_id: "synthetic-subject",
    event_kind: "user_marker",
    text: "Offline fixture, zero flagged events",
    occurrence_start: "2026-11-07T14:05:00+10:00"
  }, runtime, new Date("2026-11-07T04:15:00Z"));
  const packet = await capture.makeEnvelope(event, runtime);
  return {
    event,
    bytes: new Uint8Array(packet.bytes),
    info: await status.decodeEnvelope(new Uint8Array(packet.bytes), runtime)
  };
}

function report(info, state, changes = {}) {
  const archived = state.startsWith("archive_");
  return {
    report_version: "1.0.0",
    state,
    envelope_sha256: info.envelope_sha256,
    event_id: info.event_id,
    archive_checked: archived,
    receipt_present: state.endsWith("valid") || state.endsWith("invalid"),
    receipt_checked: state.endsWith("valid") || state.endsWith("invalid"),
    safe_to_delete_original: false,
    authenticated_sender: false,
    ...changes
  };
}

test("actual Coach packet decoded, preserving digest and not echoing personal data", async () => {
  const a = await example();
  assert.equal(a.info.event_id, a.event.id);
  assert.match(a.info.envelope_sha256, /^[a-f0-9]{64}$/);
  assert.equal(a.info.event_sha256.length, 64);
  assert.equal(Object.keys(a.info).length, 3);
  assert.doesNotMatch(JSON.stringify(a.info), /synthetic-subject/);
});

test("prepared has no archive evidence and cannot delete", async () => {
  const a = await example();
  const view = status.interpretStatus(a.info);
  assert.equal(view.state, "prepared_pending");
  assert.equal(view.archive_claimed, false);
  assert.equal(view.is_authenticated_confirmation, false);
  assert.equal(view.safe_to_delete_original, false);
});

test("delivery attempted without verified report remains unknown", async () => {
  const a = await example();
  assert.equal(status.interpretStatus(a.info, null, true).state, "delivery_unknown");
  assert.equal(status.interpretStatus(a.info, undefined, true).state, "delivery_unknown");
});

test("report can say archived but never becomes authenticated in browser", async () => {
  const a = await example();
  const view = status.interpretStatus(
    a.info, report(a.info, "archive_verified_receipt_valid"), true
  );
  assert.equal(view.state, "archive_verified_receipt_valid");
  assert.equal(view.archive_claimed, true);
  assert.equal(view.is_authenticated_confirmation, false);
  assert.equal(view.safe_to_delete_original, false);
  assert.match(view.explanation, /copied report is not authenticated/);
});

test("receipt missing, receipt invalid and immutable conflict remain separate", async () => {
  const a = await example();
  for (const s of [
    "archive_verified_receipt_missing", "archive_verified_receipt_invalid", "archive_conflict"
  ]) {
    const view = status.interpretStatus(a.info, report(a.info, s), true);
    assert.equal(view.state, s);
    assert.equal(view.safe_to_delete_original, false);
  }
});

test("copied report with different packet digest or event id is rejected", async () => {
  const a = await example();
  assert.throws(() => status.interpretStatus(
    a.info, report(a.info, "archive_verified_receipt_valid", {envelope_sha256: "f".repeat(64)})
  ), /does not match/);
  assert.throws(() => status.interpretStatus(
    a.info, report(a.info, "archive_verified_receipt_valid", {event_id: "different"})
  ), /does not match/);
});

test("unsafe deletion and fake authenticated sender claims are rejected", async () => {
  const a = await example();
  for (const forged of [
    {safe_to_delete_original: true},
    {authenticated_sender: true},
    {report_version: "2.0.0"},
    {archive_checked: false},
    {receipt_checked: false, receipt_present: false}
  ]) {
    assert.throws(() => status.interpretStatus(
      a.info, report(a.info, "archive_verified_receipt_valid", forged)
    ), /does not match|inconsistent/);
  }
});

test("a reported pending status cannot override actual attempted flag", async () => {
  const a = await example();
  const view = status.interpretStatus(a.info,
    report(a.info, "prepared_pending", {archive_checked: false}), true);
  assert.equal(view.state, "delivery_unknown");
});

test("wrong archive flag, unknown states or malformed report are rejected", async () => {
  const a = await example();
  for (const r of [
    report(a.info, "archive_conflict", {archive_checked: false}),
    report(a.info, "unsupported"),
    {report_version: "1.0.0"},
    "archive_verified_receipt_valid"
  ]) {
    assert.throws(() => status.interpretStatus(a.info, r), /does not match|inconsistent/);
  }
});

test("invalid event envelope original digest is rejected", async () => {
  const a = await example();
  const parsed = JSON.parse(Buffer.from(a.bytes).toString("utf8"));
  parsed.event_sha256 = "0".repeat(64);
  await assert.rejects(
    () => status.decodeEnvelope(new Uint8Array(Buffer.from(JSON.stringify(parsed))), runtime),
    /digest mismatch/
  );
});

test("incompatible file and malformed base64 are rejected", async () => {
  const a = await example();
  for (const change of [
    {envelope_version: "2.0.0"},
    {event_base64: "@@"},
    {new_field: "unexpected"}
  ]) {
    const p = {...JSON.parse(Buffer.from(a.bytes).toString("utf8")), ...change};
    await assert.rejects(
      () => status.decodeEnvelope(new Uint8Array(Buffer.from(JSON.stringify(p))), runtime)
    );
  }
});

test("viewer has no network, storage or deletion controls", () => {
  const html = readFileSync(path.join(__dirname, "../coach_app/physiology/delivery_status.html"), "utf8");
  const js = readFileSync(path.join(__dirname, "../coach_app/physiology/delivery_status.js"), "utf8");
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.match(html, /delivery_status\.js/);
  assert.match(html, /copied report can be forged/);
  assert.doesNotMatch(js, /\bfetch\s*\(|\bWebSocket\b|\blocalStorage\b|\bsessionStorage\b|\bXMLHttpRequest\b/);
  assert.doesNotMatch(html, /type="submit"|delete-envelope/);
});

test("report claims never turn copied document into real live Mother authentication", async () => {
  const a = await example();
  const fake = report(a.info, "archive_verified_receipt_missing", {
    evidence_level: "local_archive_snapshot"
  });
  const view = status.interpretStatus(a.info, fake);
  assert.equal(view.archive_claimed, true);
  assert.equal(view.is_authenticated_confirmation, false);
  assert.equal(view.report_present, true);
});
