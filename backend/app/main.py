"""FastAPI main application with menu parsing and restaurant endpoints."""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import logging
from typing import Optional

from app.core.config import settings
from app.services.vision_parser import parse_menu_image
from app.models.menu import ParsedMenu
from app.api.v1.endpoints import restaurant, google_places

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Menu AI Backend",
    description="AI-powered menu parsing and recommendation system",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
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


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Simple status message.
    """
    return {"status": "ok", "message": "Menu AI Backend is running"}


@app.post("/api/v1/menu/parse", response_model=ParsedMenu)
async def parse_menu(
    image: UploadFile = File(...),
    target_language: Optional[str] = Form(None)
) -> ParsedMenu:
    """Parse a menu image into structured JSON with optional translation.

    Args:
        image: Uploaded image file (JPEG, PNG, etc.).
        target_language: Target language for translation (e.g., "English", "Chinese", "Japanese").
                        If not provided, only parses without translation.

    Returns:
        Structured menu data with categories and items in original and optionally translated languages.

    Raises:
        HTTPException: If parsing fails or API key is missing.
    """
    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    try:
        # Read image bytes
        image_bytes = await image.read()
        logger.info(f"Received image: {image.filename}, size: {len(image_bytes)} bytes")
        if target_language:
            logger.info(f"Target language: {target_language}")

        # Parse with Gemini
        parsed_menu = parse_menu_image(
            image_source=image_bytes,
            api_key=settings.gemini_api_key,
            target_language=target_language,
            model_name=settings.gemini_model
        )

        logger.info(f"Successfully parsed menu with {len(parsed_menu.menu)} categories")
        if parsed_menu.detected_language:
            logger.info(f"Detected language: {parsed_menu.detected_language}")
        return parsed_menu

    except ValueError as e:
        msg = f"Failed to parse menu: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=400, detail=msg) from e
    except Exception as e:
        msg = f"Unexpected error during parsing: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e
