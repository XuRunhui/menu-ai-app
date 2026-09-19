# Demo deployment

A single Docker image serves the whole app, so reviewers get **one public link** with nothing to install.

```
Browser ──► Next.js server (:7860, public)
              ├─ pages, static assets, /sample-menu.png
              └─ rewrites /api/* and /dish-images/* ──► FastAPI (127.0.0.1:8000, internal)
                                                          ├─ DeepSeek (deepseek-flash, non-thinking)
                                                          └─ Google Places / DuckDuckGo
```

## Option A — Google Cloud Run (recommended, about $0.02/month)

Scales to zero, keep-warm ping, sample results built in. Step-by-step console guide and cost table:
**[deploy/cloudrun/README.md](cloudrun/README.md)**.

```bash
deploy/cloudrun/deploy.sh <gcp-project-id>
```

## Option A2 — Hugging Face Spaces (requires PRO, $9/month)

Since 2026, Docker Spaces need a PRO subscription even on free CPU hardware. With PRO:
`hf auth login`, then `deploy/huggingface/push.sh <hf-username>/menuist`, and add
`DEEPSEEK_API_KEY` and `GOOGLE_PLACES_API_KEY` under the Space's **Variables and secrets**.

## Option B — any Docker host (Render, Fly.io, Railway, a VPS)

```bash
docker build -t menuist-demo .
docker run -p 7860:7860 -e DEEPSEEK_API_KEY=sk-... -e GOOGLE_PLACES_API_KEY=... menuist-demo
```

Give the instance at least **2 GB RAM**. The server listens on `$PORT` (default 7860), so
platforms that inject `PORT` work without changes.

## Data stored by the app

Two SQLite files under `backend/.data/`:

| File | Contents | Rebuilt how |
|---|---|---|
| `menuist.db` | shared caches (parsed menus, dish images, web search, LLM responses, embeddings), place IDs, request log; users and libraries only when accounts are enabled | Created at startup; expired cache rows purged at startup |
| `knowledge.db` | meal-composition notes, Wikipedia meal-structure articles, FlavorGraph pairings, Wikidata dishes, cookbook passages | `python -m app.knowledge.cli build`; the deploy scripts upload your local copy |

On Cloud Run (and Hugging Face) `menuist.db` starts empty whenever a new container starts;
`knowledge.db` and the sample menu's results (`backend/app/demo/sample_seed.json`) come from the image.

## Cost guards

Every endpoint that calls DeepSeek or Google Places is rate limited in the demo image
(`backend/app/core/rate_limit.py`). Override via environment variables:

| Variable | Demo default | Meaning |
|---|---|---|
| `DEMO_RATE_LIMIT_PER_HOUR` | 60 | Requests per visitor IP per rolling hour |
| `DEMO_DAILY_REQUEST_CAP` | 500 | Total requests per UTC day across everyone |
| `DEMO_DISH_IMAGE_RATE_LIMIT_PER_HOUR` | 300 | Dish-photo lookups per visitor IP per hour (a miss costs a DeepSeek call to pick the photo) |

All are `0` (disabled) in local development. Backstops outside the app:

- **DeepSeek** is prepaid — keep only a small balance on the account.
- **Google Cloud** budgets only send alerts; they don't stop billing. For a hard cap, lower the
  per-day request quotas under APIs & Services → Places API → Quotas.
