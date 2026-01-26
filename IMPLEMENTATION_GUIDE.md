# RAG System Implementation Guide

## ✅ Completed So Far

### 1. Multi-Source Data Collection (Phase 1)
- ✅ **DuckDuckGo Collector** (`ddgs_collector.py`)
  - Web reviews from Yelp/TripAdvisor
  - Dish images via image search
  - Fully documented with examples

- ✅ **Yelp Collector** (`yelp_collector.py`)
  - Business search + details
  - Photos (up to 3)
  - Fault-tolerant (fails gracefully)
  - Detailed docstrings with input/output examples

- ✅ **Multi-Source Aggregator** (`multi_source_aggregator.py` - partially updated)
  - Parallel collection from 3 sources
  - Yelp integration added
  - Needs: Yelp data handling in `_aggregate_results`

- ✅ **Vector Store** (`vector_store.py`)
  - Sentence-transformers embeddings
  - Cosine similarity search
  - Lightweight model (80MB)

### 2. Dependencies
- ✅ Updated `pyproject.toml`
  - duckduckgo-search
  - sentence-transformers
  - numpy

## 🔄 Next Steps (In Order)

### Step 1: Complete Multi-Source Aggregator
Need to add Yelp handling in `_aggregate_results` method:

```python
# Handle Yelp data
elif source == "Yelp":
    business = data.get("business", {})
    photos = data.get("photos", [])

    # Add business rating as metadata
    if business:
        aggregated["place_info"] = aggregated["place_info"] or {}
        aggregated["place_info"]["yelp_rating"] = business.get("rating")
        aggregated["place_info"]["yelp_review_count"] = business.get("review_count")

    # Add photos
    for photo_url in photos:
        aggregated["images"].append({
            "url": photo_url,
            "source": "yelp",
            "type": "restaurant_photo"
        })
```

### Step 2: Enhance Menu OCR Prompt
Update `backend/app/services/vision_parser.py` to detect:
- Spicy level indicators (🌶️, *, "spicy", "hot")
- Allergen symbols (🥜 nuts, 🥛 dairy, 🌾 gluten)
- Dietary markers (V for vegan, GF for gluten-free)

Add to prompt:
```python
5. Detect special symbols and indicators:
   - spicy_level: Number of chili peppers or stars (0-5)
   - allergens: ["nuts", "dairy", "gluten", "shellfish", "soy", "eggs"]
   - dietary_tags: ["vegetarian", "vegan", "gluten-free", "halal", "kosher"]
```

### Step 3: Create RAG Engine
File: `backend/app/services/recommendation/rag_engine.py`

Key methods:
- `build_knowledge_base()` - Index all reviews + menu
- `extract_dish_mentions()` - Find dish names in reviews
- `recommend_dishes()` - Semantic search + ranking
- `get_dish_context()` - Get all info about a specific dish

### Step 4: Create Taste & Texture Predictor
File: `backend/app/services/recommendation/taste_texture_predictor.py`

Features:
- Round 1: Menu description → predictions
- Round 2: + Reviews → refined predictions
- Taxonomy: 10 taste attributes, 10 texture attributes
- Confidence scoring

### Step 5: Create Pydantic Models
File: `backend/app/models/recommendation.py`

Models needed:
- `RecommendationRequest`
- `RecommendationResponse`
- `TasteTextureRequest`
- `TasteTextureResponse`
- `DishRecommendation`

### Step 6: Create API Endpoints
File: `backend/app/api/v1/endpoints/recommendation.py`

Endpoints:
- `POST /api/v1/recommendation/build-knowledge-base`
- `POST /api/v1/recommendation/recommend`
- `POST /api/v1/recommendation/taste-texture`

### Step 7: Update main.py
Register recommendation router

### Step 8: Docker Rebuild
Rebuild containers with new dependencies

### Step 9: Testing
Create integration tests with real examples

## Code Standards (As Requested)

### 1. Detailed Comments
Every function/class must have:
- Description
- Args with types
- Returns with types
- Example usage with actual input/output

