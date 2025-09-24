#!/usr/bin/env bash
set -u

# =========================
# Host Orchestrator (llm)
# =========================
# Runs *everything* from the host. VM work is done via SSH.
# Safe to re-run. Never exits early; logs each step.

# ----- Environment guard: must be on llm -----
if ! hostname | grep -q '^llm$'; then
  echo "Refusing to run: this script is only for the libvirt host (llm)." >&2
  echo "hostname=$(hostname)" >&2
  exit 1
fi

# ---------- Config (edit if needed) ----------
REPO=/repos/coach
VM_HOST=192.168.122.22
VM_USER=coach
VM="${VM_USER}@${VM_HOST}"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
SSH="ssh ${SSH_OPTS} ${VM}"
SCP="scp ${SSH_OPTS}"

NET_XML_SRC=$REPO/host/llm/libvirt/default.xml
NET_XML_ETC=/etc/libvirt/qemu/networks/default.xml
NET_XML_AUTO=/etc/libvirt/qemu/networks/autostart/default.xml

# ---------- Logging helpers ----------
TS_GLOBAL="$(date +%F_%H-%M-%S)"
RUNLOG="/tmp/llm-run_${TS_GLOBAL}.log"
FAIL=0
log(){ printf "\n[%s] %s\n" "$(date +%F-%T)" "$*" | tee -a "$RUNLOG"; }
run(){ log "\$ $*"; eval "$@" >>"$RUNLOG" 2>&1; rc=$?; [ $rc -ne 0 ] && { echo "  -> ERROR rc=$rc" | tee -a "$RUNLOG"; FAIL=1; }; return $rc; }
finish(){ echo; echo "Run log: $RUNLOG"; sha256sum "$RUNLOG" | awk '{print "SHA256:",$1}'; [ $FAIL -eq 0 ] || echo "Completed with errors (see log)."; }

# ---------- VM file payloads (heredocs) ----------
emit_vm_compose(){ cat <<'YAML'
services:
  caddy:
    image: caddy:2
    container_name: caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - caddy_config:/config
      - caddy_data:/data
      - /repos/coach/vm/coach/docker/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    depends_on:
      - homeassistant
      - nodered
    restart: unless-stopped

  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    ports:
      - "8123:8123"
    volumes:
      - ha_config:/config
    restart: unless-stopped

  nodered:
    image: nodered/node-red:latest
    container_name: nodered
    ports:
      - "1880:1880"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:1880"]
      interval: 30s
      timeout: 5s
      retries: 5
    volumes:
      - nodered_data:/data
volumes:
  caddy_config:
  caddy_data:
  ha_config:
  nodered_data:
YAML
}

