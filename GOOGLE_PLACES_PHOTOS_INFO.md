# Google Places API - Photo Fetching Guide

## Quick Answer

**Can you fetch all images available on Google Maps?**
- **No**, you cannot fetch ALL images from Google Maps
- **Yes**, you can fetch **up to 10 photos per restaurant** from Google Places API
- The current implementation fetches **5 photos** (configurable)

## Photo Limits & Restrictions

### Number of Photos Available

| API Call Type | Max Photos Returned |
|--------------|-------------------|
| **Text Search** | 1 photo reference |
| **Find Place** | 1 photo reference |
| **Place Details** | **Up to 10 photo references** ✅ |

**In this app**: We use Place Details API, so we can get **up to 10 photos per restaurant**.

### Current Implementation

**File**: [backend/app/services/google_places_service.py](backend/app/services/google_places_service.py:214)

```python
# Current code fetches 5 photos (line 214):
for photo in photos[:5]:  # Get up to 5 photos
    photo_ref = photo.get("photo_reference")
    if photo_ref:
        photo_urls.append(self.get_photo_url(photo_ref, max_width=800))
```

**You can change this to fetch up to 10 photos:**
```python
for photo in photos[:10]:  # Get up to 10 photos
```

## Photo Sources

Photos come from two sources:

1. **Business Owners** - Photos uploaded by restaurant owners
2. **User Contributions** - Photos uploaded by Google Maps users (customers)

This means:
- Popular restaurants have MORE photos available
- New/unpopular restaurants may have FEWER photos
- The actual number varies by location

## Photo Quality & Size

### Size Options

When requesting photos, you can specify:
- `maxwidth`: Maximum width (1-1600 pixels)
- `maxheight`: Maximum height (1-1600 pixels)

**Current implementation uses**: `max_width=800` pixels

**High resolution example**:
```python
self.get_photo_url(photo_ref, max_width=1600)  # Full resolution
```

**Thumbnail example**:
```python
self.get_photo_url(photo_ref, max_width=400)   # Smaller, faster
```

## Important Restrictions

### 1. Photo References Expire ⚠️

Photo references are **temporary tokens** that expire. You cannot:
- Cache photo references indefinitely
- Store them in a database for long-term use
- Reuse old references (they expire)

**Best Practice**: Always fetch fresh photo references when needed.

### 2. Attribution Required

When displaying photos, you must:
- Show proper attribution to Google
- Follow Google's [attribution requirements](https://developers.google.com/maps/documentation/places/web-service/policies#logo_attribution_requirements)

### 3. Usage Limits

Photo requests are billed separately:
- **Place Photo request**: $0.007 per photo
- If you fetch 5 photos per restaurant: 5 × $0.007 = **$0.035 per restaurant**

**Current cost breakdown** (per restaurant):
- Search: $0.032
- Details: $0.017
- Photos (5): $0.035
- **Total**: ~$0.084

## Fetching More Photos

### Option 1: Increase Photo Count (Up to 10)

**Modify**: `backend/app/services/google_places_service.py` line 214

```python
# Change from:
for photo in photos[:5]:  # Get up to 5 photos

# To:
for photo in photos[:10]:  # Get up to 10 photos (maximum)
```

**Cost impact**:
- 5 photos: $0.035
- 10 photos: $0.070
- **Additional cost**: $0.035 per restaurant

### Option 2: Make it Configurable

Add a parameter to control photo count:

```python
def get_full_place_data(self, place_id: str, num_photos: int = 5) -> dict:
    """Get complete place data (details + reviews).

    Args:
        place_id: Google Place ID.
        num_photos: Number of photos to fetch (1-10, default 5).
    """
    place = self.get_place_details(place_id)
    reviews = place.get("reviews", [])

    # Process photo URLs
    photos = place.get("photos", [])
    photo_urls = []

    # Ensure num_photos is between 1 and 10
    num_photos = min(max(num_photos, 1), 10)

    for photo in photos[:num_photos]:
        photo_ref = photo.get("photo_reference")
        if photo_ref:
            photo_urls.append(self.get_photo_url(photo_ref, max_width=800))

    place["photo_urls"] = photo_urls

    return {
        "place": place,
        "reviews": reviews
    }
```

### Option 3: Fetch Different Sizes

You can optimize by fetching thumbnails first, then full-size on demand:

```python
# Thumbnails for gallery preview
thumbnail_urls = [
    self.get_photo_url(ref, max_width=400)
    for ref in photo_refs[:10]
]

# Full resolution for selected photo
full_res_url = self.get_photo_url(selected_ref, max_width=1600)
```

## Comparison: Google Places vs Google Maps Web

