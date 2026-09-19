"""Unit tests for the DeepSeek LLMClient wrapper."""

import os
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("openai")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.llm_client import LLMClient, detect_image_mime  # noqa: E402


class _FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self._replies.pop(0)
        message = SimpleNamespace(content=text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _client_with(replies):
    client = LLMClient(api_key="test-key", model_name="deepseek-flash")
    completions = _FakeCompletions(replies)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return client, completions


def test_generate_disables_thinking():
    client, completions = _client_with(["hello"])
    assert client.generate("hi") == "hello"
    call = completions.calls[0]
    assert call["model"] == "deepseek-flash"
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert call["messages"][0]["content"] == "hi"
    assert "response_format" not in call


def test_generate_with_image_sends_data_url():
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    client, completions = _client_with(["{}"])
    client.generate("read menu", image_bytes=png)
    parts = completions.calls[0]["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "read menu"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_json_mode_retries_without_format_on_empty_content():
    client, completions = _client_with(["", '{"ok": true}'])
    assert client.generate("return json", json_mode=True) == '{"ok": true}'
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in completions.calls[1]


def test_detect_image_mime():
    assert detect_image_mime(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert detect_image_mime(b"GIF89a....") == "image/gif"
    assert detect_image_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"


def test_menu_item_tolerates_null_lists_and_bad_spice_levels():
    from app.models.menu import MenuItem

    item = MenuItem(name="Classic", dietary_tags=None, allergens=None, spicy_level="very")
    assert item.dietary_tags == [] and item.allergens == [] and item.spicy_level is None
    assert MenuItem(name="Hot", spicy_level=9).spicy_level is None
    assert MenuItem(name="Mild", spicy_level=2).spicy_level == 2


def test_truncated_or_invalid_json_responses_are_not_cached(monkeypatch):
    from app.services import cache_service

    stored = []
    monkeypatch.setattr(cache_service, "get_llm_response", lambda key: None)
    monkeypatch.setattr(cache_service, "set_llm_response", lambda *args, **kwargs: stored.append(args))

    client, completions = _client_with(['{"cut": "off'])
    completions.create_finish = "length"
    original = completions.create

    def truncated(**kwargs):
        response = original(**kwargs)
        response.choices[0].finish_reason = "length"
        return response

    completions.create = truncated
    client.generate("json please", json_mode=True, cache=True)
    assert stored == []

    client, _ = _client_with(["not json at all"])
    client.generate("json please", json_mode=True, cache=True)
    assert stored == []

    client, _ = _client_with(['{"ok": true}'])
    client.generate("json please", json_mode=True, cache=True)
    assert len(stored) == 1


def test_api_keys_are_stripped_of_whitespace(monkeypatch):
    from app.core.config import Settings

    settings = Settings(deepseek_api_key="sk-test\n", google_places_api_key="  AIzaTest  ")
    assert settings.deepseek_api_key == "sk-test"
    assert settings.google_places_api_key == "AIzaTest"
