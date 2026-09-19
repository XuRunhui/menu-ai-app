"""FastAPI main application with menu parsing and restaurant endpoints."""

from contextlib import asynccontextmanager
from pathlib import Path

import hashlib
import os
import time

from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import logging
from typing import Optional

from app.core.config import settings
from app.core.rate_limit import claim_menu_read, enforce_demo_limits
from app.services.vision_parser import parse_menu_image
from app.models.menu import ParsedMenu
from app.api.v1.endpoints import (assistant, auth, library, menus, menu_sources, restaurant,
                                  google_places, recommendation, dish_image, knowledge)
from app.api.v1.endpoints.auth import get_optional_user, session_user_id
from app.db.models import User
from app.db.session import get_db, init_db
from app.demo import sample_seed
from app.services import cache_service
from app.services.llm_client import start_usage_tracking

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    cache_service.import_legacy_json_caches(_CACHE_DIR)
    cache_service.purge_expired()
    sample_seed.load_seed()
    yield


# Create FastAPI app
app = FastAPI(
    title="Menu AI Backend",
    description="AI-powered menu parsing and recommendation system",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_api_requests(request: Request, call_next):
    """Record each API call (path, status, latency, DeepSeek usage) in the request_log table."""
    path = request.url.path
    if not path.startswith("/api/") or path == "/api/health":
        return await call_next(request)

    usage = start_usage_tracking()
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        await run_in_threadpool(
            cache_service.log_request,
            request.method, path, status_code, (time.perf_counter() - started) * 1000,
            session_user_id(request), usage,
        )


# Include routers
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["auth"]
)

app.include_router(
    library.router,
    prefix="/api/v1/me",
    tags=["library"]
)

app.include_router(
    menus.router,
    prefix="/api/v1/menus",
    tags=["menus"]
)

app.include_router(
    menu_sources.router,
    prefix="/api/v1/menus",
    tags=["menus"]
)

app.include_router(
    knowledge.router,
    prefix="/api/v1/knowledge",
    tags=["knowledge"]
)

app.include_router(
    restaurant.router,
    prefix="/api/v1/restaurant",
    tags=["restaurant"]
)

app.include_router(
    google_places.router,
    prefix="/api/v1/places",
    tags=["places"]
)

app.include_router(
    recommendation.router,
    prefix="/api/v1/recommendation",
    tags=["recommendation"]
)

app.include_router(
    dish_image.router,
    prefix="/api/v1/dish-image",
    tags=["dish-image"]
)

app.include_router(
    assistant.router,
    prefix="/api/v1/assistant",
    tags=["assistant"]
)

# Serve locally-cached dish images as static files.
# Must come AFTER all API routers so it doesn't shadow /api/* paths.
_images_dir = _CACHE_DIR / "dish_images"
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/dish-images", StaticFiles(directory=str(_images_dir)), name="dish-images")


# Bumped when a change matters for debugging a deployment; K_REVISION is set by Cloud Run.
BUILD_MARKER = "2026-09-18 tour+security-limits"


@app.get("/")
@app.get("/api/health", include_in_schema=False)
async def root() -> dict[str, str]:
    """Health check; also reports which build and revision are serving.

    Returns:
        Status, build marker, and the platform revision (or "local").
    """
    return {
        "status": "ok",
        "message": "Menu AI Backend is running",
        "build": BUILD_MARKER,
        "revision": os.getenv("K_REVISION", "local"),
    }


@app.post("/api/v1/menu/parse", response_model=ParsedMenu)
async def parse_menu(
    request: Request,
    image: UploadFile = File(...),
    target_language: Optional[str] = Form(None),
    restaurant_name: Optional[str] = Form(None),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ParsedMenu:
    """Parse a menu image into structured JSON with optional translation.

    Results are cached for everyone by image content + target language, so re-uploading the same
    menu returns instantly. The response's ``menu_id`` restores the page via GET /api/v1/menus/{id}.
    Only a new parse counts toward the demo limits: the sample menu is always answered from the
    cache, and it shouldn't use up the day's allowance however many visitors try it.

    Args:
        image: Uploaded image file (JPEG, PNG, etc.).
        target_language: Target language for translation (e.g., "English", "Chinese", "Japanese").
        restaurant_name: Optional restaurant name to label the menu.

    Returns:
        Structured menu data with ``menu_id``.

    Raises:
        HTTPException: If parsing fails or API key is missing.
    """
    try:
        image_bytes = await image.read()
        logger.info(f"Received image: {image.filename}, size: {len(image_bytes)} bytes")
        image_sha256 = hashlib.sha256(image_bytes).hexdigest()
        model = settings.deepseek_model

        cached = cache_service.get_menu_parse(image_sha256, target_language, model)
        if cached is not None:
            logger.info("Menu parse cache hit (%s)", cached.id)
            if restaurant_name and restaurant_name.strip() != cached.restaurant_name:
                cache_service.label_menu(cached.id, restaurant_name)
            parsed_menu = ParsedMenu(**cached.parsed_menu, menu_id=cached.id)
        else:
            await enforce_demo_limits(request)
            claim_menu_read()  # the site-wide ceiling, whoever is asking
            if not settings.deepseek_api_key:
                msg = "DEEPSEEK_API_KEY environment variable not set"
                logger.error(msg)
                raise HTTPException(status_code=500, detail=msg)
            # Parsing blocks for several seconds; run it off the event loop.
            parsed_menu = await run_in_threadpool(
                parse_menu_image,
                image_source=image_bytes,
                api_key=settings.deepseek_api_key,
                target_language=target_language,
            )
            logger.info(f"Successfully parsed menu with {len(parsed_menu.menu)} categories")
            parsed_menu.menu_id = cache_service.set_menu_parse(
                image_sha256, target_language, model, restaurant_name,
                parsed_menu.detected_language,
                sum(len(category.items) for category in parsed_menu.menu),
                parsed_menu.model_dump(exclude={"menu_id"}),
            )

        if user is not None:  # only when accounts are enabled
            library.save_menu(db, user, image_sha256, target_language, restaurant_name,
                              parsed_menu, menu_id=parsed_menu.menu_id)
        return parsed_menu

    except ValueError as e:
        msg = f"Failed to parse menu: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=400, detail=msg) from e
    except HTTPException:
        raise
    except Exception as e:
        msg = f"Unexpected error during parsing: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e
