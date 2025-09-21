# VM Deployment: Pros, Cons, and Suggestions

## Why a VM for the coach stack
You asked to isolate all coach services inside a virtual machine (VM), keeping the **LLM** and **Postgres** at the system level. This section details trade‑offs and gives practical suggestions.

## Pros
- **Isolation & stability:** Changes to the coach stack cannot break your other projects. Snapshots let you roll back safely.
- **Reproducibility:** One image is the source of truth. New environments are consistent and predictable.
- **Security boundary:** UFW inside the VM, separate credentials, and limited exposed ports reduce blast radius.
- **Upgrade safety:** You can test new versions of HA/Node‑RED/flows in a cloned VM before promoting.
- **Clean dependency graph:** Python/Node libraries, HACS, and addons stay inside the VM—no conflicts with host tools.
- **Backup simplicity:** VM snapshots + a small internal backup routine (tar of `/srv/coach/configs`, diary, signals).
- **Resource controls:** Limit CPU/RAM/I/O for the stack independent of the host workloads.

## Cons
- **Overhead:** Some CPU/RAM and storage overhead vs. bare‑metal containers.
- **Device passthrough friction:** Direct BLE/NFC/USB integrations are trickier from a VM (workarounds exist: bridges, HA add‑ons, or host↔VM proxies).
- **Networking complexity:** You’ll manage VM IPs, reverse proxy, certificates; slightly more moving parts.
- **Observability duplication:** Separate logs/metrics inside the VM unless you federate to host-level monitoring.
- **Image drift risk:** If you hot‑patch inside the VM but forget to update the build manifest, reproducibility suffers.

## When a VM is an especially good choice
- You want **hard isolation** from other services and a safe roll‑back path.
- You expect frequent iteration on HA/Node‑RED/RAG without disturbing host LLM/DB.
- You plan to use **Nightscout** or similar services whose dependencies may collide with other projects.

## When you might *not* want a VM
- You need **very low latency** hardware integrations requiring direct device access (e.g., local BLE devices the VM can’t see).
- Host has **tight resources** (RAM/CPU) and you cannot afford the VM overhead.

## Suggestions to make the VM approach smooth
1. **Choose a snapshot‑friendly hypervisor** (Proxmox/KVM). Automate *image build* with cloud‑init or Packer.
2. **Two disks**: small root disk + dedicated data disk mounted at `/srv/coach` for persistent volumes and configs.
3. **Reverse proxy in the VM** (Caddy/Traefik) terminating TLS; expose only **443** and **22** externally; keep HA/Node‑RED internal.
4. **Secrets management**: use **SOPS/age** inside the VM, but keep master keys on the host; decrypt only for runtime.
5. **Strict networking**: VM talks out to Postgres (`192.168.1.225:55432`) and to host LLM endpoints; no inbound from internet.
6. **Backups**: nightly hypervisor snapshots + daily tar of `/srv/coach/{configs,diary,signals}`; rsync to NAS.
7. **Health checks & verify**: include smoke tests—watch notification, single‑room Alexa whisper, synthetic CGM spike event.
8. **Promote with blue/green**: bring up a clone VM on a test IP, run `VERIFY.md`, then cut over DNS when satisfied.
