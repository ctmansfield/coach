# Change Control

- Dedicated repo: `/mnt/nas_storage/repos/coach/`
- Branching model: `main` (stable), `dev` (next).
- Patches delivered to `/mnt/nas_storage/incoming/` with:
  - `INSTALL.md` (exact steps),
  - `VERIFY.md` (smoke tests),
  - `RELEASE_NOTES.md` (rationale, diffs).
- Every change updates `CHANGELOG.md` and increments semver.
