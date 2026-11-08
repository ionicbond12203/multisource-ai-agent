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
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.gemini_thinking_level is None


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
