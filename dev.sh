#!/bin/bash
# Local development: start/stop the backend (:8000) and frontend (:3000) in the background.
#
#   ./dev.sh start      start both (logs in .run/)
#   ./dev.sh stop       stop both
#   ./dev.sh restart    stop, then start
#   ./dev.sh status     what's running
#   ./dev.sh logs       follow both logs (Ctrl+C to leave; the servers keep running)

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
mkdir -p "$RUN"

# The conda env this project uses; override with MENU_PYTHON=/path/to/python ./dev.sh start
PYTHON="${MENU_PYTHON:-$HOME/miniconda3/envs/menu/bin/python}"

port_pids() { lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null; }

wait_for() {  # name url seconds
  for _ in $(seq 1 "$3"); do
    curl -s -o /dev/null "$2" && { echo "  $1 ready  → $2"; return 0; }
    sleep 1
  done
  echo "  $1 did not come up in $3s — see .run/$1.log"; return 1
}

start() {
  [ -f "$ROOT/.env" ] || { echo "Missing .env (cp .env.example .env, then add keys)"; exit 1; }
  [ -x "$PYTHON" ] || { echo "Python not found at $PYTHON (set MENU_PYTHON)"; exit 1; }

  if [ -n "$(port_pids 8000)" ]; then echo "  backend already running on :8000"
  else
    # exec: the server replaces the subshell, so no stray shell is left holding this terminal.
    (cd "$ROOT/backend" && exec nohup "$PYTHON" -m uvicorn app.main:app --reload --port 8000) \
      > "$RUN/backend.log" 2>&1 < /dev/null &
    echo "  backend starting…"
  fi

  if [ -n "$(port_pids 3000)" ]; then echo "  frontend already running on :3000"
  else
    [ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)
    (cd "$ROOT/frontend" && exec nohup npm run dev) > "$RUN/frontend.log" 2>&1 < /dev/null &
    echo "  frontend starting…"
  fi

  wait_for backend http://127.0.0.1:8000/api/health 60
  wait_for frontend http://localhost:3000 60
}

stop() {
  # Stop by port rather than by saved PID: --reload and `npm run dev` spawn child processes,
  # and whatever is actually listening is what has to go.
  for port in 8000 3000; do
    pids=$(port_pids $port)
    if [ -n "$pids" ]; then
      kill $pids 2>/dev/null; sleep 1
      pids=$(port_pids $port); [ -n "$pids" ] && kill -9 $pids 2>/dev/null
      echo "  stopped :$port"
    else
      echo "  nothing on :$port"
    fi
  done
}

status() {
  for pair in "backend 8000" "frontend 3000"; do
    set -- $pair
    if [ -n "$(port_pids $2)" ]; then echo "  $1  running on :$2"; else echo "  $1  stopped"; fi
  done
}

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  logs)    tail -n 30 -f "$RUN/backend.log" "$RUN/frontend.log" ;;
  *)       sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
