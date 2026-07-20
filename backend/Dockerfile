# Backend image: FastAPI API + DBOS workers run in one process (see ROADMAP —
# DBOS Transact is in-process, so a single service is both API and worker).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependency layer first: cache survives source-only changes
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra aws

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra aws

FROM python:3.13-slim-bookworm
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
