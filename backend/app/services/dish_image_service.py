"""Dish image service: find a photo of a dish, pick the right one, download it, and cache it.

Four stages:

1. **Search** — providers are tried in order (see image_sources.py): DuckDuckGo image search first,
   because it can find the actual restaurant's dish, then Wikimedia Commons for what it misses.
2. **Shortlist** — up to ``settings.dish_image_candidates`` results are downloaded and checked for
   being real, reasonably sized images.
3. **Judge** — DeepSeek looks at the shortlist and says which photo actually shows the dish
   (see image_judge.py). Search alone matches keywords, so it happily returns the restaurant's
   sign or an unrelated stock photo; this is the step that catches that. With no API key, or if
   the call fails, the first usable result is used instead, exactly as before.
4. **Ask what to search for** — when nothing usable turned up, one small DeepSeek call turns the
   menu's name into what an image library calls the dish ("#81.5 Rick's 50/50 mix" -> "pastrami
   sandwich", "Ba-corn" -> "corn cheese"), and stages 1–3 run again with those terms. On 97 dishes
   searched on Wikimedia alone, this took recall from 65% to 97%.

Each provider gets queries in its own style: web-search wording for DuckDuckGo, and for Wikimedia
Commons (whose search needs every word to match) short dish names without brand words.

A photo already shown for another dish at the same restaurant is never picked again, so a menu
with five Reubens shows five different Reubens rather than one photo five times.

Cache strategy:
- Image files live in ``backend/.cache/dish_images/``; the ``image_cache`` table maps
  restaurant + dish to a file (28-day TTL), so a dish is searched and judged once for everyone.
- Failed searches are remembered for 10 minutes (``image_search_failures``) so a page full of
  cards doesn't keep retrying a source that is down or blocked.
- Concurrent requests for the same dish share one search, and at most
  ``MAX_CONCURRENT_SEARCHES`` searches run at once.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

import requests

from app.core.config import settings
from app.services import cache_service
from app.services.image_judge import Shortlisted, pick_best, suggest_search_terms, thumbnail
from app.services.image_sources import (
    ImageCandidate,
    build_queries,
    commons_queries,
    search_duckduckgo,
    search_wikimedia,
)

logger = logging.getLogger(__name__)

_IMAGE_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")
_EXTENSIONS = ((b"\x89PNG\r\n\x1a\n", ".png"), (b"GIF87a", ".gif"), (b"GIF89a", ".gif"))

MIN_IMAGE_BYTES = 1024      # smaller than this is an icon or an error page
MIN_IMAGE_WIDTH = 200       # thumbnails are rarely the dish; skip before paying for a download


def _web_queries(restaurant: str, dish: str, translated: str) -> list[str]:
    return build_queries(restaurant, dish)


def _commons_queries(restaurant: str, dish: str, translated: str) -> list[str]:
    return commons_queries(dish, restaurant, translated)


# (name, search function, how many queries to try, how to word them for this provider).
# A three-item entry uses the web-search wording.
DEFAULT_PROVIDERS: list[tuple] = [
    ("duckduckgo", search_duckduckgo, 2, _web_queries),
    ("wikimedia", search_wikimedia, 3, _commons_queries),
]


def _looks_like_image(content: bytes) -> bool:
    return content.startswith(_IMAGE_SIGNATURES) or (content[:4] == b"RIFF" and content[8:12] == b"WEBP")


def _extension(content: bytes) -> str:
    """File extension from the magic bytes; URLs lie about their format often enough to matter."""
    for signature, suffix in _EXTENSIONS:
        if content.startswith(signature):
            return suffix
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


class DishImageService:
    """Fetch dish-specific images, let DeepSeek pick the right one, and cache it locally."""

    DOWNLOAD_TIMEOUT: int = 10          # seconds per download attempt
    MAX_SEARCH_RESULTS: int = 10        # results requested per query, to fill the shortlist
    MAX_CONCURRENT_SEARCHES: int = 3
    SEARCH_RETRY_DELAYS: tuple[float, ...] = (2.0, 5.0)  # backoff after a rate-limit error
    # How a busy search engine says "slow down". DuckDuckGo throttles by answering "No results
    # found" for a moment: from Google Cloud, 6 of 90 menu searches got it, and all 6 worked when
    # asked again 2-5 s later. A dish photo search with truly no results is rare enough to pay that.
    THROTTLE_SIGNS: tuple[str, ...] = ("ratelimit", "no results found")

    def __init__(self, images_dir: Optional[Path] = None, providers=None) -> None:
        base = Path(__file__).resolve().parents[2]   # → backend/
        self.images_dir = images_dir or (base / ".cache" / "dish_images")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.providers = providers if providers is not None else DEFAULT_PROVIDERS
        self._semaphore: asyncio.Semaphore | None = None
        self._inflight: dict[str, asyncio.Task] = {}
        # Photos picked in this process, per restaurant, before they reach the cache: dishes are
        # searched concurrently, and two must not grab the same photo in the same moment.
        self._claimed: dict[str, set[str]] = {}

    def cached_image(self, restaurant_name: str, dish_name: str):
        """The photo already chosen for this dish (an ``ImageCache`` row), if its file is still here.

        Photos are kept per restaurant: a search that names the restaurant can find its own dish,
        and one menu's "Classic" is not another's. A menu uploaded without a restaurant name has
        nothing like that to search for, so the photo already chosen for the same dish anywhere
        serves it. Before this, uploading a menu again without its name searched every dish again
        (23 of 34 dishes on the live site).
        """
        entry = cache_service.get_image(restaurant_name, dish_name)
        if entry is None and not restaurant_name.strip():
            entry = cache_service.get_image_for_dish(dish_name)
        if entry is not None and (self.images_dir / entry.filename).exists():
            return entry
        return None

    def get_cached_filename(self, restaurant_name: str, dish_name: str) -> Optional[str]:
        """Return the cached image filename if the entry is fresh and the file still exists."""
        entry = self.cached_image(restaurant_name, dish_name)
        return entry.filename if entry else None

    async def fetch_and_cache(self, restaurant_name: str, dish_name: str, translated_name: str = "",
                              description: str = "") -> Optional[str]:
        """Find, judge, download, and cache an image. Returns the filename, or None if nothing fits.

        ``translated_name`` and ``description`` come from the menu and only sharpen the search
        and the judging; the cache is keyed by restaurant and dish name alone.
        """
        key = cache_service.image_key(restaurant_name, dish_name)
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(
                self._fetch(restaurant_name, dish_name, translated_name or "", description or ""))
            self._inflight[key] = task
            task.add_done_callback(lambda _: self._inflight.pop(key, None))
        # shield: one client disconnecting must not cancel a search other requests are waiting on
        return await asyncio.shield(task)

    def _judge_client(self):
        """The LLM used to choose between candidates, or None when judging is off/unavailable."""
        if not settings.dish_image_judge_enabled or not settings.deepseek_api_key:
            return None
        from app.services.llm_client import LLMClient

        return LLMClient(api_key=settings.deepseek_api_key)

    def _plan(self, restaurant: str, dish: str, translated: str,
              terms: Optional[list[str]] = None) -> list[tuple[str, Callable, list[str]]]:
        """(provider, search, queries) in order. Suggested terms replace every provider's wording."""
        plan = []
        for provider in self.providers:
            name, search, limit = provider[:3]
            wording = provider[3] if len(provider) > 3 else _web_queries
            queries = terms if terms is not None else wording(restaurant, dish, translated)
            plan.append((name, search, list(queries)[:max(limit, len(terms or []))]))
        return plan

    def _used_urls(self, restaurant: str, dish: str) -> set[str]:
        """Photos already shown, or being picked right now, for this restaurant's other dishes."""
        if not restaurant.strip():
            return set()  # an unnamed upload: dishes from unrelated menus mustn't block each other
        stored = cache_service.image_urls_for_restaurant(restaurant, dish, fallback=set()) or set()
        return stored | self._claimed.get(restaurant.strip().lower(), set())

    async def _fetch(self, restaurant_name: str, dish_name: str, translated_name: str = "",
                     description: str = "") -> Optional[str]:
        if cache_service.recent_image_failure(restaurant_name, dish_name):
            logger.debug("dish_image: skipping '%s', failed recently", dish_name)
            return None

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SEARCHES)

        llm = self._judge_client()
        # Without a judge there is nothing to compare, so stop at the first usable photo.
        wanted = max(1, settings.dish_image_candidates) if llm else 1

        async with self._semaphore:
            used = self._used_urls(restaurant_name, dish_name)
            chosen, judged = await self._search_and_choose(
                llm, restaurant_name, dish_name, description, wanted, used,
                self._plan(restaurant_name, dish_name, translated_name))

            if chosen is None and llm is not None:
                # Nothing usable under the menu's own name: ask what the dish is called in an
                # image library, and try once more.
                try:
                    terms = await asyncio.to_thread(suggest_search_terms, llm, dish_name,
                                                    restaurant_name, translated_name, description)
                except Exception as exc:
                    logger.warning("dish_image: couldn't get search terms for '%s' (%s)", dish_name, exc)
                    terms = []
                if terms:
                    logger.info("dish_image: retrying '%s' as %s", dish_name, terms)
                    chosen, judged_again = await self._search_and_choose(
                        llm, restaurant_name, dish_name, description, wanted, used,
                        self._plan(restaurant_name, dish_name, translated_name, terms))
                    judged = judged or judged_again

            if chosen is None:
                # Better a blank card than a photo of something else. Photos judged and rejected
                # stay rejected for days; a search that found nothing is tried again soon.
                logger.info("dish_image: nothing shows '%s'", dish_name)
                cache_service.record_image_failure(
                    restaurant_name, dish_name,
                    cache_service.NO_MATCHING_PHOTO if judged else "search found nothing")
                return None

            return self._store(restaurant_name, dish_name, chosen)

    async def _search_and_choose(self, llm, restaurant_name: str, dish_name: str, description: str,
                                 wanted: int, used: set[str], plan) -> tuple[Optional[Shortlisted], bool]:
        """The chosen photo, and whether any were put to the judge at all."""
        shortlist = await self._collect_shortlist(restaurant_name, dish_name, plan, wanted, used)
        chosen = await self._choose_unclaimed(llm, restaurant_name, dish_name, shortlist, description)
        return chosen, bool(shortlist) and llm is not None

    async def _choose_unclaimed(self, llm, restaurant_name: str, dish_name: str,
                                shortlist: list[Shortlisted], description: str) -> Optional[Shortlisted]:
        """Pick a photo, and claim it for this dish unless another dish got there first.

        ``used`` was read when this search started, but dishes on one menu are searched side by side,
        so another may have picked the same photo since. Checking and claiming happen with no
        ``await`` in between, so on the event loop they can't interleave with another dish's claim;
        a photo that's been taken is dropped and the rest judged again.
        """
        claims = self._claimed.setdefault(restaurant_name.strip().lower(), set()) \
            if restaurant_name.strip() else None
        while shortlist:
            chosen = await self._choose(llm, restaurant_name, dish_name, shortlist, description)
            if chosen is None or claims is None:
                return chosen
            if chosen.candidate.url not in claims:
                claims.add(chosen.candidate.url)
                return chosen
            logger.info("dish_image: '%s' lost its photo to another dish; choosing again", dish_name)
            shortlist = [item for item in shortlist if item.candidate.url != chosen.candidate.url]
        return None

    async def _collect_shortlist(
        self, restaurant_name: str, dish_name: str, plan, wanted: int, used: frozenset | set = frozenset()
    ) -> list[Shortlisted]:
        """Search each provider in turn until ``wanted`` candidates have downloaded cleanly."""
        shortlist: list[Shortlisted] = []
        seen: set[str] = set(used)

        for provider_name, search, queries in plan:
            for query in queries:
                candidates = await self._search_with_retry(provider_name, search, query)
                pool = [c for c in candidates
                        if c.url not in seen and not (c.width and c.width < MIN_IMAGE_WIDTH)]
                seen.update(c.url for c in pool)

                # Download in chunks of exactly what is still missing, so a page of dishes never
                # pulls down more photos than it will look at.
                while pool and len(shortlist) < wanted:
                    take, pool = pool[:wanted - len(shortlist)], pool[wanted - len(shortlist):]
                    shortlist += await self._download_batch(take, query)

                if len(shortlist) >= wanted:
                    return shortlist[:wanted]

        return shortlist

    async def _download_batch(self, candidates: list[ImageCandidate], query: str) -> list[Shortlisted]:
        """Download candidates in parallel and keep the ones that really are images."""
        results = await asyncio.gather(
            *[asyncio.to_thread(self._download_bytes, candidate.url) for candidate in candidates],
            return_exceptions=True,
        )

        kept = []
        for candidate, content in zip(candidates, results):
            if isinstance(content, BaseException):
                logger.debug("dish_image: download failed for %s: %s", candidate.url, content)
                continue
            # Skip tiny files and HTML error pages served with a 200 status.
            if len(content) < MIN_IMAGE_BYTES or not _looks_like_image(content):
                continue
            kept.append(Shortlisted(candidate=candidate, query=query, content=content, thumbnail=b""))
        return kept

    async def _choose(self, llm, restaurant_name: str, dish_name: str,
                      shortlist: list[Shortlisted], description: str = "") -> Optional[Shortlisted]:
        """Ask DeepSeek which photo shows the dish; fall back to the first usable one."""
        if llm is None:
            return shortlist[0]

        thumbnails = await asyncio.gather(
            *[asyncio.to_thread(thumbnail, item.content) for item in shortlist])
        for item, small in zip(shortlist, thumbnails):
            item.thumbnail = small

        try:
            logger.info("dish_image: judging %d candidates for '%s'", len(shortlist), dish_name)
            return await asyncio.to_thread(pick_best, llm, restaurant_name, dish_name, shortlist,
                                           None, description)
        except Exception as exc:
            # A quota error or a timeout must not cost the card its picture.
            logger.warning("dish_image: judging failed for '%s' (%s); using the first result",
                           dish_name, exc)
            return shortlist[0]

    def _store(self, restaurant_name: str, dish_name: str, chosen: Shortlisted) -> Optional[str]:
        """Write the winning photo to disk and record it in the shared image cache."""
        filename = f"{cache_service.image_key(restaurant_name, dish_name)}{_extension(chosen.content)}"
        try:
            (self.images_dir / filename).write_bytes(chosen.content)
        except OSError as exc:
            logger.error("dish_image: failed to write %s: %s", filename, exc)
            return None

        cache_service.set_image(
            restaurant_name, dish_name, chosen.query, filename, chosen.candidate.url,
            source=chosen.candidate.source, attribution=chosen.candidate.attribution)
        logger.info("dish_image: cached '%s' from %s (%d bytes)",
                    dish_name, chosen.candidate.source, len(chosen.content))
        return filename

    async def _search_with_retry(self, provider: str, search, query: str) -> list[ImageCandidate]:
        attempts = len(self.SEARCH_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            try:
                logger.info("dish_image: %s search for '%s'", provider, query)
                return await asyncio.to_thread(search, query, self.MAX_SEARCH_RESULTS)
            except Exception as exc:
                text = f"{exc.__class__.__name__} {exc}".lower()
                rate_limited = any(sign in text for sign in self.THROTTLE_SIGNS)
                if not rate_limited or attempt == attempts - 1:
                    logger.warning("dish_image: %s search failed for '%s': %s", provider, query, exc)
                    return []
                delay = self.SEARCH_RETRY_DELAYS[attempt]
                logger.info("dish_image: %s rate limited, retrying '%s' in %.0fs", provider, query, delay)
                await asyncio.sleep(delay)
        return []

    @staticmethod
    def _download_bytes(url: str) -> bytes:
        """Synchronous HTTP GET for running in a thread pool."""
        resp = requests.get(
            url,
            timeout=DishImageService.DOWNLOAD_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MenuAI/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content


# ── Module-level singleton ────────────────────────────────────────────────────

_service: Optional[DishImageService] = None


def get_dish_image_service() -> DishImageService:
    """Return (or lazily create) the application-scoped DishImageService."""
    global _service
    if _service is None:
        _service = DishImageService()
    return _service
