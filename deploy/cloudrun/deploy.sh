#!/usr/bin/env bash
# Deploy Menuist to Google Cloud Run with a free keep-warm ping.
#
# Usage:   deploy/cloudrun/deploy.sh <gcp-project-id> [region]
# Before:  follow deploy/cloudrun/README.md (billing, two secrets, gcloud login)
#
# Cost design: request-based billing (idle instances aren't charged), scales to zero, at most one
# instance, a Tier 1 region, and a Cloud Scheduler ping every 10 minutes so visitors rarely hit a cold start.
set -euo pipefail

PROJECT="${1:?Usage: $0 <gcp-project-id> [region]}"
REGION="${2:-us-central1}"   # Tier 1 region; the free tier is applied at Tier 1 prices
SERVICE="menuist"
PING_JOB="menuist-keep-warm"
SECRETS=(DEEPSEEK_API_KEY GOOGLE_PLACES_API_KEY)
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"

echo "==> Project: $PROJECT   Region: $REGION"
gcloud config set project "$PROJECT" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
# Cloud Run runs as, and source builds use, the Compute Engine default service account.
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "==> Enabling APIs (the first time takes a minute or two)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com

echo "==> Checking secrets"
for name in "${SECRETS[@]}"; do
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    echo "ERROR: secret $name not found. Create it in Console > Security > Secret Manager (deploy/cloudrun/README.md, step 3)." >&2
    exit 1
  fi
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/secretmanager.secretAccessor >/dev/null
done

echo "==> Allowing source builds"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SERVICE_ACCOUNT" --role=roles/run.builder --condition=None >/dev/null

echo "==> Packing the knowledge database"
KNOWLEDGE_DB=backend/.data/knowledge.db
if [ ! -f "$KNOWLEDGE_DB" ]; then
  (cd backend && python -m app.knowledge.cli build)
fi
python3 -c "import sqlite3,sys; sqlite3.connect(sys.argv[1]).execute('PRAGMA wal_checkpoint(TRUNCATE)')" "$KNOWLEDGE_DB"
cp "$KNOWLEDGE_DB" deploy/knowledge/knowledge.db

echo "==> Building and deploying (about 10-15 minutes the first time)"
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --cpu 1 --memory 2Gi --cpu-boost \
  --min-instances 0 --max-instances 1 \
  --concurrency 40 --timeout 300 \
  --set-secrets "DEEPSEEK_API_KEY=DEEPSEEK_API_KEY:latest,GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"

echo "==> Keep-warm ping every 10 minutes (Cloud Run keeps an idle instance for up to 15)"
if gcloud scheduler jobs describe "$PING_JOB" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$PING_JOB" --location "$REGION" \
    --schedule "*/10 * * * *" --uri "$URL/api/health" --http-method GET >/dev/null
else
  gcloud scheduler jobs create http "$PING_JOB" --location "$REGION" \
    --schedule "*/10 * * * *" --uri "$URL/api/health" --http-method GET >/dev/null
fi

echo "==> Deleting old images after each deploy (Artifact Registry's free tier is 0.5 GB)"
gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy \
  --location "$REGION" --policy deploy/cloudrun/cleanup-policy.json --no-dry-run >/dev/null || \
  echo "   (skipped: set it later in Console > Artifact Registry > cloud-run-source-deploy > Cleanup policies)"

echo
echo "Deployed: $URL"
echo "Try it:   $URL/results?menu=$(python3 -c "import json; print(json.load(open('backend/app/demo/sample_seed.json'))['menu_id'])")"
