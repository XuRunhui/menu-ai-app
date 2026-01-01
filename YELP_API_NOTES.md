# Yelp API Implementation Notes

## Yelp Reviews API Issue

### Problem

The Yelp Fusion API Reviews endpoint (`/v3/businesses/{id}/reviews`) returns a 404 error for some businesses, even with a valid API key.

**Error Example**:
```
404 Client Error: Not Found for url: https://api.yelp.com/v3/businesses/{business_id}/reviews?limit=3
```

### Confirmed Cause

**The Yelp Reviews endpoint requires a paid plan.**

According to the official Yelp API documentation:

> "This endpoint is part of Yelp Fusion, visit Yelp Places API to learn more. To access this endpoint, you require either the **Enhanced Plan** or **Premium Plan** permission."

The **free tier API key does NOT have access** to the `/v3/businesses/{id}/reviews` endpoint. This is why you get 404 errors for all businesses, even though they have reviews on the Yelp website.

**API Tier Breakdown**:
- ✅ **Free Tier**: Business search, details, photos, location
- ❌ **Free Tier**: NO access to review text
- ✅ **Enhanced/Premium Plan**: Full access including reviews

### Current Workaround

The implementation has been updated to handle this gracefully:

#### Backend ([yelp_service.py](backend/app/services/yelp_service.py))

The `get_reviews()` method now returns an empty list instead of crashing:

```python
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        logger.warning(f"Reviews not available for business {business_id} (404)")
        return []  # Return empty list instead of raising error
    else:
        logger.error(f"Failed to fetch reviews: {e}")
        raise
```

#### Frontend ([RestaurantInfo.tsx](frontend/components/RestaurantInfo.tsx))

Displays a helpful message when reviews are unavailable:

```tsx
{reviews.length > 0 ? (
  // Display reviews
) : (
  // Show explanation message
  <div>Reviews are not available for this restaurant...</div>
)}
```

### What Still Works (Free Tier)

Even without review text access, the app still provides valuable functionality:

**✅ Available with Free Tier:**
- Restaurant search by name and location
- Business details (name, rating, **review count**, price level)
- Address and phone number
- Category information (cuisine types)
- **Photo gallery** (up to 3 photos from business details)
- Operating hours
- Coordinates (latitude/longitude)
- Link to Yelp website for full reviews
- Menu parsing with multilingual support

**❌ NOT Available with Free Tier:**
- Review text content
- Review user names and avatars
- Review timestamps
- Individual review ratings

**Note**: You can see the **review COUNT** (e.g., "5000 reviews") but not the actual review text.

### Alternative Data Sources for Popular Dishes

Since Yelp reviews might not be accessible, consider these alternatives for extracting popular dishes:

1. **Google Places API**:
   - Provides reviews with text
   - Free tier: ~$200/month credit
   - Endpoint: `places/{place_id}/reviews`

2. **Manual Entry**:
   - Allow restaurant owners to add popular dishes
   - Build a database of user-submitted recommendations

3. **Web Scraping** (with permission):
   - Scrape Yelp website directly (check ToS)
   - Use Google search results
   - Aggregate from multiple sources

4. **OpenTable API**:
   - Restaurant reservations platform
   - May have review/dish data
   - Requires partnership/approval

### Testing Without Reviews

You can still test the full workflow:

1. **Search for a restaurant** - Works perfectly
2. **View restaurant details** - Shows all business info
3. **View photos** - Photo gallery works (from business details endpoint)
4. **Upload menu** - Menu parsing works independently
5. **No popular dishes** - This section won't show (or will be empty)

### Future Enhancement: Photo-Based Popular Dishes

Since reviews aren't available, we could implement an alternative approach:

**Idea**: Extract popular dishes from **restaurant photos** instead of reviews

1. Get photos from Yelp business details (already working)
2. Use Gemini Vision to analyze photos
3. Prompt: "Identify any dish names visible in these restaurant photos"
4. Extract dish names from menu boards, table tents, photo captions

**Pros**:
- Works without reviews API
- Visual confirmation of dishes
- Already have photos from business endpoint

**Cons**:
- Less accurate than text reviews
- Photos might not show dish names
- More API calls to Gemini

### Checking Your Yelp API Access

To verify what endpoints you have access to:

1. Visit [Yelp Developer Portal](https://www.yelp.com/developers/v3/manage_app)
2. Check your app's API access level
3. Look for "Business Details" vs "Reviews" permissions
4. Consider upgrading if needed (paid tiers may have reviews access)

### Recommended Actions

**For Development**:
- ✅ App works without reviews (photos and business details still valuable)
- ✅ Graceful error handling in place
- ✅ User-friendly messaging when reviews unavailable

**For Production**:
1. **Option A**: Apply for extended Yelp API access
   - Contact Yelp developer support
   - Explain use case
   - May require partnership or paid tier

2. **Option B**: Implement alternative data source
   - Google Places API for reviews
   - Build user-generated content system
   - Hybrid approach (multiple sources)

3. **Option C**: Focus on photo analysis
   - Use Gemini Vision on restaurant photos
   - Extract dish names from visual content
   - Complement with user submissions

### API Endpoint Status

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/businesses/search` | ✅ Working | Restaurant search by name/location |
| `/businesses/{id}` | ✅ Working | Business details + photos |
| `/businesses/{id}/reviews` | ⚠️ Limited | Returns 404 for many businesses |

### Related Documentation

- [Yelp Fusion API Docs](https://docs.developer.yelp.com/docs/fusion-intro)
- [Yelp API Pricing](https://www.yelp.com/developers/faq)
- [Google Places API](https://developers.google.com/maps/documentation/places/web-service/overview)

## Questions to Investigate

1. **Does the Yelp API free tier include reviews access?**
   - Need to check official docs or contact Yelp support

2. **Are there rate limits on the reviews endpoint?**
   - Might be separate from general API limits

3. **Do all businesses have reviews accessible via API?**
   - Some might opt out of API access

4. **Is there a different endpoint for reviews?**
   - API might have changed since documentation was written

## Workaround Implementation Timeline

- ✅ **Phase 1**: Graceful error handling (COMPLETE)
  - Backend returns empty reviews list
  - Frontend shows helpful message
  - App continues to function

- 🔄 **Phase 2**: Photo-based dish extraction (FUTURE)
  - Use Gemini Vision on restaurant photos
  - Extract visible dish names
  - Alternative to text reviews

- 📋 **Phase 3**: Multi-source integration (FUTURE)
  - Add Google Places API
  - Aggregate from multiple sources
  - Build hybrid recommendation system

## Bottom Line

**The app works great without the Reviews API!**

The core value proposition remains:
- 🔍 Find restaurants easily
- 📸 View restaurant photos
- 📋 Upload and parse menus in any language
- 🌐 Get instant translations
- 💰 Handle native language prices

The popular dishes feature would be a nice-to-have, but isn't critical for the MVP. We can add it later when we find a reliable data source.
