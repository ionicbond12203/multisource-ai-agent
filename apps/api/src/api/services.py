"""
Builds the objects the API needs and hands them to the routes.

This is the one place that decides which implementation is used (fake or real
provider, in-memory or Postgres store). Routes receive a `Services` through
FastAPI's dependency injection and never construct anything themselves, which
also lets tests build an app with their own settings.
"""

from dataclasses import dataclass

from fastapi import Request

from api.config import Settings
from api.graph.build import ChatAgent
from api.ingestion.pipeline import IngestionPipeline
from api.ingestion.registry import DocumentRegistry
from api.providers import build_providers
from api.store.memory import InMemoryVectorStore


@dataclass(frozen=True)
class Services:
    settings: Settings
    registry: DocumentRegistry
    pipeline: IngestionPipeline
    agent: ChatAgent


def build_services(settings: Settings) -> Services:
    embedder, chat_model = build_providers(settings)
    store = InMemoryVectorStore()
    registry = DocumentRegistry()
    return Services(
        settings=settings,
        registry=registry,
        pipeline=IngestionPipeline(settings, registry, embedder, store),
        agent=ChatAgent(settings, embedder, chat_model, store),
    )


def get_services(request: Request) -> Services:
    return request.app.state.services
