# Build from the repo root:
#   docker build -f services/reverify_worker/Dockerfile -t <tag> .
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY config ./config
COPY packages ./packages
COPY services/reverify_worker ./services/reverify_worker

RUN uv sync --frozen --no-dev

ENV PORT=8080
# See services/ingest/Dockerfile — without this, `uv run` re-syncs against the full
# (dev-inclusive) lockfile on every cold start.
ENV UV_NO_SYNC=1
CMD ["uv", "run", "uvicorn", "services.reverify_worker.main:app", "--host", "0.0.0.0", "--port", "8080"]
