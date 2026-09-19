"""Test setup: throwaway databases, and no accidental spending on the live API."""

import os
import sys
import tempfile

import pytest

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="menuist-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DATA_DIR, 'app.db')}"
os.environ["KNOWLEDGE_DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DATA_DIR, 'knowledge.db')}"
os.environ["AUTH_SECRET_KEY"] = "test-secret-key-not-for-production-use-000000"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings  # noqa: E402
from app.db.session import init_db  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def no_live_api_calls(request, monkeypatch):
    """Hide the real DeepSeek key from unit tests.

    A key in .env is picked up by ``settings``, and any code path that checks it — judging dish
    photos, extracting dishes from reviews — will then call the live API from a unit test. That
    spends tokens and makes results depend on the network. Tests that need a key set one
    themselves; the integration tests, which are meant to hit the real API, are left alone.
    """
    if request.node.get_closest_marker("integration"):
        return
    monkeypatch.setattr(settings, "deepseek_api_key", "")