Example:
```python
def search_dishes(query: str, top_k: int = 5) -> List[Dict]:
    """Search for dishes using semantic similarity.

    Args:
        query: User query (e.g., "spicy noodles")
        top_k: Number of results to return (default 5)

    Returns:
        List of dish dictionaries sorted by relevance

    Example:
        >>> engine = RAGEngine()
        >>> results = engine.search_dishes("I want something spicy", top_k=3)
        >>> results[0]
        {
            'dish_name': 'Spicy Tonkatsu Ramen',
            'score': 0.92,
            'reasons': ['Mentioned in 8 reviews', 'Customers love the spicy broth']
        }

    Debug:
        # Uncomment to test
        # results = search_dishes("vegetarian options")
        # print(json.dumps(results, indent=2))
    """
```

### 2. Debug Examples
Include commented-out debugging code:
```python
# Debug Example 1: Test with real data
# if __name__ == "__main__":
#     collector = MultiSourceAggregator(
#         google_api_key=os.getenv("GOOGLE_PLACES_API_KEY"),
#         yelp_api_key=os.getenv("YELP_API_KEY")
#     )
#     result = await collector.collect_all_data(
#         "Tartine Bakery",
#         "San Francisco",
#         place_id="ChIJ..."
#     )
#     print(json.dumps(result, indent=2))
```

### 3. Type Hints
All functions must have complete type hints:
```python
from typing import List, Dict, Optional, Union

def process_reviews(
    reviews: List[Dict[str, str]],
    min_length: int = 10
) -> Dict[str, Union[int, List[str]]]:
    ...
```

## Testing Strategy

### Unit Tests
```python
# test_yelp_collector.py
def test_yelp_graceful_failure():
    collector = YelpCollector(None)  # No API key
    result = collector.collect_all("Any Restaurant", "Anywhere")
    assert result["success"] == False
    assert "error" in result
```

### Integration Tests
```python
# test_multi_source.py
async def test_fault_tolerance():
    # Test with invalid Google key, valid Yelp
    aggregator = MultiSourceAggregator(
        google_api_key="invalid",
        yelp_api_key=os.getenv("YELP_API_KEY")
    )
    result = await aggregator.collect_all_data(...)
    # Should succeed with Yelp + DDGS even if Google fails
    assert len(result["sources"]) >= 2
```

## Current File Structure

```
backend/app/
├── services/
│   ├── data_collection/
│   │   ├── __init__.py                     ✅ Created
│   │   ├── ddgs_collector.py               ✅ Created (with examples)
│   │   ├── yelp_collector.py               ✅ Created (with examples)
│   │   └── multi_source_aggregator.py      🔄 Partially updated
│   │
│   ├── recommendation/
│   │   ├── __init__.py                     ✅ Created
│   │   ├── vector_store.py                 ✅ Created
│   │   ├── rag_engine.py                   ⏳ TODO
│   │   └── taste_texture_predictor.py      ⏳ TODO
│   │
│   ├── vision_parser.py                    🔄 Needs OCR enhancement
│   └── (existing files)
│
├── models/
│   ├── recommendation.py                   ⏳ TODO
│   └── (existing files)
│
├── api/v1/endpoints/
│   ├── recommendation.py                   ⏳ TODO
│   └── (existing files)
│
└── main.py                                 🔄 Needs router registration
```

## Priority Order

1. **Finish Multi-Source Aggregator** - Add Yelp handling
2. **Enhance OCR Prompt** - Add spicy/allergen detection
3. **RAG Engine** - Core recommendation logic
4. **Taste Predictor** - Sensory attributes
5. **API Endpoints** - Expose functionality
6. **Testing** - Verify end-to-end

## Expected Results

After completion:
```
Input: "BCD Tofu House, Koreatown LA"

Output:
{
  "data_sources": ["Google Places", "DuckDuckGo", "Yelp"],
  "total_reviews": 27,
  "total_images": 23,
  "recommendations": [
    {
      "dish_name": "Soon Tofu Jjigae",
      "confidence": 0.94,
      "taste_texture": {
        "tastes": ["spicy", "savory", "umami"],
        "textures": ["soft", "silky"],
        "spicy_level": 3,
        "allergens": ["shellfish", "soy"]
      },
      "reasons": [
        "Mentioned in 12 reviews as must-try",
        "Customers love the spicy seafood broth"
      ]
    }
  ]
}
```

Ready to continue? I'll complete the remaining files with full documentation and examples.
