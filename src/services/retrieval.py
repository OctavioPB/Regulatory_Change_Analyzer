"""Hybrid retrieval over regulatory changes and contract clauses (shared by RAG chat and agent tools).

Two arms, fused by rank (Legal_AI_Assistant / Library-RAG):

* **semantic** — cosine over pgvector embeddings (bge-m3 is multilingual, so an English question
  reaches a Spanish circular), filtered by a calibrated floor (``CHANGE_MIN_SIM``, ``CLAUSE_MIN_SIM``) so an unrelated question
  does not pull the nearest-but-irrelevant rows;
* **lexical** — keyword ILIKE, ranked by how many of the question's keywords a row contains.

Reciprocal-rank fusion (k=60) uses ranks only, never raw scores, and breaks ties by id so a run is
reproducible. With embeddings unavailable the semantic arm is empty and this is keyword search.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from src.mapping.embedder import vector_literal

logger = logging.getLogger(__name__)

Fetch = Callable[[str, dict], Awaitable[Sequence[Any]]]

RRF_K = 60
ARM_TOP = 20
# bge-m3 cosine floors, measured 2026-11-25 on the eval corpus (9 eval questions + 6 unrelated
# probes in es/en): a covered question puts its article at 0.577-0.853, unrelated questions top
# out at 0.50 against any article; for clauses relevant hits reach 0.51-0.58 and unrelated ones
# 0.535. Below the floor a row can still come in through the keyword arm.
CHANGE_MIN_SIM = 0.52
CLAUSE_MIN_SIM = 0.55

_STOPWORDS = {
    "what", "which", "when", "where", "does", "have", "with", "about", "that", "this",
    "there", "their", "from", "into", "should", "would", "could", "need", "changed",
    "cuál", "cuáles", "qué", "como", "cómo", "para", "sobre", "esta", "este", "tiene",
}


def keywords(query_text: str, limit: int = 6) -> list[str]:
    """Meaningful words of a question: punctuation stripped, stopwords dropped."""
    seen: list[str] = []
    for w in re.findall(r"\w+", query_text.lower()):
        if len(w) > 3 and w not in _STOPWORDS and w not in seen:
            seen.append(w)
    return seen[:limit]


def patterns(query_text: str) -> list[str]:
    # \w includes "_", an ILIKE single-char wildcard — escape it (backslash is the default escape)
    return [f"%{w.replace('_', chr(92) + '_')}%" for w in keywords(query_text)]


def rrf(arms: Sequence[Sequence[Any]], *, key: Callable[[Any], str], k: int = RRF_K) -> list[Any]:
    """Reciprocal-rank fusion: rank-only, ties broken by ``key`` for determinism."""
    scores: dict[str, float] = {}
    first: dict[str, Any] = {}
    for arm in arms:
        for rank, row in enumerate(arm, 1):
            kk = key(row)
            scores[kk] = scores.get(kk, 0.0) + 1.0 / (k + rank)
            first.setdefault(kk, row)
    return [first[kk] for kk in sorted(scores, key=lambda kk: (-scores[kk], kk))]


async def query_vector(query_text: str) -> list[float] | None:
    """Embedding of the question, or None when no backend is available (never raises)."""
    from src.mapping import embedder

    if not await asyncio.to_thread(embedder.available):
        return None
    try:
        return await asyncio.to_thread(embedder.embed_text, query_text)
    except Exception as exc:
        logger.warning("Query embedding failed (%s) — keyword search only", exc)
        return None


# ── Regulatory changes ────────────────────────────────────────────────────────

_CHANGE_COLS = """rc.id, rc.article_ref, rc.change_type, rc.summary, rc.new_text,
                  rd.title AS doc_title, rd.source, rd.publication_date"""


async def search_changes(fetch: Fetch, query_text: str, *, limit: int, source: str | None = None,
                         vec: list[float] | None = None) -> list[Any]:
    vec = vec if vec is not None else await query_vector(query_text)
    src_filter = "AND upper(rd.source) = :source" if source else ""
    semantic: Sequence[Any] = []
    if vec is not None:
        semantic = await fetch(
            f"""
            SELECT {_CHANGE_COLS}
            FROM regulatory_changes rc JOIN regulatory_documents rd ON rd.id = rc.document_id
            WHERE rc.embedding IS NOT NULL {src_filter}
              AND 1 - (rc.embedding <=> CAST(:vec AS vector)) >= :min_sim
            ORDER BY rc.embedding <=> CAST(:vec AS vector), rc.id
            LIMIT :top
            """,
            {"vec": vector_literal(vec), "min_sim": CHANGE_MIN_SIM, "top": ARM_TOP, "source": source},
        )
    lexical: Sequence[Any] = []
    if pats := patterns(query_text):
        lexical = await fetch(
            f"""
            SELECT * FROM (
                SELECT {_CHANGE_COLS},
                       (SELECT count(*) FROM unnest(CAST(:patterns AS text[])) AS p
                         WHERE rc.new_text ILIKE p OR rc.summary ILIKE p OR rd.title ILIKE p) AS hits
                FROM regulatory_changes rc JOIN regulatory_documents rd ON rd.id = rc.document_id
                WHERE true {src_filter}
            ) ranked
            WHERE hits > 0
            ORDER BY hits DESC, publication_date DESC, id
            LIMIT :top
            """,
            {"patterns": pats, "top": ARM_TOP, "source": source},
        )
    return rrf([semantic, lexical], key=lambda r: str(r.id))[:limit]


# ── Contract clauses ──────────────────────────────────────────────────────────

_CLAUSE_COLS = "cc.id, cc.clause_ref, cc.text, c.name, c.area"


async def search_clauses(fetch: Fetch, query_text: str, *, limit: int, contract_name: str | None = None,
                         vec: list[float] | None = None) -> list[Any]:
    vec = vec if vec is not None else await query_vector(query_text)
    name_filter = "AND c.name ILIKE :name" if contract_name else ""
    name = f"%{contract_name}%" if contract_name else None
    semantic: Sequence[Any] = []
    if vec is not None:
        semantic = await fetch(
            f"""
            SELECT {_CLAUSE_COLS}
            FROM contract_clauses cc JOIN contracts c ON c.id = cc.contract_id
            WHERE cc.embedding IS NOT NULL {name_filter}
              AND 1 - (cc.embedding <=> CAST(:vec AS vector)) >= :min_sim
            ORDER BY cc.embedding <=> CAST(:vec AS vector), cc.id
            LIMIT :top
            """,
            {"vec": vector_literal(vec), "min_sim": CLAUSE_MIN_SIM, "top": ARM_TOP, "name": name},
        )
    lexical: Sequence[Any] = []
    if pats := patterns(query_text):
        lexical = await fetch(
            f"""
            SELECT * FROM (
                SELECT {_CLAUSE_COLS},
                       (SELECT count(*) FROM unnest(CAST(:patterns AS text[])) AS p
                         WHERE cc.text ILIKE p OR c.name ILIKE p) AS hits
                FROM contract_clauses cc JOIN contracts c ON c.id = cc.contract_id
                WHERE true {name_filter}
            ) ranked
            WHERE hits > 0
            ORDER BY hits DESC, id
            LIMIT :top
            """,
            {"patterns": pats, "top": ARM_TOP, "name": name},
        )
    return rrf([semantic, lexical], key=lambda r: str(r.id))[:limit]
