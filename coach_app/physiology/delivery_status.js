/* Offline Coach delivery-state viewer. Never treats a copied report as auth. */
(function (root) {
  "use strict";

  const states = Object.freeze({
    prepared_pending: ["Prepared — not submitted", "Keep the original envelope until an authorized transfer."],
    delivery_unknown: ["Delivery unknown", "A missing response is not proof of a failed archive write. Keep the exact envelope."],
    archive_verified_receipt_missing: ["Local archive match reported · receipt missing", "The report says Mother found the original event, but the receipt still needs recovery."],
    archive_verified_receipt_valid: ["Local archive and receipt match reported", "The report says the archive and receipt agree; this copied report is not authenticated."],
    archive_verified_receipt_invalid: ["Local archive match reported · receipt invalid", "The receipt conflicts with the local verification result. Investigate before trusting it."],
    archive_conflict: ["Archive conflict reported", "A different source revision or record was found under this event identity. Preserve all evidence."]
  });
  const archivedStates = new Set([
    "archive_verified_receipt_missing",
    "archive_verified_receipt_valid",
    "archive_verified_receipt_invalid",
    "archive_conflict"
  ]);
  const MAX_ENVELOPE_BYTES = 400 * 1024;
  const MAX_REPORT_BYTES = 32 * 1024;

  function byteHex(bytes) {
    return Array.from(bytes, item => item.toString(16).padStart(2, "0")).join("");
  }

  async function sha256(bytes, cryptoAPI = root.crypto) {
    if (!cryptoAPI || !cryptoAPI.subtle) throw new Error("Secure SHA-256 unavailable");
    return byteHex(new Uint8Array(await cryptoAPI.subtle.digest("SHA-256", bytes)));
  }

  function parseBase64(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9+/]*={0,2}$/.test(value) ||
        value.length % 4 !== 0) throw new Error("Malformed base64 envelope");
    const binary = atob(value);
    return Uint8Array.from(binary, x => x.charCodeAt(0));
  }

  async function decodeEnvelope(bytes, cryptoAPI = root.crypto) {
    if (!(bytes instanceof Uint8Array) || !bytes.length ||
        bytes.length > MAX_ENVELOPE_BYTES) throw new Error("Invalid envelope size");
    let parsed;
    try {
      parsed = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(bytes));
    } catch (_) {
      throw new Error("Envelope JSON is invalid");
    }
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object" ||
        Object.keys(parsed).sort().join("|") !==
          "content_type|encoding|envelope_version|event_base64|event_sha256") {
      throw new Error("Unsupported envelope keys");
    }
    if (parsed.envelope_version !== "1.0.0" ||
        parsed.content_type !== "application/vnd.coach.manual-event+json" ||
        parsed.encoding !== "base64" ||
        typeof parsed.event_sha256 !== "string" ||
        !/^[a-f0-9]{64}$/.test(parsed.event_sha256)) {
      throw new Error("Incompatible event envelope");
    }
    const source = parseBase64(parsed.event_base64);
    if (!source.length || source.length > 256 * 1024 ||
        await sha256(source, cryptoAPI) !== parsed.event_sha256) {
      throw new Error("Original event digest mismatch");
    }
    let event;
    try {
      event = JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(source));
    } catch (_) {
      throw new Error("Original event is not JSON");
    }
    if (!event || Array.isArray(event) || event.record_type !== "event" ||
        event.schema_version !== "1.0.0" ||
        event.source !== "coach:manual" ||
        typeof event.id !== "string" || !event.id) {
      throw new Error("Not a compatible Coach manual event");
    }
    return {
      event_id: event.id,
      envelope_sha256: await sha256(bytes, cryptoAPI),
      event_sha256: parsed.event_sha256
    };
  }

  function interpretStatus(envelopeInfo, report, attempted = false) {
    if (!envelopeInfo || typeof envelopeInfo.envelope_sha256 !== "string" ||
        typeof envelopeInfo.event_id !== "string") {
      throw new Error("Select a valid event envelope first");
    }
    if (typeof attempted !== "boolean") throw new Error("Attempted must be boolean");
    let state = attempted ? "delivery_unknown" : "prepared_pending";
    let reportPresent = false;
    if (report !== null && report !== undefined) {
      if (!report || Array.isArray(report) || typeof report !== "object" ||
          report.report_version !== "1.0.0" ||
          report.envelope_sha256 !== envelopeInfo.envelope_sha256 ||
          report.event_id !== envelopeInfo.event_id ||
          report.safe_to_delete_original !== false ||
          report.authenticated_sender !== false ||
          typeof report.archive_checked !== "boolean" ||
          typeof report.receipt_present !== "boolean" ||
          typeof report.receipt_checked !== "boolean" ||
          !Object.prototype.hasOwnProperty.call(states, report.state) ||
          (archivedStates.has(report.state) && !report.archive_checked) ||
          (report.receipt_checked && !report.archive_checked) ||
          (report.state === "archive_verified_receipt_valid" &&
           (!report.receipt_present || !report.receipt_checked))) {
        throw new Error("Local status report does not match this envelope or is inconsistent");
      }
      state = report.state;
      reportPresent = true;
      if (attempted && state === "prepared_pending") state = "delivery_unknown";
    }
    return {
      state,
      title: states[state][0],
      explanation: states[state][1],
      archive_claimed: reportPresent && archivedStates.has(state),
      report_present: reportPresent,
      is_authenticated_confirmation: false,
      safe_to_delete_original: false
    };
  }

  function attach() {
    const packet = document.querySelector("#event-envelope");
    const report = document.querySelector("#mother-report");
    const attempted = document.querySelector("#delivery-attempted");
    const button = document.querySelector("#review-button");
    const title = document.querySelector("#state-title");
    const text = document.querySelector("#state-explanation");
    const warning = document.querySelector("#state-warning");
    const fingerprint = document.querySelector("#state-fingerprint");

    button.addEventListener("click", async () => {
      button.disabled = true;
      title.textContent = "Checking local files…";
      text.textContent = "";
      warning.textContent = "";
      fingerprint.textContent = "";
      try {
        const selected = packet.files[0];
        if (!selected || selected.size > MAX_ENVELOPE_BYTES) {
          throw new Error("Choose a bounded Coach event envelope");
        }
        const envelope = await decodeEnvelope(new Uint8Array(await selected.arrayBuffer()));
        let loaded = null;
        if (report.files.length) {
          const file = report.files[0];
          if (file.size > MAX_REPORT_BYTES) throw new Error("Report exceeds 32 KiB");
          try {
            loaded = JSON.parse(await file.text());
          } catch (_) {
            throw new Error("Invalid report JSON");
          }
        }
        const status = interpretStatus(envelope, loaded, attempted.checked);
        title.textContent = status.title;
        text.textContent = status.explanation;
        fingerprint.textContent = "Envelope SHA-256: " + envelope.envelope_sha256.slice(0, 16) + "…";
        warning.textContent = status.archive_claimed
          ? "Mother archive verification is claimed by a copied file. This browser cannot authenticate it. Do not delete the original envelope."
          : "No Mother archive confirmation is established here. Keep the original envelope.";
      } catch (error) {
        title.textContent = "Verification unavailable";
        text.textContent = error instanceof Error ? error.message : "Could not read files";
        warning.textContent = "Keep the original envelope and do not assume delivery succeeded or failed.";
      } finally {
        button.disabled = false;
      }
    });
  }

  const api = Object.freeze({decodeEnvelope, interpretStatus});
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", attach);
    else attach();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
