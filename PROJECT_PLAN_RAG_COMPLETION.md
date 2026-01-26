# Project Plan: RAG System Completion & Integration

**Project Manager**: Claude
**Project**: Multi-Source RAG Recommendation System
**Phase**: Implementation & Testing
**Last Updated**: 2026-01-25

---

## Executive Summary

This document outlines the detailed implementation plan for completing the RAG (Retrieval-Augmented Generation) recommendation system. The system will provide intelligent dish recommendations using data from multiple sources (Google Places, DuckDuckGo, Yelp) with advanced features like taste/texture prediction and allergen detection.

**Current Status**: ~60% Complete
**Estimated Completion Time**: 12-15 hours
**Priority**: High

---

## Table of Contents

1. [Completed Components](#completed-components)
2. [Remaining Implementation Tasks](#remaining-implementation-tasks)
3. [File-by-File Implementation Plan](#file-by-file-implementation-plan)
4. [Testing Strategy](#testing-strategy)
5. [Integration Steps](#integration-steps)
6. [Deployment Checklist](#deployment-checklist)
7. [Success Criteria](#success-criteria)

---

## Completed Components ✅

### 1. Data Collection Layer
- ✅ **DuckDuckGo Collector** (`ddgs_collector.py`)
  - Collects 20+ web review snippets
  - Fetches 10+ dish images
  - Fully documented with examples

- ✅ **Yelp Collector** (`yelp_collector.py`)
  - Business search and details
  - Up to 3 photos per restaurant
  - Fault-tolerant (graceful failures)

- ✅ **Multi-Source Aggregator** (`multi_source_aggregator.py`)
  - Parallel collection from 3 sources
  - Automatic deduplication
  - Comprehensive error handling

### 2. Enhanced Menu OCR
- ✅ **Vision Parser Updates** (`vision_parser.py`)
  - Detects spicy levels (🌶️ symbols, 0-5)
  - Detects allergens (nuts, dairy, gluten, etc.)
  - Detects dietary tags (vegetarian, vegan, GF)

- ✅ **MenuItem Model Updates** (`menu.py`)
  - New fields: `spicy_level`, `allergens`, `dietary_tags`
  - Validation constraints (spicy 0-5)

### 3. RAG Infrastructure
- ✅ **Vector Store** (`vector_store.py`)
  - Sentence-transformers embeddings
  - Cosine similarity search
  - Efficient in-memory storage

- ✅ **RAG Engine** (`rag_engine.py`)
  - Knowledge base builder
  - Dish recommendation logic
  - LLM-enhanced explanations

### 4. Dependencies
- ✅ Updated `pyproject.toml` with new packages

---

## Remaining Implementation Tasks

### Task Breakdown

| Task | Priority | Estimated Time | Dependencies |
|------|----------|----------------|--------------|
| 1. Taste & Texture Predictor | High | 3-4 hours | RAG Engine |
| 2. Pydantic Models | High | 1-2 hours | None |
| 3. API Endpoints | High | 2-3 hours | Models, RAG Engine, Predictor |
| 4. Configuration Updates | Medium | 30 min | None |
| 5. Main.py Router Registration | Medium | 15 min | API Endpoints |
| 6. Docker Configuration | Medium | 30 min | All dependencies |
| 7. Unit Tests | High | 3-4 hours | All components |
| 8. Integration Tests | High | 2-3 hours | Full system |
| 9. Documentation | Medium | 1-2 hours | All components |

**Total Estimated Time**: 12-15 hours

---

## File-by-File Implementation Plan

### 1. Taste & Texture Predictor

**File**: `backend/app/services/recommendation/taste_texture_predictor.py`

#### Purpose
Predict sensory attributes (taste, texture) of dishes using a two-round approach:
- Round 1: Based on menu description
- Round 2: Refined with customer review data

#### Key Requirements

**Input Specifications**:
```python
# Round 1 Input
{
    "dish_name": "Soon Tofu Jjigae",
    "description": "Spicy soft tofu stew with seafood and vegetables"
}

# Round 2 Input (additional)
{
    "review_excerpts": [
        "The tofu was incredibly silky and the broth was rich",
        "Perfect level of spice, not too overwhelming",
        "Seafood was fresh and tender"
    ]
}
```

**Output Specifications**:
```python
# Round 1 Output
{
    "tastes": ["spicy", "savory", "umami"],
    "textures": ["soft", "silky"],
    "flavor_profile": "Rich and complex with moderate heat",
    "confidence": 0.72,
    "round": 1
}

# Round 2 Output (refined)
{
    "tastes": ["spicy", "savory", "umami", "rich"],
    "textures": ["soft", "silky", "tender"],
    "flavor_profile": "Rich umami broth with perfect spice balance and silky tofu texture",
    "confidence": 0.89,
    "round": 2,
    "changes_from_round1": [
        "Added 'rich' based on review mentions",
        "Added 'tender' for seafood texture",
        "Increased confidence from 0.72 to 0.89"
    ]
}
```

#### Implementation Details

**Required Methods**:

1. `__init__(self, api_key: str)`:
   - Initialize Gemini client
   - Define taste/texture taxonomies

2. `predict_round1(self, dish_name: str, description: str) -> Dict`:
   - Build prompt with menu description
   - Call Gemini with structured output format
   - Parse and validate JSON response
   - Return prediction with confidence score

3. `predict_round2(self, dish_name: str, description: str, review_excerpts: List[str], round1_prediction: Dict) -> Dict`:
   - Build prompt including round 1 results + reviews
   - Ask Gemini to refine predictions based on real customer feedback
   - Parse and validate enhanced prediction
   - Calculate improvement metrics

4. `_build_round1_prompt(self, dish_name: str, description: str) -> str`:
   - Template for round 1 prediction
   - Include taste/texture taxonomies
   - Specify JSON output format

5. `_build_round2_prompt(self, dish_name: str, description: str, reviews: List[str], round1: Dict) -> str`:
   - Template for round 2 refinement
   - Include round 1 results
   - Add review excerpts
   - Ask for comparison and improvements

6. `_parse_prediction(self, response_text: str) -> Dict`:
   - Extract JSON from Gemini response
   - Handle markdown code blocks
   - Validate against schema
   - Provide fallback on parse failure

**Taxonomies** (Predefined Lists):

```python
TASTE_ATTRIBUTES = [
    "sweet", "salty", "sour", "bitter", "umami",
    "spicy", "savory", "mild", "rich", "light",
    "smoky", "tangy", "aromatic", "fresh", "creamy"
]

TEXTURE_ATTRIBUTES = [
    "crispy", "crunchy", "tender", "soft", "chewy",
    "juicy", "creamy", "flaky", "smooth", "firm",
    "silky", "fluffy", "sticky", "moist", "delicate"
]
```

**Error Handling**:
- Handle Gemini API failures gracefully
- Provide default predictions if LLM fails
- Validate all outputs against schema
- Log errors with context for debugging

**Documentation Requirements**:
- Detailed docstrings for each method
- Input/output examples with actual dish data
- Commented debug/test code
- Edge case handling notes

---

### 2. Pydantic Models

**File**: `backend/app/models/recommendation.py`

#### Purpose
Define data models for API requests/responses related to recommendations.

#### Required Models

**2.1 BuildKnowledgeBaseRequest**
```python
class BuildKnowledgeBaseRequest(BaseModel):
    restaurant_name: str = Field(..., example="BCD Tofu House")
    location: str = Field(..., example="Koreatown Los Angeles")
    place_id: Optional[str] = Field(None, example="ChIJobNa...")
    parsed_menu: Optional[Dict] = Field(None)

    # Documentation with example
    class Config:
        schema_extra = {
            "example": {
                "restaurant_name": "Tartine Bakery",
                "location": "San Francisco",
                "place_id": "ChIJ...",
                "parsed_menu": {...}
            }
        }
```

**2.2 BuildKnowledgeBaseResponse**
```python
class BuildKnowledgeBaseResponse(BaseModel):
    status: str = Field(..., example="success")
    total_documents: int
    menu_items: int
    review_mentions: int
    unique_dishes: int
    sources: List[str]
    successful_sources: int
    failed_sources: List[Dict]
    build_time_seconds: float
```

**2.3 RecommendationRequest**
```python
class RecommendationRequest(BaseModel):
    restaurant_name: str
    location: str
    user_preferences: str = Field(..., example="I want something spicy")
    top_k: int = Field(5, ge=1, le=20)
    use_llm_enhancement: bool = True
    filter_allergens: Optional[List[str]] = None
    filter_dietary: Optional[List[str]] = None
```

**2.4 DishRecommendation**
```python
class DishRecommendation(BaseModel):
    dish_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasons: List[str]
    review_count: int
    data_sources: List[str]
    metadata: Dict = Field(default_factory=dict)
    taste_texture: Optional[Dict] = None
```

**2.5 RecommendationResponse**
```python
class RecommendationResponse(BaseModel):
    query: str
    recommendations: List[DishRecommendation]
    total_dishes_analyzed: int
    search_time_seconds: float
```

**2.6 TasteTextureRequest**
```python
class TasteTextureRequest(BaseModel):
    dish_name: str
    description: str
    include_reviews: bool = True
    review_excerpts: Optional[List[str]] = None
```

**2.7 TasteTextureResponse**
```python
class TasteTextureResponse(BaseModel):
    dish_name: str
    round1: Dict
    round2: Optional[Dict] = None
    improvement_score: Optional[float] = None
    processing_time_seconds: float
```

#### Implementation Notes
- All models need comprehensive docstrings
- Include `Config` with schema examples
- Add validation constraints where appropriate
- Use Field descriptions for API docs

---

### 3. API Endpoints

**File**: `backend/app/api/v1/endpoints/recommendation.py`

#### Purpose
Expose RAG functionality via REST API endpoints.

#### Endpoints to Implement

**3.1 POST /api/v1/recommendation/build-knowledge-base**

**Purpose**: Build or rebuild knowledge base for a restaurant

**Request Body**: `BuildKnowledgeBaseRequest`

**Response**: `BuildKnowledgeBaseResponse`

**Implementation Steps**:
1. Validate request (restaurant_name, location required)
2. Initialize RAG engine with API keys from settings
3. Call `engine.build_knowledge_base()`
4. Track timing metrics
5. Return stats with success/failure info

**Error Handling**:
- 400: Invalid request (missing fields)
- 500: API key not configured
- 500: Collection failed from all sources
- 503: Gemini API unavailable

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/recommendation/build-knowledge-base" \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "BCD Tofu House",
    "location": "Koreatown Los Angeles"
  }'
```

---

**3.2 POST /api/v1/recommendation/recommend**

**Purpose**: Get dish recommendations based on user preferences

**Request Body**: `RecommendationRequest`

**Response**: `RecommendationResponse`

**Implementation Steps**:
1. Validate request
2. Check if knowledge base exists for this restaurant (or build it)
3. Call `engine.recommend_dishes()`
4. Optionally filter by allergens/dietary preferences
5. Optionally add taste/texture predictions to each recommendation
6. Track timing
7. Return recommendations

**Query Parameters**:
- `include_taste_texture`: bool (add taste/texture to each dish)

**Error Handling**:
- 400: Invalid request
- 404: Restaurant not found in knowledge base
- 500: Recommendation generation failed

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/recommendation/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "BCD Tofu House",
    "location": "Koreatown LA",
    "user_preferences": "spicy Korean soup",
    "top_k": 5,
    "filter_allergens": ["nuts"],
    "filter_dietary": ["gluten-free"]
  }'
```

---

**3.3 POST /api/v1/recommendation/taste-texture**

**Purpose**: Predict taste and texture for a specific dish

**Request Body**: `TasteTextureRequest`

**Response**: `TasteTextureResponse`

**Implementation Steps**:
1. Validate request (dish_name, description required)
2. Initialize taste/texture predictor
3. Call `predict_round1()`
4. If `include_reviews=True`, get reviews from RAG engine
5. Call `predict_round2()` with reviews
6. Calculate improvement metrics
7. Return both rounds with comparison

**Error Handling**:
- 400: Missing required fields
- 500: Gemini API failure
- 500: Invalid prediction format

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/recommendation/taste-texture" \
  -H "Content-Type: application/json" \
  -d '{
    "dish_name": "Soon Tofu Jjigae",
    "description": "Spicy soft tofu stew with seafood",
    "include_reviews": true
  }'
```

---

**3.4 GET /api/v1/recommendation/dish/{dish_name}**

**Purpose**: Get all available context about a specific dish

**Path Parameter**: `dish_name` (URL-encoded)

**Query Parameters**:
- `restaurant_name`: str (required)
- `location`: str (required)

**Response**:
```python
{
    "dish_name": "Soon Tofu Jjigae",
    "menu_description": "...",
    "review_count": 12,
    "review_excerpts": [...],
    "metadata": {...},
    "is_popular": true,
    "taste_texture": {...}
}
```

**Example**:
```bash
curl "http://localhost:8000/api/v1/recommendation/dish/Soon%20Tofu%20Jjigae?restaurant_name=BCD%20Tofu%20House&location=Koreatown"
```

---

#### General API Requirements

**All endpoints must**:
- Include detailed docstrings
- Log all requests/responses
- Track timing metrics
- Handle errors gracefully
- Return proper HTTP status codes
- Include CORS headers (already configured)

**Logging Format**:
```python
logger.info(f"[Endpoint] Action - restaurant: {name}, user: {user_id}, duration: {elapsed}s")
```

---

### 4. Configuration Updates

**Files to Update**:

**4.1 `backend/app/core/config.py`**

**Changes Needed**:
```python
class Settings(BaseSettings):
    # Existing fields...
    gemini_api_key: str
    google_places_api_key: Optional[str] = None

    # ADD THIS:
    yelp_api_key: Optional[str] = None

    # RAG-specific settings (optional, with defaults)
    rag_embedding_model: str = "all-MiniLM-L6-v2"
    rag_top_k_default: int = 5
    rag_use_llm_enhancement: bool = True
```

**4.2 `.env.example`**

**Add Documentation**:
```bash
# Yelp Fusion API Configuration (OPTIONAL)
# Get your API key from: https://www.yelp.com/developers/v3/manage_app
# Note: Works for some restaurants, fails for others (expected behavior)
# Free tier: 500 API calls per day
YELP_API_KEY=your_yelp_api_key_here
```

---

### 5. Main.py Router Registration

**File**: `backend/app/main.py`

**Changes Needed**:

```python
# Add import
from app.api.v1.endpoints import restaurant, google_places, recommendation

# Add router registration (after existing routers)
app.include_router(
    recommendation.router,
    prefix="/api/v1/recommendation",
    tags=["recommendation"]
)
```

**Verification**:
- Check `/docs` endpoint shows new routes
- Verify tags are correct
- Test route registration doesn't break existing routes

---

### 6. Docker Configuration

**File**: `docker-compose.yml`

**Changes Needed**:

```yaml
backend:
  environment:
    - GEMINI_API_KEY=${GEMINI_API_KEY}
    - GOOGLE_PLACES_API_KEY=${GOOGLE_PLACES_API_KEY}
    - YELP_API_KEY=${YELP_API_KEY}  # ADD THIS LINE
    - FIRESTORE_EMULATOR_HOST=firestore:8080
```

**Rebuild Steps**:
```bash
# Stop containers
docker compose down

# Rebuild with new dependencies
docker compose build --no-cache

# Start
docker compose up -d

# Verify
docker compose logs backend | grep "sentence-transformers"
```

**Expected Output**:
- Should see sentence-transformers loading
- Should see "all-MiniLM-L6-v2" model download on first run
- No errors about missing packages

---

## Testing Strategy

### Unit Tests

**Location**: `backend/tests/`

#### Test Files to Create

**1. `test_yelp_collector.py`**

**Test Cases**:
```python
def test_yelp_collector_with_valid_key():
    """Test Yelp collector with valid API key"""
    # Should return business data

def test_yelp_collector_without_key():
    """Test graceful failure without API key"""
    # Should return success=False

def test_yelp_collector_restaurant_not_found():
    """Test when restaurant doesn't exist"""
    # Should return success=False with error message

def test_yelp_collector_network_error():
    """Test network failure handling"""
    # Mock requests to raise exception
    # Should return success=False
```

---

**2. `test_multi_source_aggregator.py`**

**Test Cases**:
```python
@pytest.mark.asyncio
async def test_aggregator_all_sources_success():
    """Test when all sources return data"""
    # Should combine data from Google + DDGS + Yelp
    # Should have 3 sources in result

@pytest.mark.asyncio
async def test_aggregator_partial_failure():
    """Test when some sources fail"""
    # Mock Google to fail, DDGS + Yelp succeed
    # Should still return data from 2 sources
    # Should log failures

@pytest.mark.asyncio
async def test_aggregator_deduplication():
    """Test review/image deduplication"""
    # Create duplicate reviews
    # Should remove duplicates

@pytest.mark.asyncio
async def test_aggregator_empty_results():
    """Test when all sources return empty"""
    # Should return structure with empty lists
    # Should not crash
```

---

**3. `test_vector_store.py`**

**Test Cases**:
```python
def test_vector_store_add_documents():
    """Test adding documents creates embeddings"""
    store = VectorStore()
    docs = [{"text": "spicy ramen", "dish": "Ramen", "metadata": {}}]
    store.add_documents(docs)
    assert store.embeddings is not None
    assert len(store.documents) == 1

def test_vector_store_search():
    """Test semantic search returns relevant results"""
    # Add documents about various dishes
    # Search for "spicy noodles"
    # Should return ramen, not salad

def test_vector_store_filter_by_dish():
    """Test filtering search results by dish name"""
    # Search with filter_dish parameter
    # Should only return that specific dish

def test_vector_store_empty_search():
    """Test search on empty store"""
    # Should return empty list, not crash
```

---

**4. `test_rag_engine.py`**

**Test Cases**:
```python
@pytest.mark.asyncio
async def test_rag_build_knowledge_base():
    """Test building knowledge base from menu + reviews"""
    # Should create documents
    # Should build embeddings
    # Should return stats

@pytest.mark.asyncio
async def test_rag_build_without_menu():
    """Test building with only reviews (no menu)"""
    # Should still work with review-only data

def test_rag_recommend_before_build():
    """Test recommendation fails if KB not built"""
    # Should raise ValueError

def test_rag_recommend_dishes():
    """Test getting recommendations"""
    # Build KB first
    # Search for "spicy"
    # Should return spicy dishes ranked by relevance

def test_rag_extract_dish_mentions():
    """Test dish mention extraction from reviews"""
    dishes = ["Ramen", "Gyoza"]
    text = "The ramen was amazing!"
    mentions = engine._extract_dish_mentions(text, dishes)
    assert "Ramen" in mentions

def test_rag_get_dish_context():
    """Test retrieving context for specific dish"""
    # Should return menu description + reviews
```

---

**5. `test_taste_texture_predictor.py`**

**Test Cases**:
```python
@pytest.mark.asyncio
async def test_predict_round1():
    """Test round 1 prediction from description"""
    result = await predictor.predict_round1(
        "Spicy Ramen",
        "Hot noodles in spicy broth"
    )
    assert "spicy" in result["tastes"]
    assert result["round"] == 1

@pytest.mark.asyncio
async def test_predict_round2_improves_confidence():
    """Test round 2 increases confidence"""
    round1 = await predictor.predict_round1(...)
    round2 = await predictor.predict_round2(..., round1)
    assert round2["confidence"] >= round1["confidence"]

@pytest.mark.asyncio
async def test_predict_invalid_response():
    """Test handling of invalid LLM response"""
    # Mock Gemini to return invalid JSON
    # Should return fallback prediction

def test_parse_prediction_with_markdown():
    """Test parsing JSON from markdown code blocks"""
    # Should handle ```json ... ```
```

---

**6. `test_recommendation_api.py`**

**Test Cases**:
```python
@pytest.mark.asyncio
async def test_build_kb_endpoint(client):
    """Test /build-knowledge-base endpoint"""
    response = await client.post(
        "/api/v1/recommendation/build-knowledge-base",
        json={"restaurant_name": "Test", "location": "SF"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_recommend_endpoint(client):
    """Test /recommend endpoint"""
    # Build KB first, then get recommendations

@pytest.mark.asyncio
async def test_taste_texture_endpoint(client):
    """Test /taste-texture endpoint"""
    response = await client.post(
        "/api/v1/recommendation/taste-texture",
        json={
            "dish_name": "Ramen",
            "description": "Spicy noodles",
            "include_reviews": False
        }
    )
    assert response.status_code == 200

async def test_endpoint_missing_api_key(client):
    """Test endpoints fail gracefully without API keys"""
    # Mock settings with no keys
    # Should return 500 with clear error message
```

---

### Integration Tests

**Location**: `backend/tests/integration/`

#### Test Files to Create

**1. `test_end_to_end_workflow.py`**

**Test Scenario**:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_recommendation_workflow():
    """
    End-to-end test of complete RAG workflow:
    1. Collect data from all sources
    2. Build knowledge base
    3. Get recommendations
    4. Predict taste/texture
    5. Verify results
    """
    # Use real API keys from env
    # Use a well-known restaurant (e.g., Tartine Bakery SF)
    # Verify:
    # - At least 2 sources succeed
    # - KB has documents
    # - Recommendations are relevant
    # - Taste predictions are reasonable
```

**2. `test_multi_source_resilience.py`**

**Test Scenario**:
```python
@pytest.mark.integration
async def test_system_works_with_one_source():
    """Test system works even if 2/3 sources fail"""
    # Provide invalid keys for 2 sources
    # Should still work with 1 source

async def test_system_handles_all_failures():
    """Test graceful degradation when all sources fail"""
    # All invalid keys
    # Should return meaningful error, not crash
```

---

### Manual Testing Checklist

**Test Plan**: `backend/tests/MANUAL_TEST_PLAN.md`

```markdown
# Manual Testing Checklist

## Prerequisites
- [ ] All API keys configured in .env
- [ ] Docker containers running
- [ ] Can access http://localhost:8000/docs

## Test 1: Build Knowledge Base
- [ ] Go to /docs
- [ ] Find /api/v1/recommendation/build-knowledge-base
- [ ] Input: BCD Tofu House, Koreatown LA
- [ ] Click Execute
- [ ] Verify: Returns 200 with stats
- [ ] Verify: total_documents > 50
- [ ] Verify: At least 2 sources succeeded

## Test 2: Get Recommendations
- [ ] Find /api/v1/recommendation/recommend
- [ ] Input: "spicy Korean soup"
- [ ] Click Execute
- [ ] Verify: Returns 5 recommendations
- [ ] Verify: Top result has confidence > 0.7
- [ ] Verify: Reasons are meaningful

## Test 3: Taste & Texture Prediction
- [ ] Find /api/v1/recommendation/taste-texture
- [ ] Input: Soon Tofu Jjigae, "Spicy soft tofu stew"
- [ ] Set include_reviews: true
- [ ] Verify: Round 2 confidence > Round 1
- [ ] Verify: Tastes include "spicy"

## Test 4: Enhanced Menu OCR
- [ ] Use /api/v1/menu/parse
- [ ] Upload menu with spicy symbols (🌶️🌶️🌶️)
- [ ] Verify: spicy_level = 3
- [ ] Upload menu with allergen text
- [ ] Verify: allergens list populated

## Test 5: Error Handling
- [ ] Call /recommend without building KB first
- [ ] Verify: 404 or clear error message
- [ ] Call with invalid restaurant name
- [ ] Verify: Graceful error response
```

---

## Integration Steps

### Step 1: Install Dependencies in Docker

```bash
# 1. Rebuild backend container
cd /path/to/menu-ai-app
docker compose down
docker compose build backend --no-cache

# 2. Verify installation
docker compose run backend python -c "import sentence_transformers; print('OK')"

# Expected: "OK" (no errors)
```

---

### Step 2: Environment Configuration

```bash
# 1. Update .env file
echo "YELP_API_KEY=your_yelp_key_here" >> .env

# 2. Verify all keys present
grep -E "GEMINI|GOOGLE_PLACES|YELP" .env

# Expected output:
# GEMINI_API_KEY=AIza...
# GOOGLE_PLACES_API_KEY=AIza...
# YELP_API_KEY=abc...
```

---

### Step 3: Test Imports

Create `backend/test_imports.py`:
```python
#!/usr/bin/env python3
"""Test that all new modules can be imported."""

if __name__ == "__main__":
    try:
        from app.services.data_collection.yelp_collector import YelpCollector
        print("✓ YelpCollector")

        from app.services.data_collection.multi_source_aggregator import MultiSourceAggregator
        print("✓ MultiSourceAggregator")

        from app.services.recommendation.vector_store import VectorStore
        print("✓ VectorStore")

        from app.services.recommendation.rag_engine import RAGRecommendationEngine
        print("✓ RAGRecommendationEngine")

        from app.services.recommendation.taste_texture_predictor import TasteTexturePredictor
        print("✓ TasteTexturePredictor")

        from app.models.recommendation import (
            BuildKnowledgeBaseRequest,
            RecommendationRequest,
            TasteTextureRequest
        )
        print("✓ Recommendation Models")

        from app.api.v1.endpoints.recommendation import router
        print("✓ Recommendation Router")

        print("\n✅ All imports successful!")

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
```

Run:
```bash
docker compose run backend python test_imports.py
```

---

### Step 4: Start Services

```bash
# 1. Start all services
docker compose up -d

# 2. Check logs
docker compose logs -f backend

# 3. Verify API docs
curl http://localhost:8000/docs
# Should return HTML (Swagger UI)

# 4. Check new endpoints
curl http://localhost:8000/openapi.json | grep recommendation
# Should see new recommendation endpoints
```

---

### Step 5: Smoke Test

Create `backend/smoke_test.py`:
```python
#!/usr/bin/env python3
"""Smoke test for RAG system."""

import asyncio
import os
import sys

async def main():
    from app.services.recommendation.rag_engine import RAGRecommendationEngine

    print("🔥 RAG System Smoke Test\n")

    # Check API keys
    keys = {
        "GEMINI": os.getenv("GEMINI_API_KEY"),
        "GOOGLE_PLACES": os.getenv("GOOGLE_PLACES_API_KEY"),
        "YELP": os.getenv("YELP_API_KEY")
    }

    for name, key in keys.items():
        status = "✓" if key else "✗"
        print(f"{status} {name}_API_KEY: {'set' if key else 'NOT SET'}")

    if not keys["GEMINI"]:
        print("\n❌ GEMINI_API_KEY required!")
        sys.exit(1)

    # Test RAG engine
    print("\n📊 Testing RAG Engine...")
    engine = RAGRecommendationEngine(
        gemini_api_key=keys["GEMINI"],
        google_places_api_key=keys["GOOGLE_PLACES"],
        yelp_api_key=keys["YELP"]
    )

    # Build KB (with a well-known restaurant)
    print("Building knowledge base...")
    stats = await engine.build_knowledge_base(
        restaurant_name="Tartine Bakery",
        location="San Francisco",
        place_id="ChIJoR6f5PmAhYARg0b8wfLo2DY"  # Real Place ID
    )

    print(f"✓ Built KB: {stats['total_documents']} documents")
    print(f"  Sources: {', '.join(stats['sources'])}")

    # Test recommendations
    print("\nGetting recommendations...")
    recs = engine.recommend_dishes("bread pastries", top_k=3)

    print(f"✓ Got {len(recs)} recommendations:")
    for i, rec in enumerate(recs, 1):
        print(f"  {i}. {rec['dish_name']} (confidence: {rec['confidence']:.2f})")

    print("\n✅ Smoke test passed!\n")

if __name__ == "__main__":
    asyncio.run(main())
```

Run:
```bash
docker compose run backend python smoke_test.py
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Manual tests completed
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] API docs generated and accurate
- [ ] Environment variables documented

### Deployment Steps

1. **Backup Current State**
   ```bash
   git commit -am "Pre-deployment checkpoint"
   git tag v1.0-pre-rag
   ```

2. **Deploy to Staging**
   ```bash
   # Pull latest code
   git pull origin frontend_ui

   # Rebuild containers
   docker compose -f docker-compose.staging.yml build
   docker compose -f docker-compose.staging.yml up -d

   # Run smoke test
   docker compose -f docker-compose.staging.yml run backend python smoke_test.py
   ```

3. **Monitor Logs**
   ```bash
   docker compose logs -f backend | grep -E "ERROR|WARNING|recommendation"
   ```

4. **Deploy to Production**
   ```bash
   # Same steps as staging
   # Add health checks
   # Monitor metrics
   ```

### Post-Deployment

- [ ] Health check endpoint responding
- [ ] API endpoints accessible
- [ ] No errors in logs for 1 hour
- [ ] Test with real users
- [ ] Monitor API usage/costs
- [ ] Set up alerts for failures

---

## Success Criteria

### Functional Requirements

1. **Multi-Source Data Collection**
   - ✅ Collects from at least 2/3 sources for 90% of restaurants
   - ✅ Gracefully handles source failures
   - ✅ Returns 20+ reviews combined

2. **Enhanced Menu OCR**
   - ✅ Detects spicy levels with 80% accuracy
   - ✅ Detects allergens when present
   - ✅ Detects dietary tags when present

3. **RAG Recommendations**
   - ✅ Returns relevant recommendations (top result confidence > 0.7)
   - ✅ Provides meaningful explanations
   - ✅ Responds within 5 seconds

4. **Taste & Texture Prediction**
   - ✅ Round 1 completes successfully
   - ✅ Round 2 improves confidence by 10%+
   - ✅ Predictions align with menu descriptions

### Non-Functional Requirements

1. **Performance**
   - Knowledge base build: < 15 seconds
   - Recommendations: < 3 seconds
   - Taste prediction: < 5 seconds

2. **Reliability**
   - 99% uptime
   - Graceful degradation on failures
   - No data loss

3. **Code Quality**
   - 80%+ test coverage
   - All functions documented
   - No critical security issues

4. **Cost**
   - < $0.50 per restaurant lookup
   - Within free tier limits for development

---

## Risk Management

### Identified Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Gemini API rate limits | High | Medium | Implement caching, retry logic |
| Some sources always fail | Medium | High | Accept partial data, don't fail completely |
| Sentence-transformers model too large | Medium | Low | Use smaller model, lazy loading |
| LLM predictions inaccurate | Medium | Medium | Validate with ground truth, add confidence scores |
| Docker build timeout | Low | Medium | Optimize Dockerfile, cache layers |

### Monitoring Plan

**Metrics to Track**:
- API response times (p50, p95, p99)
- Error rates per endpoint
- Source success/failure rates
- Knowledge base build times
- LLM token usage
- Cache hit rates

**Alerts**:
- Error rate > 5%
- Response time > 10 seconds
- All sources failing
- API costs > $10/day

---

## Timeline

### Week 1: Core Implementation
- **Day 1-2**: Taste & Texture Predictor
- **Day 2-3**: Pydantic Models + API Endpoints
- **Day 3-4**: Configuration + Integration
- **Day 4-5**: Unit Tests

### Week 2: Testing & Deployment
- **Day 1-2**: Integration Tests
- **Day 2-3**: Manual Testing + Bug Fixes
- **Day 3-4**: Documentation
- **Day 4-5**: Staging Deployment
- **Day 5**: Production Deployment

---

## Next Actions

### Immediate (Developer)
1. Implement `taste_texture_predictor.py`
2. Implement `models/recommendation.py`
3. Implement `api/v1/endpoints/recommendation.py`
4. Update configuration files
5. Write unit tests

### Code Review Checkpoints
- After each major component (predictor, models, API)
- Before integration
- Before deployment

### Project Manager Reviews
- Daily: Progress check
- After each checkpoint: Code quality review
- Weekly: Timeline adjustment

---

## Appendix

### A. Code Style Guidelines

**Docstring Format**:
```python
def function_name(arg1: Type1, arg2: Type2) -> ReturnType:
    """Brief description.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Example:
        >>> result = function_name("value1", 42)
        >>> print(result)
        Expected output

    Raises:
        ValueError: When arg1 is invalid
    """
```

**Testing Format**:
```python
def test_specific_behavior():
    """Test that specific behavior works correctly."""
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result.property == expected_value
    assert len(result.items) > 0
```

### B. Useful Commands

```bash
# Run specific test
pytest backend/tests/test_rag_engine.py::test_specific -v

# Run with coverage
pytest --cov=app --cov-report=html

# Type checking
mypy backend/app

# Lint
ruff check backend/app

# Format
black backend/app
```

### C. References

- LangChain RAG Patterns: https://python.langchain.com/docs/tutorials/rag/
- Sentence-Transformers: https://www.sbert.net/
- Gemini API: https://ai.google.dev/docs
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/

---

**End of Plan**

This plan will be updated as implementation progresses. All changes should be tracked in git with clear commit messages.
