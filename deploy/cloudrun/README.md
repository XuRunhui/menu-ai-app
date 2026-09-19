# Deploy to Google Cloud Run

One public HTTPS link, about two cents a month at demo traffic. The app scales to zero when idle; a Cloud
Scheduler ping every 10 minutes keeps it warm so recruiters rarely wait for a cold start, and the
sample menu's results are built into the image so "Try a sample menu" is instant even right after
a restart.

## What it costs (checked September 2026)

| Piece | Free tier (per billing account, monthly) | This demo's use |
|---|---|---|
| Cloud Run (request-based billing) | 180,000 vCPU-seconds, 360,000 GiB-seconds, 2M requests, 1 GB egress (North America) | Keep-warm pings ≈ 450 vCPU-s / 900 GiB-s; each visitor ≈ 30–60 s of request time. Idle instances aren't charged. |
| Cloud Scheduler | 3 jobs | 1 job |
| Secret Manager | 6 active secret versions, 10,000 accesses | 2 secrets, a few accesses per start |
| Cloud Build | 2,500 build-minutes (e2-standard-2) | ≈ 15 minutes per deploy |
| Artifact Registry | 0.5 GB storage, then $0.10/GB-month | One image kept (0.71 GB compressed, measured) → **about $0.02/month** |

So: **about $0.02/month** for image storage, everything else inside the free tier at demo traffic.
DeepSeek and Google Places usage are billed separately by those services, as before.

DeepSeek costs at demo traffic, measured (off-peak; peak rates are double):

| What | Tokens | Cost |
|---|---|---|
| Parsing one menu | varies with the photo | ~$0.002 |
| Choosing photos for a 25-dish menu | ~1,400 in / 20 out per dish | ~$0.006, once per menu (cached 28 days) |
| Suggesting search terms when a dish's name finds nothing | ~200 in / 20 out per dish | ~$0.00004 per dish that needs it |
| One 3-turn assistant conversation | ~13,000 in / 750 out | ~$0.0024 |
| Reading a menu off a restaurant's website | depends on menu size (Katz's: 194 dishes) | ~$0.002–0.01, **once** (cached by page content) |

Set `DISH_IMAGE_JUDGE_ENABLED=false` to turn photo selection off if you'd rather have the free
(and often wrong) first search result. Google place photos are not used at all (see google_places_service.py for why), so Places
billing is limited to searches and place details.

Opening a restaurant makes two rate-limited requests (details, website), and the assistant
one per chat turn, so the hourly per-visitor limit is 60.
The free tier is applied at Tier 1 prices, so the script deploys to `us-central1` (Iowa).

## 1. Project and billing (Console)

1. Open https://console.cloud.google.com and pick the project that already holds your Places API
   key (or create a new project). Note the **Project ID** shown on the dashboard.
2. **Billing → Account management**: make sure the project is linked to your billing account
   (required even for free-tier usage).

## 2. Budget alert (Console, recommended)

**Billing → Budgets & alerts → Create budget**: scope = this project, amount = **$1**, keep the
default email alerts at 50% / 90% / 100%. Budgets only notify; they don't stop services, but you'll
hear about any unexpected charge right away.

## 3. Secrets (Console)

**Security → Secret Manager** (click **Enable** if asked) → **Create secret**, twice:

| Name (exactly) | Secret value |
|---|---|
| `DEEPSEEK_API_KEY` | your DeepSeek key |
| `GOOGLE_PLACES_API_KEY` | your Google Places key |

Leave the other options at their defaults. The deploy script gives Cloud Run read access to them.

## 4. Install and log in to gcloud (Terminal, one time)

```bash
brew install --cask google-cloud-sdk   # or https://cloud.google.com/sdk/docs/install
gcloud auth login                      # opens the browser
```

## 5. Deploy (Terminal)

```bash
cd /Users/xurunhui/Desktop/App/menu-ai-app
deploy/cloudrun/deploy.sh <your-project-id>
```

