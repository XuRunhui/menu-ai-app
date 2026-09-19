"""Ask DeepSeek which search result actually shows the dish.

Image search is keyword matching, so a query for "Galbi" comes back with short ribs, but also the
restaurant's sign, a stock-photo watermark, a recipe infographic, and now and then something with
no connection to food at all. Picking "the first one that downloads" is what put wrong photos on
the menu cards. A vision model can look at the shortlist and answer the question keywords can't:
*is this the dish?*

Cost control, in order of how much each one saves:

1. **Thumbnails.** DeepSeek counts image tokens from the image's final dimensions after its own
   resize and caps each image at 1024 tokens, so a ``THUMBNAIL_PX``-wide copy costs a fraction of
   a full photo. Recognising a dish does not need detail.
2. **One call for the whole shortlist.** DeepSeek accepts up to 600 images per request, so the
   usual case is a single request for all candidates.
3. **Judged once per dish.** The winner goes into the 28-day ``image_cache``, so a dish is judged
   once for every visitor, not once per page view.

Batching exists for the case where that 600-image allowance shrinks, or where a caller sets
``dish_image_judge_batch_size`` low deliberately: each batch nominates a winner and the winners
run off in a further round, until one is left or ``MAX_ROUNDS`` is reached.
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.services.image_sources import ImageCandidate

logger = logging.getLogger(__name__)

# Wide enough for the model to tell soup from noodles, small enough to stay cheap.
THUMBNAIL_PX = 448
JPEG_QUALITY = 80
# A shortlist only ever shrinks between rounds, so this is a safety net, not a real limit.
MAX_ROUNDS = 3
# The reply is one small JSON object; anything longer means the model ignored the format.
MAX_REPLY_TOKENS = 120


@dataclass
class Shortlisted:
    """A candidate that downloaded cleanly, ready to be judged."""

    candidate: ImageCandidate
    query: str
    content: bytes      # full-size bytes, written to the image cache if this one wins
    thumbnail: bytes    # downscaled copy, the one actually uploaded


def thumbnail(content: bytes, max_px: int = THUMBNAIL_PX) -> bytes:
    """Shrink an image for upload. Returns the original bytes if it can't be decoded."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            image = image.convert("RGB")
            image.thumbnail((max_px, max_px))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
            return buffer.getvalue()
    except Exception as exc:  # unsupported format, truncated download, decompression bomb guard…
        logger.debug("image_judge: could not downscale (%s); sending as-is", exc)
        return content


def _prompt(dish_name: str, restaurant_name: str, count: int, description: str = "") -> str:
    where = f' at the restaurant "{restaurant_name}"' if restaurant_name.strip() else ""
    # The menu's own description is what tells "Ba-corn" (corn, bacon, mozzarella) from a corn dog.
    described = f'\nThe menu describes it as: "{description.strip()[:300]}".' if description.strip() else ""
    return f"""You are choosing the photo to show next to a menu item.

The dish is "{dish_name}"{where}.{described}

The {count} photos below are candidates, in order: photo 1 is the first image, photo 2 the second, \
and so on up to photo {count}. Choose the one photo that best shows this dish as it would be served.

Reject a photo that shows:
- a different dish, or a spread of many different dishes
- a menu, sign, storefront, logo, map, chart, recipe card or screenshot of text
- raw ingredients or a packaged supermarket product instead of a prepared dish
- a person, a cartoon, or anything that is not food

A clear, generic photo of the dish is a good answer. It does not have to have been taken at this \
restaurant. Only answer null when none of the photos show the dish.

Reply with JSON only, in this shape: {{"choice": <photo number from 1 to {count}, or null>, \
"reason": "<at most 8 words>"}}"""


# A photo named while its own reason rules it out: once on the live site the model answered
# {"choice": 1, "reason": "It is a chemistry diagram, not food."}, and the diagram was cached as
# the dish's photo. Only explicit rejections match; "not packaged bottle" and the like do not.
_SELF_REJECTION = re.compile(r"\bnot (?:food|a food|a dish|the dish|this dish)\b|\bnone of\b", re.IGNORECASE)


def _parse_choice(reply: str, count: int) -> Optional[int]:
    """Read the model's answer as a 0-based index, or None for 'none of these'."""
    if not reply:
        return None
    try:
        answer = json.loads(reply)
    except json.JSONDecodeError:
        # JSON mode occasionally wraps the object in prose; take the first object in the text.
        match = re.search(r"\{.*\}", reply, re.DOTALL)
        if not match:
            logger.warning("image_judge: unreadable reply %r", reply[:200])
            return None
        try:
            answer = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.warning("image_judge: unreadable reply %r", reply[:200])
            return None

    if not isinstance(answer, dict):
        return None
    reason = str(answer.get("reason") or "")[:80]
    choice = answer.get("choice")
    if isinstance(choice, str):
        digits = re.search(r"\d+", choice)          # "photo 2", "2", "none"
        choice = int(digits.group()) if digits else None
    if not isinstance(choice, int) or isinstance(choice, bool):
        logger.info("image_judge: none (%s)", reason)
        return None
    if not 1 <= choice <= count:                     # out of range means the model lost count
        logger.info("image_judge: choice %s outside 1-%d, treating as none", choice, count)
        return None
    if _SELF_REJECTION.search(reason):
        logger.info("image_judge: photo %d named but ruled out by its own reason (%s)", choice, reason)
        return None
    logger.info("image_judge: picked photo %d (%s)", choice, reason[:60])
    return choice - 1


