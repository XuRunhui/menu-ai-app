"""Unit tests for MultiSourceAggregator aggregation logic."""

import os
import sys

import pytest

pytest.importorskip("requests")
pytest.importorskip("ddgs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.data_collection.multi_source_aggregator import MultiSourceAggregator  # noqa: E402


def test_aggregate_results_partial_failure():
    """Aggregate results with partial failures."""
    aggregator = MultiSourceAggregator()

    results = [
        {
            "source": "Google Places",
            "success": True,
            "data": {
                "place": {},
                "reviews": [{"text": "Amazing ramen", "rating": 5}],
                "popular_dishes": [{"name": "Ramen", "mention_count": 2}]
            }
        },
        {
            "source": "DuckDuckGo",
            "success": True,
            "data": {
                "reviews": [{"text": "Great ramen", "url": "https://review.test/1"}],
                "images": [{"url": "https://img.test/photo2.jpg"}]
            }
        },
        {
            "source": "Yelp",
            "success": False,
            "data": None,
            "error": "Business not found"
        }
    ]

    aggregated = aggregator._aggregate_results(results)
    assert aggregated["metadata"]["successful_sources"] == 2
    assert len(aggregated["metadata"]["failed_sources"]) == 1
    assert "Google Places" in aggregated["sources"]
    assert "DuckDuckGo" in aggregated["sources"]
    assert len(aggregated["reviews"]) == 2


def test_aggregate_results_deduplication():
    """Deduplicate reviews and images across sources."""
    aggregator = MultiSourceAggregator()

    results = [
        {
            "source": "Google Places",
            "success": True,
            "data": {
                "place": {},
                "reviews": [{"text": "Amazing ramen with rich broth"}],
                "popular_dishes": []
            }
        },
        {
            "source": "DuckDuckGo",
            "success": True,
            "data": {
                "reviews": [{"text": "Amazing ramen with rich broth"}],
                "images": [{"url": "https://img.test/photo1.jpg"}]
            }
        }
    ]

    aggregated = aggregator._aggregate_results(results)
    assert len(aggregated["reviews"]) == 1
    assert len(aggregated["images"]) == 1


def test_aggregate_results_yelp_photos():
    """Include Yelp photos in aggregated images."""
    aggregator = MultiSourceAggregator()

    results = [
        {
            "source": "Yelp",
            "success": True,
            "data": {
                "photos": ["https://img.test/yelp1.jpg", "https://img.test/yelp2.jpg"]
            }
        }
    ]

    aggregated = aggregator._aggregate_results(results)
    urls = [image.get("url") for image in aggregated["images"]]
    assert "https://img.test/yelp1.jpg" in urls
    assert "https://img.test/yelp2.jpg" in urls
