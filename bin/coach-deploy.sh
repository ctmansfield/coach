#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="/repos/coach/vm/coach/coach.env"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE"; exit 1; }
source "$ENV_FILE"

log(){ printf "[%s] %s\n" "$(date +%F-%T)" "$*"; }
need(){ command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1"; exit 1; }; }

ensure_symlinks() {
  # Compose dir
  sudo install -d -m 0755 "$(dirname "$SYS_COMPOSE_DIR")"
  sudo rm -rf "$SYS_COMPOSE_DIR" 2>/dev/null || true
  sudo ln -sfn "$(dirname "$COMPOSE_FILE")" "$SYS_COMPOSE_DIR"

  # Caddy dir
  sudo install -d -m 0755 "$(dirname "$SYS_CADDY_DIR")"
  sudo rm -rf "$SYS_CADDY_DIR" 2>/dev/null || true
  sudo ln -sfn "$(dirname "$CADDYFILE")" "$SYS_CADDY_DIR"
}

backup_root() {
  local root="$NAS_BACKUP_ROOT"
  if ! mkdir -p "$root" 2>/dev/null || ! test -w "$root"; then
    root="$HOME/backups"
    mkdir -p "$root"
    log "NAS not writable; using local fallback: $root"
  fi
  echo "$root"
}

preflight() {
  need docker; need curl
  command -v jq >/dev/null 2>&1 || log "Note: jq not found (volume backup will skip named volumes)"
  ensure_symlinks
  # Quick DNS sanity (non-fatal)
  dig +short @"$DNS_IP" coach-vm."$DOMAIN" ha."$DOMAIN" flows."$DOMAIN" | sed 's/^/  /' || true
  [ -f "$COMPOSE_FILE" ] || { echo "Missing $COMPOSE_FILE"; exit 1; }
  [ -f "$CADDYFILE" ] || { echo "Missing $CADDYFILE"; exit 1; }
  log "Preflight OK"
}

up() {
  preflight
  docker compose -f "$COMPOSE_FILE" up -d
  sleep 2
  docker port caddy || true
}

verify() {
  preflight
  curl -sI http://localhost/ | head -n1 || true
  for h in $HOSTNAMES; do
    case "$h" in *.*|localhost)
      curl -sk --http1.1 "https://$h/" -o /dev/null -w "  $h: %{http_code}\n" || true
      ;;
    esac
  done
  curl -sk --http1.1 "https://ha.$DOMAIN/" -o /dev/null -w "  ha: %{http_code}\n" || true
  curl -sk --http1.1 "https://flows.$DOMAIN/" -o /dev/null -w "  flows: %{http_code}\n" || true
}

backup() {
  need tar
  local root stamp out
  root="$(backup_root)"
  stamp="$(date +%F_%H-%M-%S)"
  out="$root/coach-vm-backup_$stamp"
  mkdir -p "$out"

  log "Copying repo configs"
  sudo mkdir -p "$out/repo"
  sudo cp -a /repos/coach/vm/coach "$out/repo/" 2>/dev/null || true

  if command -v jq >/dev/null 2>&1; then
    for svc in $SERVICES; do
      if docker inspect "$svc" >/dev/null 2>&1; then
        docker inspect "$svc" \
        | jq -r '.[0].Mounts[] | select(.Type=="volume") | .Name + ":" + .Destination' \
        | while IFS=: read -r vol dest; do
            [ -z "${vol:-}" ] && continue
            mkdir -p "$out/volumes/$svc"
            log "Saving named volume $vol from $svc"
            docker run --rm -v "$vol":/src -v "$out/volumes/$svc":/dest alpine \
              sh -lc "cd /src && tar -czf /dest/${vol}.tar.gz ."
          done
      fi
    done
  else
    log "Skipping named volume export (jq not installed)"
  fi

  tar -C "$out/.." -czf "$out.tar.gz" "$(basename "$out")"
  log "Backup: $out.tar.gz"
}

trust_ca() {
  local ca_src="/config/pki/authorities/local/root.crt"
  local tmp="/tmp/caddy-local-ca.crt"
  if docker exec caddy test -f "$ca_src"; then
    docker cp caddy:"$ca_src" "$tmp"
    log "Exported CA to $tmp (import to clients' truststores)"
  else
    log "CA not present yet (run 'up' first and hit the HTTPS hostnames once)"
  fi
}

usage(){ cat <<USAGE
Usage: $(basename "$0") <preflight|up|verify|backup|trust-ca>
USAGE
}

case "${1:-}" in
  preflight) preflight ;;
  up) up ;;
  verify) verify ;;
  backup) backup ;;
  trust-ca) trust_ca ;;
  *) usage; exit 1;;
esac
