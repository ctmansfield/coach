# INSTALL (Design Docs Only) — v0.1.0

> This bundle contains **documents and templates only**. No services are deployed in this version.

## Where to place files
1. Save the tarball to: `/mnt/nas_storage/incoming/coach-design-v0.1.0.tar.gz`
2. Extract into your repo path:
   ```
   mkdir -p /mnt/nas_storage/repos/coach
   tar -xzf /mnt/nas_storage/incoming/coach-design-v0.1.0.tar.gz -C /mnt/nas_storage/repos/coach
   ```

## Initialize Git repository and push to GitHub
```
cd /mnt/nas_storage/repos/coach
git init
git add -A
git commit -m "chore: add coach design docs v0.1.0"
git branch -M main
# Replace with your repo:
git remote add origin git@github.com:ctmansfield/coach.git
git push -u origin main
```

## Context reader tooling — v0.1.1

Obtain the reviewed adoption commit through the normal repository update flow.
From the repository root, run `python3 tools/context_project.py --root context resume`.
The committed profile is initialized and starts UNSEEDED; use `.codex/READER.md`
when initializing a separate project. Review `.codex/hooks.json` through the
supported host's normal hook trust process. Old worktrees and conversations need
the explicit intake/update described in `.codex/RESUME.md`.
