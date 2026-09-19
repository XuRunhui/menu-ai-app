"""Unit tests for YelpCollector."""

import os
import sys

import pytest

requests = pytest.importorskip("requests")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.data_collection.yelp_collector import (  # noqa: E402
    YelpCollector,
    YELP_SEARCH_URL,
    YELP_DETAILS_URL
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


def test_yelp_collector_with_valid_key(monkeypatch):
    """Collector returns business data when API calls succeed."""
    def fake_get(url, headers=None, params=None, timeout=10):
        if url == YELP_SEARCH_URL:
            return _FakeResponse(
                {
                    "businesses": [
                        {
                            "id": "test-business",
                            "name": "Test Bistro",
                            "rating": 4.5,
                            "review_count": 120
                        }
                    ]
                }
            )
        if url == f"{YELP_DETAILS_URL}/test-business":
            return _FakeResponse(
                {
                    "id": "test-business",
                    "name": "Test Bistro",
                    "rating": 4.5,
                    "review_count": 120,
                    "photos": ["url1", "url2", "url3"]
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    collector = YelpCollector(api_key="test-key")
    result = collector.collect_all("Test Bistro", "SF")

    assert result["success"] is True
    assert result["business"]["id"] == "test-business"
    assert len(result["photos"]) == 3


def test_yelp_collector_without_key():
    """Collector fails gracefully without API key."""
    collector = YelpCollector(api_key=None)
    result = collector.collect_all("Any Place", "Anywhere")
    assert result["success"] is False
    assert result["error"] == "Business not found"


def test_yelp_collector_restaurant_not_found(monkeypatch):
    """Collector returns not found when search yields no results."""
    def fake_get(url, headers=None, params=None, timeout=10):
        if url == YELP_SEARCH_URL:
            return _FakeResponse({"businesses": []})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    collector = YelpCollector(api_key="test-key")
    result = collector.collect_all("Missing Place", "SF")

    assert result["success"] is False
    assert result["error"] == "Business not found"


def test_yelp_collector_network_error(monkeypatch):
    """Collector handles network errors gracefully."""
    def fake_get(url, headers=None, params=None, timeout=10):
        raise requests.exceptions.RequestException("network error")

    monkeypatch.setattr(requests, "get", fake_get)
    collector = YelpCollector(api_key="test-key")
    result = collector.collect_all("Test Bistro", "SF")

    assert result["success"] is False
    assert result["error"] == "Business not found"
