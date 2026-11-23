#!/usr/bin/env bash
# Ticket Arena: start/stop everything with one command.
#
#   ./ta.sh up       build + start the container AND the host agent (worktrees, context meter)
#   ./ta.sh down     stop both
#   ./ta.sh restart  restart both (after editing config.json or code)
#   ./ta.sh status   is each part running?
#   ./ta.sh logs     follow the host agent's log
#
# The host agent runs as a systemd user service when systemd is available, so it restarts
# by itself if it crashes and starts again when you log in. Otherwise it runs in the background.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
DIR="$PWD"
UNIT="ticket-arena-host"
UNIT_FILE="$HOME/.config/systemd/user/$UNIT.service"
PIDFILE="$DIR/data/host.pid"
LOGFILE="$DIR/data/host.log"

have_systemd() { systemctl --user is-system-running >/dev/null 2>&1 || [ "$(systemctl --user is-system-running 2>/dev/null)" = "degraded" ]; }

host_up() {
  mkdir -p "$DIR/data"
  if have_systemd; then
    mkdir -p "$(dirname "$UNIT_FILE")"
    # PATH captured now, so the service finds node/pnpm (nvm), gh and your worktree script
    cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Ticket Arena host agent (worktrees + Claude context meter)

[Service]
WorkingDirectory=$DIR
ExecStart=$(command -v python3) $DIR/ta-host.py
Environment=PATH=$HOME/.local/bin:$PATH
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now "$UNIT" >/dev/null 2>&1
    systemctl --user restart "$UNIT"
    echo "host agent: running (systemd user service $UNIT)"
  else
    host_down_bg
    nohup python3 "$DIR/ta-host.py" >>"$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "host agent: running in the background (pid $(cat "$PIDFILE"), log data/host.log)"
  fi
}

host_down_bg() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then kill "$(cat "$PIDFILE")"; fi
  rm -f "$PIDFILE"
}

host_down() {
  if have_systemd && [ -f "$UNIT_FILE" ]; then
    systemctl --user disable --now "$UNIT" >/dev/null 2>&1 || true
  fi
  host_down_bg
  echo "host agent: stopped"
}

container_up() {
  GH_TOKEN="$(gh auth token)" TA_UID="$(id -u)" TA_GID="$(id -g)" docker compose up -d --build
}

case "${1:-}" in
  up)      container_up; host_up; echo "dashboard: http://localhost:8765" ;;
  down)    docker compose down; host_down ;;
  restart) docker compose restart; host_up ;;
  status)
    docker ps --filter name=ticket-arena --format 'container: {{.Status}}' | grep . || echo "container: stopped"
    if have_systemd && [ -f "$UNIT_FILE" ]; then echo "host agent: $(systemctl --user is-active "$UNIT")"
    elif [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then echo "host agent: running"
    else echo "host agent: stopped"; fi ;;
  logs)
    if have_systemd && [ -f "$UNIT_FILE" ]; then journalctl --user -u "$UNIT" -f; else tail -F "$LOGFILE"; fi ;;
  *) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
