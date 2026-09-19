"""Thin wrapper around the DeepSeek chat completions API (OpenAI-compatible).

All LLM calls in the backend go through ``LLMClient.generate`` so provider-specific
details (base URL, non-thinking mode, JSON mode quirks, image encoding) live in one place.

Example:
    >>> client = LLMClient(api_key="sk-...")
    >>> text = client.generate("Return a JSON object with key 'ok'", json_mode=True)
    >>> menu_json = client.generate(prompt, image_bytes=open("menu.jpg", "rb").read())
"""

import base64
import hashlib
import json
import logging
from contextvars import ContextVar
from typing import Optional

from openai import OpenAI

from app.core.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)

# Per-request token counters; the request-log middleware installs a fresh dict for each request.
_usage: ContextVar[dict[str, int] | None] = ContextVar("llm_usage", default=None)


def start_usage_tracking() -> dict[str, int]:
    usage = {"calls": 0, "cache_hits": 0, "prompt_tokens": 0, "completion_tokens": 0}
    _usage.set(usage)
    return usage


def _record_usage(field: str, amount: int = 1) -> None:
    usage = _usage.get()
    if usage is not None:
        usage[field] += amount


def data_url(image_bytes: bytes) -> str:
    """Inline an image as a base64 data URL, the form DeepSeek's chat API takes."""
    return f"data:{detect_image_mime(image_bytes)};base64,{base64.b64encode(image_bytes).decode('utf-8')}"


def detect_image_mime(image_bytes: bytes) -> str:
    """Detect image MIME type from magic bytes (DeepSeek accepts JPEG, PNG, GIF, WebP)."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class LLMClient:
    """DeepSeek multimodal client running in non-thinking mode.

    Attributes:
        model_name: DeepSeek model id (``deepseek-flash`` supports image input).
        max_tokens: Default cap on output tokens per request.
    """

    def __init__(
        self,
        api_key: str,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.model_name = model_name or settings.deepseek_model
        self.max_tokens = max_tokens or settings.deepseek_max_tokens
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or settings.deepseek_base_url,
            timeout=timeout_seconds or settings.deepseek_timeout_seconds,
        )

    def generate(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        images: Optional[list[bytes]] = None,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
        cache: bool = False,
        purpose: str = "",
    ) -> str:
        """Send a single-turn prompt (optionally with images) and return the text reply.

        Args:
            prompt: User prompt text. For ``json_mode`` it must mention "json" and
                show the expected object shape (DeepSeek requirement).
            image_bytes: Optional raw image bytes, sent inline as a base64 data URL.
            images: Several images instead of one, appended in order after the text so the
                prompt can refer to them by position ("photo 1", "photo 2", ...). DeepSeek
                accepts up to 600 images per request and caps each at 1024 tokens.
            json_mode: Request ``response_format=json_object``. Only use when the
                expected top-level value is an object, not an array.
            max_tokens: Override the default output token cap.
            cache: Reuse a stored response for the identical request. Only enable for prompts
                that contain no Google Places content (their terms forbid storing it).
            purpose: Short label saved with cached responses (e.g. "taste_round1").

        Returns:
            The model's reply text (may be empty string if the API returned nothing).
        """
        all_images = list(images) if images else []
        if image_bytes is not None:
            all_images.insert(0, image_bytes)

        output_cap = max_tokens or self.max_tokens
        cache_key = None
        if cache:
            cache_key = hashlib.sha256(json.dumps({
                "model": self.model_name,
                "prompt": prompt,
                "image": [hashlib.sha256(one).hexdigest() for one in all_images] or None,
                "json_mode": json_mode,
                "max_tokens": output_cap,
            }, sort_keys=True).encode("utf-8")).hexdigest()
            cached = cache_service.get_llm_response(cache_key)
            if cached:
                _record_usage("cache_hits")
                return cached

        if all_images:
            content = [{"type": "text", "text": prompt}]
            content += [{"type": "image_url", "image_url": {"url": data_url(one)}} for one in all_images]
        else:
            content = prompt

        request = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": output_cap,
            # Thinking is on by default for DeepSeek; disable it for fast, direct answers.
            "extra_body": {"thinking": {"type": "disabled"}},
        }

        text = ""
        if json_mode:
            response = self._create(
                **request, response_format={"type": "json_object"}
            )
            text = self._extract_text(response)
            if not text:
                # DeepSeek JSON mode can occasionally return empty content; retry in plain mode.
                logger.warning("DeepSeek JSON mode returned empty content; retrying without it")

        if not text:
            response = self._create(**request)
            text = self._extract_text(response)

        if cache_key and text and self._cacheable(response, text, json_mode):
            usage = getattr(response, "usage", None)
            cache_service.set_llm_response(
                cache_key, self.model_name, purpose, text,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            )
        return text

    @staticmethod
    def _cacheable(response, text: str, json_mode: bool) -> bool:
        """Never cache a cut-off answer or broken JSON; it would be served again for weeks."""
        choice = response.choices[0] if response.choices else None
        if choice is None or choice.finish_reason == "length":
            return False
        if json_mode:
            try:
                json.loads(text)
            except json.JSONDecodeError:
                return False
        return True

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ):
        """Multi-turn conversation, optionally with tools. Returns the raw assistant message.

        Unlike ``generate`` this is not cached and takes the full message list, because a
        conversation's meaning depends on everything said before it. The caller is responsible
        for appending the reply (and any ``role: "tool"`` results) before calling again.

        Args:
            messages: OpenAI-shaped messages, including ``system``, ``tool_calls`` and
                ``role: "tool"`` entries.
            tools: Tool schemas the model may call. DeepSeek uses the OpenAI shape.
            tool_choice: ``"auto"``, ``"none"``, or ``"required"``. ``"none"`` is how you force a
                written answer once the tool budget is spent.
            max_tokens: Override the default output token cap.

        Returns:
            The assistant message object: ``.content`` and, when it wants a tool, ``.tool_calls``.
        """
        request = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "extra_body": {"thinking": {"type": "disabled"}},
        }
        if tools:
            request["tools"] = tools
            if tool_choice:
                request["tool_choice"] = tool_choice

        response = self._create(**request)
        self._track_usage(response)
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return None
        if choice.finish_reason == "length":
            logger.warning("DeepSeek chat reply truncated at max_tokens")
        return choice.message

    def _create(self, **request):
        """The one place a request leaves for DeepSeek, so the site-wide budget sees every call.

        Raises ``DemoCapReached`` (a 429) once the demo's hourly or daily allowance is spent.
        """
        from app.core.rate_limit import claim_llm_call

        claim_llm_call()
        return self._client.chat.completions.create(**request)

    @staticmethod
    def _track_usage(response) -> None:
        _record_usage("calls")
        usage = getattr(response, "usage", None)
        if usage is not None:
            _record_usage("prompt_tokens", getattr(usage, "prompt_tokens", 0) or 0)
            _record_usage("completion_tokens", getattr(usage, "completion_tokens", 0) or 0)

    @classmethod
    def _extract_text(cls, response) -> str:
        cls._track_usage(response)
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return ""
        if choice.finish_reason == "length":
            logger.warning("DeepSeek response truncated at max_tokens")
        return (choice.message.content or "").strip()
