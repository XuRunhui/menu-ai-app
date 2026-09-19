"""Tests for the knowledge base: importers, retrieval, combos, PDF extraction, and the API."""

import json

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentence_transformers import SentenceTransformer

from app.api.v1.endpoints import knowledge as knowledge_api
from app.core.config import settings
from app.knowledge import models
from app.knowledge.combos import (
    DishInput,
    DishTraits,
    _heuristic_traits,
    profile_dishes,
    recommend_combos,
    score_pair,
)
from app.knowledge.db import knowledge_session
from app.knowledge.retrieval import DishProfile, build_dish_profile, distinct_pairings, pairing_evidence, search_passages
from app.knowledge.sources.documents import extract_pdf_pages, import_editorial, import_pdf, strip_gutenberg_boilerplate
from app.knowledge.sources.flavorgraph import import_flavorgraph
from app.knowledge.sources.wikidata import import_wikidata
from app.knowledge.store import stats
from app.knowledge.text import MentionMatcher, chunk_text, normalize_name
from app.services import embeddings


class _FakeEmbedder:
    VOCAB = ["tomato", "basil", "cheese", "sauce", "bread", "soup"]

    def get_sentence_embedding_dimension(self):
        return len(self.VOCAB)

    def encode(self, texts, **kwargs):
        rows = [[float(word in t.lower()) for word in self.VOCAB] for t in texts]
        return np.array(rows, dtype=np.float32) + 1e-3


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    """Empty knowledge DB with a small FlavorGraph + Wikidata graph and a fake embedding model."""
    monkeypatch.setitem(embeddings._models, (SentenceTransformer, settings.rag_embedding_model), _FakeEmbedder())
    with knowledge_session() as db:
        for model in (models.Edge, models.Chunk, models.Document, models.Entity):
            db.query(model).delete()

    nodes = tmp_path / "nodes.csv"
    nodes.write_text(
        "node_id,name,id,node_type,is_hub\n"
        "1,tomato,,ingredient,hub\n2,basil,,ingredient,hub\n3,mozzarella_cheese,,ingredient,no_hub\n"
        "4,pickle,,ingredient,no_hub\n5,mustard,,ingredient,no_hub\n6,chocolate,,ingredient,no_hub\n"
        "7,salt,,ingredient,hub\n100,Linalool,100.0,compound,no_hub\n"
    )
    edges = tmp_path / "edges.csv"
    edges.write_text(
        "id_1,id_2,score,edge_type\n"
        "1,2,0.6,ingr-ingr\n1,3,0.4,ingr-ingr\n4,5,0.5,ingr-ingr\n6,7,0.9,ingr-ingr\n"
        "1,100,,ingr-fcomp\n2,100,,ingr-fcomp\n"
    )
    wikidata = tmp_path / "dishes.json"

    def b(dish, label, ingredient, ingredient_label, desc=""):
        return {"dish": {"value": f"http://www.wikidata.org/entity/{dish}"}, "dishLabel": {"value": label},
                "dishDescription": {"value": desc},
                "ingredient": {"value": f"http://www.wikidata.org/entity/{ingredient}"},
                "ingredientLabel": {"value": ingredient_label}}

    wikidata.write_text(json.dumps({
        "ingredients": [b("Q1", "Caprese salad", "Q10", "tomatoes"), b("Q1", "Caprese salad", "Q11", "basil"),
                        b("Q2", "Unlabeled", "Q12", "Q12")],
        "origins": [{"dish": {"value": "http://www.wikidata.org/entity/Q1"},
                     "cuisineLabel": {"value": "Italian cuisine"}, "countryLabel": {"value": "Italy"}}],
    }))
    with knowledge_session() as db:
        import_flavorgraph(db, nodes, edges)
        import_wikidata(db, wikidata)
    yield


def test_normalize_and_match():
    assert normalize_name("Soy_Sauces") == "soy sauce"
    assert normalize_name("Jalapeño Peppers") == "jalapeno pepper"
    matcher = MentionMatcher({"soy sauce": 1, "sauce": 2, "tomato": 3})
    assert matcher.find("Tomatoes with soy sauce") == {3: "tomato", 1: "soy sauce"}


def test_chunk_text_respects_target_and_overlap():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(10))
    chunks = chunk_text(text, target_chars=500, overlap_chars=50)
    assert len(chunks) > 3
    assert all(len(c) <= 1000 for c in chunks)
    assert chunk_text("") == []


