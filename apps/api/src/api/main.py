"""
FastAPI application.

Run locally:  uv run uvicorn api.main:app --reload
API docs:     http://localhost:8000/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings, get_settings
from api.routes import chat, documents, sales
from api.services import build_services


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    services = build_services(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        services.close()  # release database connections on shutdown

    app = FastAPI(title="Multisource AI Agent API", version="0.2.0", lifespan=lifespan)
    app.state.services = services

    # The browser calls this API directly from the frontend's origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(sales.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Someone opening the API's address in a browser gets pointers instead of "Not Found".
    frontend = next((o for o in settings.cors_origins if o.startswith("https://")), None)

    @app.get("/", tags=["meta"])
    def index() -> dict[str, str | None]:
        return {
            "name": "Multisource AI Agent API",
            "about": "Answers questions from uploaded documents (RAG) and a sample sales database (SQL agent).",
            "app": frontend,
            "docs": "/docs",
            "health": "/health",
            "source": "https://github.com/ionicbond12203/multisource-ai-agent",
        }

    return app


app = create_app()
