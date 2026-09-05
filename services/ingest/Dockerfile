# Build from the repo root:
#   docker build -f services/ingest/Dockerfile -t <tag> .
FROM python:3.12-slim

# ffmpeg/ffprobe for video chunking (packages/gemini_client/video.py, PHASE_03.md §3.3).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY config ./config
COPY packages ./packages
COPY services/ingest ./services/ingest

RUN uv sync --frozen --no-dev

ENV PORT=8080
# Found live: without this, `uv run` re-checks and re-syncs the environment against the
# full (dev-inclusive) lockfile on every container cold start, downloading mypy/ruff/
# hypothesis/etc. and adding ~10s to every cold start for no reason — the image already
# has exactly the environment `uv sync --frozen --no-dev` produced above.
ENV UV_NO_SYNC=1
CMD ["uv", "run", "uvicorn", "services.ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]
