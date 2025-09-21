# Operations (when implemented)

- **Backups**
  - Nightly VM snapshot (hypervisor).
  - Daily tar of `/srv/coach/configs`, `/srv/coach/diary`, `/srv/coach/signals` to `/srv/coach/backups`, then rsync to NAS.
- **Monitoring**
  - HA dashboards for Risk gauge and cue stats.
  - Node-RED simple dashboard for event stream and escalations.
- **Security**
  - UFW allow 22, 443; deny others.
  - TLS on reverse proxy; internal services not exposed.
  - Tokens via SOPS; rotate quarterly.
