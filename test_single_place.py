#!/usr/bin/env python3
"""Quick test for a single place search."""

import os
import sys
from pathlib import Path

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.google_places_service import GooglePlacesService

api_key = os.getenv("GOOGLE_PLACES_API_KEY")
if not api_key:
    print("Error: GOOGLE_PLACES_API_KEY not set")
    sys.exit(1)

google_places = GooglePlacesService(api_key)

print("Testing exact address matching:\n")

# Test 1: Name + Full Address (most precise)
print("Test 1: Name + Full Address")
print("Query: 'Sun Nong Dan 3470 W 6th St Los Angeles CA'\n")
result = google_places.search_places("Sun Nong Dan 3470 W 6th St Los Angeles CA")

print(f"Status: {result['status']}")
print(f"Results: {len(result['results'])}\n")

# if result['results']:
if False:
    for i, place in enumerate(result['results'], 1):
        print(f"{i}. {place['name']}")
        print(f"   Address: {place.get('formatted_address')}")
        print(f"   Rating: {place.get('rating')} ({place.get('user_ratings_total')} reviews)")
        print()
else:
    print("No results found with exact address")
    print("\nTrying fallback search...")

    # Test 2: Name + City (broader search)
    result = google_places.search_places("Sun Nong Dan Los Angeles", use_exact_match=False)

print(f"Status: {result['status']}")
print(f"Results: {len(result['results'])}\n")

if result['results']:
    for i, place in enumerate(result['results'], 1):
        print(f"{i}. {place['name']}")
        print(f"   Address: {place.get('formatted_address')}")
        print(f"   Rating: {place.get('rating')} ({place.get('user_ratings_total')} reviews)")
        print()
else:
    print("No results found")
    print(f"This might be due to:")
    print("- Rate limiting (too many requests too quickly)")
    print("- The restaurant name not matching exactly")
    print("- Temporary API issue")
