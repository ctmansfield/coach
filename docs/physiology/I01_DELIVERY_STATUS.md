# I01-S2 — Offline delivery-state viewer for Coach

**State:** Review-only browser interface, no live Mother connection.
**Base:** Coach I01-U2 browser QA PR #5. **Dependency:** Mother
I01-S1 read-only verifier PR #9. Shared contract 1.0.0 is unchanged.

## Purpose

A user can select the **original Coach event envelope** and an optional
**Mother local reconciliation report** to distinguish a prepared event,
an attempted but unconfirmed event, and a reported locally verified archive
state. This viewer never modifies or deletes an event, automatically retries,
or contacts a service.

### Trust boundary

The browser verifies SHA-256 integrity of the selected original envelope.
It also checks that a supplied status report refers to the **same exact
envelope SHA-256 and event ID**, and refuses a report claiming sender
authentication, permission to delete an original, or a contradictory archive
verification state.

However, **a copied JSON report can be forged**. The browser cannot open
Mother's database or authenticate a copied report's origin. Therefore
archival states are labeled "local archive match reported" rather than
"verified by this browser". Only Mother's explicit read-only verification
against the selected archive, or a future authenticated server status
endpoint, can establish a trustworthy archival claim.

No report or missing receipt is interpreted as proof of failed ingestion.
The original event file must be retained until an independently approved
retention policy is implemented. No forced completion, negative outcome,
medical inference, or treatment recommendation is generated.

## Install (disposable Coach review checkout)

Keep `coach_app/physiology/delivery_status.html` beside
`delivery_status.js`. Open the HTML file directly in a modern browser.
A static local page is sufficient; no API, Home Assistant connection,
Node-RED flow or new credential is needed.

First, select the original `.coach-event.json` file in the browser.
Optionally select a report created by Mother's **explicit local** command:

```bash
python -m mother.physiology.delivery_state \
  --input /path/to/synthetic.coach-event.json \
  --archive /path/to/disposable/archive.sqlite3 \
  --receipt /path/to/private/receipt.mother-receipt.json \
  --output /path/to/new-private-status.json
```

Use only synthetic/disposable files until the restored NAS path and
identity/permission policy are reviewed. An `--attempted` flag in
Mother's CLI, or the browser's own checkbox, means the *operator reports*
a transfer attempt — it is not a verified event delivery.

The viewer uses only a local file chooser, browser Web Crypto and
textContent for untrusted data. It does not use browser localStorage,
sessionStorage, network APIs or event deletion. A Content Security
Policy explicitly forbids all network connections.

## VERIFY (isolated and synthetic)

```bash
node --test tests/test_delivery_status.cjs
node --check coach_app/physiology/delivery_status.js
```

For actual-browser QA, install pinned Playwright 1.55 Chromium in an
isolated Python environment and run:

```bash
python -m unittest discover -s tests -p test_delivery_status_browser.py -v
```

The GitHub Actions workflow runs Node 22 pure-function tests and real
Chromium tests on Ubuntu 24.04. Acceptance covers packet SHA-256 and event
ID, distinct prepared/unknown/archive-reported states, forged/mismatched
report rejection, copy-only warning, no file deletion, keyboard use,
small-screen layout and no external requests.

## Release notes, limitations and next work

- Adds a read-only status page; **does not** modify the existing Coach
  capture form or the Mother archive.
- Displays Mother verification results only as **unauthenticated claims
  imported from a local file**.
- Preserves all original event envelopes and receipts.
- Does not implement secure live sender authorization, receipt transport,
  browser archive verification, deployment, voice capture or auto-prompts.
- Actual NAS files, credentials, physical devices and personal records
  remain outside the test scope.

Further work: pinned paired CI using actual Mother S1-generated status
reports; then, only after runtime reconciliation, decide authenticated
Coach/Mother transport and subject grants. That is a separate acceptance
gate, not implied by this UI.
