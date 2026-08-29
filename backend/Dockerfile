# syntax=docker/dockerfile:1

FROM python:3.14.6-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

FROM base AS development

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

EXPOSE 8000
CMD ["uv", "run", "fastapi", "dev", "src/api/main.py", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS production

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-editable
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

USER app
EXPOSE 8000
CMD ["/app/.venv/bin/fastapi", "run", "src/api/main.py", "--host", "0.0.0.0", "--port", "8000"]
