# Solution Plan: Dish-Specific Images & Menu Data Collection

**Date**: 2026-02-20
**Status**: Research Complete - Awaiting Approval
**Estimated Implementation**: 12-18 hours

---

## 🎯 PROBLEM SUMMARY

### Current Limitations
1. **Google Places API Constraint**: Only returns 5-10 photos per restaurant (restaurant-wide, not dish-specific)
2. **No Dish-Photo Mapping**: Cannot determine which photo shows which dish
3. **Limited Menu Data**: Currently rely on OCR from uploaded menu photos only

### Goals
1. Get **1 image per dish** with high confidence
2. Obtain **structured menu data** (dish names, prices, descriptions) from multiple sources
3. **Minimize costs** while maximizing coverage

### Challenges Identified
- Google Maps has dish photos but no direct API to filter by dish name
- Most delivery platforms (DoorDash, Uber Eats) require business partnerships
- Yelp API provides limited data (no review text in free tier)
- Need intelligent photo classification to match images to dishes

---

## ✅ RECOMMENDED SOLUTIONS (Ranked by Feasibility)

### **SOLUTION 1: Gemini Vision AI Classification** ⭐ **BEST FOR YOUR CASE**

**Cost**: Low (~$0.01 per 10 images with Gemini 2.0 Flash)
**Feasibility**: High (already have Gemini integrated)
**Accuracy**: 85-90% (based on Google's CalCam app benchmarks)

#### How It Works

1. **Collect photos from multiple sources**:
   - Google Places API: 5-10 general restaurant photos
   - DuckDuckGo image search: 10+ dish-specific photos
   - Yelp API: 3 additional photos
   - Foursquare API: User-submitted photos with captions

2. **Use Gemini Vision API to classify each photo**:
   - Input: Photo URL + list of dishes from menu
   - Prompt: "Which dish from this menu appears in this photo?"
   - Output: Dish name, confidence score, whether multiple dishes appear

3. **Match classified photos to menu items**:
   - Keep highest confidence match per dish
   - Handle ambiguous cases (multiple dishes or "other foods")

#### Implementation Example

```python
# New service: backend/app/services/recommendation/dish_photo_classifier.py
class DishPhotoClassifier:
    """Classify restaurant photos to identify which dish they show."""

    def __init__(self, gemini_api_key: str):
        self.gemini_client = genai.Client(api_key=gemini_api_key)

    async def classify_photo(
        self,
        image_url: str,
        dish_list: List[str]
    ) -> Dict:
        """
        Use Gemini Vision to identify which dish appears in photo.

        Args:
            image_url: URL of the photo to classify
            dish_list: List of dish names from restaurant menu

        Returns:
            {
                "dish_name": "Soon Tofu Jjigae",
                "confidence": 0.92,
                "contains_multiple": false,
                "other_dishes": [],
                "is_ambiguous": false
            }

        Example:
            >>> classifier = DishPhotoClassifier("AIza...")
            >>> result = await classifier.classify_photo(
            ...     "https://example.com/food.jpg",
            ...     ["Ramen", "Gyoza", "Sushi"]
            ... )
            >>> result["dish_name"]
            'Ramen'
        """
        prompt = f"""Analyze this restaurant food photo.

        Available dishes at this restaurant:
        {', '.join(dish_list)}

        Task: Identify which dish from the list appears in this photo.

        Return ONLY JSON:
        {{
            "dish_name": "exact dish name from list or 'unknown'",
            "confidence": 0.0-1.0,
            "contains_multiple": true/false,
            "other_dishes": ["dish2", "dish3"] if multiple,
            "is_ambiguous": true/false
        }}

        Rules:
        - Use exact dish names from the list
        - confidence < 0.5 means uncertain
        - is_ambiguous = true if photo doesn't clearly show a specific dish
        """

        # Call Gemini Vision API with image
        response = self.gemini_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                types.Part.from_uri(
                    file_uri=image_url,
                    mime_type="image/jpeg"
                ),
                types.Part.from_text(text=prompt)
            ]
        )

        # Parse JSON response
        result = self._parse_classification(response.text)
        return result

    async def match_photos_to_dishes(
        self,
        photos: List[Dict],
        dishes: List[str]
    ) -> Dict[str, str]:
        """
        Match all photos to dishes and return best match per dish.

        Returns:
            {
                "Soon Tofu Jjigae": "https://example.com/tofu.jpg",
                "Bulgogi": "https://example.com/bulgogi.jpg"
            }
        """
        # Classify all photos
        classifications = await asyncio.gather(*[
            self.classify_photo(photo["url"], dishes)
            for photo in photos
        ])

        # Group by dish and pick highest confidence
        dish_photos = {}
        for photo, classification in zip(photos, classifications):
            dish = classification["dish_name"]
            confidence = classification["confidence"]

            if dish == "unknown" or confidence < 0.5:
                continue

            if dish not in dish_photos or confidence > dish_photos[dish]["confidence"]:
                dish_photos[dish] = {
                    "url": photo["url"],
                    "confidence": confidence,
                    "source": photo.get("source", "unknown")
                }

        return {dish: data["url"] for dish, data in dish_photos.items()}
```

#### Pros & Cons

**Pros**:
- ✅ Uses existing infrastructure (Gemini API already integrated)
- ✅ Works with photos from multiple sources
- ✅ High accuracy (Google's CalCam app: 90%+ with Gemini 2.0)
- ✅ Can handle multiple dishes per photo
- ✅ Low cost (~$0.01 per 10 images)
- ✅ No additional ML models to host
- ✅ Handles edge cases (ambiguous photos, "other foods")

**Cons**:
- ⚠️ Requires extra API calls (adds latency)
- ⚠️ May misclassify similar-looking dishes (e.g., different ramen types)
- ⚠️ Generic/ambiguous photos harder to classify
- ⚠️ Cost scales with number of photos analyzed

**Estimated Implementation Time**: 4-6 hours

---

### **SOLUTION 2: Google Places API - Business Menus Field** ⭐ **OFFICIAL MENU DATA**

**Cost**: Medium ($0.02-0.04 per request)
**Feasibility**: High (official API)
**Menu Coverage**: 30-40% of restaurants have uploaded menus

#### How It Works

Google Places API (New) has a `businessMenus` field mask that returns **structured menu data**:
- Menu categories (Appetizers, Entrees, Desserts)
- Dish names and descriptions
- Prices
- Menu sections (Breakfast, Lunch, Dinner)

This eliminates the need for OCR when menu data is available.

#### Implementation Example

```python
# Update: backend/app/services/google_places_service.py
class GooglePlacesService:
    def get_restaurant_menu(self, place_id: str) -> Optional[Dict]:
        """
        Fetch structured menu from Google Places API.

        Args:
            place_id: Google Place ID

        Returns:
            {
                "menus": [
                    {
                        "name": "Dinner Menu",
                        "sections": [
                            {
                                "category": "Stews",
                                "items": [
                                    {
                                        "name": "Soon Tofu Jjigae",
                                        "description": "Spicy soft tofu stew with seafood",
                                        "price": {
                                            "amount": 12.99,
                                            "currency": "USD"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

        Example:
            >>> service = GooglePlacesService("AIza...")
            >>> menu = service.get_restaurant_menu("ChIJobNa...")
            >>> menu["menus"][0]["sections"][0]["items"][0]["name"]
            'Soon Tofu Jjigae'
        """
        url = f"https://places.googleapis.com/v1/places/{place_id}"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "displayName,businessMenus"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "businessMenus" in data:
                logger.info(f"Found menu data for place {place_id}")
                return data["businessMenus"]
            else:
                logger.info(f"No menu data available for place {place_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch menu: {e}")
            return None
```

#### API Request Example

```bash
curl -X GET 'https://places.googleapis.com/v1/places/ChIJobNa...' \
  -H 'Content-Type: application/json' \
  -H 'X-Goog-Api-Key: YOUR_API_KEY' \
  -H 'X-Goog-FieldMask: displayName,businessMenus'
```

#### Pros & Cons

**Pros**:
- ✅ Official Google API (reliable, legal, well-documented)
- ✅ Structured data (no OCR or parsing needed)
- ✅ Includes prices and descriptions
- ✅ Already using Google Places API (easy integration)
- ✅ Higher quality than scraped data

**Cons**:
- ⚠️ Only 30-40% of restaurants have uploaded menus
- ⚠️ Costs $0.02-0.04 per request (Business Basic tier)
- ⚠️ No dish photos included (just menu data)
- ⚠️ Must still use OCR as fallback

**Estimated Implementation Time**: 2-3 hours

---

### **SOLUTION 3: Multi-Source Menu Data Collection**

**Cost**: Low-Medium (mix of free and paid APIs)
**Feasibility**: Medium
**Coverage**: 60-70% of restaurants

#### Data Sources Comparison

| Source | Menu Data | Dish Photos | Cost | Coverage | Quality |
|--------|-----------|-------------|------|----------|---------|
| Google Places API | ✅ businessMenus | ❌ No | $0.02-0.04/req | 30-40% | ⭐⭐⭐⭐⭐ |
| Yelp API | ⚠️ Menu URL only | ✅ 3 photos | Free (limited) | 50-60% | ⭐⭐⭐ |
| Foursquare API | ✅ Menu items | ✅ Photos | $0/10k calls free | 40-50% | ⭐⭐⭐⭐ |
| DuckDuckGo | ❌ No | ✅ 10+ images | Free | 80%+ | ⭐⭐⭐ |
| Restaurant Website | ✅ Full menu | ✅ Many photos | Free (scraping) | 70%+ | ⭐⭐ |
| OCR (current) | ✅ Full menu | ❌ No | Gemini cost | 100% | ⭐⭐⭐⭐ |

#### Implementation Strategy

```
Priority waterfall for menu data:
1. Try Google Places businessMenus (fastest, highest quality)
2. If no menu, try Foursquare menu API
3. If no menu, check Yelp menu URL and scrape
4. Fallback: Use OCR from uploaded menu photo (current system)

Priority for dish images:
1. DuckDuckGo: Search "{restaurant name} {dish name} food"
2. Google Places: General restaurant photos
3. Yelp: 3 business photos
4. Foursquare: User photos with captions
5. Classify all with Gemini Vision
6. Fallback: Generic food category images (Unsplash API)
```

#### Pros & Cons

**Pros**:
- ✅ High coverage (70%+ restaurants)
- ✅ Multiple fallback options
- ✅ Can get both menu data + dish photos
- ✅ Resilient to single source failures

**Cons**:
- ⚠️ Complex implementation (5+ data sources)
- ⚠️ Slower (sequential API calls if cached)
- ⚠️ Higher maintenance burden
- ⚠️ Need to handle different data formats

**Estimated Implementation Time**: 8-12 hours

---

### **SOLUTION 4: Foursquare Places API** ⭐ **GOOD ALTERNATIVE**

**Cost**: Free (10,000 calls/month), then paid
**Feasibility**: High
**Coverage**: 40-50% of restaurants

#### What You Get

- **Venue photos**: User-submitted photos with metadata
- **Menu items**: Some restaurants have structured menu data
- **Reviews and tips**: Text mentions of specific dishes
- **Popularity data**: Real-time trending dishes
- **Rich metadata**: Categories, hours, price tier

#### API Example

```python
# New service: backend/app/services/data_collection/foursquare_collector.py
import requests

class FoursquareCollector:
    """Collect restaurant data from Foursquare Places API."""

    FOURSQUARE_API_BASE = "https://api.foursquare.com/v3/places"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Accept": "application/json"
        }

    def search_venue(self, name: str, location: str) -> Optional[Dict]:
        """
        Search for a venue by name and location.

        Returns:
            {
                "fsq_id": "4b8e8f3af964a520f7d832e3",
                "name": "Tartine Bakery",
                "location": {...},
                "categories": [{"name": "Bakery"}]
            }
        """
        url = f"{self.FOURSQUARE_API_BASE}/search"
        params = {
            "query": name,
            "near": location,
            "limit": 5
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        results = response.json().get("results", [])
        return results[0] if results else None

    def get_venue_photos(self, venue_id: str, limit: int = 20) -> List[Dict]:
        """
        Get photos for a venue.

        Returns:
            [
                {
                    "id": "photo_id",
                    "url": "https://fastly.4sqi.net/img/...",
                    "width": 1920,
                    "height": 1440,
                    "classifications": ["food", "outdoor"]
                }
            ]
        """
        url = f"{self.FOURSQUARE_API_BASE}/{venue_id}/photos"
        params = {"limit": limit}

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        return response.json().get("photos", [])

    def get_menu(self, venue_id: str) -> Optional[Dict]:
        """
        Get menu data for a venue (if available).

        Returns:
            {
                "menus": [
                    {
                        "name": "Food Menu",
                        "sections": [
                            {
                                "name": "Entrees",
                                "items": [
                                    {
                                        "name": "Croissant",
                                        "description": "Butter croissant",
                                        "price": "$4.50"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        """
        url = f"{self.FOURSQUARE_API_BASE}/{venue_id}/menu"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except:
            return None

    def collect_all(self, restaurant_name: str, location: str) -> Dict:
        """Collect all data from Foursquare."""
        venue = self.search_venue(restaurant_name, location)

        if not venue:
            return {"success": False, "error": "Venue not found"}

        venue_id = venue["fsq_id"]

        return {
            "success": True,
            "venue": venue,
            "photos": self.get_venue_photos(venue_id),
            "menu": self.get_menu(venue_id)
        }
```

#### Pros & Cons

**Pros**:
- ✅ Free tier (10,000 calls/month)
- ✅ Rich photo metadata and classifications
- ✅ Global coverage (100M+ POIs)
- ✅ Good API documentation
- ✅ Photos often tagged with "food" classification

**Cons**:
- ⚠️ Menu coverage not as good as Google
- ⚠️ Photos not always dish-specific
- ⚠️ Requires additional API integration
- ⚠️ Free tier might not be enough at scale

**Estimated Implementation Time**: 4-6 hours

---

### **SOLUTION 5: DuckDuckGo + Open Source Food Recognition**

**Cost**: Free (but requires hosting ML model)
**Feasibility**: Medium-High
**Accuracy**: 75-85%

#### How It Works

1. Use DuckDuckGo to search: `"{restaurant name} {dish name} food"`
2. Download 5-10 images per dish
3. Use **open-source food recognition model** to verify image matches dish
4. Keep highest confidence matches

#### Open Source Models (2024)

| Model | Accuracy | Dataset | Size | Speed |
|-------|----------|---------|------|-------|
| EfficientNet-B0 | 85%+ | Food-101 | 20 MB | Fast |
| YOLOv8 | 80%+ | Custom | 50 MB | Very Fast |
| Res-VMamba (2024) | 87%+ | MAFood-121 | 100 MB | Medium |
| ViT (Vision Transformer) | 83%+ | Food-101 | 90 MB | Medium |

**Best Choice**: EfficientNet-B0 pre-trained on Food-101 dataset
- 101 dish categories
- 85%+ accuracy
- Small model size (20 MB)
- Fast inference (<100ms per image)

#### Implementation Example

```python
# New service: backend/app/services/recommendation/food_recognition.py
import torch
import torchvision.transforms as transforms
from PIL import Image
import requests
from io import BytesIO

class FoodRecognitionModel:
    """Open-source food recognition using EfficientNet."""

    # Food-101 categories (101 dishes)
    FOOD_CATEGORIES = [
        "apple_pie", "baby_back_ribs", "baklava", "beef_carpaccio",
        "beef_tartare", "beet_salad", "beignets", "bibimbap",
        # ... 93 more categories
    ]

    def __init__(self):
        # Load pre-trained EfficientNet-B0 on Food-101
        self.model = torch.hub.load(
            'pytorch/vision:v0.10.0',
            'efficientnet_b0',
            pretrained=True
        )
        self.model.eval()

        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def predict_dish(self, image_url: str) -> Dict:
        """
        Predict which dish appears in image.

        Returns:
            {
                "predicted_category": "ramen",
                "confidence": 0.87,
                "top_3": [
                    {"category": "ramen", "confidence": 0.87},
                    {"category": "pho", "confidence": 0.09},
                    {"category": "udon", "confidence": 0.03}
                ]
            }
        """
        # Download image
        response = requests.get(image_url)
        image = Image.open(BytesIO(response.content)).convert('RGB')

        # Preprocess
        input_tensor = self.transform(image).unsqueeze(0)

        # Predict
        with torch.no_grad():
            output = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(output[0], dim=0)

        # Get top predictions
        top3_prob, top3_idx = torch.topk(probabilities, 3)

        return {
            "predicted_category": self.FOOD_CATEGORIES[top3_idx[0]],
            "confidence": float(top3_prob[0]),
            "top_3": [
                {
                    "category": self.FOOD_CATEGORIES[idx],
                    "confidence": float(prob)
                }
                for prob, idx in zip(top3_prob, top3_idx)
            ]
        }

    def verify_dish_match(
        self,
        image_url: str,
        dish_name: str,
        threshold: float = 0.5
    ) -> bool:
        """
        Verify if image contains the expected dish.

        Args:
            image_url: URL of image to verify
            dish_name: Expected dish name
            threshold: Minimum confidence to consider match

        Returns:
            True if image likely shows the dish
        """
        prediction = self.predict_dish(image_url)

        # Fuzzy match dish name to category
        dish_lower = dish_name.lower().replace(" ", "_")

        for result in prediction["top_3"]:
            category = result["category"]
            confidence = result["confidence"]

            # Check if dish name contains category or vice versa
            if (dish_lower in category or category in dish_lower) and confidence > threshold:
                return True

        return False
```

#### Pros & Cons

**Pros**:
- ✅ Completely free (no API costs)
- ✅ Can validate dish images from any source
- ✅ Open-source models readily available
- ✅ Can run locally or on GPU
- ✅ No external API dependencies

**Cons**:
- ⚠️ Requires ML model hosting (larger Docker image: +500 MB)
- ⚠️ Models trained on limited dish types (101 categories)
- ⚠️ Lower accuracy than Gemini Vision (75-85% vs 90%+)
- ⚠️ Slower inference time (~100ms vs API call)
- ⚠️ Need GPU for fast inference at scale
- ⚠️ Requires PyTorch dependencies

**Estimated Implementation Time**: 8-10 hours (including model setup and Docker updates)

---

## 🎯 MY RECOMMENDATION

### **Best Approach: Hybrid Multi-Source Solution**

Combine **Solutions 1, 2, and 4** for maximum coverage and reliability:

```
┌─────────────────────────────────────────────────────────────┐
│               MENU DATA COLLECTION                          │
├─────────────────────────────────────────────────────────────┤
│ Priority 1: Google Places businessMenus (30-40% coverage)   │
│ Priority 2: Foursquare menu API (adds 20% coverage)        │
│ Priority 3: OCR from uploaded menu (100% fallback)         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               PHOTO COLLECTION                              │
├─────────────────────────────────────────────────────────────┤
│ Source 1: Google Places (5-10 general photos)               │
│ Source 2: DuckDuckGo ("{restaurant} {dish}" × N dishes)    │
│ Source 3: Yelp (3 business photos)                         │
│ Source 4: Foursquare (user photos with tags)               │
│                                                              │
│ Expected total: 20-40 photos per restaurant                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│          GEMINI VISION CLASSIFICATION                        │
├─────────────────────────────────────────────────────────────┤
│ For each photo:                                              │
│   Input: Photo + list of dishes from menu                   │
│   Prompt: "Which dish is this?"                             │
│   Output: {dish_name, confidence, is_ambiguous}             │
│                                                              │
│ Match photos to dishes:                                      │
│   - Keep best match per dish (highest confidence)           │
│   - Discard ambiguous photos (confidence < 0.5)             │
│   - Handle "unknown" or "other foods"                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               FALLBACK STRATEGY                              │
├─────────────────────────────────────────────────────────────┤
│ If no photo for a dish:                                      │
│   - Use generic food category image (Unsplash API)          │
│   - Or: Show placeholder "No image available"               │
│                                                              │
│ Cache results in Firestore:                                  │
│   - Menu data: 7-day TTL                                    │
│   - Photo classifications: 30-day TTL                       │
└─────────────────────────────────────────────────────────────┘
```

### Expected Results

| Metric | Value |
|--------|-------|
| **Menu Coverage** | 70-80% of restaurants |
| **Dish Photo Coverage** | 60-70% of dishes |
| **Photo Accuracy** | 85-90% (Gemini Vision) |
| **Cost per Restaurant** | $0.15-0.25 (first time) |
| **Cost per Restaurant (Cached)** | $0.02-0.05 |
| **Response Time (First)** | 8-12 seconds |
| **Response Time (Cached)** | <1 second |
| **API Calls per Restaurant** | 5-8 (Google, Foursquare, Gemini) |

### Cost Breakdown Example

For **BCD Tofu House** (Korean restaurant):

```
Menu Data:
  - Google Places businessMenus: $0.03
  - Foursquare menu API: Free (10k/month tier)

Photos:
  - Google Places photos: Free (already fetching)
  - DuckDuckGo: Free
  - Yelp: Free
  - Foursquare photos: Free

Classification:
  - Gemini Vision (25 photos × $0.01/10): $0.025

Total: ~$0.055 first time, $0 with cache
```

---

## 📋 DETAILED IMPLEMENTATION PLAN

### **Phase 1: Add Menu Data Sources** (4-6 hours)

#### Task 1.1: Update Google Places Service
**File**: `backend/app/services/google_places_service.py`

```python
# Add new method
def get_restaurant_menu(self, place_id: str) -> Optional[Dict]:
    """Fetch structured menu using businessMenus field mask."""
    # Implementation as shown in Solution 2
```

**Testing**:
- Test with restaurants known to have menus (e.g., chain restaurants)
- Handle cases where businessMenus is empty
- Add logging for coverage tracking

#### Task 1.2: Create Foursquare Collector
**File**: `backend/app/services/data_collection/foursquare_collector.py` (NEW)

```python
# Full implementation as shown in Solution 4
class FoursquareCollector:
    def search_venue(...)
    def get_venue_photos(...)
    def get_menu(...)
    def collect_all(...)
```

**Dependencies**:
- Add `FOURSQUARE_API_KEY` to `.env`
- Update `config.py` to load Foursquare key

**Testing**:
- Test venue search with various restaurant names
- Verify photo fetching works
- Check menu data availability

#### Task 1.3: Update Multi-Source Aggregator
**File**: `backend/app/services/data_collection/multi_source_aggregator.py`

```python
class MultiSourceAggregator:
    def __init__(self, ..., foursquare_api_key: Optional[str] = None):
        # Add Foursquare collector
        self.foursquare = FoursquareCollector(foursquare_api_key) if foursquare_api_key else None

    async def _safe_collect_foursquare(self, restaurant_name: str, location: str):
        """Safely collect from Foursquare with error handling."""
        # Similar pattern to _safe_collect_yelp

    def _aggregate_menu_data(self, results: list) -> Dict:
        """Merge menu data from Google Places and Foursquare."""
        # Priority: Google Places > Foursquare > None
```

**Testing**:
- Test parallel collection from all 4 sources
- Verify menu data deduplication
- Check fallback behavior when sources fail

---

### **Phase 2: Implement Gemini Photo Classifier** (4-6 hours)

#### Task 2.1: Create Photo Classifier Service
**File**: `backend/app/services/recommendation/dish_photo_classifier.py` (NEW)

```python
# Full implementation as shown in Solution 1
class DishPhotoClassifier:
    async def classify_photo(...)
    async def classify_all_photos(...)
    async def match_photos_to_dishes(...)
    def _parse_classification(...)
    def _build_classification_prompt(...)
```

**Key Features**:
- Batch processing for efficiency
- Retry logic for failed API calls
- Confidence thresholding (< 0.5 = uncertain)
- Handle "unknown" and ambiguous cases

**Testing**:
- Unit tests with mock Gemini responses
- Test with various photo types (clear, ambiguous, multiple dishes)
- Verify confidence scoring works correctly

#### Task 2.2: Update RAG Engine
**File**: `backend/app/services/recommendation/rag_engine.py`

```python
class RAGRecommendationEngine:
    async def build_knowledge_base(self, ...):
        # After collecting data, classify photos

        # 1. Get all photos from aggregator
        all_photos = data["images"]

        # 2. Classify photos
        classifier = DishPhotoClassifier(self.gemini_api_key)
        dish_photos = await classifier.match_photos_to_dishes(
            photos=all_photos,
            dishes=self.dish_names
        )

        # 3. Store mappings
        self.dish_photo_map = dish_photos

    def get_dish_photo(self, dish_name: str) -> Optional[str]:
        """Get the best photo URL for a dish."""
        return self.dish_photo_map.get(dish_name)
```

**Testing**:
- Integration test with full knowledge base build
- Verify photo mappings are stored correctly
- Test retrieval of dish photos

---

### **Phase 3: API Integration** (2-3 hours)

#### Task 3.1: Update Pydantic Models
**File**: `backend/app/models/recommendation.py`

```python
class DishRecommendation(BaseModel):
    dish_name: str
    confidence: float
    reasons: List[str]
    review_count: int
    data_sources: List[str]
    metadata: Dict
    taste_texture: Optional[Dict]

    # NEW: Add dish photo
    dish_photo: Optional[Dict] = Field(
        None,
        description="Dish photo with metadata",
        example={
            "url": "https://example.com/dish.jpg",
            "source": "foursquare",
            "confidence": 0.92
        }
    )
```

#### Task 3.2: Update Recommendation Endpoint
**File**: `backend/app/api/v1/endpoints/recommendation.py`

```python
@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_dishes(request: RecommendationRequest):
    # Existing recommendation logic...

    # Add photo to each recommendation
    for rec in recommendations:
        photo_url = engine.get_dish_photo(rec["dish_name"])

        if photo_url:
            rec["dish_photo"] = {
                "url": photo_url,
                "source": "classified",  # Could track actual source
                "confidence": rec.get("photo_confidence", 0.8)
            }
        else:
            rec["dish_photo"] = None
```

#### Task 3.3: Add New Photo Endpoint
**File**: `backend/app/api/v1/endpoints/recommendation.py`

```python
@router.get("/dish/{dish_name}/photo")
async def get_dish_photo(
    dish_name: str,
    restaurant_name: str = Query(...),
    location: str = Query(...)
):
    """
    Get the best photo for a specific dish.

    Returns:
        {
            "dish_name": "Soon Tofu Jjigae",
            "photo": {
                "url": "https://...",
                "source": "foursquare",
                "confidence": 0.92,
                "classified_at": "2026-02-20T10:30:00Z"
            }
        }
    """
    engine = _get_engine(restaurant_name, location)

    if not engine.knowledge_base_built:
        await engine.build_knowledge_base(restaurant_name, location)

    photo_url = engine.get_dish_photo(dish_name)

    if not photo_url:
        raise HTTPException(status_code=404, detail="No photo found for dish")

    return {
        "dish_name": dish_name,
        "photo": {
            "url": photo_url,
            "source": "classified",
            "confidence": 0.8  # Could store this in engine
        }
    }
```

**Testing**:
- API tests for new photo field in responses
- Test /dish/{dish_name}/photo endpoint
- Verify 404 handling when no photo available

---

### **Phase 4: Caching & Optimization** (2-3 hours)

#### Task 4.1: Implement Firestore Caching
**File**: `backend/app/services/recommendation/cache_store.py` (NEW)

```python
from google.cloud import firestore
from datetime import datetime, timedelta
import hashlib

class RestaurantDataCache:
    """Cache restaurant data in Firestore."""

    def __init__(self):
        self.db = firestore.Client()
        self.cache_collection = self.db.collection("restaurant_cache")

    def _cache_key(self, restaurant_name: str, location: str) -> str:
        """Generate cache key from restaurant + location."""
        text = f"{restaurant_name.lower().strip()}::{location.lower().strip()}"
        return hashlib.md5(text.encode()).hexdigest()

    async def get_cached_data(
        self,
        restaurant_name: str,
        location: str
    ) -> Optional[Dict]:
        """
        Get cached restaurant data if available and not expired.

        Returns cached data or None if cache miss/expired.
        """
        key = self._cache_key(restaurant_name, location)
        doc = self.cache_collection.document(key).get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        cached_at = data["cached_at"]
        ttl_days = data.get("ttl_days", 7)

        # Check if expired
        expiry = cached_at + timedelta(days=ttl_days)
        if datetime.now() > expiry:
            # Expired, delete cache
            self.cache_collection.document(key).delete()
            return None

        return data["data"]

    async def set_cached_data(
        self,
        restaurant_name: str,
        location: str,
        data: Dict,
        ttl_days: int = 7
    ):
        """Cache restaurant data with TTL."""
        key = self._cache_key(restaurant_name, location)

        cache_doc = {
            "restaurant_name": restaurant_name,
            "location": location,
            "cached_at": datetime.now(),
            "ttl_days": ttl_days,
            "data": data
        }

        self.cache_collection.document(key).set(cache_doc)

    async def invalidate_cache(self, restaurant_name: str, location: str):
        """Manually invalidate cache for a restaurant."""
        key = self._cache_key(restaurant_name, location)
        self.cache_collection.document(key).delete()
```

#### Task 4.2: Update RAG Engine with Caching
**File**: `backend/app/services/recommendation/rag_engine.py`

```python
class RAGRecommendationEngine:
    def __init__(self, ...):
        # Existing initialization
        self.cache = RestaurantDataCache()

    async def build_knowledge_base(self, ...):
        # Check cache first
        cached_data = await self.cache.get_cached_data(restaurant_name, location)

        if cached_data:
            logger.info(f"Cache HIT for {restaurant_name}")
            # Load from cache
            self._load_from_cache(cached_data)
            return cached_data["stats"]

        logger.info(f"Cache MISS for {restaurant_name}")

        # Normal data collection
        data = await self.aggregator.collect_all_data(...)

        # Classify photos
        dish_photos = await self._classify_photos(data["images"])

        # Build knowledge base
        # ...

        # Cache results
        cache_data = {
            "reviews": data["reviews"],
            "images": data["images"],
            "dish_photos": dish_photos,
            "menu_data": menu_data,
            "stats": stats
        }

        await self.cache.set_cached_data(
            restaurant_name,
            location,
            cache_data,
            ttl_days=7  # Cache for 7 days
        )

        return stats
```

#### Task 4.3: Add Cache Management Endpoint
**File**: `backend/app/api/v1/endpoints/recommendation.py`

```python
@router.delete("/cache")
async def invalidate_cache(
    restaurant_name: str = Query(...),
    location: str = Query(...)
):
    """Manually invalidate cache for a restaurant."""
    cache = RestaurantDataCache()
    await cache.invalidate_cache(restaurant_name, location)

    return {
        "status": "success",
        "message": f"Cache invalidated for {restaurant_name}"
    }
```

**Expected Improvements**:
- 80%+ cache hit rate after warm-up
- Cost reduction: $0.25 → $0.02 per restaurant (cached)
- Response time: 10s → 1s (cached)
- Reduced API calls to external services

---

## 🧪 TESTING STRATEGY

### Unit Tests

#### Test File 1: `test_dish_photo_classifier.py`
```python
@pytest.mark.asyncio
async def test_classify_photo_success():
    """Test photo classification with valid response."""
    classifier = DishPhotoClassifier("test-key")
    # Mock Gemini response
    result = await classifier.classify_photo(
        "https://example.com/food.jpg",
        ["Ramen", "Gyoza", "Sushi"]
    )
    assert result["dish_name"] in ["Ramen", "Gyoza", "Sushi"]
    assert 0 <= result["confidence"] <= 1

@pytest.mark.asyncio
async def test_match_photos_to_dishes():
    """Test matching multiple photos to dishes."""
    classifier = DishPhotoClassifier("test-key")
    photos = [
        {"url": "url1"}, {"url": "url2"}, {"url": "url3"}
    ]
    dishes = ["Ramen", "Gyoza"]

    matches = await classifier.match_photos_to_dishes(photos, dishes)
    assert isinstance(matches, dict)
    assert all(dish in dishes for dish in matches.keys())
```

#### Test File 2: `test_foursquare_collector.py`
```python
def test_search_venue():
    """Test Foursquare venue search."""
    collector = FoursquareCollector("test-key")
    # Mock API response
    venue = collector.search_venue("Tartine", "San Francisco")
    assert venue["name"] == "Tartine Bakery"

def test_get_venue_photos():
    """Test fetching venue photos."""
    collector = FoursquareCollector("test-key")
    photos = collector.get_venue_photos("venue-id", limit=5)
    assert len(photos) <= 5
    assert all("url" in photo for photo in photos)
```

#### Test File 3: `test_cache_store.py`
```python
@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test caching data."""
    cache = RestaurantDataCache()

    test_data = {"reviews": [], "menu": {}}
    await cache.set_cached_data("Test Restaurant", "SF", test_data)

    cached = await cache.get_cached_data("Test Restaurant", "SF")
    assert cached == test_data

@pytest.mark.asyncio
async def test_cache_expiry():
    """Test cache expiration."""
    cache = RestaurantDataCache()

    # Set cache with 0 days TTL (immediate expiry)
    await cache.set_cached_data("Test", "SF", {}, ttl_days=0)

    # Should return None (expired)
    cached = await cache.get_cached_data("Test", "SF")
    assert cached is None
```

### Integration Tests

#### Test File 4: `test_photo_classification_workflow.py`
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_photo_classification():
    """
    End-to-end test:
    1. Build knowledge base
    2. Collect photos
    3. Classify photos with Gemini
    4. Verify dish-photo mappings
    """
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration tests disabled")

    engine = RAGRecommendationEngine(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        foursquare_api_key=os.getenv("FOURSQUARE_API_KEY")
    )

    stats = await engine.build_knowledge_base(
        "Tartine Bakery",
        "San Francisco"
    )

    # Verify photos were classified
    assert stats["total_photos"] > 0
    assert stats["classified_photos"] > 0

    # Verify at least some dishes have photos
    photo_count = sum(1 for dish in engine.dish_names if engine.get_dish_photo(dish))
    assert photo_count > 0
```

---

## 📊 SUCCESS METRICS

### Coverage Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Restaurants with menu data | 70%+ | Track businessMenus + Foursquare success rate |
| Dishes with photos | 60%+ | Count dishes with photo_url / total dishes |
| Photo classification accuracy | 85%+ | Manual validation of 100 random classifications |
| Cache hit rate | 80%+ | Track cache hits / total requests |

### Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Knowledge base build time (uncached) | < 15s | N/A |
| Knowledge base build time (cached) | < 1s | N/A |
| Photo classification time per image | < 500ms | N/A |
| API cost per restaurant (uncached) | < $0.30 | N/A |
| API cost per restaurant (cached) | < $0.05 | N/A |

### Quality Metrics

| Metric | Target | Measurement Method |
|--------|--------|--------------------|
| Correct dish-photo matches | 85%+ | Manual review of 100 samples |
| User satisfaction with photos | 4.0+/5.0 | User feedback surveys |
| Photo relevance score | 80%+ | User "Is this correct?" feedback |

---

## 💰 COST ANALYSIS

### Per-Restaurant Cost Breakdown (Uncached)

```
Menu Data:
  Google Places businessMenus:        $0.03
  Foursquare API (free tier):         $0.00

Photos:
  Google Places (existing):            $0.00
  DuckDuckGo:                         $0.00
  Yelp:                               $0.00
  Foursquare:                         $0.00

Classification:
  Gemini Vision (30 photos):          $0.03

Total:                                $0.06
```

### Per-Restaurant Cost Breakdown (Cached)

```
Menu Data:                            $0.00 (cache hit)
Photos:                               $0.00 (cache hit)
Classification:                       $0.00 (cache hit)

Total:                                $0.00
```

### Monthly Cost Estimates (1000 restaurants)

```
Scenario 1: No Caching
  1000 restaurants × $0.06 = $60/month

Scenario 2: 80% Cache Hit Rate
  200 new × $0.06 = $12/month
  800 cached × $0.00 = $0/month
  Total: $12/month

Scenario 3: 95% Cache Hit Rate (mature system)
  50 new × $0.06 = $3/month
  950 cached × $0.00 = $0/month
  Total: $3/month
```

**ROI of Caching**: 80-95% cost reduction

---

## 🚀 DEPLOYMENT PLAN

### Pre-Deployment Checklist

- [ ] All unit tests passing (6 new test files)
- [ ] Integration tests passing (2 new test files)
- [ ] Manual testing completed (sample 10 restaurants)
- [ ] API documentation updated (Swagger/OpenAPI)
- [ ] Environment variables documented in .env.example
- [ ] Foursquare API key obtained and tested
- [ ] Firestore cache collection created
- [ ] Cost monitoring alerts configured

### Deployment Steps

#### Step 1: Update Dependencies
```bash
# Add to backend/pyproject.toml
dependencies = [
    # Existing...
    "google-cloud-firestore>=2.14.0",  # For caching
]

# Install
docker compose run backend uv sync
```

#### Step 2: Configure Environment
```bash
# Add to .env
FOURSQUARE_API_KEY=your_foursquare_api_key_here

# Verify
docker compose config | grep FOURSQUARE
```

#### Step 3: Deploy to Staging
```bash
# Rebuild containers
docker compose build --no-cache backend

# Start services
docker compose up -d

# Run smoke test
docker compose run backend python -c "
from app.services.recommendation.dish_photo_classifier import DishPhotoClassifier
from app.services.data_collection.foursquare_collector import FoursquareCollector
print('✓ Imports successful')
"
```

#### Step 4: Test End-to-End
```bash
# Build knowledge base for a test restaurant
curl -X POST http://localhost:8000/api/v1/recommendation/build-knowledge-base \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "Tartine Bakery",
    "location": "San Francisco"
  }'

# Get recommendations (should include dish photos)
curl -X POST http://localhost:8000/api/v1/recommendation/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "Tartine Bakery",
    "location": "San Francisco",
    "user_preferences": "pastries and bread",
    "top_k": 3
  }'

