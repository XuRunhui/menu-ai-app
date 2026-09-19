#!/bin/bash
# Deploy Menuist to Cloud Run, and check the new version is really the one serving.
#
#   ./deploy.sh              test, deploy, then verify the live site runs the new revision
#   ./deploy.sh --dry-run    run every check and show what would happen, but don't deploy
#   ./deploy.sh status       the live URL, and which build and revision are serving
#   ./deploy.sh logs         the last 50 lines of the live server's log
#   ./deploy.sh secrets      copy the API keys from .env to Secret Manager, if they changed
#
# Project and region default to the ones below; override with MENUIST_GCP_PROJECT / MENUIST_REGION.
# First-time setup (billing, secrets, gcloud login) is in deploy/cloudrun/README.md.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${MENUIST_GCP_PROJECT:-gen-lang-client-0738760822}"
REGION="${MENUIST_REGION:-us-central1}"
SERVICE="menuist"
SECRETS=(DEEPSEEK_API_KEY GOOGLE_PLACES_API_KEY)
PYTHON="${MENU_PYTHON:-$HOME/miniconda3/envs/menu/bin/python}"

say()  { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

service_url() {
  gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
    --format='value(status.url)' 2>/dev/null || true
}

# The build marker main.py reports, so a deploy can be checked against the code that was sent.
local_build() {
  sed -n 's/^BUILD_MARKER = "\(.*\)"$/\1/p' "$ROOT/backend/app/main.py"
}

# The key from .env exactly as the app will read it: no quotes, no trailing newline or spaces.
# A newline pasted into a secret once made Places search silently return nothing.
env_value() {
  grep -E "^$1=" "$ROOT/.env" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' | tr -d '\r\n' |
    sed -e 's/[[:space:]]*$//'
}

preflight() {
  say "Checking gcloud"
  command -v gcloud >/dev/null || fail "gcloud isn't installed (brew install --cask google-cloud-sdk)."
  local account
  account="$(gcloud config get-value account 2>/dev/null)"
  [ -n "$account" ] || fail "gcloud isn't logged in. Run: gcloud auth login"
  echo "   account $account · project $PROJECT · region $REGION"

  say "Checking what will be sent"
  [ -f "$ROOT/.env" ] || fail "No .env file: the secrets check needs it."
  local branch changed
  branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  changed="$(git -C "$ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  # gcloud uploads the working directory, so uncommitted work is deployed too.
  echo "   branch $branch, $changed uncommitted file(s) — the working directory is what gets deployed"
  echo "   build marker: $(local_build)"

  say "Running backend tests"
  [ -x "$PYTHON" ] || fail "Python not found at $PYTHON (set MENU_PYTHON)."
  local output
  if output="$(cd "$ROOT/backend" && "$PYTHON" -m pytest -q -p no:warnings -m "not integration" 2>&1)"; then
    echo "   $(printf '%s\n' "$output" | tail -n 1)"
  else
    printf '%s\n' "$output" | tail -n 25
    fail "Backend tests fail — not deploying."
  fi

  say "Type-checking the frontend"
  (cd "$ROOT/frontend" && npx tsc --noEmit) || fail "Frontend has type errors — not deploying."
  echo "   ok"
}

# The stored value byte for byte. $(...) strips trailing newlines, which would hide exactly the
# problem worth catching, so a sentinel character is appended and removed again.
stored_secret() {
  local value
  value="$(gcloud secrets versions access latest --secret "$1" --project "$PROJECT" 2>/dev/null && printf x)" ||
    { printf ''; return; }
  printf '%s' "${value%x}"
}

secrets_status() {
  # Prints one line per secret; returns 1 if any differs from .env.
  local drift=0 name local_value remote_value
  for name in "${SECRETS[@]}"; do
    local_value="$(env_value "$name")"
    if [ -z "$local_value" ]; then
      echo "   $name: not set in .env (leaving the stored one alone)"
      continue
    fi
    remote_value="$(stored_secret "$name"; printf x)"; remote_value="${remote_value%x}"
    if [ -z "$remote_value" ]; then
      echo "   $name: missing in Secret Manager"; drift=1
    elif [ "$remote_value" != "$local_value" ]; then
      if [ "$(printf '%s' "$remote_value" | tr -d '[:space:]')" == "$local_value" ]; then
        echo "   $name: same key, but stored with extra whitespace or a newline"
      else
        echo "   $name: differs from .env"
      fi
      drift=1
    else
      echo "   $name: matches .env"
    fi
  done
  return $drift
}

sync_secrets() {
  say "Syncing API keys from .env to Secret Manager"
  local name value
  for name in "${SECRETS[@]}"; do
    value="$(env_value "$name")"
    [ -n "$value" ] || { echo "   $name: not set in .env, skipped"; continue; }
    local stored; stored="$(stored_secret "$name"; printf x)"; stored="${stored%x}"
    if [ "$stored" == "$value" ]; then
      echo "   $name: already up to date"
      continue
    fi
    if ! gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
      gcloud secrets create "$name" --project "$PROJECT" --replication-policy=automatic >/dev/null
    fi
    printf '%s' "$value" | gcloud secrets versions add "$name" --project "$PROJECT" --data-file=- >/dev/null
    echo "   $name: updated (new version added)"
  done
}

verify() {
  local url="$1" expected_revision expected_build health
  say "Checking the live site"
  expected_revision="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
    --format='value(status.latestReadyRevisionName)')"
  expected_build="$(local_build)"

  for attempt in 1 2 3 4 5 6; do
    health="$(curl -fsS --max-time 30 "$url/api/health" 2>/dev/null || true)"
    [ -n "$health" ] && break
    echo "   not answering yet (attempt $attempt), retrying in 10s…"
    sleep 10
  done
  [ -n "$health" ] || fail "$url/api/health didn't answer. See: ./deploy.sh logs"

  local live_revision live_build
  live_revision="$(printf '%s' "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("revision",""))')"
  live_build="$(printf '%s' "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("build",""))')"
  echo "   serving revision $live_revision · build \"$live_build\""
  [ "$live_revision" == "$expected_revision" ] ||
    fail "The site still serves $live_revision, not the new $expected_revision. Try again in a minute: ./deploy.sh status"
  [ "$live_build" == "$expected_build" ] ||
    echo "   note: build marker is \"$live_build\", expected \"$expected_build\" (bump BUILD_MARKER in backend/app/main.py when it matters)"

  # The sample menu is served from the built-in seed, so this costs nothing and proves the
  # frontend, the proxy to the backend and the database are all up.
  local menu_id
  menu_id="$(python3 -c "import json; print(json.load(open('$ROOT/backend/app/demo/sample_seed.json'))['menu_id'])")"
  curl -fsS --max-time 30 -o /dev/null "$url/" || fail "The homepage doesn't load."
  curl -fsS --max-time 30 -o /dev/null "$url/api/v1/menus/$menu_id" || fail "The sample menu doesn't load."
  echo "   homepage and sample menu load"

  # One real dish-photo search in the new container (about $0.0003 for the judge). A search library
  # update once broke DuckDuckGo for three deploys without a single error: photos quietly came from a
  # worse source instead. The restaurant name is unique per revision, so this never hits the cache.
  local photo source
  photo="$(curl -fsS --max-time 90 \
    "$url/api/v1/dish-image?dish_name=Bibimbap&restaurant_name=deploy-check-$live_revision" 2>/dev/null || true)"
  source="$(printf '%s' "$photo" | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print(d.get("source") or "?" if d.get("image_url") else "no photo")' \
    2>/dev/null || echo "no answer")"
  if [ "$source" == "duckduckgo" ]; then
    echo "   dish photos: DuckDuckGo search works"
  else
    echo "   WARNING: the test dish photo came from: $source (expected duckduckgo)."
    echo "            Dish photos will be worse. Look for 'duckduckgo search failed' in: ./deploy.sh logs"
  fi
}

