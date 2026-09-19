#!/usr/bin/env bash
# Start FastAPI (internal only), wait until it answers, then start the public Next.js server.
# Platforms route traffic once $PORT is listening, so starting Next.js last avoids errors on cold start.
# Exit if either process dies so the platform restarts the container.
set -euo pipefail

cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

python - <<'PY'
import time, urllib.request
for _ in range(240):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1)
        break
    except Exception:
        time.sleep(0.25)
PY

cd /app/frontend
HOSTNAME=0.0.0.0 PORT="${PORT:-7860}" node server.js &

wait -n
exit $?
