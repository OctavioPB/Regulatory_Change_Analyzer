"""Regulatory RAG service — retrieval-augmented generation over regulatory documents."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

import anthropic
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.document import RegulatoryChange, RegulatoryDocument

logger = logging.getLogger(__name__)

# ── Retrieval config ──────────────────────────────────────────────────────────

_TOP_K_CHANGES  = 5   # regulatory change chunks to retrieve
_TOP_K_CLAUSES  = 3   # contract clause chunks to retrieve
_MIN_SIM        = 0.35 # minimum cosine similarity to include a chunk

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a regulatory compliance assistant for a financial institution.
Your role is to help compliance officers understand how new regulations affect their contracts,
policies, and processes.

RULES:
1. Base your answer ONLY on the <context> provided. Never invent or assume regulatory content.
2. Cite every claim using [REG-N] for regulatory changes or [CON-N] for contract clauses.
3. If the context doesn't contain enough information to answer, say exactly:
   "The documents in the system don't contain sufficient information about this topic. I recommend consulting the original source directly."
4. Highlight HIGH SEVERITY items that require immediate action.
5. Be precise about thresholds, dates, and article references.
6. Answer in the same language as the question (English or Spanish)."""

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Citation:
    """A source document referenced in the answer."""
    type: str           # "regulation" | "contract"
    ref_id: int         # [REG-N] or [CON-N] index shown in answer
    title: str          # document or contract name
    source: str         # "CNBV" | "SEC" | contract area
    article_ref: str    # "Article 5" or "Clause 4.2"
    excerpt: str        # the retrieved chunk text (truncated)
    publication_date: str | None = None


@dataclass
class ChatResponse:
    """Full (non-streaming) RAG answer."""
    answer: str
    citations: list[Citation]
    tokens_used: int = 0


@dataclass
class ContextChunk:
    ref_id: int
    chunk_type: str  # "regulation" | "contract"
    title: str
    source: str
    article_ref: str
    excerpt: str
    publication_date: str | None = None


# ── Public API ────────────────────────────────────────────────────────────────

async def query(user_question: str, db: AsyncSession) -> ChatResponse:
    """Retrieve relevant context and ask Claude for a cited answer.

    Args:
        user_question: The compliance officer's natural-language question.
        db: Async database session.

    Returns:
        ChatResponse with answer text and structured citations.
    """
    chunks = await _retrieve(user_question, db)
    context_xml, citations = _build_context(chunks)

    if not settings.anthropic_api_key:
        return ChatResponse(
            answer="[LLM not configured] No ANTHROPIC_API_KEY set. Retrieved context:\n\n" + context_xml,
            citations=citations,
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"<context>\n{context_xml}\n</context>\n\n{user_question}"},
        ],
    )
    answer = message.content[0].text if message.content else ""
    tokens = message.usage.input_tokens + message.usage.output_tokens

    return ChatResponse(answer=answer, citations=citations, tokens_used=tokens)


async def stream_query(
    user_question: str,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Stream the Claude response as Server-Sent Events.

    Yields SSE lines. Each event is a JSON string on a `data:` line.
    Event types:
      {"type": "token",     "text": "..."}   — partial answer token
      {"type": "citations", "citations": [...]} — final citations payload
      {"type": "done"}                          — stream finished
      {"type": "error",     "message": "..."}  — error

    Args:
        user_question: Compliance question.
        db: Async session.

    Yields:
        SSE-formatted strings.
    """
    chunks = await _retrieve(user_question, db)
    context_xml, citations = _build_context(chunks)

    # Send citations immediately so the UI can render them while text streams
    cit_payload = [
        {
            "type": c.chunk_type,
            "ref_id": c.ref_id,
            "title": c.title,
            "source": c.source,
            "article_ref": c.article_ref,
            "excerpt": c.excerpt[:300],
            "publication_date": c.publication_date,
        }
        for c in chunks
    ]
    yield _sse("citations", citations=cit_payload)

    if not settings.anthropic_api_key:
        fallback = (
            "[LLM not configured — set ANTHROPIC_API_KEY]\n\n"
            "Retrieved context snippet:\n\n"
            + "\n\n".join(f"[{c.chunk_type.upper()}-{c.ref_id}] {c.excerpt[:200]}" for c in chunks)
        )
        yield _sse("token", text=fallback)
        yield _sse("done")
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        with client.messages.stream(
            model=settings.llm_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"<context>\n{context_xml}\n</context>\n\n{user_question}",
                }
            ],
        ) as stream:
            for text_chunk in stream.text_stream:
                yield _sse("token", text=text_chunk)
    except Exception as exc:
        logger.error("Claude streaming error: %s", exc)
        yield _sse("error", message=str(exc))
        return

    yield _sse("done")


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def _retrieve(query_text: str, db: AsyncSession) -> list[ContextChunk]:
    """Embed query, vector-search regulatory changes and contract clauses.

    Falls back to ILIKE full-text search when no embeddings are available.
    """
    changes: list = []
    clauses: list = []

    try:
        from src.mapping.embedder import embed_text as _embed
        query_vec = _embed(query_text)
        changes = await _search_changes(db, query_vec)
        clauses = await _search_clauses(db, query_vec)
    except Exception as exc:
        logger.warning("Vector search failed (%s) — falling back to text search", exc)

    # Text fallback when vector search returns nothing
    if not changes and not clauses:
        changes = await _text_search_changes(db, query_text)

    chunks: list[ContextChunk] = []
    ref_id = 1

    for row in changes[:_TOP_K_CHANGES]:
        pub_date = row.publication_date.strftime("%Y-%m-%d") if row.publication_date else None
        chunks.append(ContextChunk(
            ref_id=ref_id,
            chunk_type="regulation",
            title=row.doc_title,
            source=row.source,
            article_ref=row.article_ref or "—",
            excerpt=(row.new_text or row.summary or "")[:500],
            publication_date=pub_date,
        ))
        ref_id += 1

    for row in clauses[:_TOP_K_CLAUSES]:
        chunks.append(ContextChunk(
            ref_id=ref_id,
            chunk_type="contract",
            title=row.contract_name,
            source=row.contract_area or "Internal",
            article_ref=row.clause_ref or "—",
            excerpt=row.clause_text[:500],
            publication_date=None,
        ))
        ref_id += 1

    logger.info(
        "RAG retrieved %d change chunks + %d clause chunks for query (%d chars)",
        len(changes), len(clauses), len(query_text),
    )
    return chunks


async def _search_changes(db: AsyncSession, query_vec: list[float]):
    """Vector search over regulatory_changes that have embeddings."""
    stmt = text(
        """
        SELECT
            rc.article_ref,
            rc.summary,
            rc.new_text,
            rd.title  AS doc_title,
            rd.source,
            rd.publication_date,
            1 - (rc.embedding <=> CAST(:vec AS vector)) AS sim
        FROM regulatory_changes rc
        JOIN regulatory_documents rd ON rd.id = rc.document_id
        WHERE rc.embedding IS NOT NULL
          AND 1 - (rc.embedding <=> CAST(:vec AS vector)) >= :min_sim
        ORDER BY rc.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )
    result = await db.execute(stmt, {"vec": str(query_vec), "min_sim": _MIN_SIM, "top_k": _TOP_K_CHANGES})
    return result.fetchall()