def test_gutenberg_boilerplate_is_stripped():
    raw = ("Title: The Cook Book\n\n*** START OF THE PROJECT GUTENBERG EBOOK THE COOK BOOK ***\n"
           "Boil the water.\n*** END OF THE PROJECT GUTENBERG EBOOK THE COOK BOOK ***\nLicense text")
    assert strip_gutenberg_boilerplate(raw) == ("The Cook Book", "Boil the water.")


def test_importers_merge_entities_across_sources(kb):
    with knowledge_session() as db:
        counts = stats(db)
        tomato = db.query(models.Entity).filter_by(type="ingredient", normalized_name="tomato").one()
    assert counts["entities"]["dish"] == 1          # the unlabeled Q-id dish is skipped
    assert counts["edges"]["pairs_with"] == 4
    assert counts["edges"]["made_from"] == 2
    assert counts["edges"]["cuisine"] == 1 and counts["edges"]["origin_country"] == 1
    # "tomatoes" (Wikidata) and "tomato" (FlavorGraph) are one entity with both ids.
    assert tomato.flavorgraph_id == "1" and tomato.wikidata_id == "Q10"


def test_dish_profile_uses_wikidata_and_text(kb):
    with knowledge_session() as db:
        profile = build_dish_profile(db, "Caprese Salad", "with mozzarella cheese and a pinch of salt")
    assert profile.matched_dish == "Caprese salad"
    assert set(profile.ingredient_ids.values()) >= {"tomato", "basil", "mozzarella cheese"}
    assert "salt" not in profile.ingredient_ids.values()   # generic ingredients are ignored


def _traits(name, role, tastes=(), textures=(), colors=(), temperature="hot", weight="medium", richness=3, spiciness=0):
    return DishTraits(name=name, role=role, tastes=list(tastes), textures=list(textures), colors=list(colors),
                      temperature=temperature, weight=weight, richness=richness, spiciness=spiciness)


def test_score_pair_rewards_balance_and_contrast():
    poutine = _traits("Poutine", "main", ["rich", "salty", "savory"], ["crispy", "saucy"], ["golden brown"],
                      weight="heavy", richness=5)
    slaw = _traits("Pickled Slaw", "salad", ["tangy", "fresh"], ["crunchy"], ["green", "purple"],
                   temperature="cold", weight="light", richness=1)
    burger = _traits("Double Burger", "main", ["rich", "savory"], ["juicy", "soft"], ["brown"],
                     weight="heavy", richness=5)

    good, _, reasons = score_pair(poutine, slaw, [])
    heavy, _, _ = score_pair(poutine, burger, [])
    assert good > heavy + 0.2
    assert "rich balanced by tangy/fresh" in reasons and "hot with cold" in reasons
    assert "colorful plate" in reasons


def test_each_ingredient_pairing_is_listed_once():
    # Two entries named "vegetable" (and the pair found both ways round) used to list
    # "soup × vegetable" twice: shown twice on the card, and counted twice in the score.
    soup = DishProfile(name="Wonton Soup", ingredient_ids={1: "soup", 2: "pork"})
    stir_fry = DishProfile(name="Stir-fried Greens", ingredient_ids={3: "vegetable", 4: "Vegetable", 5: "garlic"})
    weights = {(1, 3): 0.9, (1, 4): 0.8, (2, 5): 0.5}
    assert [(e["a"], e["b"]) for e in pairing_evidence(soup, stir_fry, weights)] == [("soup", "vegetable"), ("pork", "garlic")]

    # A trio gathers evidence from its three dish pairs, which repeat each other.
    trio = [{"a": "soup", "b": "vegetable", "weight": 0.9}, {"a": "vegetable", "b": "soup", "weight": 0.7},
            {"a": "rice", "b": "rice", "weight": 0.6}, {"a": "rice", "b": "egg", "weight": 0.5}]
    assert [(e["a"], e["b"], e["weight"]) for e in distinct_pairings(trio)] == [("soup", "vegetable", 0.9), ("rice", "egg", 0.5)]


def test_profile_dishes_sanitizes_llm_output():
    class FakeLLM:
        def generate(self, prompt, **kwargs):
            assert kwargs["cache"] is True
            return json.dumps({"cuisine": "Quebecois", "dishes": [
                {"index": 2, "role": "drink", "tastes": ["SWEET", "unknown-taste"], "textures": [],
                 "colors": ["amber"], "temperature": "cold", "richness": 99, "spiciness": -2, "weight": "light"},
                {"index": 1, "role": "not-a-role", "tastes": ["rich"], "weight": "enormous"},
                {"index": 7},
            ]})

    traits, cuisine = profile_dishes([DishInput("Poutine", "fries, gravy, cheese curds"), DishInput("Cola")], llm_client=FakeLLM())
    assert cuisine == "Quebecois"
    assert traits[1].role == "drink" and traits[1].tastes == ["sweet"] and traits[1].richness == 5 and traits[1].spiciness == 0
    fallback = _heuristic_traits(DishInput("Poutine", "fries, gravy, cheese curds"))
    assert traits[0].role == fallback.role and traits[0].weight == fallback.weight  # invalid values ignored
    assert traits[0].tastes == ["rich"]
    assert "saucy" in traits[0].textures  # keyword fallback kept when the model gave none