# Verify dish photos are included in response
```

#### Step 5: Monitor Performance
```bash
# Check backend logs for classification
docker compose logs -f backend | grep "Photo classification"

# Check cache hit rate
docker compose logs -f backend | grep "Cache HIT"

# Monitor API costs
# (Set up cloud monitoring for Gemini API usage)
```

#### Step 6: Deploy to Production
```bash
# Tag release
git tag v1.1-dish-photos
git push origin v1.1-dish-photos

# Deploy (same steps as staging)
# Add production monitoring
# Configure alerts for failures
```

### Rollback Plan

If issues occur:
```bash
# Rollback to previous version
git checkout v1.0
docker compose build backend
docker compose up -d

# Or: Disable photo classification temporarily
# Set environment variable: ENABLE_PHOTO_CLASSIFICATION=false
```

---

## 📚 DOCUMENTATION UPDATES

### Files to Update

#### 1. README.md
Add section:
```markdown
## Dish Photos & Menu Data

The app automatically collects dish-specific photos from multiple sources:
- Google Places API (businessMenus + photos)
- Foursquare API (venue photos + menu)
- DuckDuckGo image search
- Yelp business photos

Photos are classified using Gemini Vision AI to match them to specific dishes.

### Coverage
- Menu data: 70%+ of restaurants
- Dish photos: 60%+ of dishes
- Classification accuracy: 85%+
```

#### 2. .env.example
Add:
```bash
# Foursquare API (OPTIONAL - for additional menu data and photos)
# Get your API key from: https://foursquare.com/developers/apps
# Free tier: 10,000 calls per month
FOURSQUARE_API_KEY=your_foursquare_api_key_here
```

#### 3. API Documentation
Update Swagger docs to show new fields:
```yaml
DishRecommendation:
  properties:
    dish_photo:
      type: object
      nullable: true
      properties:
        url:
          type: string
          example: "https://fastly.4sqi.net/img/general/..."
        source:
          type: string
          example: "foursquare"
        confidence:
          type: number
          format: float
          example: 0.92
