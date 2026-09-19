# Single-container demo image: Next.js (public, $PORT) proxies /api/* to FastAPI (127.0.0.1:8000).
# Built for Hugging Face Spaces (Docker SDK, port 7860) but runs on any Docker host with ~2GB RAM.

# ---------- Stage 1: build the Next.js frontend ----------
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---------- Stage 2: runtime (Python backend + Node server) ----------
FROM python:3.11-slim

# Node runtime for the standalone Next.js server
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Hugging Face Spaces runs containers as uid 1000; the app writes to backend/.cache at runtime.
RUN useradd -m -u 1000 user
WORKDIR /app

ENV HF_HOME=/app/.hf-cache \
    PYTHONUNBUFFERED=1 \
    NEXT_TELEMETRY_DISABLED=1

# CPU-only torch keeps the image ~2GB smaller than the default CUDA build.
RUN uv pip install --system --no-cache --index-url https://download.pytorch.org/whl/cpu torch
COPY backend/pyproject.toml backend/pyproject.toml
RUN uv pip install --system --no-cache -r backend/pyproject.toml

# Bake the embedding model into the image so the first request doesn't download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend/app backend/app
COPY backend/.cache backend/.cache

# Food knowledge base (FlavorGraph, Wikidata, a public-domain cookbook). Prefer the prebuilt copy that
# deploy/huggingface/push.sh places in deploy/knowledge/; otherwise build it from the network (slow).
COPY deploy/knowledge/ backend/.data/
RUN cd backend && if [ ! -f .data/knowledge.db ]; then python -m app.knowledge.cli build; fi
COPY --from=frontend-build /frontend/.next/standalone frontend/
COPY --from=frontend-build /frontend/.next/static frontend/.next/static
COPY --from=frontend-build /frontend/public frontend/public
COPY deploy/start.sh start.sh

RUN chmod +x start.sh && chown -R user:user /app
USER user

# The embedding model was baked in above, so never ask the Hub about it at runtime: its update
# check got rate-limited from Cloud Run once, and the library's 103 s wait froze the server.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

ENV PORT=7860 \
    DEMO_RATE_LIMIT_PER_HOUR=60 \
    DEMO_DAILY_REQUEST_CAP=500 \
    DEMO_DISH_IMAGE_RATE_LIMIT_PER_HOUR=300
EXPOSE 7860

CMD ["./start.sh"]
