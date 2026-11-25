"""Text embeddings — Ollama (default: bge-m3, multilingual es/en) or sentence-transformers.

``settings.embedding_provider`` picks the backend:

* ``ollama`` — ``POST {ollama_url}/api/embed`` with ``settings.embedding_model`` (default ``bge-m3``,
  1024 dims, 8192-token window). No torch needed. Multilingual, so an English question finds a
  Spanish circular (the keyword arm cannot).
* ``sentence-transformers`` — local model through the optional ``[ml]`` extra. This is the only
  module that imports it.
* ``none`` — embeddings off: rules-only mapping and keyword retrieval.

Callers must keep working when embeddings are unavailable: check :func:`available` and treat
any exception from ``embed_*`` as "no vector". A vector whose length differs from
``settings.embedding_dim`` (the pgvector column size) raises instead of being stored.
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_PROBE_TTL_S = 60.0          # how long an availability probe is trusted
_probe: tuple[float, bool] | None = None
_schema_ok = True            # set by check_schema(); a dimension mismatch disables embeddings


class EmbeddingsUnavailable(RuntimeError):
    pass


def available() -> bool:
    """Whether embeddings can be produced now (cached for a minute; never raises)."""
    global _probe
    if settings.embedding_provider == "none" or not _schema_ok:
        return False
    now = time.monotonic()
    if _probe and now - _probe[0] < _PROBE_TTL_S:
        return _probe[1]
    ok = _probe_backend()
    _probe = (now, ok)
    return ok


def reset_probe() -> None:
    global _probe
    _probe = None


def _probe_backend() -> bool:
    if settings.embedding_provider == "sentence-transformers":
        from importlib.util import find_spec
        return find_spec("sentence_transformers") is not None
    try:
        r = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=2.0)
        r.raise_for_status()
        names = {m.get("name", "") for m in r.json().get("models", [])}
    except Exception as exc:
        logger.warning("Ollama embeddings unavailable at %s (%s)", settings.ollama_url, exc)
        return False
    wanted = settings.embedding_model
    ok = wanted in names or f"{wanted}:latest" in names
    if not ok:
        logger.warning("Embedding model %s not pulled in Ollama (ollama pull %s)", wanted, wanted)
    return ok


def embed_text(text: str) -> list[float]:
    """Embed one text (normalised, ``settings.embedding_dim`` floats)."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed several texts in one call."""
    if not texts:
        return []
    if settings.embedding_provider == "none":
        raise EmbeddingsUnavailable("embedding_provider is 'none'")
    if settings.embedding_provider == "sentence-transformers":
        vectors = _st_encode(texts)
    else:
        vectors = _ollama_embed(texts)
    for v in vectors:
        if len(v) != settings.embedding_dim:
            raise EmbeddingsUnavailable(
                f"{settings.embedding_model} returned {len(v)} dims, the schema expects "
                f"{settings.embedding_dim} (set EMBEDDING_DIM and re-embed)"
            )
    return vectors


def _ollama_embed(texts: list[str]) -> list[list[float]]:
    # truncate=False: an input past the model window fails loudly instead of being cut silently
    r = httpx.post(
        f"{settings.ollama_url.rstrip('/')}/api/embed",
        json={"model": settings.embedding_model, "input": texts, "truncate": False},
        timeout=120.0,
    )
    if r.status_code >= 400:
        raise EmbeddingsUnavailable(f"Ollama /api/embed {r.status_code}: {r.text[:200]}")
    return r.json()["embeddings"]  # already L2-normalised by Ollama


@lru_cache(maxsize=1)
def _st_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover — depends on the install
        raise EmbeddingsUnavailable(
            "sentence-transformers needs the optional ML dependencies: pip install -e \".[ml]\""
        ) from exc
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def _st_encode(texts: list[str]) -> list[list[float]]:
    vectors = _st_model().encode(
        texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=64, show_progress_bar=False
    )
    return [v.tolist() for v in vectors]


def vector_literal(vec) -> str:
    """pgvector text literal for a list or numpy array, every component written out.

    ``str(numpy_array)`` elides the middle of arrays over 1000 items ("[a b ... z]"), which
    broke queries once bge-m3's 1024-dim vectors replaced all-MiniLM's 384.
    """
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


# ── Schema guard ──────────────────────────────────────────────────────────────

EMBEDDING_COLUMNS = (("regulatory_changes", "embedding"), ("contract_clauses", "embedding"))


async def check_schema(conn) -> dict[str, int]:
    """Compare the pgvector column sizes with ``settings.embedding_dim``.

    A mismatch (e.g. a database created for all-MiniLM's 384 dims, now configured for bge-m3's
    1024) disables embeddings instead of failing every insert: run ``alembic upgrade head`` and
    ``python scripts/reembed.py`` to switch.
    """
    from sqlalchemy import text

    global _schema_ok
    dims: dict[str, int] = {}
    for table, column in EMBEDDING_COLUMNS:
        row = (await conn.execute(text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = CAST(:t AS regclass) AND attname = :c AND NOT attisdropped"
        ), {"t": table, "c": column})).first()
        if row is not None:
            dims[table] = int(row[0])
    wrong = {t: d for t, d in dims.items() if d != settings.embedding_dim}
    _schema_ok = not wrong
    if wrong:
        logger.error(
            "Embedding columns %s do not match EMBEDDING_DIM=%d — embeddings disabled. "
            "Run `alembic upgrade head` then `python scripts/reembed.py`.", wrong, settings.embedding_dim,
        )
    return dims
