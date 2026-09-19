"""Dish combo recommendations.

Pipeline:
1. Profile every dish once (one LLM call, cached): its role in a meal, cuisine, tastes, textures,
   colors, temperature, richness, spiciness, and weight. Keyword heuristics are the fallback.
2. Score candidate pairs and trios with explainable rules from meal-composition principles:
   role fit, taste balance, texture contrast, color variety, temperature contrast, weight balance,
   plus FlavorGraph ingredient-pairing evidence.
3. Retrieve passages on how the menu's food culture combines dishes (editorial notes + Wikipedia).
4. Let the LLM pick the best candidates and explain them in that cultural context.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from sqlalchemy.orm import Session

from app.knowledge.retrieval import (
    DishProfile,
    build_dish_profile,
    distinct_pairings,
    pairing_evidence,
    pairing_weights,
    search_passages,
    shared_compounds,
)

logger = logging.getLogger(__name__)

MAX_DISHES = 60
MAX_PAIR_CANDIDATES = 8
MAX_TRIO_CANDIDATES = 4

ROLES = ["starter", "soup", "salad", "main", "side", "rice_or_bread", "dessert", "drink", "dip_or_sauce", "snack"]
TASTES = ["sweet", "salty", "sour", "bitter", "umami", "spicy", "savory", "mild", "rich", "light",
          "smoky", "tangy", "aromatic", "fresh", "creamy"]
TEXTURES = ["crispy", "crunchy", "tender", "soft", "chewy", "juicy", "creamy", "flaky", "smooth", "firm",
            "silky", "fluffy", "sticky", "moist", "delicate", "saucy", "brothy"]
WEIGHTS = ["light", "medium", "heavy"]
TEMPERATURES = ["hot", "warm", "room", "cold"]

# How naturally two roles form a combo (order-independent; a one-role set means two of the same role).
ROLE_FIT = {
    frozenset({"main", "side"}): 1.0, frozenset({"main", "salad"}): 0.95,
    frozenset({"main", "rice_or_bread"}): 0.9, frozenset({"main", "soup"}): 0.85,
    frozenset({"main", "drink"}): 0.8, frozenset({"starter", "main"}): 0.8,
    frozenset({"snack", "drink"}): 0.85, frozenset({"snack", "dip_or_sauce"}): 0.8,
    frozenset({"main", "dip_or_sauce"}): 0.7, frozenset({"side", "dip_or_sauce"}): 0.7,
    frozenset({"soup", "salad"}): 0.7, frozenset({"dessert", "drink"}): 0.7,
    frozenset({"main", "snack"}): 0.7, frozenset({"side", "drink"}): 0.65,
    frozenset({"soup", "rice_or_bread"}): 0.75, frozenset({"main", "dessert"}): 0.55,
    frozenset({"starter", "soup"}): 0.6, frozenset({"starter", "side"}): 0.5,
    frozenset({"side"}): 0.5, frozenset({"starter"}): 0.5, frozenset({"main"}): 0.45,
}
FOOD_ROLES = set(ROLES) - {"drink", "dip_or_sauce"}
COMPLEMENTARY_ROLES = {"side", "salad", "drink", "rice_or_bread", "soup", "dip_or_sauce", "starter", "dessert"}

HEAVY_TASTES = {"rich", "creamy", "savory", "umami", "salty", "smoky"}
BRIGHT_TASTES = {"sour", "tangy", "fresh", "light"}
COOLING_TASTES = {"mild", "creamy", "sweet", "fresh"}
CRISP_TEXTURES = {"crispy", "crunchy", "flaky"}
SOFT_TEXTURES = {"soft", "creamy", "tender", "smooth", "silky", "saucy", "brothy", "moist", "fluffy", "sticky"}
COLOR_FAMILIES = {
    "brown": ("brown", "golden", "tan", "beige", "caramel", "bronze"),
    "red": ("red", "orange", "crimson", "coral"),
    "green": ("green", "herb", "olive"),
    "white": ("white", "cream", "ivory", "pale"),
    "yellow": ("yellow", "gold "),
    "dark": ("black", "dark", "charcoal"),
    "purple": ("purple", "pink", "magenta", "violet"),
}

WEIGHTS_BY_COMPONENT = {
    "role": 0.25, "taste": 0.2, "texture": 0.15, "ingredients": 0.15,
    "weight": 0.1, "color": 0.1, "temperature": 0.05,
}


@dataclass
class DishInput:
    name: str
    description: str = ""
    category: str = ""


@dataclass
class DishTraits:
    name: str
    description: str = ""
    category: str = ""
    role: str = "main"
    cuisine: str = ""
    tastes: list[str] = field(default_factory=list)
    textures: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    temperature: str = "hot"
    richness: int = 3
    spiciness: int = 0
    weight: str = "medium"
    ingredients: DishProfile | None = None

    def summary(self) -> dict:
        return {"name": self.name, "role": self.role, "tastes": self.tastes, "textures": self.textures,
                "colors": self.colors, "temperature": self.temperature, "weight": self.weight}


# ─── 1. Dish profiling ──────────────────────────────────────────────────────────

PROFILE_PROMPT = """You are a culinary expert. For every dish on this menu, infer how it tastes and what role it plays in a meal.
Use the menu description when present; otherwise assume the dish's typical preparation.

