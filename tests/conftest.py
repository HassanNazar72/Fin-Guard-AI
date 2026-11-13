import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.fake_gemini import FakeGeminiClient  # noqa: E402
from backend.main import app, get_llm_client, get_rate_limiter  # noqa: E402
from backend.pipeline import load_sample_csv, prepare_statement  # noqa: E402
from backend.rate_limit import RateLimiter  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_api_key(monkeypatch):
    """Guarantee the suite can never reach the real Gemini API."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def sample_csv() -> str:
    return load_sample_csv()


@pytest.fixture
def statement(sample_csv):
    return prepare_statement(sample_csv)


@pytest.fixture
def toolbox(statement):
    return statement.toolbox


@pytest.fixture
def fake_client() -> FakeGeminiClient:
    return FakeGeminiClient()


@pytest.fixture
def limiter() -> RateLimiter:
    return RateLimiter(limit=10, global_limit=500)


@pytest.fixture
def api(fake_client, limiter):
    """TestClient wired to the FakeGeminiClient and a fresh rate limiter."""
    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def api_without_key(limiter):
    app.dependency_overrides[get_llm_client] = lambda: None
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