def test_combos_without_llm_are_distinct_and_explained(kb):
    dishes = [
        DishInput("Tomato Soup", "Roasted tomato soup", "Soups"),
        DishInput("Basil Toast", "Grilled bread with basil", "Starters"),
        DishInput("Pickle Plate", "House pickles", "Starters"),
        DishInput("Mustard Pretzel", "Soft pretzel with mustard", "Snacks"),
        DishInput("Lemonade", "Fresh lemon drink", "Drinks"),
    ]
    with knowledge_session() as db:
        combos = recommend_combos(db, dishes, max_combos=2)
    assert 1 <= len(combos) <= 2
    names = [name for combo in combos for name in combo["dishes"]]
    assert len(names) == len(set(names))  # no dish reused across combos without an LLM
    assert all(combo["title"] and combo["explanation"] and 2 <= len(combo["dishes"]) <= 3 for combo in combos)


def test_combo_selection_uses_llm_and_cultural_passages(kb):
    with knowledge_session() as db:
        import_editorial(db)

    class FakeLLM:
        def __init__(self):
            self.calls = []

        def generate(self, prompt, **kwargs):
            self.calls.append(kwargs["purpose"])
            if kwargs["purpose"] == "dish_profiles":
                return json.dumps({"cuisine": "Italian", "dishes": [
                    {"index": 1, "role": "soup", "tastes": ["umami"], "textures": ["brothy"], "temperature": "hot"},
                    {"index": 2, "role": "starter", "tastes": ["fresh"], "textures": ["crispy"], "temperature": "room"},
                ]})
            assert "How dishes are combined" in prompt or "[1]" in prompt
            return json.dumps({"combos": [{"candidate": "C1", "title": "Garden Duo", "explanation": "Tomato meets basil.",
                                           "cultural_note": "Italians follow soup with lighter plates.", "tip": "Dip the toast."}]})

    llm = FakeLLM()
    with knowledge_session() as db:
        combos = recommend_combos(db, [DishInput("Tomato Soup", "tomato"), DishInput("Basil Toast", "basil bread")],
                                  llm_client=llm, restaurant="Trattoria")
    assert llm.calls == ["dish_profiles", "combo_selection"]
    assert combos[0]["title"] == "Garden Duo" and combos[0]["cultural_note"].startswith("Italians")
    assert combos[0]["pairings"][0]["a"] in {"tomato", "basil"}
    assert combos[0]["sources"] and combos[0]["sources"][0]["license"] == "Menuist editorial (MIT)"


def test_editorial_import_and_source_filter(kb):
    with knowledge_session() as db:
        result = import_editorial(db)
        assert result["chunks"] >= 10
        hits = search_passages(db, "tomato basil soup", top_k=3, sources=("wikipedia",))
    assert hits == []  # no Wikipedia documents in this test database


def test_wikipedia_import(kb, tmp_path, monkeypatch):
    from app.knowledge.sources import wikipedia

    monkeypatch.setattr(wikipedia, "SOURCES_DIR", tmp_path)

    class FakeResponse:
        def __init__(self, title):
            self.title = title

        def raise_for_status(self):
            pass

        def json(self):
            if self.title == "Missing page":
                return {"query": {"pages": [{"title": self.title, "missing": True}]}}
            text = "Thali is a round platter.\n\n== Components ==\nRice, dal and raita.\n\n== References ==\nBooks."
            return {"query": {"pages": [{"title": "Thali", "extract": text}]}}

    monkeypatch.setattr(wikipedia.requests, "get", lambda url, params, headers, timeout: FakeResponse(params["titles"]))
    with knowledge_session() as db:
        result = wikipedia.import_wikipedia(db, ["Thali", "Missing page"])
    with knowledge_session() as db:
        document = db.query(models.Document).filter_by(source="wikipedia").one()
        chunk_text_value = db.query(models.Chunk).filter_by(document_id=document.id).first().text
    assert result == {"articles": 1, "chunks": 1, "missing": ["Missing page"]}
    assert document.url == "https://en.wikipedia.org/wiki/Thali" and "CC BY-SA" in document.license
    assert "raita" in chunk_text_value and "Books" not in chunk_text_value


