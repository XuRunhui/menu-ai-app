#!/usr/bin/env python3
"""
Demo script: Fetch dish images from DuckDuckGo Search

This script demonstrates how to search for dish-specific images using
DuckDuckGo's image search API via the duckduckgo-search library.

Usage:
    python demo_ddgs_images.py

Requirements:
    pip install duckduckgo-search
"""

import json
from duckduckgo_search import DDGS


def search_dish_images(restaurant_name: str, dish_name: str, max_results: int = 10):
    """
    Search for dish images using DuckDuckGo.

    Args:
        restaurant_name: Name of the restaurant (e.g., "BCD Tofu House")
        dish_name: Name of the dish (e.g., "Soon Tofu Jjigae")
        max_results: Maximum number of images to fetch (default: 10)

    Returns:
        List of image dictionaries with URLs and metadata

    Example:
        >>> images = search_dish_images("Tartine Bakery", "Croissant", max_results=5)
        >>> print(f"Found {len(images)} images")
        Found 5 images
    """
    # Initialize DuckDuckGo Search
    ddgs = DDGS()

    # Build search query
    # Format: "{restaurant} {dish} food" gives best results
    query = f"{restaurant_name} {dish_name} food"

    print(f"🔍 Searching DuckDuckGo for: '{query}'")
    print(f"📊 Max results: {max_results}\n")

    try:
        # Search for images
        results = ddgs.images(
            keywords=query,
            max_results=max_results,
            # Optional filters:
            # size="Medium",  # Small, Medium, Large, Wallpaper
            # type_image="photo",  # photo, clipart, gif, transparent, line
            # layout="Square",  # Square, Tall, Wide
            # color="color"  # color, Monochrome, Red, Orange, Yellow, etc.
        )

        # Convert generator to list
        images = list(results)

        print(f"✅ Found {len(images)} images\n")

        return images

    except Exception as e:
        print(f"❌ Error searching DuckDuckGo: {e}")
        return []


def display_image_info(images: list, verbose: bool = False):
    """
    Display information about fetched images.

    Args:
        images: List of image dictionaries from DuckDuckGo
        verbose: Whether to show full details (default: False)
    """
    if not images:
        print("No images to display.")
        return

    print("=" * 80)
    print("IMAGE RESULTS")
    print("=" * 80)

    for i, img in enumerate(images, 1):
        print(f"\n📸 Image #{i}")
        print(f"   Title: {img.get('title', 'N/A')[:60]}...")
        print(f"   URL: {img.get('image', 'N/A')[:70]}...")
        print(f"   Thumbnail: {img.get('thumbnail', 'N/A')[:70]}...")
        print(f"   Source: {img.get('source', 'N/A')[:50]}...")
        print(f"   Width: {img.get('width', 'N/A')} px")
        print(f"   Height: {img.get('height', 'N/A')} px")

        if verbose:
            print(f"\n   Full data:")
            print(f"   {json.dumps(img, indent=2)}")

    print("\n" + "=" * 80)


def save_image_urls(images: list, output_file: str = "dish_images.json"):
    """
    Save image URLs to a JSON file.

    Args:
        images: List of image dictionaries
        output_file: Path to output JSON file
    """
    # Extract useful information
    simplified = [
        {
            "title": img.get("title", ""),
            "image_url": img.get("image", ""),
            "thumbnail_url": img.get("thumbnail", ""),
            "source_url": img.get("source", ""),
            "width": img.get("width"),
            "height": img.get("height"),
        }
        for img in images
    ]

    with open(output_file, "w") as f:
        json.dump(simplified, f, indent=2)

    print(f"💾 Saved {len(simplified)} image URLs to '{output_file}'")


def demo_multiple_dishes():
    """
    Demo: Search for images of multiple dishes from different restaurants.
    """
    print("\n" + "=" * 80)
    print("DEMO: Multiple Dish Image Search")
    print("=" * 80 + "\n")

    # Test cases: (restaurant, dish)
    test_cases = [
        ("BCD Tofu House", "Soon Tofu Jjigae"),
        ("Tartine Bakery", "Morning Bun"),
        ("Joe's Pizza", "Pepperoni Slice"),
        ("Sushi Gen", "Omakase"),
    ]

    all_results = {}

    for restaurant, dish in test_cases:
        print(f"\n{'─' * 80}")
        print(f"🍽️  Restaurant: {restaurant}")
        print(f"🥘 Dish: {dish}")
        print(f"{'─' * 80}")

        # Search for images
        images = search_dish_images(restaurant, dish, max_results=5)

        # Store results
        all_results[f"{restaurant} - {dish}"] = images

        # Display summary
        if images:
            print(f"\n📊 Sample results:")
            for i, img in enumerate(images[:3], 1):
                print(f"   {i}. {img.get('title', 'No title')[:50]}...")

    return all_results


def demo_single_dish():
    """
    Demo: Detailed search for a single dish.
    """
    print("\n" + "=" * 80)
    print("DEMO: Single Dish Image Search (Detailed)")
    print("=" * 80 + "\n")

    # Example: Korean restaurant dish
    restaurant = "BCD Tofu House"
    dish = "Soon Tofu Jjigae"

    # Search for images
    images = search_dish_images(restaurant, dish, max_results=10)

    # Display detailed information
    display_image_info(images, verbose=False)

    # Save to file
    if images:
        save_image_urls(images, f"images_{dish.replace(' ', '_').lower()}.json")

    return images