### Google Maps Website
- Shows **MANY** photos (potentially hundreds)
- Includes Street View
- User can upload unlimited photos
- Not accessible via Places API

### Google Places API
- **Limited to 10 photo references** per Place Details request
- These are the "featured" or most relevant photos
- Curated selection (not all photos available on Google Maps)

**Why the difference?**
- API provides a curated subset for performance
- Prevents abuse and excessive data transfer
- Keeps costs predictable

## Example: Real Restaurant

Let's say "Tartine Bakery" has 500 photos on Google Maps:

**What you can fetch via API:**
- **10 photo references** (maximum from Place Details)
- These are typically the "best" or most viewed photos
- You cannot access all 500 photos via the API

**What you see on Google Maps:**
- All 500+ photos
- Includes user uploads, Street View, etc.
- Different data access model

## Cost Analysis

### Scenario 1: 5 Photos per Restaurant (Current)
```
Per restaurant:
- Search: $0.032
- Details: $0.017
- Photos (5): $0.035
- Total: $0.084

With $200 free credit:
- ~2,380 restaurants/month
```

### Scenario 2: 10 Photos per Restaurant (Maximum)
```
Per restaurant:
- Search: $0.032
- Details: $0.017
- Photos (10): $0.070
- Total: $0.119

With $200 free credit:
- ~1,680 restaurants/month
```

### Recommendation
**Stick with 5 photos** for most use cases:
- Good balance of visual content
- Lower cost
- Faster loading
- Fetch more on-demand if needed

## How to Increase Photo Limit in Your App

### Step 1: Update Backend Service

Edit `backend/app/services/google_places_service.py`:

```python
# Find line 214 and change:
for photo in photos[:5]:  # Current

# To:
for photo in photos[:10]:  # Maximum
```

### Step 2: Restart Backend

```bash
# If using Docker:
docker compose restart backend

# If running locally:
# Stop (Ctrl+C) and restart:
uvicorn app.main:app --reload
```

### Step 3: Test

```bash
curl http://localhost:8000/api/v1/places/ChIJobNaHIO4woARmjJB77L7Heg
```

Look for `photo_urls` array - should now have up to 10 URLs instead of 5.

## Advanced: Lazy Loading Photos

For better performance, fetch photos progressively:

### Frontend Strategy:
1. **Initial load**: Show first 3 photos
2. **User scrolls**: Fetch next 2-7 photos
3. **User clicks "See all"**: Fetch remaining photos (8-10)

This minimizes initial API calls while providing a smooth UX.

### Implementation Idea:
```typescript
// frontend/lib/api.ts
export async function getPlacePhotos(
  placeId: string,
  offset: number = 0,
  limit: number = 5
) {
  // Fetch place details with photo_limit parameter
  const response = await fetch(
    `/api/v1/places/${placeId}?num_photos=${offset + limit}`
  );
  // Return only the requested slice
}
```

## FAQ

### Q: Can I get more than 10 photos?
**A**: No, 10 is the maximum from a single Place Details request. You cannot fetch more via the API.

### Q: Why doesn't the API show all photos like Google Maps?
**A**: The API provides a curated subset for performance and cost management. It's designed for programmatic access, not browsing.

### Q: Can I cache the photos?
**A**: You can cache the **photo URLs** temporarily, but photo **references** expire. Best practice: Fetch fresh references regularly.

### Q: Do photo URLs work directly in `<img>` tags?
**A**: Yes! The URLs returned are direct links to images:
```html
<img src="https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference=..." />
```

### Q: What if a restaurant has fewer than 10 photos?
**A**: The API returns however many are available (could be 0-10). The code handles this gracefully.

### Q: Can I filter photos by type (food, interior, exterior)?
**A**: No, the API doesn't provide photo type filtering. You get the most relevant photos selected by Google's algorithm.

## Summary

✅ **Maximum photos per restaurant**: 10 (via Place Details API)
✅ **Current implementation**: 5 photos (configurable)
✅ **Photo quality**: Up to 1600px (current: 800px)
✅ **Cost per photo**: $0.007
❌ **Cannot fetch ALL Google Maps photos** (only curated subset)
❌ **Photo references expire** (cannot cache long-term)

**Recommendation**: Keep the current 5-photo limit unless you specifically need more visual content. It's a good balance of quality, cost, and performance.

## Related Documentation

- [Google Places Photos API](https://developers.google.com/maps/documentation/places/web-service/photos)
- [Google Places Pricing](https://developers.google.com/maps/billing/gmp-billing)
- [Attribution Requirements](https://developers.google.com/maps/documentation/places/web-service/policies)
- Current implementation: [google_places_service.py](backend/app/services/google_places_service.py)