def _minimal_pdf(lines: list[str]) -> bytes:
    stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_pdf_import_and_passage_search(kb, tmp_path):
    pdf = tmp_path / "notes.pdf"
    pdf.write_bytes(_minimal_pdf(["Tomato soup is best with fresh basil.", "Serve with cheese bread."]))
    with knowledge_session() as db:
        result = import_pdf(db, pdf, title="Soup Notes", license="CC BY 4.0")
        assert result["chunks"] == 1
        assert import_pdf(db, pdf, title="Soup Notes", license="CC BY 4.0")["skipped"] is True
    with knowledge_session() as db:
        hits = search_passages(db, "tomato basil", top_k=1)
    assert hits[0]["document_title"] == "Soup Notes" and hits[0]["page"] == 1
    assert "basil" in hits[0]["text"] and hits[0]["license"] == "CC BY 4.0"


def test_pdf_pages_without_text_are_ocrd(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_minimal_pdf([]))

    class FakeVision:
        def generate(self, prompt, image_bytes=None, **kwargs):
            assert image_bytes.startswith(b"\x89PNG")
            return "Scanned recipe text"

    assert extract_pdf_pages(pdf) == []
    assert extract_pdf_pages(pdf, llm_client=FakeVision()) == [(1, "Scanned recipe text")]


def test_combo_endpoint(kb, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    app = FastAPI()
    app.include_router(knowledge_api.router, prefix="/api/v1/knowledge")
    client = TestClient(app)

    response = client.post("/api/v1/knowledge/combos", json={"dishes": [
        {"name": "Tomato Soup", "description": "tomato"}, {"name": "Basil Toast", "description": "basil"},
    ]})
    body = response.json()
    assert response.status_code == 200 and body["knowledge_available"] is True
    assert set(body["combos"][0]["dishes"]) == {"Tomato Soup", "Basil Toast"}

    assert client.post("/api/v1/knowledge/combos", json={"dishes": [{"name": "Only one"}]}).status_code == 422


def test_combo_endpoint_caches_full_responses(kb, monkeypatch):
    calls = []

    def fake_compute(request):
        calls.append(request)
        from app.models.knowledge import ComboResponse
        return ComboResponse(combos=[{
            "dishes": ["A", "B"], "score": 0.7, "title": "Duo", "explanation": "Works.", "tip": "Share.",
            "pairings": [], "shared_compounds": [], "sources": [],
        }], knowledge_available=True, cuisine="Test")

    monkeypatch.setattr(knowledge_api, "compute_combos", fake_compute)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    app = FastAPI()
    app.include_router(knowledge_api.router, prefix="/api/v1/knowledge")
    client = TestClient(app)
    body = {"dishes": [{"name": "Cache A"}, {"name": "Cache B"}], "restaurant_name": "Cache Test"}

    first = client.post("/api/v1/knowledge/combos", json=body).json()
    second = client.post("/api/v1/knowledge/combos", json=body).json()
    assert first == second and first["cuisine"] == "Test"
    assert len(calls) == 1


def test_demo_seed_makes_sample_instant(kb, tmp_path, monkeypatch):
    from app.demo import sample_seed
    from app.services import cache_service

    seed = {
        "image_sha256": "ab" * 32,
        "menu_id": ("ab" * 32)[:32],
        "restaurant_name": "The Kroft",
        "parsed_menu": {"detected_language": "English", "target_language": None,
                        "menu": [{"category": "Mains", "items": [{"name": "Classic", "price": 10.95}]}]},
        "combo_request": {"dishes": [{"name": "Classic", "description": None, "category": "Mains"},
                                     {"name": "French Dip", "description": None, "category": "Sandwiches"}],
                          "max_combos": 3, "restaurant_name": "The Kroft"},
        "combo_response": {"combos": [], "knowledge_available": True, "cuisine": "Seeded cuisine"},
    }
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(seed))
    assert sample_seed.load_seed(path) is True
    assert sample_seed.load_seed(tmp_path / "missing.json") is False

    row = cache_service.get_menu_parse("ab" * 32, None, settings.deepseek_model)
    assert row.id == seed["menu_id"] and row.restaurant_name == "The Kroft"

    def must_not_run(request):
        raise AssertionError("seeded combos should come from the cache")

    monkeypatch.setattr(knowledge_api, "compute_combos", must_not_run)
    app = FastAPI()
    app.include_router(knowledge_api.router, prefix="/api/v1/knowledge")
    response = TestClient(app).post("/api/v1/knowledge/combos", json=seed["combo_request"])
    assert response.json()["cuisine"] == "Seeded cuisine"