async def _search_clauses(db: AsyncSession, query_vec: list[float]):
    """Vector search over contract_clauses that have embeddings."""
    stmt = text(
        """
        SELECT
            cc.clause_ref,
            cc.text  AS clause_text,
            c.name   AS contract_name,
            c.area   AS contract_area,
            1 - (cc.embedding <=> CAST(:vec AS vector)) AS sim
        FROM contract_clauses cc
        JOIN contracts c ON c.id = cc.contract_id
        WHERE cc.embedding IS NOT NULL
          AND 1 - (cc.embedding <=> CAST(:vec AS vector)) >= :min_sim
        ORDER BY cc.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )
    result = await db.execute(stmt, {"vec": str(query_vec), "min_sim": _MIN_SIM, "top_k": _TOP_K_CLAUSES})
    return result.fetchall()


async def _text_search_changes(db: AsyncSession, query_text: str):
    """ILIKE fallback: search regulatory_changes.summary when no embeddings exist."""
    words = [w.strip() for w in query_text.split() if len(w.strip()) > 3][:5]
    if not words:
        return []

    stmt = text(
        """
        SELECT
            rc.article_ref,
            rc.summary,
            rc.new_text,
            rd.title  AS doc_title,
            rd.source,
            rd.publication_date,
            0.5       AS sim
        FROM regulatory_changes rc
        JOIN regulatory_documents rd ON rd.id = rc.document_id
        WHERE rc.summary ILIKE :pattern
           OR rd.title   ILIKE :pattern
        ORDER BY rd.publication_date DESC
        LIMIT :top_k
        """
    )
    pattern = f"%{words[0]}%"
    result = await db.execute(stmt, {"pattern": pattern, "top_k": _TOP_K_CHANGES})
    return result.fetchall()


# ── Context assembly ──────────────────────────────────────────────────────────

def _build_context(chunks: list[ContextChunk]) -> tuple[str, list[Citation]]:
    """Format chunks as XML context block and build citation list."""
    lines: list[str] = []
    citations: list[Citation] = []

    for c in chunks:
        if c.chunk_type == "regulation":
            tag = f'REG-{c.ref_id}'
            lines.append(
                f'<regulation ref="{tag}" source="{c.source}" '
                f'title="{c.title}" article="{c.article_ref}" '
                f'date="{c.publication_date or "unknown"}">'
            )
            lines.append(c.excerpt)
            lines.append("</regulation>")
        else:
            tag = f'CON-{c.ref_id}'
            lines.append(
                f'<contract ref="{tag}" name="{c.title}" '
                f'area="{c.source}" clause="{c.article_ref}">'
            )
            lines.append(c.excerpt)
            lines.append("</contract>")

        citations.append(Citation(
            type=c.chunk_type,
            ref_id=c.ref_id,
            title=c.title,
            source=c.source,
            article_ref=c.article_ref,
            excerpt=c.excerpt[:300],
            publication_date=c.publication_date,
        ))

    return "\n".join(lines), citations


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(event_type: str, **kwargs) -> str:
    payload = {"type": event_type, **kwargs}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
