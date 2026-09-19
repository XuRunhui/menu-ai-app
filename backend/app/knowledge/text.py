"""Name normalization, ingredient mention matching, and text chunking."""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")

# Ingredients so common they say nothing about whether two dishes pair well.
GENERIC_INGREDIENTS = {
    "water", "salt", "ice", "ice cube", "sugar", "oil", "vegetable oil", "cooking spray",
    "kosher salt", "sea salt", "black pepper", "pepper", "salt and pepper", "flour",
    "all purpose flour", "butter", "egg", "roll", "bun", "bread",
}


def singularize(word: str) -> str:
    """Crude English singularization; applied identically everywhere, so it only needs to be consistent."""
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("oes"):
        return word[:-2]
    if word.endswith(("ches", "shes", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def normalize_name(name: str) -> str:
    """'Soy_Sauces' -> 'soy sauce', 'Jalapeño' -> 'jalapeno'."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("_", " ").replace("-", " ")
    text = _SPACES.sub(" ", _NON_WORD.sub(" ", text)).strip()
    return " ".join(singularize(token) for token in text.split())


def display_name(name: str) -> str:
    return _SPACES.sub(" ", name.replace("_", " ")).strip()


class MentionMatcher:
    """Find known names (e.g. ingredients) mentioned in free text, longest match first."""

    def __init__(self, vocabulary: dict[str, int], max_words: int = 4):
        self.vocabulary = vocabulary      # normalized name -> entity id
        self.max_words = max_words

    def find(self, text: str) -> dict[int, str]:
        tokens = normalize_name(text).split()
        found: dict[int, str] = {}
        i = 0
        while i < len(tokens):
            for size in range(min(self.max_words, len(tokens) - i), 0, -1):
                phrase = " ".join(tokens[i:i + size])
                entity_id = self.vocabulary.get(phrase)
                if entity_id is not None:
                    found[entity_id] = phrase
                    i += size
                    break
            else:
                i += 1
        return found


def chunk_text(text: str, target_chars: int = 1200, overlap_chars: int = 150) -> list[str]:
    """Split text into ~target_chars chunks on paragraph (then sentence) boundaries, with overlap."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        paragraph = _SPACES.sub(" ", paragraph)
        if len(paragraph) <= target_chars:
            pieces.append(paragraph)
        else:
            pieces.extend(s.strip() for s in re.split(r"(?<=[.!?;])\s+", paragraph) if s.strip())

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 1 > target_chars:
            chunks.append(current)
            tail = current[-overlap_chars:]
            current = tail[tail.find(" ") + 1:] if " " in tail else ""
        current = f"{current} {piece}".strip()
        while len(current) > target_chars * 2:  # a single enormous sentence
            chunks.append(current[:target_chars])
            current = current[target_chars - overlap_chars:]
    if current:
        chunks.append(current)
    return chunks