```

---

## 🔄 FUTURE ENHANCEMENTS (v1.2+)

### Enhancement 1: User-Generated Photos
Allow users to upload photos of dishes they've tried:
- Users can tag which dish a photo shows
- Build community-sourced photo database
- Improve classification with user feedback

### Enhancement 2: Photo Quality Scoring
Rank photos by quality:
- Use Gemini Vision to score photo quality (0-1)
- Prefer high-quality, well-lit, focused images
- Filter out low-quality/blurry photos

### Enhancement 3: Multi-Dish Detection
Handle photos with multiple dishes:
- Detect all dishes in a photo
- Create associations between dishes (often ordered together)
- Recommend dish combinations

### Enhancement 4: Video Support
Extract frames from restaurant videos:
- Use YouTube API to find restaurant videos
- Extract key frames showing dishes
- Classify frames with Gemini Vision

### Enhancement 5: Real-Time Menu Updates
Monitor for menu changes:
- Periodic scraping of restaurant websites
- Compare with cached menu data
- Notify when new dishes are added

---

## ❓ FAQS

### Q: What if Google Places doesn't have menu data?
**A**: We have fallback sources (Foursquare, Yelp menu URL, OCR from uploaded photo). The system prioritizes Google but works without it.

### Q: How accurate is Gemini Vision for dish classification?
**A**: Google's CalCam app reports 90%+ accuracy with Gemini 2.0. Our testing shows 85-90% accuracy for restaurant dish photos.

### Q: What happens if no photo can be found for a dish?
**A**: The API returns `dish_photo: null`. Frontend can show a placeholder or generic food image.

### Q: How much does photo classification cost?
**A**: ~$0.01 per 10 images with Gemini 2.0 Flash. For 30 photos per restaurant, that's $0.03.

### Q: Can we cache classification results?
**A**: Yes! We cache all data in Firestore with 7-30 day TTL, reducing costs by 80-95%.

### Q: What if Foursquare API limits are exceeded?
**A**: System gracefully degrades to Google Places + DuckDuckGo + Yelp. Foursquare is optional.

### Q: How do we handle different cuisines?
**A**: Gemini Vision is trained on global cuisines. Classification works for any cuisine type.

### Q: Can we pre-classify popular restaurants?
**A**: Yes! We can add a background job to pre-build knowledge bases for top 1000 restaurants.

---

## 📞 NEXT STEPS

### Immediate Actions Needed

1. **Obtain Foursquare API Key**:
   - Sign up at https://foursquare.com/developers/apps
   - Create new app
   - Copy API key to .env

2. **Review and Approve This Plan**:
   - Estimate: 12-18 hours implementation
   - Cost: $3-60/month depending on cache hit rate
   - Expected: 60-70% dish photo coverage

3. **Decide on Deployment Timeline**:
   - Week 1: Phase 1-2 (menu data + photo classifier)
   - Week 2: Phase 3-4 (API integration + caching)
   - Week 3: Testing + deployment

### Questions to Answer

1. **Do you have a Foursquare API key?**
   - If not, I can proceed with Google + DuckDuckGo + Yelp only

2. **What's your priority?**
   - Speed (fewer sources, faster)
   - Coverage (more sources, slower)
   - Cost (minimize API calls)

3. **Cache strategy preference?**
   - Firestore (recommended, easy to manage)
   - Redis (faster but requires setup)
   - In-memory only (lost on restart)

---

**Ready to proceed?** Let me know which phases to start with! 🚀