def demo_query_variations():
    """
    Demo: Test different query formats to see which gives best results.
    """
    print("\n" + "=" * 80)
    print("DEMO: Query Format Comparison")
    print("=" * 80 + "\n")

    restaurant = "Tartine Bakery"
    dish = "Country Bread"

    # Test different query formats
    queries = [
        f"{restaurant} {dish}",  # Basic
        f"{restaurant} {dish} food",  # With "food"
        f"{dish} {restaurant}",  # Reversed order
        f"{dish} from {restaurant}",  # Natural language
        f'"{restaurant}" "{dish}"',  # Quoted
    ]

    results = {}

    for query in queries:
        print(f"\n🔍 Testing query: '{query}'")

        ddgs = DDGS()
        try:
            images = list(ddgs.images(keywords=query, max_results=5))
            results[query] = len(images)
            print(f"   ✅ Found {len(images)} images")

            # Show first result
            if images:
                print(f"   📸 First result: {images[0].get('title', 'N/A')[:50]}...")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            results[query] = 0

    # Summary
    print(f"\n{'─' * 80}")
    print("SUMMARY: Results by query format")
    print(f"{'─' * 80}")
    for query, count in results.items():
        print(f"  {count:2d} images | '{query}'")

    best_query = max(results, key=results.get)
    print(f"\n🏆 Best query format: '{best_query}' ({results[best_query]} images)")

    return results


def demo_filter_options():
    """
    Demo: Show how to use different filter options.
    """
    print("\n" + "=" * 80)
    print("DEMO: Image Filter Options")
    print("=" * 80 + "\n")

    restaurant = "Sushi Gen"
    dish = "Sashimi"
    query = f"{restaurant} {dish} food"

    ddgs = DDGS()

    # Test different filters
    filters = [
        {"size": "Medium"},
        {"type_image": "photo"},
        {"layout": "Square"},
        {"size": "Large", "type_image": "photo"},
    ]

    for i, filter_opts in enumerate(filters, 1):
        print(f"\n🔧 Filter #{i}: {filter_opts}")

        try:
            images = list(ddgs.images(keywords=query, max_results=5, **filter_opts))
            print(f"   ✅ Found {len(images)} images")

            if images:
                first = images[0]
                print(f"   📸 First result: {first.get('width')}x{first.get('height')} px")

        except Exception as e:
            print(f"   ❌ Error: {e}")


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🦆 DuckDuckGo Image Search Demo")
    print("=" * 80)

    # Run different demos
    choice = input(
        """
Choose a demo to run:

1. Single dish (detailed)
2. Multiple dishes (summary)
3. Query format comparison
4. Filter options
5. All demos

Enter choice (1-5): """
    ).strip()

    if choice == "1":
        demo_single_dish()

    elif choice == "2":
        demo_multiple_dishes()

    elif choice == "3":
        demo_query_variations()

    elif choice == "4":
        demo_filter_options()

    elif choice == "5":
        print("\n🚀 Running all demos...\n")
        demo_single_dish()
        demo_multiple_dishes()
        demo_query_variations()
        demo_filter_options()

    else:
        print("\n❌ Invalid choice. Running demo #1 (single dish)...\n")
        demo_single_dish()

    print("\n" + "=" * 80)
    print("✅ Demo complete!")
    print("=" * 80 + "\n")


# =============================================================================
# EXAMPLE OUTPUT STRUCTURE
# =============================================================================
"""
Example of what each image dictionary contains:

{
  "title": "Soon Tofu Jjigae - Spicy Korean Soft Tofu Stew",
  "image": "https://example.com/path/to/full-size-image.jpg",
  "thumbnail": "https://example.com/path/to/thumbnail.jpg",
  "url": "https://example.com/source-page",
  "height": 1200,
  "width": 1600,
  "source": "example.com"
}

Available fields:
- title: Image title/description
- image: Full-size image URL (direct link to JPG/PNG)
- thumbnail: Thumbnail URL (smaller version)
- url: Source webpage URL
- height: Image height in pixels
- width: Image width in pixels
- source: Source domain
"""


# =============================================================================
# USAGE IN YOUR RAG SYSTEM
# =============================================================================
"""
How to integrate this into your app:

1. In data collection phase:

   from duckduckgo_search import DDGS

   def collect_dish_images(restaurant_name, dish_names, images_per_dish=5):
       ddgs = DDGS()
       all_images = {}

       for dish in dish_names:
           query = f"{restaurant_name} {dish} food"
           images = list(ddgs.images(query, max_results=images_per_dish))
           all_images[dish] = images

       return all_images

2. In classification phase:

   from app.services.recommendation.dish_photo_classifier import DishPhotoClassifier

   classifier = DishPhotoClassifier(gemini_api_key)

   for dish_name, images in all_images.items():
       # Classify each image
       for img in images:
           classification = await classifier.classify_photo(
               img["image"],
               dish_list=[dish_name]
           )

           if classification["confidence"] > 0.7:
               # High confidence match!
               dish_photo_map[dish_name] = img["image"]
               break

3. In API response:

   {
       "dish_name": "Soon Tofu Jjigae",
       "confidence": 0.94,
       "dish_photo": {
           "url": "https://example.com/tofu.jpg",
           "source": "duckduckgo",
           "thumbnail": "https://example.com/tofu_thumb.jpg"
       }
   }
"""
