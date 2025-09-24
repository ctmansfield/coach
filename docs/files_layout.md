# Files & Layout (target)

Inside the VM (persistent):

```
/srv/coach/
  compose/                  # docker compose files (future)
  configs/
    ha/
    nodered/
    coach/
      profile/pop.yaml
      playbooks/
      nutrition/
      study/
    rag/
    nightscout/
    signals/
    diary/
  secrets/                  # SOPS-encrypted secrets (tokens, credentials)
  logs/
  backups/
```

Repository on NAS (design docs and templates only in v0.1.0): `/mnt/nas_storage/repos/coach/`
