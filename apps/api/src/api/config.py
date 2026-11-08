"""
Settings read from environment variables (or a local `.env` file).

Every setting has a safe default, so the API starts with no configuration.
See `.env.example` for the full list.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Browser origins allowed to call the API. Comma-separated in the environment.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Which model provider to use. "fake" runs fully offline (tests, local dev).
    llm_provider: Literal["fake"] = "fake"

    # Uploads
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pages: int = 300

    # Chunking: target size and overlap, in characters.
    chunk_size: int = Field(default=1200, ge=200)
    chunk_overlap: int = Field(default=200, ge=0)

    # Retrieval
    top_k: int = Field(default=4, ge=1, le=20)
    # Chunks scoring below this are treated as "not found in your files".
    min_score: float = Field(default=0.08, ge=0, le=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
