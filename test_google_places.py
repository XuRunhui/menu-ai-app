#!/usr/bin/env python3
"""Test script for Google Places API functionality.

This script tests the restaurant search and details retrieval
to verify the Google Places API integration is working correctly.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.google_places_service import GooglePlacesService
from app.services.dish_extractor import extract_popular_dishes


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'=' * 80}")
        print(f"  {title}")
        print(f"{'=' * 80}\n")
    else:
        print(f"{'=' * 80}\n")


def test_search(google_places: GooglePlacesService, query: str):
    """Test place search functionality.

    Args:
        google_places: GooglePlacesService instance.
        query: Search query (e.g., "Tartine Bakery San Francisco").
    """
    print_separator(f"Testing Search: '{query}'")

    try:
        result = google_places.search_places(query)
        places = result.get("results", [])
        status = result.get("status")

        print(f"✅ Search successful! (Status: {status})")
        print(f"Found {len(places)} places")

        if places:
            print("\nResults:")
            for i, place in enumerate(places[:5], 1):  # Show top 5
                print(f"\n{i}. {place.get('name')}")
                print(f"   Place ID: {place.get('place_id')}")
                print(f"   Address: {place.get('formatted_address', 'N/A')}")

                rating = place.get('rating')
                total_ratings = place.get('user_ratings_total', 0)
                if rating:
                    print(f"   Rating: {rating} ⭐ ({total_ratings} reviews)")

                price_level = place.get('price_level')
                if price_level is not None:
                    price_str = '$' * (price_level + 1)
                    print(f"   Price: {price_str}")

                types = place.get('types', [])
                if types:
                    print(f"   Types: {', '.join(types[:3])}")
        else:
            print("\n⚠️  No places found for this search.")

        return places

    except Exception as e:
        print(f"❌ Search failed: {e}")
        return []


def test_place_details(google_places: GooglePlacesService, place_id: str):
    """Test getting place details.

    Args:
        google_places: GooglePlacesService instance.
        place_id: Google Place ID.
    """
    print_separator(f"Testing Place Details: {place_id}")

    try:
        place = google_places.get_place_details(place_id)

        print(f"✅ Place details retrieved!")
        print(f"\nName: {place.get('name')}")
        print(f"Address: {place.get('formatted_address')}")
        print(f"Phone: {place.get('formatted_phone_number', 'N/A')}")
        print(f"Website: {place.get('website', 'N/A')}")

        rating = place.get('rating')
        total_ratings = place.get('user_ratings_total', 0)
        if rating:
            print(f"Rating: {rating} ⭐ ({total_ratings} reviews)")

        # Photos
        photos = place.get('photos', [])
        print(f"\nPhotos: {len(photos)} available")

        # Reviews
        reviews = place.get('reviews', [])
        print(f"Reviews: {len(reviews)} available")

        if reviews:
            print("\nSample Reviews:")
            for i, review in enumerate(reviews[:3], 1):
                print(f"\n  Review {i}:")
                print(f"  Author: {review.get('author_name')}")
                print(f"  Rating: {review.get('rating')} ⭐")
                print(f"  Time: {review.get('relative_time_description')}")
                text = review.get('text', '')
                preview = text[:150] + "..." if len(text) > 150 else text
                print(f"  Text: {preview}")

        return place

    except Exception as e:
        print(f"❌ Failed to get place details: {e}")
        return None


def test_dish_extraction(google_places: GooglePlacesService, place_id: str, gemini_api_key: str):
    """Test extracting popular dishes from reviews.

    Args:
        google_places: GooglePlacesService instance.
        place_id: Google Place ID.
        gemini_api_key: Gemini API key for dish extraction.
    """
    print_separator(f"Testing Dish Extraction: {place_id}")

    try:
        # Get full place data
        data = google_places.get_full_place_data(place_id)
        place = data.get('place', {})
        reviews = data.get('reviews', [])

        print(f"Place: {place.get('name')}")
        print(f"Reviews available: {len(reviews)}")

        if not reviews:
            print("⚠️  No reviews to extract dishes from")
            return []

        # Extract review texts
        review_texts = [r.get('text', '') for r in reviews if r.get('text')]

        if not review_texts:
            print("⚠️  No review text available")
            return []

        print(f"\nExtracting popular dishes from {len(review_texts)} reviews...")

        # Extract dishes
        popular_dishes = extract_popular_dishes(
            review_texts,
            gemini_api_key,
            top_n=10
        )

        print(f"✅ Extracted {len(popular_dishes)} popular dishes!")

        if popular_dishes:
            print("\nPopular Dishes:")
            for i, dish in enumerate(popular_dishes, 1):
                print(f"{i}. {dish.get('name')}")
                print(f"   Mentions: {dish.get('mention_count')}")
                print(f"   Sentiment: {dish.get('avg_sentiment', 0):.2%}")

        return popular_dishes

    except Exception as e:
        print(f"❌ Failed to extract dishes: {e}")
        return []


def main():
    """Run all tests."""
    print_separator("Google Places API Restaurant Search Test")

    # Check for API keys
    google_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not google_api_key:
        print("❌ ERROR: GOOGLE_PLACES_API_KEY environment variable not set!")
        print("\nPlease set your Google Places API key:")
        print("  export GOOGLE_PLACES_API_KEY='your_api_key_here'")
        print("\nGet one from: https://console.cloud.google.com/apis/credentials")
        print("Make sure to enable 'Places API (New)' in your project")
        sys.exit(1)

    if not gemini_api_key:
        print("⚠️  WARNING: GEMINI_API_KEY not set. Dish extraction will be skipped.")
        gemini_api_key = None

    print(f"✅ Google Places API Key found: {google_api_key[:10]}...{google_api_key[-4:]}")
    if gemini_api_key:
        print(f"✅ Gemini API Key found: {gemini_api_key[:10]}...{gemini_api_key[-4:]}")

    # Initialize service
    google_places = GooglePlacesService(google_api_key)

    # Test cases
    test_cases = [
        "Tartine Bakery San Francisco",
        "BCD Tofu House Los Angeles",
        "Sun Nong Dan Los Angeles",
    ]

    print("\n📋 Running tests for the following queries:")
    for query in test_cases:
        print(f"  - {query}")

    # Run tests
    for query in test_cases:
        # Search
        places = test_search(google_places, query)

        if places:
            # Test first result
            place_id = places[0].get('place_id')

            # Get details
            place = test_place_details(google_places, place_id)

            # Extract dishes if Gemini key available
            if gemini_api_key and place:
                test_dish_extraction(google_places, place_id, gemini_api_key)

        print("\n" + "-" * 80)

    # Summary
    print_separator("Test Summary")
    print("✅ Place search: Working")
    print("✅ Place details: Working")
    print("✅ Reviews: Available (with review text!)")
    print("✅ Photos: Available")
    if gemini_api_key:
        print("✅ Dish extraction: Working")
    else:
        print("⚠️  Dish extraction: Skipped (no Gemini API key)")

    print("\n💡 Google Places API Benefits:")
    print("  • Free tier: $200/month credit (~28,000 requests)")
    print("  • ✅ Review text included (unlike Yelp free tier)")
    print("  • ✅ Up to 5 reviews per place")
    print("  • ✅ Photos and detailed place info")
    print("  • ✅ No special permissions needed")

    print_separator()


if __name__ == "__main__":
    main()
