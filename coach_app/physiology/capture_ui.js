/* Offline Coach factual-event capture. No network, storage or auto-questions. */
(function (root) {
  "use strict";

  const KINDS = new Set([
    "user_marker", "context", "answer", "acknowledgment",
    "reported_action", "outcome"
  ]);
  const PARENTS = Object.freeze({
    answer: ["question"],
    acknowledgment: ["recommendation"],
    reported_action: ["recommendation", "acknowledgment"],
    outcome: ["reported_action", "observed_action"]
  });
  const REQUIRED_PARENT = new Set(["answer", "acknowledgment", "outcome"]);
  const EVENT_LIMIT = 256 * 1024;
  const ENVELOPE_LIMIT = 400 * 1024;
  const MIME = "application/vnd.coach.manual-event+json";
  const ISO_OFFSET = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-](?:0\d|1\d|2[0-3]):[0-5]\d)$/;

  function validTimestamp(value, required) {
    if (value == null || value === "") {
      if (required) throw new Error("A recorded timestamp is required");
      return null;
    }
    if (typeof value !== "string" || !ISO_OFFSET.test(value) ||
        !Number.isFinite(Date.parse(value))) {
      throw new Error("Use an explicit offset-aware ISO time, such as 2026-11-07T14:00:00+10:00");
    }
    return value;
  }

  function cleanText(value, label, limit) {
    if (typeof value !== "string" || !value.trim() || value.length > limit ||
        /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(value)) {
      throw new Error(label + " must contain 1–" + limit + " printable characters");
    }
    return value.trim();
  }

  function createDraft(fields, runtime = root.crypto, now = new Date()) {
    if (!fields || typeof fields !== "object" || !runtime ||
        typeof runtime.randomUUID !== "function") {
      throw new Error("Secure random event identity is unavailable");
    }
    const subject = cleanText(fields.subject_id, "Subject identifier", 256);
    const kind = fields.event_kind;
    if (!KINDS.has(kind)) throw new Error("Unsupported event kind");
    const description = cleanText(fields.text, "Factual description", 4000);
    const start = validTimestamp(fields.occurrence_start, false);
    const end = validTimestamp(fields.occurrence_end, false);
    const known = validTimestamp(fields.known_at, false);
    const recorded = validTimestamp(now.toISOString(), true);
    if (end && (!start || Date.parse(end) < Date.parse(start))) {
      throw new Error("Occurrence end requires a start and cannot precede it");
    }
    const sessionId = fields.session_id
      ? cleanText(fields.session_id, "Session ID", 256) : null;
    const parentId = fields.parent_id
      ? cleanText(fields.parent_id, "Parent event ID", 256) : null;
    const parentKind = fields.parent_kind || null;
    if (REQUIRED_PARENT.has(kind) && !parentId) {
      throw new Error("This event requires a previously recorded parent event");
    }
    if (parentId && (!PARENTS[kind] || !PARENTS[kind].includes(parentKind))) {
      throw new Error("Parent event kind is not compatible with this event");
    }
    if (!parentId && parentKind) throw new Error("Parent kind requires an ID");
    if (kind !== "reported_action" && !REQUIRED_PARENT.has(kind) && parentId) {
      throw new Error("Standalone annotations cannot have a parent");
    }
    return {
      schema_version: "1.0.0",
      record_type: "event",
      id: "coach-manual:" + runtime.randomUUID(),
      subject_id: subject,
      processing_version: "coach-manual-events/0.1.0",
      event_kind: kind,
      occurrence_start: start,
      occurrence_end: end,
      known_at: known,
      recorded_at: recorded,
      source: "coach:manual",
      source_revision_id: null,
      session_id: sessionId,
      related_ids: parentId ? [parentId] : [],
      payload: {text: description},
      epistemic_type: "reported",
      quality_flags: []
    };
  }

  function hex(bytes) {
    return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  }

  function base64(bytes) {
    let binary = "";
    for (let pos = 0; pos < bytes.length; pos += 16384) {
      binary += String.fromCharCode(...bytes.subarray(pos, pos + 16384));
    }
    return btoa(binary);
  }

  async function makeEnvelope(event, runtime = root.crypto) {
    if (!runtime || !runtime.subtle || typeof runtime.subtle.digest !== "function") {
      throw new Error("Web Crypto SHA-256 is required to export an event");
    }
    const encoder = new TextEncoder();
    const original = encoder.encode(JSON.stringify(event));
    if (!original.length || original.length > EVENT_LIMIT) {
      throw new Error("Event exceeds the 256 KiB ingestion limit");
    }
    const digest = hex(new Uint8Array(await runtime.subtle.digest("SHA-256", original)));
    const envelope = {
      envelope_version: "1.0.0",
      content_type: MIME,
      encoding: "base64",
      event_sha256: digest,
      event_base64: base64(original)
    };
    const bytes = encoder.encode(JSON.stringify(envelope) + "\n");
    if (bytes.length > ENVELOPE_LIMIT) {
      throw new Error("Event envelope exceeds the 400 KiB transfer limit");
    }
    const envelopeDigest = hex(new Uint8Array(await runtime.subtle.digest("SHA-256", bytes)));
    return {bytes, original, filename: envelopeDigest + ".coach-event.json"};
  }

  function attach() {
    const form = document.querySelector("#capture-form");
    if (!form) return;
    const kind = form.elements.namedItem("event_kind");
    const parentBox = document.querySelector("#parent-fields");
    const parentKind = form.elements.namedItem("parent_kind");
    const parentId = form.elements.namedItem("parent_id");
    const status = document.querySelector("#capture-status");

    function refresh() {
      const kinds = PARENTS[kind.value] || [];
      parentBox.hidden = kinds.length === 0;
      parentKind.replaceChildren();
      const blank = new Option(kinds.length ? "Select event kind" : "Not applicable", "");
      parentKind.add(blank);
      for (const value of kinds) parentKind.add(new Option(value.replaceAll("_", " "), value));
      parentKind.required = REQUIRED_PARENT.has(kind.value);
      parentId.required = REQUIRED_PARENT.has(kind.value);
      if (kinds.length === 0) parentId.value = "";
      const label = document.querySelector("#description-label");
      label.textContent = kind.value === "acknowledgment"
        ? "What exactly was acknowledged? (not an action)"
        : kind.value === "reported_action"
          ? "What did you actually do?"
          : kind.value === "outcome"
            ? "What subsequently happened? (factual observation)"
            : kind.value === "answer"
              ? "Factual answer" : "Factual description";
    }
    kind.addEventListener("change", refresh);
    refresh();
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      const submit = form.querySelector("button[type=submit]");
      submit.disabled = true;
      status.textContent = "Preparing local file…";
      try {
        const input = Object.fromEntries(new FormData(form).entries());
        const draft = createDraft(input);
        const file = await makeEnvelope(draft);
        const objectUrl = URL.createObjectURL(new Blob([file.bytes], {type: "application/json"}));
        try {
          const link = document.createElement("a");
          link.href = objectUrl;
          link.download = file.filename;
          link.hidden = true;
          document.body.append(link);
          link.click();
          link.remove();
        } finally {
          setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
        }
        status.textContent = "Export prepared. Check browser downloads. Nothing was uploaded or archived.";
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Export failed";
      } finally {
        submit.disabled = false;
      }
    });
  }

  const api = Object.freeze({createDraft, makeEnvelope, validTimestamp});
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attach);
    else attach();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
