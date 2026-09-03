# Temporary Phase 1.3 smoke-test image. Build from the repo root:
#   docker build -f services/_hello/Dockerfile -t <tag> .
FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY config ./config
COPY packages ./packages
COPY services/_hello ./services/_hello

RUN uv sync --frozen --no-dev

ENV PORT=8080
CMD ["uv", "run", "uvicorn", "services._hello.main:app", "--host", "0.0.0.0", "--port", "8080"]
