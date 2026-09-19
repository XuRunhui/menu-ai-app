#!/usr/bin/env bash
# Upload the current working tree to a Hugging Face Docker Space.
# Usage: deploy/huggingface/push.sh <hf-username>/<space-name>
# Requires: pip install -U huggingface_hub && hf auth login
set -euo pipefail

SPACE="${1:?Usage: $0 <hf-username>/<space-name>}"
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cd "$ROOT"
# Tracked + untracked-but-not-ignored files only (never .env), minus what the image doesn't need.
git ls-files -co --exclude-standard -z \
  | grep -zv -E '^(mobile/|.*\.md$|bcd_tofu_house\.png$|sample-menu\.png$|test_.*\.py$|snippet_search\.py$)' \
  | rsync -a --from0 --files-from=- ./ "$STAGE/"

# The Space card (YAML front matter) must be the root README.md.
cp deploy/huggingface/README.md "$STAGE/README.md"

# Ship the prebuilt knowledge database so the Space build doesn't depend on third-party downloads.
KNOWLEDGE_DB=backend/.data/knowledge.db
if [ ! -f "$KNOWLEDGE_DB" ]; then
  echo "Building knowledge database (one-time, about a minute)..."
  (cd backend && python -m app.knowledge.cli build)
fi
# Fold any write-ahead log into the main file before copying it.
python3 -c "import sqlite3,sys; sqlite3.connect(sys.argv[1]).execute('PRAGMA wal_checkpoint(TRUNCATE)')" "$KNOWLEDGE_DB"
mkdir -p "$STAGE/deploy/knowledge"
cp "$KNOWLEDGE_DB" "$STAGE/deploy/knowledge/knowledge.db"

hf repos create "$SPACE" --repo-type space --space-sdk docker --exist-ok
hf upload "$SPACE" "$STAGE" . --repo-type space --commit-message "Deploy $(git rev-parse --short HEAD)"

echo
echo "Uploaded. Next: add secrets at https://huggingface.co/spaces/$SPACE/settings"
echo "  DEEPSEEK_API_KEY, GOOGLE_PLACES_API_KEY  (then the Space rebuilds automatically)"
