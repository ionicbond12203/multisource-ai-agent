from pathlib import Path

import pytest
from pydantic import ValidationError

from api.config import Settings


def test_defaults_run_offline():
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "fake"
    assert settings.database_url is None


def test_gemini_needs_a_key():
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings(llm_provider="gemini", gemini_api_key=None, _env_file=None)


def test_empty_values_mean_unset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "")
    monkeypatch.setenv("MIN_SCORE", "")
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.gemini_thinking_level is None
    assert settings.min_score is None


def test_env_example_loads():
    # Copying .env.example unchanged must give a working configuration.
    settings = Settings(_env_file=Path(__file__).parent.parent / ".env.example")
    assert settings.llm_provider == "fake"


def test_cors_origins_are_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://demo.vercel.app")
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000", "https://demo.vercel.app"]


def test_min_score_default_depends_on_provider():
    assert Settings(_env_file=None).effective_min_score == 0.08
    gemini = Settings(llm_provider="gemini", gemini_api_key="k", _env_file=None)
    assert gemini.effective_min_score == 0.55
    assert Settings(min_score=0.3, _env_file=None).effective_min_score == 0.3


def test_secrets_are_hidden_in_logs():
    settings = Settings(llm_provider="gemini", gemini_api_key="secret-key", _env_file=None)
    assert "secret-key" not in repr(settings)


def test_api_root_points_to_the_app_and_docs(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import create_app

    settings = Settings(cors_origins="http://localhost:3000,https://demo.vercel.app", _env_file=None)
    body = TestClient(create_app(settings)).get("/").json()
    assert body["app"] == "https://demo.vercel.app"
    assert body["docs"] == "/docs"