Restaurant: {restaurant}
Menu:
{menu}

Allowed roles: {roles}
Allowed tastes: {tastes}
Allowed textures: {textures}

Return JSON:
{{
  "cuisine": "the menu's overall cuisine, e.g. 'Quebecois comfort food' or 'Sichuan Chinese'",
  "dishes": [
    {{"index": 1, "role": "main", "cuisine": "cuisine of this dish", "tastes": ["savory", "rich"],
      "textures": ["crispy", "saucy"], "colors": ["golden brown", "white"], "temperature": "hot",
      "richness": 4, "spiciness": 0, "weight": "heavy"}}
  ]
}}
Rules: one entry per dish, same index as the menu list; temperature is one of {temperatures}; richness 1-5;
spiciness 0-5; weight is one of {weights}; 1-3 dominant colors of the plated dish.
"""

_ROLE_KEYWORDS = [
    ("drink", ("drink", "beverage", "soda", "juice", "tea", "coffee", "milk", "beer", "wine", "lassi", "shake")),
    ("dessert", ("dessert", "sweet", "cake", "pie", "ice cream", "pudding")),
    ("soup", ("soup", "broth", "stew", "jjigae", "ramen", "pho")),
    ("salad", ("salad", "slaw")),
    ("rice_or_bread", ("rice", "bread", "naan", "roti", "bun", "tortilla")),
    ("dip_or_sauce", ("dip", "sauce", "salsa", "chutney", "hummus")),
    ("side", ("side", "fries", "chips", "kids")),
    ("starter", ("starter", "appetizer", "appetiser", "small plate", "antipast")),
]
_TASTE_KEYWORDS = {
    "spicy": ("spicy", "chili", "chile", "jalapeno", "jalapeño", "sriracha", "hot sauce", "curry", "masala", "togarashi"),
    "tangy": ("pickle", "pickled", "vinegar", "lime", "lemon", "citrus", "slaw", "salsa verde", "mustard"),
    "rich": ("cheese", "gravy", "cream", "butter", "bacon", "pork belly", "braised", "fried", "aioli", "mayo"),
    "sweet": ("honey", "caramel", "sweet", "chocolate", "syrup", "glaze"),
    "fresh": ("salad", "arugula", "herb", "cilantro", "parsley", "cucumber", "lettuce"),
    "savory": ("beef", "chicken", "pork", "ham", "steak", "sausage", "egg"),
    "smoky": ("smoked", "bbq", "grilled", "charred"),
}
_TEXTURE_KEYWORDS = {
    "crispy": ("fried", "crispy", "panko", "crackling", "fries", "tempura", "katsu"),
    "saucy": ("gravy", "sauce", "curry", "au jus", "masala", "marinara"),
    "creamy": ("cheese", "cream", "mayo", "aioli", "crema"),
    "tender": ("braised", "slow", "pulled", "roast"),
    "crunchy": ("slaw", "pickle", "radish", "crunch"),
    "soft": ("roll", "bun", "ciabatta", "bread"),
}


def _heuristic_traits(dish: DishInput) -> DishTraits:
    text = f"{dish.name} {dish.category} {dish.description}".lower()
    role = next((r for r, words in _ROLE_KEYWORDS if any(w in text for w in words)), "main")
    tastes = [t for t, words in _TASTE_KEYWORDS.items() if any(w in text for w in words)] or ["savory"]
    textures = [t for t, words in _TEXTURE_KEYWORDS.items() if any(w in text for w in words)]
    heavy = "rich" in tastes and role in {"main", "side"}
    return DishTraits(
        name=dish.name, description=dish.description, category=dish.category, role=role,
        tastes=tastes, textures=textures,
        temperature="cold" if role in {"drink", "salad", "dessert"} else "hot",
        richness=4 if heavy else 2, spiciness=3 if "spicy" in tastes else 0,
        weight="heavy" if heavy else ("light" if role in {"drink", "salad", "dip_or_sauce"} else "medium"),
    )


def _pick(values, allowed: list[str], limit: int) -> list[str]:
    allowed_set = set(allowed)
    picked = [v.strip().lower() for v in values or [] if isinstance(v, str) and v.strip().lower() in allowed_set]
    return list(dict.fromkeys(picked))[:limit]


def _int(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def profile_dishes(dishes: list[DishInput], restaurant: str = "", llm_client=None) -> tuple[list[DishTraits], str]:
    """Return per-dish traits and the menu's overall cuisine."""
    traits = [_heuristic_traits(d) for d in dishes]
    if llm_client is None or not dishes:
        return traits, ""

    menu = "\n".join(
        f"{i + 1}. {d.name}" + (f" [{d.category}]" if d.category else "") + (f" — {d.description}" if d.description else "")
        for i, d in enumerate(dishes)
    )
    prompt = PROFILE_PROMPT.format(
        restaurant=restaurant or "unknown", menu=menu, roles=", ".join(ROLES), tastes=", ".join(TASTES),
        textures=", ".join(TEXTURES), temperatures=", ".join(TEMPERATURES), weights=", ".join(WEIGHTS),
    )
    try:
        data = json.loads(llm_client.generate(prompt, json_mode=True, cache=True, purpose="dish_profiles", max_tokens=8000))
    except Exception as exc:
        logger.warning("Dish profiling failed, using keyword heuristics: %s", exc)
        return traits, ""

    for entry in data.get("dishes") or []:
        if not isinstance(entry, dict):
            continue
        index = _int(entry.get("index"), 1, len(dishes), 0) - 1
        if index < 0:
            continue
        t = traits[index]
        t.role = entry.get("role") if entry.get("role") in ROLES else t.role
        t.cuisine = str(entry.get("cuisine") or "")[:80]
        t.tastes = _pick(entry.get("tastes"), TASTES, 5) or t.tastes
        t.textures = _pick(entry.get("textures"), TEXTURES, 4) or t.textures
        t.colors = [str(c).strip().lower()[:30] for c in entry.get("colors") or [] if str(c).strip()][:3]
        t.temperature = entry.get("temperature") if entry.get("temperature") in TEMPERATURES else t.temperature
        t.richness = _int(entry.get("richness"), 1, 5, t.richness)
        t.spiciness = _int(entry.get("spiciness"), 0, 5, t.spiciness)
        t.weight = entry.get("weight") if entry.get("weight") in WEIGHTS else t.weight
    return traits, str(data.get("cuisine") or "")[:120]


