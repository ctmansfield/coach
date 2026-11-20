# I01-U2 — Offline browser QA for Coach manual capture

**Scope:** Browser usability, keyboard access, standalone file:// operation, local
download and evidence integrity. Synthetic input only. No NAS or service changes.

**Owner:** Independent UI verification worker; the Coach capture form and JS
remain with the existing Coach interaction owner, and Mother owns the
archive/receipt path. Shared contract 1.0.0 remains PM-owned and unchanged.

**Base:** Coach I01-U PR #4, `work/i01-offline-manual-capture-ui`.
The next branch adds only independent browser tests, a dedicated CI job,
and these instructions unless a browser failure requires a bounded fix.

## Installation and testing

Use an isolated checkout on the I01-U2 branch, with Python 3.11+.
Install the pinned Playwright runtime and its Chromium build into a disposable
environment. Do not install browser automation into the NAS deployment.

```bash
python -m pip install 'playwright==1.55.0'
python -m playwright install chromium
python -m unittest discover -s tests -p test_capture_browser.py -v
```

The GitHub workflow additionally installs Chromium's system dependencies
and uploads **synthetic-only** desktop/mobile screenshots for visual review.

## Acceptance

The test must directly open the static `manual_capture.html` file in
Chromium. It should verify:

- A label and useful tab order for required inputs.
- No unexpected horizontal scroll on desktop or 390px mobile viewport.
- A successful, actual browser download whose original event bytes,
  SHA-256, event kind, null known time and explicit time offset are correct.
- An outcome cannot be submitted without a typed parent; valid parent
  produces a separate reported outcome with a related event ID.
- Switching to a standalone marker clears the hidden parent fields.
- Invalid dates are rejected visibly without creating a file.
- No external HTTP requests, no browser storage after reload, and no
  uncaught page exceptions.

## Evidence boundaries

The GUI is not a logged-in app and does not persist to the Mother archive.
The browser's recorded clock and any caller-selected subject ID are
unverified. A content digest provides byte integrity, not authentication.

Automation results do not establish usability with every assistive
technology, browser, language or physical device. Uploaded screenshots
use only synthetic subject IDs; actual event exports are private data
and must not be uploaded to GitHub.

The existing Mother I01-T2 offline acceptance remains authoritative for
archival idempotency, revisions, and source-linked replay. A future
authenticated identity/transport design cannot be replaced by this test.

## Release

Review the screenshot artifact and CI logs. Keep the PR in draft until
independent usability, acceptance checks and release dependencies are
reconciled. No deployment to NAS, merger into main, or credentials change.

## Executed browser verification (8 November 2026)

**Independent browser gate: PASS, source/synthetic browser evidence only.**

- Verified head before documentation update:
  `78c15fccfbf83df5d33df8d29549cd7a02efd10e`.
- [GitHub Actions real Chromium run](https://github.com/ctmansfield/coach/actions/runs/42446663212):
  **7 tests passed, 0 failures**, Python 3.11, Playwright 1.55.0,
  Ubuntu 24.04, with pinned Chromium and no live application services.
- [Synthetic desktop and mobile screenshots](https://github.com/ctmansfield/coach/actions/runs/42446663212/artifacts/13603658618)
  were uploaded for independent visual review.
- Manual screenshot inspection: labels, field spacing and warnings are
  readable on 1365px desktop and 390px mobile; no horizontal clipping was
  observed in either screenshot. This does not establish screen-reader
  compatibility or color-contrast conformance.
- Actual Chromium download parsed successfully, and the original event
  bytes, envelope SHA-256, filename digest, unknown knowledge time,
  reported epistemic state and explicit timestamp offset matched
  expectations. No external HTTP requests were observed.

**Resolved test/infrastructure failures:** The first run stopped before
tests because Playwright 1.55 did not support the runner's Ubuntu 26.04
browser installation. The workflow now uses Ubuntu 24.04. The first
actual browser attempt then passed four tests but exposed three ambiguous
test locators (the accessible name "Event type" was also a substring of
"Earlier event type"). These locators were made exact; seven tests passed
on the final focused run. The product code was not changed to hide those
test problems.

**Still open:** A human can review the browser in other operating systems
and assistive technologies. A completed browser download does *not*
establish archival receipt. Authenticated sender identity, local file
retention policy, actual NAS installation, any device integration, and
live delivery remain outside this gate. No private source data was used.
