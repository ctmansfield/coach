# Coach physiology replay — PF-001

Canonical contract: Mother `mother/physiology/schemas/v1.schema.json`, version
1.0.0. The byte-identical Coach copy is `coach_app/physiology/schemas/v1.schema.json`.
The paired release manifest pins compatible repository commits and tree hashes;
the release verifier rejects differing schemas. The PM owns schema changes.

## Offline replay

Mother imports retained originals and emits replay JSON. Coach validates that
bundle and renders a self-contained HTML view without making service requests:

```bash
python -m coach_app.physiology.replay \
  --input /path/to/synthetic_replay.json \
  --output /path/to/synthetic_replay.html \
  --title "Synthetic exercise-to-sleep replay"
```

The viewer shows separate source/channel/epistemic lanes, discrete observations,
coverage gaps and unknown cadence. Tables preserve original and normalized
units, all four timing concepts, quality, method, session and source revisions.
Events with unknown occurrence remain in the event table. Import accounting
shows whole-source accepted/rejected/unsupported counts, including records not
plotted in the selected interval. Raw original payloads remain in the archive
and replay source records; the HTML source manifest omits those raw payloads.

This is a retrospective current-revision view. It does not establish what a
historical live predictor knew. No interpolation or clinical interpretation is
implied. Waveform/beat stream rendering is not implemented: nonempty `streams`
inputs are rejected explicitly. The marker constructor creates a reported event
for a caller to archive with source lineage; it is not a completed persistence or
automatic prompt workflow.

## Flow and test scope

`vm/coach/docker/nodered/README.md` documents canonical flows and the gated
legacy Nightscout candidate preview. The preview has no archive/catch-up
guarantee and does not emit blanket spike notifications. Reconcile actual
deployed exports and local changes before importing any flow replacement.

```bash
COACH_RUN_NETWORK_TESTS=0 python -m pytest -q \
  tests/test_physiology_flows.py tests/test_physiology_replay.py \
  tests/test_end_to_end.py
```

Root integration observed 54 passing checks and seven explicit live-test skips.
Use the final paired bundle's verification record for its exact tree evidence.
Do not enable live tests during ordinary development; the legacy suite can send
Home Assistant/Node-RED notifications. No notification was sent for this release.

See Mother `docs/physiology/` in the paired bundle for INSTALL, VERIFY, contracts,
capability inventory, task dependencies, design gaps and release notes. The
bundle uses new worktrees and preserves existing checkouts. Browser visual
inspection and real-data/runtime integration remain open gates.