# ─── 2. Rule-based scoring ──────────────────────────────────────────────────────


def _color_families(colors: list[str]) -> set[str]:
    families = set()
    for color in colors:
        padded = f"{color} "
        for family, words in COLOR_FAMILIES.items():
            if any(word in padded for word in words):
                families.add(family)
    return families


def score_pair(a: DishTraits, b: DishTraits, evidence: list[dict]) -> tuple[float, dict[str, float], list[str]]:
    """Score two dishes as a combo. Returns (score 0-1, component scores, human-readable reasons)."""
    reasons: list[str] = []
    ta, tb = set(a.tastes), set(b.tastes)

    role = ROLE_FIT.get(frozenset({a.role, b.role}), 0.45)
    if role >= 0.8:
        reasons.append(f"{a.role.replace('_', ' ')} + {b.role.replace('_', ' ')}")

    taste = 0.5
    if (ta & HEAVY_TASTES and tb & BRIGHT_TASTES) or (tb & HEAVY_TASTES and ta & BRIGHT_TASTES):
        taste += 0.3
        reasons.append("rich balanced by tangy/fresh")
    if ("spicy" in ta and tb & COOLING_TASTES) or ("spicy" in tb and ta & COOLING_TASTES):
        taste += 0.2
        reasons.append("heat cooled by a milder dish")
    if ("sweet" in ta and tb & {"salty", "sour"}) or ("sweet" in tb and ta & {"salty", "sour"}):
        taste += 0.1
    if a.spiciness >= 4 and b.spiciness >= 4:
        taste -= 0.3
    if a.richness + b.richness >= 9:
        taste -= 0.3
    if ta and tb and len(ta & tb) / len(ta | tb) > 0.8:
        taste -= 0.1
    taste = max(0.0, min(1.0, taste))

    xa, xb = set(a.textures), set(b.textures)
    if (xa & CRISP_TEXTURES and xb & SOFT_TEXTURES) or (xb & CRISP_TEXTURES and xa & SOFT_TEXTURES):
        texture = 0.9
        reasons.append("crisp meets soft")
    elif xa and xb and len(xa & xb) / len(xa | xb) < 0.3:
        texture = 0.6
    else:
        texture = 0.35

    families = _color_families(a.colors) | _color_families(b.colors)
    color = min(1.0, len(families) / 3) if families else 0.5
    if len(families) >= 3:
        reasons.append("colorful plate")

    hot = {"hot", "warm"}
    if (a.temperature in hot) != (b.temperature in hot):
        temperature = 0.8
        reasons.append("hot with cold")
    else:
        temperature = 0.5

    weights = {a.weight, b.weight}
    if weights == {"heavy", "light"}:
        weight = 1.0
        reasons.append("heavy with light")
    elif weights == {"heavy"}:
        weight = 0.2
    elif "heavy" in weights or weights == {"medium"}:
        weight = 0.7
    else:
        weight = 0.6

    ingredient = min(1.0, (sum(e["weight"] for e in evidence[:3]) / 3) / 0.35) if evidence else 0.0
    if evidence:
        reasons.append(f"{evidence[0]['a']} goes with {evidence[0]['b']}")

    components = {"role": role, "taste": taste, "texture": texture, "ingredients": ingredient,
                  "weight": weight, "color": color, "temperature": temperature}
    score = sum(WEIGHTS_BY_COMPONENT[k] * v for k, v in components.items())
    if _is_kids(a) != _is_kids(b):
        score *= 0.6  # a kids-menu item rarely belongs in an adult's combo
    return round(score, 4), components, reasons


