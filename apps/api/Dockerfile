# Production image for the API.
#   docker build -t multisource-api .
#   docker run -p 8000:8000 multisource-api
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first, in their own layer, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

# Don't run as root.
RUN useradd --create-home app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# Hosting platforms such as Render pass the port in $PORT.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
