# I01-U — Offline Coach manual factual-event capture

**State:** Draft interface under review; no production deployment.
**Depends on:** Coach I01-P event drafts, I01-T1 offline envelope and Mother
I01-T2 file receiver. Contract version 1.0.0 is unchanged.

## Purpose

A standalone static browser form creates *reported* event drafts for:
user_marker, context, answer, acknowledgment, reported_action, and outcome.

The form is deliberately **manual and passive**: no automatic questions,
readiness scales, diagnoses, recommendations, treatment actions, background
capture, network requests, or automatic transfer to Mother.

Recorded time is the browser clock at export. A separately entered known-at
or occurrence time is never inferred from recorded time. The form requires
explicit ISO 8601 offsets (e.g. `2026-11-07T14:05:00+10:00`); unknown
fields remain null. Client timestamps are **not authoritative** until a
qualified source confirms that clock.

Answers require an existing question ID; acknowledgments require an existing
recommendation ID; outcomes require an existing action ID. Reported actions
may stand alone or refer to a recommendation/acknowledgment. The browser
collects a declared kind and event ID; Mother must still confirm the reference
exists and belongs to the authorized subject. Acknowledgment does not mean
performance, and no outcome record is created from silence.

## INSTALL (review-only)

Use an isolated Coach worktree based on Coach I01-T1 PR #3. Keep the static
page and its JS file together:

- `coach_app/physiology/manual_capture.html`
- `coach_app/physiology/capture_ui.js`

Open `manual_capture.html` directly in a modern browser, without running
a local web server. Use **synthetic IDs and descriptions during qualification**.

The browser creates a version 1.0.0 Coach envelope with the exact original
event bytes, SHA-256 and base64. Clicking **Export offline event file** initiates
a download named by the envelope's hash. It does *not* indicate that Mother
has received or archived the record. A browser download prompt or policy can
prevent the file from being saved; verify downloads manually.

Transfer of an accepted file into an explicitly chosen Mother test archive
remains a separate authorized operation, as documented in Mother
`docs/physiology/I01_PAIRED_HANDOFF.md`. No network sender or live API is
provided in this increment.

## VERIFY

Run the dedicated bounded tests from the Coach repository:

```bash
node --test tests/test_capture_ui.cjs
node --check coach_app/physiology/capture_ui.js
```

Tests use Node 22 built-ins and synthetic records. They verify event-kind and
parent rules, zero versus missing, offset preservation, invalid/naive dates,
no inferred outcomes, Unicode, exact event bytes and envelope SHA-256, and
that the static form prohibits connections and contains required fields.

They do not verify browser downloads, layout, assistive technology behavior,
or real user data. Browser visual/interaction QA is a separate acceptance
gate. No live notification-capable tests are invoked.

## Privacy and security limitations

The page sets a Content Security Policy including `connect-src 'none'`,
loads only a local sibling JS file, and does not use browser storage.
It creates a browser download through an object URL. The file contains a
**base64-encoded, not encrypted** event and must be treated as personal data.
Do not commit exports to public GitHub repositories.

SHA-256 provides byte integrity, not account identity or authentication.
Subject IDs are user-supplied here and untrusted until an authenticated
Mother ingress exists. Browser wall-clock time is separately unverified.
No online endpoint, password, archive, production service, or applied
migration is changed.

## Release note and next work

- Adds a self-contained manual-capture page and reusable pure event/envelope
  builders with deterministic tests.
- Keeps action, acknowledgment and outcome semantics distinct.
- Exports the pre-existing Coach→Mother envelope format and processing version.
- Leaves server-side subject authorization, authenticated delivery,
  browser QA, NAS deployment and actual physiology evaluation open.

The next integration worker may test a *pinned* UI-generated envelope against
the existing Mother receiver on a disposable SQLite archive before offering
any live service connection. Shared schemas and migrations have one PM owner.