def _is_kids(dish: DishTraits) -> bool:
    return any(word in dish.category.lower() for word in ("kid", "child"))


@dataclass
class Candidate:
    dishes: list[DishTraits]
    score: float
    reasons: list[str]
    evidence: list[dict]


def build_candidates(traits: list[DishTraits], weights: dict) -> list[Candidate]:
    """Diverse pair and trio candidates: food pairs first, then a drink/side/etc. as an optional third."""
    pair_scores: dict[tuple[int, int], tuple[float, list[str], list[dict]]] = {}
    for i, j in combinations(range(len(traits)), 2):
        a, b = traits[i], traits[j]
        evidence = pairing_evidence(a.ingredients, b.ingredients, weights) if a.ingredients and b.ingredients else []
        score, _components, reasons = score_pair(a, b, evidence)
        pair_scores[(i, j)] = (score, reasons, evidence)

    # Pair two foods; a drink or dip only makes sense as an add-on (unless the menu has nothing else).
    food_pairs = [key for key in pair_scores if traits[key[0]].role in FOOD_ROLES and traits[key[1]].role in FOOD_ROLES]
    ranked = sorted(food_pairs or pair_scores, key=lambda key: pair_scores[key][0], reverse=True)

    picked, uses = [], Counter()
    for i, j in ranked:  # each dish in at most two pair candidates, so one great side can't crowd out the rest
        if uses[i] < 2 and uses[j] < 2:
            picked.append((i, j))
            uses.update((i, j))
            if len(picked) >= MAX_PAIR_CANDIDATES:
                break
    candidates = [Candidate([traits[i], traits[j]], *pair_scores[(i, j)]) for i, j in picked]

    trios, third_uses = [], Counter()
    for i, j in picked:
        best = None
        for k, third in enumerate(traits):
            if k in (i, j) or third.role not in COMPLEMENTARY_ROLES or third_uses[k] >= 2:
                continue
            if _is_kids(third) != _is_kids(traits[i]):
                continue
            s_ik, s_jk = pair_scores[tuple(sorted((i, k)))], pair_scores[tuple(sorted((j, k)))]
            roles = {traits[i].role, traits[j].role, third.role}
            score = (pair_scores[(i, j)][0] + s_ik[0] + s_jk[0]) / 3 + (0.05 if len(roles) == 3 else 0)
            if best is None or score > best[0]:
                best = (score, k, s_ik, s_jk)
        if best is not None:
            score, k, s_ik, s_jk = best
            reasons = list(dict.fromkeys(pair_scores[(i, j)][1] + s_ik[1] + s_jk[1]))
            trios.append(Candidate([traits[i], traits[j], traits[k]], round(score, 4), reasons,
                                   pair_scores[(i, j)][2] + s_ik[2] + s_jk[2]))
            third_uses[k] += 1
    trios.sort(key=lambda c: c.score, reverse=True)
    return sorted(candidates + trios[:MAX_TRIO_CANDIDATES], key=lambda c: c.score, reverse=True)