emit_vm_caddyfile(){ cat <<'CF'
{
  debug
}

:80 {
  encode gzip
  redir https://{host}{uri}
}

(common) {
  encode gzip

  handle_path /ha/* {
    reverse_proxy http://homeassistant:8123
  }

  handle_path /flows/* {
    reverse_proxy http://nodered:1880
  }

  handle {
    respond "coach-vm is alive (https)" 200
  }
}

localhost, coach-vm.lab.lan, coach.lab.lan, ha.lab.lan, flows.lab.lan, 192.168.122.22 {
  tls internal
  import common
}
CF
}

emit_vm_coach_deploy(){ cat <<'SHVM'
#!/usr/bin/env bash
set -u

if ! hostname | grep -q '^coach-vm$'; then
  echo "Refusing to run: only for coach-vm." >&2; echo "hostname=$(hostname)" >&2; exit 1
fi

log(){ printf "\n[%s] %s\n" "$(date +%F-%T)" "$*"; }
run(){ log "$*"; eval "$@"; rc=$?; [ $rc -ne 0 ] && echo "  -> ERROR rc=$rc"; return $rc; }

REPO=/repos/coach
COMPOSE=$REPO/vm/coach/docker/compose/docker-compose.yml
CADDYFILE=$REPO/vm/coach/docker/caddy/Caddyfile

choose_docker(){ d=docker; $d ps >/dev/null 2>&1 || d="sudo docker"; echo "$d"; }
DOCKER="$(choose_docker)"

preflight() {
  sudo install -d -m 0755 /srv/coach /srv/coach/configs
  [ -L /srv/coach/compose ] || sudo ln -sfn "$REPO/vm/coach/docker/compose" /srv/coach/compose
  [ -L /srv/coach/configs/caddy ] || sudo ln -sfn "$REPO/vm/coach/docker/caddy" /srv/coach/configs/caddy

  run "$DOCKER --version"
  run "$DOCKER compose version || docker-compose version || true"
  run "$DOCKER compose -f '$COMPOSE' config"
  log "Symlinks:"; ls -l /srv/coach/compose /srv/coach/configs/caddy 2>/dev/null || true
  log "SHA256:"; (sha256sum "$COMPOSE" "$CADDYFILE" 2>/dev/null || true)
}

up()      { run "$DOCKER compose -f '$COMPOSE' up -d"; }
down()    { run "$DOCKER compose -f '$COMPOSE' down"; }

verify() {
  run "$DOCKER ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
  log "DNS via host 192.168.122.1:"; (dig +short @192.168.122.1 coach-vm.lab.lan ha.lab.lan flows.lab.lan || true)
  run "curl -sI  http://localhost/ | head -n1"
  run "curl -skI https://localhost/ | head -n1"
  run "curl -skI https://ha.lab.lan/ | head -n1"
  run "curl -skI https://flows.lab.lan/ | head -n1"
  run "curl -skL -o /dev/null -w 'HA /ha/ -> %{http_code}\n'     https://ha.lab.lan/ha/"
  run "curl -skL -o /dev/null -w 'Node-RED /flows/ -> %{http_code}\n' https://flows.lab.lan/flows/"
  if $DOCKER ps --format '{{.Names}}' | grep -q '^caddy$'; then
    run "$DOCKER exec caddy caddy validate --config /etc/caddy/Caddyfile"
  fi
}

diag() {
  TS="$(date +%F_%H-%M-%S)"; OUT="/tmp/coach-diag_${TS}.txt"
  {
    echo "=== coach-diag $TS (coach-vm) ==="
    whoami; hostname
    $DOCKER --version 2>&1
    ($DOCKER compose version || docker-compose version) 2>&1
    sha256sum "$COMPOSE" "$CADDYFILE" 2>/dev/null || true
    ls -l /srv/coach/compose /srv/coach/configs/caddy 2>/dev/null || true
    $DOCKER ps 2>&1
    $DOCKER compose -f "$COMPOSE" config 2>&1
    $DOCKER logs --tail=120 caddy 2>&1 || true
    $DOCKER port caddy 2>&1 || true
    resolvectl status 2>&1 || true
    dig +short @192.168.122.1 coach-vm.lab.lan ha.lab.lan flows.lab.lan || true
    curl -sI  http://localhost/ | head -n1
    curl -skI https://localhost/ | head -n1
    curl -skI https://ha.lab.lan/ | head -n1
    curl -skI https://flows.lab.lan/ | head -n1
    curl -skL -o /dev/null -w 'HA /ha/ -> %{http_code}\n'     https://ha.lab.lan/ha/
    curl -skL -o /dev/null -w 'Node-RED /flows/ -> %{http_code}\n' https://flows.lab.lan/flows/
  } >"$OUT"
  HASH="$(sha256sum "$OUT" | awk '{print $1}')"
  echo "Wrote: $OUT"
  echo "SHA256: $HASH"
}

case "${1:-}" in
  preflight) preflight ;;
  up)        up ;;
  down)      down ;;
  verify)    verify ;;
  diag)      diag ;;
  *) echo "usage: $(basename "$0") {preflight|up|down|verify|diag}"; exit 0 ;;
esac
SHVM
}

emit_host_default_xml(){ cat <<'XML'
<network connections='2'>
  <name>default</name>
  <forward mode='nat'><nat><port start='1024' end='65535'/></nat></forward>
  <bridge name='virbr0' stp='on' delay='0'/>
  <mac address='52:54:00:b0:e2:00'/>
  <domain name='lab.lan' localOnly='yes'/>
  <dns>
    <host ip='192.168.122.22'>
      <hostname>coach-vm</hostname>
      <hostname>coach</hostname>
      <hostname>ha</hostname>
      <hostname>flows</hostname>
      <hostname>coach-vm.lab.lan</hostname>
      <hostname>coach.lab.lan</hostname>
      <hostname>ha.lab.lan</hostname>
      <hostname>flows.lab.lan</hostname>
    </host>
  </dns>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
      <host mac='52:54:00:0f:12:4f' name='coach-vm' ip='192.168.122.22'/>
    </dhcp>
  </ip>
</network>
XML
}

# ---------- Host-side tasks ----------
host:preflight() {
  run "virsh -v"
  run "dnsmasq --version | head -n1 || true"
  run "ip addr show virbr0 || true"
  run "ps aux | grep -E '[d]nsmasq.*virbr0' || true"
  run "dig +short @192.168.122.1 coach-vm.lab.lan ha.lab.lan flows.lab.lan || true"
}

host:dns-apply() {
  if [ ! -f "$NET_XML_SRC" ]; then
    run "sudo install -d -m 0755 '$(dirname "$NET_XML_SRC")'"
    emit_host_default_xml | sudo tee "$NET_XML_SRC" >/dev/null
  fi
  run "sudo install -D -m 0644 '$NET_XML_SRC' '$NET_XML_ETC'"
  run "sudo ln -sfn '$NET_XML_ETC' '$NET_XML_AUTO'"
  run "virsh net-destroy default || true"
  run "virsh net-define '$NET_XML_ETC'"
  run "virsh net-start default"
  run "virsh net-autostart default"
  run "ss -lunp | grep ':53' || true"
  run "dig +short @192.168.122.1 coach-vm.lab.lan ha.lab.lan flows.lab.lan"
}

host:diag() {
  TS="$(date +%F_%H-%M-%S)"; OUT="/tmp/llm-diag_${TS}.txt"
  {
    echo "=== llm-diag $TS (host) ==="
    whoami; hostname
    virsh -v 2>&1
    sed -n '1,200p' /etc/libvirt/qemu/networks/default.xml 2>/dev/null || true
    ls -l /etc/libvirt/qemu/networks/autostart/default.xml 2>/dev/null || true
    ip addr show virbr0 2>&1 || true
    ps aux | grep -E '[d]nsmasq.*virbr0' 2>&1 || true
    dig +short @192.168.122.1 coach-vm.lab.lan ha.lab.lan flows.lab.lan 2>&1
  } >"$OUT"
  HASH="$(sha256sum "$OUT" | awk '{print $1}')"
  echo "Wrote: $OUT"
  echo "SHA256: $HASH"
}

# ---------- VM-side orchestrated from host ----------
vm:push() {
  # Create dirs on VM
  run "$SSH 'sudo install -d -m 0755 /repos/coach/bin /repos/coach/vm/coach/docker/compose /repos/coach/vm/coach/docker/caddy'"

  # Write files on VM
  emit_vm_compose     | run "$SSH 'cat | sudo tee /repos/coach/vm/coach/docker/compose/docker-compose.yml >/dev/null'"
  emit_vm_caddyfile   | run "$SSH 'cat | sudo tee /repos/coach/vm/coach/docker/caddy/Caddyfile >/dev/null'"
  emit_vm_coach_deploy| run "$SSH 'cat | sudo tee /repos/coach/bin/coach-deploy.sh >/dev/null'"

  # Permissions & symlinks
  run "$SSH 'sudo chmod +x /repos/coach/bin/coach-deploy.sh && sudo ln -sfn /repos/coach/bin/coach-deploy.sh /usr/local/bin/coach-deploy'"
  # Link service config paths
  run "$SSH 'sudo install -d -m 0755 /srv/coach /srv/coach/configs && ([ -L /srv/coach/compose ] || sudo ln -sfn /repos/coach/vm/coach/docker/compose /srv/coach/compose) && ([ -L /srv/coach/configs/caddy ] || sudo ln -sfn /repos/coach/vm/coach/docker/caddy /srv/coach/configs/caddy)'"

  # Show hashes (easy to diff)
  run "$SSH 'sha256sum /repos/coach/vm/coach/docker/compose/docker-compose.yml /repos/coach/vm/coach/docker/caddy/Caddyfile /repos/coach/bin/coach-deploy.sh'"
}

vm:preflight() { run "$SSH coach-deploy preflight"; }
vm:up()        { run "$SSH coach-deploy up"; }
vm:verify()    { run "$SSH coach-deploy verify"; }
vm:diag()      { run "$SSH coach-deploy diag"; }

# ---------- One-shot workflows ----------
all() {
  host:preflight
  host:dns-apply
  vm:push
  vm:preflight
  vm:up
  vm:verify
  vm:diag
}

usage(){
  cat <<USAGE
usage: $(basename "$0") <command>

Host (llm) commands:
  host:preflight     - check libvirt/dnsmasq and current DNS answers
  host:dns-apply     - install/ensure default.xml and restart 'default' net
  host:diag          - write /tmp/llm-diag_*.txt + SHA256

VM (via SSH to ${VM}):
  vm:push            - create dirs, push compose/Caddyfile/coach-deploy, link paths
  vm:preflight       - validate docker compose & symlinks on VM
  vm:up              - docker compose up -d (VM)
  vm:verify          - probe endpoints & validate caddy (VM)
  vm:diag            - write /tmp/coach-diag_*.txt on VM + SHA256

Orchestration:
  all                - host:preflight -> host:dns-apply -> vm:push -> vm:preflight -> vm:up -> vm:verify -> vm:diag
USAGE
}

cmd="${1:-}"; shift || true
case "$cmd" in
  host:preflight) host:preflight ;;
  host:dns-apply) host:dns-apply ;;
  host:diag)      host:diag ;;
  vm:push)        vm:push ;;
  vm:preflight)   vm:preflight ;;
  vm:up)          vm:up ;;
  vm:verify)      vm:verify ;;
  vm:diag)        vm:diag ;;
  all)            all ;;
  *)              usage ;;
esac

finish