cmd_deploy() {
  local dry_run="${1:-}"
  local started=$SECONDS
  preflight

  say "Checking secrets"
  if ! secrets_status; then
    if [ "$dry_run" == "--dry-run" ]; then
      echo "   (a real deploy would sync them first)"
    else
      sync_secrets
    fi
  fi

  if [ "$dry_run" == "--dry-run" ]; then
    say "Dry run: everything checks out. Would now run:"
    echo "   deploy/cloudrun/deploy.sh $PROJECT $REGION   (10–15 minutes)"
    local url; url="$(service_url)"
    [ -n "$url" ] && echo "   then verify $url"
    return
  fi

  say "Deploying (10–15 minutes; the build log streams below)"
  "$ROOT/deploy/cloudrun/deploy.sh" "$PROJECT" "$REGION"

  local url; url="$(service_url)"
  [ -n "$url" ] || fail "Couldn't find the service URL after deploying."
  verify "$url"

  say "Done in $(( (SECONDS - started) / 60 )) min: $url"
}

cmd_status() {
  local url; url="$(service_url)"
  [ -n "$url" ] || fail "No $SERVICE service in $PROJECT/$REGION yet. Deploy with: ./deploy.sh"
  echo "URL:       $url"
  echo "Revision:  $(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
    --format='value(status.latestReadyRevisionName)')"
  echo "Health:    $(curl -fsS --max-time 30 "$url/api/health" 2>/dev/null || echo 'not answering')"
  echo "Local:     build \"$(local_build)\""
}

cmd_logs() {
  gcloud run services logs read "$SERVICE" --project "$PROJECT" --region "$REGION" --limit 50
}

case "${1:-deploy}" in
  deploy)             cmd_deploy ;;
  --dry-run|dry-run)  cmd_deploy --dry-run ;;
  status)             cmd_status ;;
  logs)               cmd_logs ;;
  secrets)            sync_secrets ;;
  -h|--help|help)     sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)                  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
