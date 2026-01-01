# Google Places API Setup Guide

This guide walks you through setting up Google Places API to replace Yelp for restaurant search and review data.

## Why Google Places API?

**Advantages over Yelp Free Tier:**
- ✅ **Review text included** (Yelp free tier doesn't have this!)
- ✅ **Generous free tier**: $200/month credit (~28,000 Place Details requests)
- ✅ **Up to 5 reviews per place** (Yelp only gives 3 even on paid plans)
- ✅ **Rich data**: Photos, ratings, hours, contact info
- ✅ **No special permissions needed** (Yelp requires paid plan for reviews)
- ✅ **Better coverage**: Comprehensive global database

**Cost Comparison:**
- Google Places: **FREE** with $200/month credit (enough for most apps)
- Yelp Reviews: **Paid plan required** (pricing varies, likely $100s/month)

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click **"Select a Project"** → **"New Project"**
4. Enter project name (e.g., "Menu AI App")
5. Click **"Create"**

### 2. Enable the Places API

1. In your project, go to **APIs & Services** → **Library**
2. Search for **"Places API"**
3. Click on **"Places API (New)"** (make sure it's the new version)
4. Click **"Enable"**

**Note**: You may also want to enable "Places API" (the legacy version) for compatibility, but the new version is recommended.

### 3. Create API Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **"API Key"**
3. Your API key will be generated (looks like: `AIzaSyA...`)
4. **IMPORTANT**: Click **"Restrict Key"** for security

### 4. Restrict Your API Key (Recommended)

For security, restrict your API key to only the APIs you need:

1. Click on your API key to edit it
2. Under **"API restrictions"**:
   - Select **"Restrict key"**
   - Check **"Places API (New)"**
   - Check **"Places API"** (legacy, for compatibility)
3. Under **"Application restrictions"** (optional):
   - For development: Select **"None"**
   - For production: Select **"HTTP referrers"** and add your domain
4. Click **"Save"**

### 5. Set Up Billing (Required for Free Tier)

Even though you get $200/month FREE credit, Google requires a billing account:

1. Go to **Billing** in the left menu
2. Click **"Link a Billing Account"**
3. Follow the prompts to add a credit card
4. ⚠️ **Don't worry**: You won't be charged unless you exceed the $200/month credit
5. Set up budget alerts (recommended):
   - Go to **Billing** → **Budgets & alerts**
   - Create a budget for $10-$20/month
   - Get email alerts if approaching limit

### 6. Configure Your App

1. Add the API key to your `.env` file:

```bash
cd menu-ai-app
nano .env  # or use any text editor
```

2. Add this line:

```bash
GOOGLE_PLACES_API_KEY=AIzaSyA_your_actual_api_key_here
```

3. Make sure you still have your Gemini API key:

```bash
GEMINI_API_KEY=your_gemini_key_here
```

### 7. Test the Integration

Run the test script to verify everything works:

```bash
cd menu-ai-app
export GOOGLE_PLACES_API_KEY='your_key_here'
export GEMINI_API_KEY='your_gemini_key_here'

python test_google_places.py
```

Expected output:
```
✅ Search successful!
✅ Place details retrieved!
✅ Reviews: 5 available (with review text!)
✅ Dish extraction: Working
```

## API Usage & Costs

### Free Tier Allowance

Google Cloud gives you **$200 in free credit every month**. Here's what you can do with it:

| Operation | Cost per Request | Requests with $200 Credit |
|-----------|------------------|---------------------------|
| Text Search | $0.032 | ~6,250 searches |
| Place Details (Basic) | $0.017 | ~11,700 details |
| Place Details (with reviews) | $0.017 + fields | ~10,000 details |
| Photos | $0.007 | ~28,500 photos |

### Estimated Usage for Menu AI App

**Per Restaurant Lookup:**
- 1x Text Search: $0.032
- 1x Place Details: $0.017
- 3x Photos: $0.021
- **Total**: ~$0.07 per restaurant

**Monthly Budget:**
- With $200 credit: ~**2,800 restaurant lookups/month**
- That's ~**90 lookups per day** for free!

### Optimizing Costs

1. **Implement Caching** (future enhancement):
   - Cache restaurant data for 7 days
   - Reduce API calls by 80%+
   - Increase capacity to ~14,000 lookups/month

2. **Request Only Needed Fields**:
   - Use the `fields` parameter to request specific data
   - Already implemented in our service

3. **Set Budget Alerts**:
   - Get notified if approaching limit
   - Prevent unexpected charges

## API Endpoints

Our implementation uses these Google Places endpoints:

### 1. Text Search
```
GET https://maps.googleapis.com/maps/api/place/textsearch/json
```
**Parameters:**
- `query`: Search query (e.g., "Tartine Bakery San Francisco")
- `key`: Your API key

**Returns:** List of matching places with basic info

### 2. Place Details
```
GET https://maps.googleapis.com/maps/api/place/details/json
```
**Parameters:**
- `place_id`: Google Place ID from search
- `fields`: Specific fields to retrieve (name, rating, reviews, etc.)
- `key`: Your API key

**Returns:** Detailed place info including reviews

### 3. Place Photos
```
GET https://maps.googleapis.com/maps/api/place/photo
```
**Parameters:**
- `photoreference`: Photo reference from place details
- `maxwidth`: Maximum photo width
- `key`: Your API key

**Returns:** Photo image (URL constructed in our service)

## Testing Different Restaurants

Try these test cases to verify your setup:

```bash
python test_google_places.py
```

The script tests:
1. **Tartine Bakery San Francisco** - Popular bakery with many reviews
2. **BCD Tofu House Los Angeles** - Korean restaurant
3. **Sun Nong Dan Los Angeles** - Another Korean spot

You should see:
- ✅ Search results with multiple places
- ✅ Detailed place information
- ✅ Reviews with actual text (unlike Yelp!)
- ✅ Popular dishes extracted from reviews

## Troubleshooting

### Error: "This API project is not authorized to use this API"

**Solution**: Enable the Places API in your project
1. Go to [API Library](https://console.cloud.google.com/apis/library)
2. Search "Places API (New)"
3. Click "Enable"

### Error: "The provided API key is invalid"

**Solution**: Check your API key
1. Make sure you copied the entire key
2. Verify it's not restricted to other IPs/domains
3. Try creating a new unrestricted key for testing

### Error: "REQUEST_DENIED"

**Possible causes:**
- Billing not set up (required even for free tier)
- API not enabled in your project
- API key restrictions too strict

**Solution**:
1. Enable billing (won't charge unless you exceed $200/month)
2. Double-check Places API is enabled
3. Temporarily remove API restrictions for testing

### Error: "OVER_QUERY_LIMIT"

**Cause**: You've exceeded your quota

**Solution**:
1. Check your usage in [Google Cloud Console](https://console.cloud.google.com/apis/dashboard)
2. Implement caching to reduce API calls
3. Increase budget if needed

### No Reviews Returned

**Possible causes:**
- Place doesn't have reviews
- Didn't request "reviews" field

**Solution**: Our implementation already requests reviews in the `fields` parameter. If no reviews, the place simply doesn't have any.

## Security Best Practices

### 1. Restrict Your API Key

Never use an unrestricted API key in production:

```
❌ Bad: Unrestricted key (anyone can use it)
✅ Good: Restricted to specific APIs and domains
```

### 2. Use Environment Variables

Never commit API keys to git:

```bash
# ✅ Good: .env file (in .gitignore)
GOOGLE_PLACES_API_KEY=your_key

# ❌ Bad: Hardcoded in code
api_key = "AIzaSyA..."
```

### 3. Set Up Budget Alerts

Prevent unexpected charges:
1. Go to [Billing → Budgets](https://console.cloud.google.com/billing/budgets)
2. Create budget alert for $10-20/month
3. Get email when approaching limit

### 4. Monitor Usage

Check your usage regularly:
1. Go to [APIs Dashboard](https://console.cloud.google.com/apis/dashboard)
2. View requests per day/month
3. Identify any unusual spikes

## Migrating from Yelp

If you were using Yelp before, here's how the data maps:

| Yelp Field | Google Places Field | Notes |
|------------|---------------------|-------|
| `name` | `name` | Same |
| `id` | `place_id` | Different format |
| `rating` | `rating` | Same scale (1-5) |
| `review_count` | `user_ratings_total` | Same concept |
| `price` | `price_level` | 0-4 scale vs $ symbols |
| `location` | `formatted_address` | Different format |
| `categories` | `types` | Different categorization |
| `photos` | `photos` | Google has more photos |
| `reviews` | `reviews` | ✅ Google includes text! |

## Next Steps

After setup, you can:

1. **Run the Test Script**:
   ```bash
   python test_google_places.py
   ```

2. **Start the App**:
   ```bash
   ./start-local.sh
   ```

3. **Test in Browser**:
   - Navigate to http://localhost:3000
   - Search for a restaurant
   - See reviews and popular dishes!

4. **Update Frontend** (if needed):
   - Frontend will need minor updates to use new `/api/v1/places` endpoints
   - See `GOOGLE_PLACES_FRONTEND.md` for details

## Comparison: Google Places vs Yelp

| Feature | Google Places (Free) | Yelp (Free) |
|---------|---------------------|-------------|
| **Search** | ✅ Unlimited | ✅ 500/day |
| **Business Details** | ✅ Yes | ✅ Yes |
| **Review Text** | ✅ **YES (up to 5)** | ❌ **NO (paid only)** |
| **Photos** | ✅ Many | ✅ Up to 3 |
| **Free Tier** | ✅ $200/month credit | ✅ 500 calls/day |
| **Cost After Free** | $0.017 per detail | Paid plan required |
| **Global Coverage** | ✅ Excellent | ⚠️ US-focused |

**Winner**: Google Places for this use case! 🏆

## Support & Resources

- [Google Places API Documentation](https://developers.google.com/maps/documentation/places/web-service/overview)
- [Pricing Calculator](https://mapsplatform.google.com/pricing/)
- [API Dashboard](https://console.cloud.google.com/apis/dashboard)
- [Support](https://developers.google.com/maps/support)

## Summary

✅ **Setup Complete!** You now have:
- Google Cloud project with Places API enabled
- API key configured in your app
- $200/month free credit (~2,800 restaurant lookups)
- Access to review text (unlike Yelp free tier!)
- Up to 5 reviews per restaurant
- Photo gallery support

Your Menu AI app can now search restaurants, display reviews, and extract popular dishes - all for free! 🎉
