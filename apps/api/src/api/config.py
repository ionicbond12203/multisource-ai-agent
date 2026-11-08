"""
Settings read from environment variables (or a local `.env` file).

Every setting has a safe default, so the API starts with no configuration and
runs fully offline. See `.env.example` for the full list.
"""

from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Browser origins allowed to call the API. Comma-separated in the environment.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Model provider. "fake" runs offline with no key; "gemini" needs GEMINI_API_KEY.
    llm_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: SecretStr | None = None
    gemini_chat_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    # How hard the chat model thinks before answering. Empty = the model's default.
    gemini_thinking_level: str | None = "low"

    # Vector size. Must match the `vector(...)` column in postgres/schema.sql.
    embedding_dimensions: int = 768

    # Postgres (e.g. Supabase) connection string. Empty = keep everything in memory.
    database_url: SecretStr | None = None

    # Uploads
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pages: int = 300

    # Chunking: target size and overlap, in characters.
    chunk_size: int = Field(default=1200, ge=200)
    chunk_overlap: int = Field(default=200, ge=0)

    # Sales database (SQL agent): row cap added to every query, and the query timeout.
    sql_max_rows: int = Field(default=200, ge=1, le=1000)
    sql_timeout_s: float = Field(default=5.0, gt=0, le=30)

    # Retrieval
    top_k: int = Field(default=4, ge=1, le=20)
    # Chunks scoring below this are treated as "not found in your files".
    # Real embeddings score unrelated text higher than the fake ones, so the
    # Gemini default is higher; see `effective_min_score`.
    min_score: float | None = Field(default=None, ge=0, le=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("gemini_api_key", "database_url", "gemini_thinking_level", "min_score", mode="before")
    @classmethod
    def empty_means_unset(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def check_provider_key(self) -> Self:
        if self.llm_provider == "gemini" and self.gemini_api_key is None:
            raise ValueError(
                "LLM_PROVIDER=gemini needs GEMINI_API_KEY. Get one at https://aistudio.google.com/apikey"
            )
        return self

    @property
    def effective_min_score(self) -> float:
        if self.min_score is not None:
            return self.min_score
        return 0.55 if self.llm_provider == "gemini" else 0.08


@lru_cache
def get_settings() -> Settings:
    return Settings()