# ─── 3 + 4. Cultural context and LLM selection ──────────────────────────────────

SELECT_PROMPT = """You recommend dish combos from one restaurant menu to a diner.

Menu cuisine: {cuisine}
Restaurant: {restaurant}

How dishes are combined in this and related food cultures (reference notes; cite as [1], [2] only when used):
{passages}

Candidate combos, pre-scored on role fit, taste balance, texture contrast, color variety, temperature, weight,
and ingredient pairing data from 1M+ recipes:
{candidates}

Choose exactly {count} combos (fewer only if there aren't enough candidates without shared dishes).
Prefer combos that follow this cuisine's customs, balance tastes, contrast textures and temperatures, look appealing
together, and aren't too heavy. Each dish may appear in only one of your combos. Fill cultural_note whenever a
reference note is relevant to the dishes.
Write for a diner: use dish names, never candidate ids or scores.
Return JSON:
{{"combos": [{{"candidate": "C1", "title": "short catchy name (max 6 words)", "explanation": "2 sentences, max 60 words, on why they work together (taste, texture, color, weight)", "cultural_note": "one sentence, max 30 words, on how this food culture combines such dishes, or empty string", "tip": "one sentence, max 20 words"}}]}}
"""


DESCRIBE_PROMPT = """Write short diner-facing descriptions for these dish combos from one menu.
Menu cuisine: {cuisine}

Reference notes on how dishes are combined (cite as [1], [2] only when used):
{passages}

Combos:
{combos}

Use dish names, never ids or scores.
Return JSON: {{"combos": [{{"id": "F1", "title": "max 6 words", "explanation": "2 sentences, max 60 words (taste, texture, color, weight)", "cultural_note": "one sentence or empty string", "tip": "one sentence, max 20 words"}}]}}
"""


def _describe_fill_ins(fill_ins: list[Candidate], cuisine: str, passages: list[dict], llm_client) -> dict[int, dict]:
    """One extra LLM call to write text for rule-picked combos the selection step didn't cover."""
    prompt = DESCRIBE_PROMPT.format(
        cuisine=cuisine,
        passages="\n".join(f"[{i + 1}] {p['text'][:700]}" for i, p in enumerate(passages)) or "(none)",
        combos="\n".join(
            f"F{i + 1}: " + " + ".join(_describe(d) for d in c.dishes)
            + (f"\n    strengths: {'; '.join(c.reasons[:5])}" if c.reasons else "")
            for i, c in enumerate(fill_ins)
        ),
    )
    try:
        data = json.loads(llm_client.generate(prompt, json_mode=True, cache=True, purpose="combo_description", max_tokens=1500))
    except Exception as exc:
        logger.warning("Combo description failed, using templates: %s", exc)
        return {}
    written = {}
    for entry in data.get("combos") or []:
        if not isinstance(entry, dict):
            continue
        index = _int(str(entry.get("id", "")).lstrip("Ff"), 1, len(fill_ins), 0) - 1
        if index >= 0:
            texts = {k: str(entry.get(k) or "") for k in ("title", "explanation", "cultural_note", "tip")}
            written[index] = {**_template(fill_ins[index]), **{k: v for k, v in texts.items() if v}}
    return written


def _overlaps(candidate: Candidate, chosen: list[Candidate]) -> bool:
    names = {d.name for d in candidate.dishes}
    return any(names & {d.name for d in other.dishes} for other in chosen)


def _describe(dish: DishTraits) -> str:
    parts = [dish.role.replace("_", " ")]
    for label, values in (("tastes", dish.tastes), ("textures", dish.textures), ("colors", dish.colors)):
        if values:
            parts.append(f"{label}: {', '.join(values)}")
    parts.append(f"{dish.temperature}, {dish.weight}")
    return f"{dish.name} ({'; '.join(parts)})"