The script enables the needed APIs, grants permissions, uploads the code plus the prebuilt
knowledge database, builds the image with Cloud Build, deploys it, creates the keep-warm ping, and
limits stored images. The first run takes 10–15 minutes and ends by printing your link:
`https://menuist-<hash>-uc.a.run.app`.

Re-run the same command after code changes to redeploy (the ping and permissions are reused).

**Day to day, use `./deploy.sh` from the project root instead.** It wraps the command above with
the checks you'd otherwise do by hand:

| Command | What it does |
|---|---|
| `./deploy.sh` | runs the backend tests and a frontend type-check, syncs the API keys from `.env` to Secret Manager if they changed, deploys, then confirms the live site serves the new revision and loads |
| `./deploy.sh --dry-run` | every check above, without deploying |
| `./deploy.sh status` | the live URL, and the build and revision it's serving next to your local build |
| `./deploy.sh logs` | the last 50 lines of the live server's log |
| `./deploy.sh secrets` | only the key sync |

It deploys your working directory, including uncommitted changes, and refuses to deploy if a test
fails.

## 6. Check it (Console)

- **Cloud Run → menuist**: the URL, logs, and metrics.
- **Cloud Scheduler → menuist-keep-warm**: "Last run" should show success every 10 minutes.
- **Billing → Reports** after a few days: filter by this project to confirm costs stay near zero.

## Settings used and why

| Setting | Value | Why |
|---|---|---|
| `--min-instances` | 0 | Scale to zero; minimum instances are billed even when idle |
| `--max-instances` | 1 | Caps cost and keeps the in-memory rate limits and caches consistent |
| `--memory` / `--cpu` | 2Gi / 1 | Idle ≈ 160 MB; the embedding model loads on first restaurant search, and Cloud Run's filesystem lives in memory |
| `--cpu-boost` | on | Extra CPU during startup to shorten cold starts |
| `--timeout` | 300s | Menu parsing and combo generation can take tens of seconds |
| Keep-warm ping | every 10 min | Cloud Run keeps idle instances for up to 15 minutes |

## Protecting the demo

The app limits itself (values in the `Dockerfile`, logic in `backend/app/core/rate_limit.py`):

- **Per visitor**, by the address Cloud Run saw (the right-most `X-Forwarded-For` entry, so sending
  a fake header doesn't make a new visitor): 60 AI/API requests, 300 dish-photo searches and 600
  menu merges an hour. Answers from the cache don't count.
- **Site-wide**, for traffic spread over many addresses: 100 menus read an hour; 500 AI/API requests
  and 3,000 dish-photo searches a day; DeepSeek 2,000 calls an hour and 10,000 a day (checked in the
  one client every call goes through); Google Places 600 requests a day. Past a limit the page gets a
  "try again later" (429), and nothing second-rate is cached in the meantime.

Outside the app, set these once:

1. **Restrict the Google key to the Places API** (the only Google API the app calls):
   `gcloud services api-keys list` to find its ID, then
   `gcloud services api-keys update KEY_ID --api-target=service=places-backend.googleapis.com`.
2. **Cap Places in Google Cloud too**: APIs & Services → Places API → Quotas → set *requests per
   day* to about 600. Google enforces it even if the app's own limits had a bug.
3. **Keep the DeepSeek balance small.** It's prepaid, so the balance is the most DeepSeek can ever
   cost; top it up by hand.
4. **Budget alert**: see step 2 above.

If a key is ever exposed, make a new one (restricted as in 1), put it in `.env`, run `./deploy.sh`
(which copies it to Secret Manager and deploys), then delete the old key.

## Troubleshooting

- **Build fails with a permission error**: in IAM, give
  `<project-number>-compute@developer.gserviceaccount.com` the **Cloud Run Builder** role, then re-run.
- **"Missing secret"**: the names in step 3 must match exactly (uppercase, underscores).
- **Parsing works locally but not on Cloud Run**: open Cloud Run → menuist → Logs and look for
  `DEEPSEEK_API_KEY environment variable not set`; re-check the secrets.