def choose_from_images(llm, prompt: str, images: list[bytes]) -> Optional[int]:
    """Show images in order, read back a choice, return its 0-based index (or None for 'none').

    The primitive behind "which of these pictures is X?". The prompt must ask for
    ``{"choice": <number or null>}`` and number the photos from 1.

    Never cached: these prompts carry restaurant names that may have come from Google Places,
    whose terms only let us store a place_id.
    """
    reply = llm.generate(prompt, images=images, json_mode=True,
                         max_tokens=MAX_REPLY_TOKENS, cache=False)
    return _parse_choice(reply, len(images))


def _judge_batch(llm, restaurant_name: str, dish_name: str, batch: list[Shortlisted],
                 description: str = "") -> Optional[Shortlisted]:
    """One request: show the model this batch and return its pick, or None."""
    index = choose_from_images(llm, _prompt(dish_name, restaurant_name, len(batch), description),
                               [item.thumbnail for item in batch])
    return batch[index] if index is not None else None


def _batches(items: list[Shortlisted], size: int) -> list[list[Shortlisted]]:
    return [items[start:start + size] for start in range(0, len(items), size)]


def pick_best(llm, restaurant_name: str, dish_name: str, shortlist: list[Shortlisted],
              batch_size: Optional[int] = None, description: str = "") -> Optional[Shortlisted]:
    """Return the candidate that shows the dish, or None if the model rejects all of them.

    A single candidate is still judged: one wrong photo is the case this whole module exists for.
    Any failure (network, quota, unparseable reply) raises, and the caller falls back to the old
    "first usable result" behaviour rather than leaving the card blank.
    """
    remaining = [item for item in shortlist if item.content]
    if not remaining:
        return None

    size = max(1, batch_size or settings.dish_image_judge_batch_size)
    for _ in range(MAX_ROUNDS):
        winners = [
            winner for winner in
            (_judge_batch(llm, restaurant_name, dish_name, batch, description)
             for batch in _batches(remaining, size))
            if winner is not None
        ]
        if not winners:
            return None
        if len(winners) == 1:
            return winners[0]
        if len(winners) >= len(remaining):
            # Nothing was eliminated (batch size of 1, say); take the first survivor.
            return winners[0]
        remaining = winners

    return remaining[0]


# ─── What to search for ──────────────────────────────────────────────────────

TERMS_PROMPT = """A restaurant menu lists the dish "{dish}"{translated}{where}{described}.
Give up to 3 short search terms for finding a photo of this dish in Wikimedia Commons, an image library:
1. its common name as a food encyclopedia writes it (e.g. "Reuben sandwich", "japchae")
2. its native name, only for a dish from a cuisine not written in the Latin alphabet (e.g. "잡채", "凉皮")
3. a broader dish type (e.g. "corned beef sandwich", "glass noodles")
Each term 1-3 words: no restaurant names, menu numbers, sizes or words like "house" or "special".
Reply with JSON only: {{"terms": ["...", "...", "..."]}}"""
MAX_TERMS = 3


def suggest_search_terms(llm, dish_name: str, restaurant_name: str = "", translated_name: str = "",
                         description: str = "") -> list[str]:
    """Ask DeepSeek what a dish is called in an image library, when searching by its name failed.

    Menus name dishes the way the restaurant likes: "#81.5 Rick's 50/50 mix", "Ba-corn",
    "Gehran Jjim". Image libraries title photos the way an encyclopedia would: "pastrami sandwich",
    "corn cheese", "gyeran-jjim". Keyword search can't cross that gap and Commons' own fuzzy
    matching only fixes spelling, but a model that knows food can. Measured on 97 dishes, adding
    this fallback raised Wikimedia recall from 65% to 97%.

    About 200 input and 20 output tokens (~$0.00004), and only called for dishes the direct search
    couldn't find. Never cached: the prompt carries a restaurant name that may come from Google.
    """
    prompt = TERMS_PROMPT.format(
        dish=dish_name.strip(),
        translated=f' ("{translated_name.strip()}")' if translated_name.strip() and translated_name.strip() != dish_name.strip() else "",
        where=f' at "{restaurant_name.strip()}"' if restaurant_name.strip() else "",
        described=f', described as "{description.strip()[:300]}"' if description.strip() else "",
    )
    reply = llm.generate(prompt, json_mode=True, max_tokens=80, cache=False)
    try:
        terms = json.loads(reply).get("terms", [])
    except (json.JSONDecodeError, AttributeError):
        logger.info("image_judge: unreadable search terms %r", (reply or "")[:120])
        return []
    if not isinstance(terms, list):
        return []
    cleaned = [term.strip() for term in terms
               if isinstance(term, str) and term.strip() and len(term.split()) <= 4 and len(term) <= 60]
    return list(dict.fromkeys(cleaned))[:MAX_TERMS]
