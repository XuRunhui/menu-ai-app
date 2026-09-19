"""Download helpers for knowledge importers."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SOURCES_DIR = Path(__file__).resolve().parents[3] / ".data" / "knowledge_sources"
USER_AGENT = "MenuistKnowledgeBuilder/0.1 (+https://github.com/runhuixu)"


def download(url: str, destination: Path, force: bool = False, timeout: int = 120) -> Path:
    """Download url to destination once (re-used on later builds unless force=True)."""
    if destination.exists() and destination.stat().st_size > 0 and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s", url)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    tmp = destination.with_suffix(destination.suffix + ".part")
    tmp.write_bytes(response.content)
    tmp.replace(destination)
    return destination
