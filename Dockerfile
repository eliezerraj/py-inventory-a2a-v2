# docker build -t py-inventory-v2-a2a .

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster cold starts
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first, leveraging Docker layer cache
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# Final Runtime Stage
FROM python:3.14-slim AS runner

WORKDIR /app

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appgroup /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OTEL_PYTHON_FASTAPI_EXCLUDED_URLS="/metrics" \
    OTEL_PYTHON_STARLETTE_EXCLUDED_URLS="/metrics" \
    OTEL_PYTHON_EXCLUDED_URLS="/metrics"

EXPOSE 7601
CMD ["python", "-m", "src.a2a_server.main"]