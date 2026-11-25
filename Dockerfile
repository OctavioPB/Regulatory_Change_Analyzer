FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build deps for lxml / asyncpg wheels that lack a prebuilt binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Embeddings come from Ollama (bge-m3) by default, so torch is not installed.
# `--build-arg EXTRAS=ml` adds sentence-transformers (CPU-only torch, not the ~2 GB CUDA wheel).
ARG EXTRAS=""
RUN if [ "$EXTRAS" = "ml" ]; then pip install --index-url https://download.pytorch.org/whl/cpu torch; fi

# Install dependencies in their own layer so code edits don't reinstall them.
# (The previous `pip install -e .` ran before src/ existed, so the package
# itself could not be built.)
COPY pyproject.toml README.md ./
COPY src ./src
RUN if [ -n "$EXTRAS" ]; then pip install ".[$EXTRAS]"; else pip install .; fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