def _template(candidate: Candidate) -> dict:
    names = " + ".join(d.name for d in candidate.dishes)
    why = "; ".join(candidate.reasons[:3]) or "complementary dishes"
    return {"title": names, "explanation": f"These work together: {why}.", "cultural_note": "",
            "tip": "Share them so every bite can alternate between the dishes."}


def recommend_combos(
    db: Session, dishes: list[DishInput], max_combos: int = 3, llm_client=None, restaurant: str = "",
) -> list[dict]:
    return recommend_combos_with_context(db, dishes, max_combos, llm_client, restaurant)["combos"]


def recommend_combos_with_context(
    db: Session, dishes: list[DishInput], max_combos: int = 3, llm_client=None, restaurant: str = "",
) -> dict:
    """Like recommend_combos, but also returns the inferred menu cuisine."""
    dishes = dishes[:MAX_DISHES]
    if len(dishes) < 2:
        return {"combos": [], "cuisine": ""}

    traits, cuisine = profile_dishes(dishes, restaurant, llm_client)
    for trait in traits:
        trait.ingredients = build_dish_profile(db, trait.name, trait.description, trait.category)
    weights = pairing_weights(db, [t.ingredients for t in traits if t.ingredients])
    candidates = build_candidates(traits, weights)
    if not candidates:
        return {"combos": [], "cuisine": cuisine}

    cuisine_label = cuisine or restaurant or "unknown"
    # Dish names (e.g. "poutine", "katsu") point retrieval at the right food culture better than a vague label.
    query = f"{cuisine_label} meals with {', '.join(d.name for d in dishes[:10])}: which dishes are eaten together"
    # Search each source separately so long Wikipedia articles can't crowd out the focused notes.
    passages = search_passages(db, query, top_k=2, sources=("editorial",)) + \
        search_passages(db, query, top_k=1, sources=("wikipedia",))

    chosen: list[tuple[Candidate, dict]] = []
    if llm_client is not None:
        labeled = {f"C{i + 1}": c for i, c in enumerate(candidates)}
        prompt = SELECT_PROMPT.format(
            cuisine=cuisine_label, restaurant=restaurant or "unknown", count=max_combos,
            passages="\n".join(f"[{i + 1}] {p['text'][:900]}" for i, p in enumerate(passages)) or "(none)",
            candidates="\n".join(
                f"{cid}: " + " + ".join(_describe(d) for d in c.dishes)
                + (f"\n    strengths: {'; '.join(c.reasons[:5])}" if c.reasons else "")
                for cid, c in labeled.items()
            ),
        )
        try:
            data = json.loads(llm_client.generate(prompt, json_mode=True, cache=True, purpose="combo_selection", max_tokens=3000))
            for entry in data.get("combos") or []:
                candidate = labeled.get(str(entry.get("candidate", "")).strip()) if isinstance(entry, dict) else None
                if candidate is None or _overlaps(candidate, [c for c, _ in chosen]):
                    continue
                text = {k: str(entry.get(k) or "") for k in ("title", "explanation", "cultural_note", "tip")}
                chosen.append((candidate, {**_template(candidate), **{k: v for k, v in text.items() if v}}))
                if len(chosen) >= max_combos:
                    break
        except Exception as exc:
            logger.warning("Combo selection failed, using rule-based ranking: %s", exc)

    # Rule-based ranking fills whatever the model didn't (no model, failure, or too few distinct picks).
    fill_ins = []
    for candidate in candidates:
        if len(chosen) + len(fill_ins) >= max_combos:
            break
        if not _overlaps(candidate, [c for c, _ in chosen] + fill_ins):
            fill_ins.append(candidate)
    written = _describe_fill_ins(fill_ins, cuisine_label, passages, llm_client) if llm_client and fill_ins else {}
    chosen += [(candidate, written.get(i) or _template(candidate)) for i, candidate in enumerate(fill_ins)]

    results = []
    for candidate, text in chosen:
        evidence = distinct_pairings(candidate.evidence)
        compounds = shared_compounds(db, evidence[0]["a"], evidence[0]["b"]) if evidence else []
        results.append({
            "dishes": [d.name for d in candidate.dishes],
            "score": candidate.score,
            **text,
            "reasons": candidate.reasons[:5],
            "dish_profiles": [d.summary() for d in candidate.dishes],
            "pairings": evidence,
            "shared_compounds": compounds,
            "sources": [
                {"title": p["document_title"], "url": p["url"], "license": p["license"],
                 "excerpt": p["text"][:300], "page": p["page"]}
                for p in passages
            ],
        })
    return {"combos": results, "cuisine": cuisine}
