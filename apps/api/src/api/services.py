"""
Builds the objects the API needs and hands them to the routes.

This is the one place that decides which implementation is used (fake or
Gemini provider, in-memory or Postgres storage). Routes receive a `Services`
through FastAPI's dependency injection and never construct anything
themselves, which also lets tests build an app with their own settings.
"""

import logging
from dataclasses import dataclass

from fastapi import Request
from psycopg_pool import ConnectionPool

from api.config import Settings
from api.graph.build import ChatAgent
from api.ingestion.pipeline import IngestionPipeline
from api.ingestion.registry import DocumentRegistry, InMemoryDocumentRegistry
from api.providers import build_providers
from api.rate_limit import Limits, build_limits
from api.sales.catalog import SalesCatalog
from api.sales.database import DuckDbSalesDatabase, SalesDatabase
from api.store.base import VectorStore
from api.store.memory import InMemoryVectorStore

logger = logging.getLogger(__name__)

# Must match `vector(...)` in postgres/schema.sql.
SCHEMA_EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class Services:
    settings: Settings
    registry: DocumentRegistry
    store: VectorStore
    sales_db: SalesDatabase
    pipeline: IngestionPipeline
    agent: ChatAgent
    limits: Limits
    sales_catalog: SalesCatalog
    pool: ConnectionPool | None = None

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()


def build_services(settings: Settings) -> Services:
    embedder, chat_model = build_providers(settings)
    registry, store, pool = _build_storage(settings)
    sales_db = _build_sales_db(settings, pool)
    return Services(
        settings=settings,
        registry=registry,
        store=store,
        sales_db=sales_db,
        pipeline=IngestionPipeline(settings, registry, embedder, store),
        agent=ChatAgent(settings, embedder, chat_model, store, sales_db),
        limits=build_limits(settings),
        sales_catalog=SalesCatalog(sales_db),
        pool=pool,
    )


def _build_sales_db(settings: Settings, pool: ConnectionPool | None) -> SalesDatabase:
    """The sales data lives next to the documents: Postgres if configured, else an embedded DuckDB file."""
    if pool is None:
        return DuckDbSalesDatabase(settings.sql_timeout_s)
    from api.postgres.sales_database import PostgresSalesDatabase

    return PostgresSalesDatabase(pool, settings.sql_timeout_s)


def _build_storage(settings: Settings) -> tuple[DocumentRegistry, VectorStore, ConnectionPool | None]:
    if settings.database_url is None:
        logger.info("No DATABASE_URL: keeping documents in memory (lost on restart)")
        return InMemoryDocumentRegistry(), InMemoryVectorStore(), None

    if settings.embedding_dimensions != SCHEMA_EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"EMBEDDING_DIMENSIONS must be {SCHEMA_EMBEDDING_DIMENSIONS} to match the database schema."
        )

    # Imported here so the in-memory setup doesn't need a database driver.
    from api.postgres import create_pool
    from api.postgres.document_registry import PostgresDocumentRegistry
    from api.postgres.vector_store import PostgresVectorStore

    pool = create_pool(settings.database_url.get_secret_value())
    registry = PostgresDocumentRegistry(pool)
    if fixed := registry.fail_interrupted():
        logger.info("Marked %d interrupted documents as failed", fixed)
    return registry, PostgresVectorStore(pool), pool


def get_services(request: Request) -> Services:
    return request.app.state.services
