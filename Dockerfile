# BestBill API (stateless FastAPI). Build: docker build -t bestbill-api .
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --system --create-home --uid 10001 bestbill \
    && mkdir -p /tmp/bestbill-catalog \
    && chown bestbill /tmp/bestbill-catalog
USER bestbill

# Render injects PORT (default 10000). Shell form so ${PORT} expands.
EXPOSE 10000
CMD uvicorn bestbill.api.main:app --host 0.0.0.0 --port "${PORT:-10000}" --proxy-headers
