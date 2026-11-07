# I01-P — Manual factual events (standalone draft foundation)

**Status:** Source implementation and offline synthetic acceptance; full durability
and prompt-response UX remain dependent on the qualified Mother import path.

**Owner and files:** Coach interaction worker owns
`coach_app/physiology/manual_events.py`, `tests/test_manual_events.py`,
and this document. PM owns shared contract 1.0.0, migrations and integration.
**Base:** Coach PF-001 `work/physiology-foundation-pf001`.

## Purpose

Provide a small, explicit draft constructor for user-initiated factual records
without turning consent, acknowledgment, or silence into actions or outcomes.
The constructor neither reads nor writes Mother archives, executes a
recommendation, asks a question, emits a notification, or assigns a readiness
score. It returns one contract-shaped `event` dictionary for a separate
validated persistence workflow.

Supported manually reported event kinds are `user_marker`, `context`,
`answer`, `acknowledgment`, `reported_action`, and `outcome`.
It cannot generate `observed_action`, `question` or `recommendation`.
The latter must originate from distinct audited components.

## References and time

- Answers require a linked question.
- Acknowledgments require a linked recommendation; they never imply performance.
- Reported actions can be independent or linked to a recommendation/acknowledgment.
- Outcomes require an explicit action parent; *no outcome record* is generated
  when no outcome is available.
- Parents must have the same subject ID and an appropriate event kind.
- Original offset-aware timestamps are preserved. Unknown occurrence/known
  times remain `null`; no recorded time is substituted for occurrence.

These checks are intentionally narrower than full schema/linkage validation.
Before any actual archival commit, Mother must validate the complete canonical
record, resolve linked event identities and session/subject ownership, and
retain source/provenance revision metadata. This release does **not** claim that
draft events are durable in Mother.

## INSTALL / VERIFY

Work in a new isolated Coach worktree based on PF-001; do not replace
running flows. The function is pure Python and adds no application runtime
dependency. No migrations or credential changes are needed.

```bash
python -m unittest discover -s tests -p test_manual_events.py -v
```

The dedicated GitHub Actions workflow runs only this suite. It neither calls
Nightscout nor enables the existing network notification tests.

## Follow-up gates

1. Implement an authorized, versioned event-ingestion path into Mother's single
   durable archive; preserve original action provenance and immutable revisions.
2. Build Coach's user-facing manual marker/answer/action capture flow and offline
   round-trip acceptance with Mother.
3. Later, after real-data source qualification and design input, add selective
   factual questions triggered by credible variation; keep missing answers
   unknown and permit no routine subjective readiness labels.
4. Independently verify repeated saves, interrupted writes, time provenance,
   permissions and replay agreement before deployment.

Synthetic construction does not constitute real-data verification, live
behavior, or clinical evaluation.
