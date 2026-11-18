# Coach — v0.2.0 review increment

Coach contains interaction code, Node-RED/Home Assistant flows, rules, planning
clients and design/configuration documents. The running deployment and its local
changes have not been verified by this review release.

PF-001 adds a source-aware offline physiology replay viewer using the shared
Mother contract 1.0.0, corrects malformed flow files, preserves CGM identity/time
in a disabled candidate-preview flow, and gates notification-capable tests.
Recommendations, acknowledgments, performed actions and outcomes remain separate.
The scalar viewer preserves explicit gaps and unknowns; it does not diagnose
baseline departures or infer ECG/RR from heart rate.

See [physiology integration](docs/physiology/README.md) for exact scope, rendering
commands and compatibility. The paired release bundle contains INSTALL/VERIFY,
patches, a pinned revision manifest, the dependency-aware task board, source
capability inventory and design decisions still requiring evidence. Install into
new review worktrees before reconciling the actual deployed flow export.

The documented `/mnt/nas_storage/repos/coach/` and incoming-bundle paths remain
deployment references, not evidence of the current host layout. Existing design
documents describe the VM and system-level LLM/PostgreSQL division; this increment
does not choose or change those deployment boundaries.

