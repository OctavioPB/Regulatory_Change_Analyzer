"""Regulatory RAG service — retrieval-augmented generation over regulatory documents."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from html import escape as _esc
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services import grounding, retrieval
from src.services.llm import get_client, response_text

logger = logging.getLogger(__name__)

# ── Retrieval config ──────────────────────────────────────────────────────────

_TOP_K_CHANGES  = 5   # regulatory change chunks to retrieve
_TOP_K_CLAUSES  = 3   # contract clause chunks to retrieve

# Grounded Q&A over a small retrieved context — medium (the Opus 5.5 default)
# is the right depth; set explicitly so a model change doesn't shift it silently.
_EFFORT = "medium"
_REFUSAL_ANSWER = "The model declined to answer this question."

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
    """Retrieve relevant context and ask Claude for a cited, validated answer.

    Nothing retrieved → the system refusal, without calling the model. An answer whose
    citations fail validation is regenerated once, then refused (see ``grounding``).

    Args:
        user_question: The compliance officer's natural-language question.
        db: Async database session.

    Returns:
        ChatResponse with answer text and structured citations.
    """
    chunks = await _retrieve(user_question, db)
    context_xml, citations = _build_context(chunks)

    if not settings.llm_enabled:
        return ChatResponse(
            answer="[LLM not configured] No ANTHROPIC_API_KEY set. Retrieved context:\n\n" + context_xml,
            citations=citations,
        )
    if not chunks:
        return ChatResponse(answer=grounding.refusal_text(user_question), citations=[])

    tags = _tags(chunks)
    messages = _messages(context_xml, user_question)
    tokens = 0
    for attempt in range(grounding.MAX_REGENERATIONS + 1):
        message = await get_client().messages.create(
            model=settings.llm_model,
            max_tokens=16000,  # thinking tokens count against this; 1024 truncated answers
            output_config={"effort": _EFFORT},
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        tokens += message.usage.input_tokens + message.usage.output_tokens
        if message.stop_reason == "refusal":
            return ChatResponse(answer=_REFUSAL_ANSWER, citations=[], tokens_used=tokens)
        answer = response_text(message)
        verdict = grounding.validate(answer, tags)
        if verdict.grounded:
            return ChatResponse(answer=answer, citations=citations, tokens_used=tokens)
        if not grounding.needs_regeneration(verdict) or attempt == grounding.MAX_REGENERATIONS:
            break
        messages = _retry(messages, answer, verdict, tags)
    return ChatResponse(answer=grounding.refusal_text(user_question), citations=[], tokens_used=tokens)


async def stream_query(
    user_question: str,
    db: AsyncSession,
) -> AsyncIterator[str]:
    """Stream the answer as Server-Sent Events.

    Yields SSE lines. Each event is a JSON string on a `data:` line.
    Event types:
      {"type": "citations", "citations": [...]} — retrieved sources (sent first, and again
                                                   as [] when the answer is replaced by a refusal)
      {"type": "token",     "text": "..."}      — partial answer token
      {"type": "reset"}                         — discard the text streamed so far: a corrected
                                                   answer or the system refusal follows
      {"type": "done", "grounded", "refused", "regenerations"} — stream finished
      {"type": "error",     "message": "..."}   — error (instead of done)

    Args:
        user_question: Compliance question.
        db: Async session.

    Yields:
        SSE-formatted strings.
    """
    chunks = await _retrieve(user_question, db)
    context_xml, _ = _build_context(chunks)

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

    if not settings.llm_enabled:
        fallback = (
            "[LLM not configured — set ANTHROPIC_API_KEY]\n\n"
            "Retrieved context snippet:\n\n"
            + "\n\n".join(f"[{c.chunk_type.upper()}-{c.ref_id}] {c.excerpt[:200]}" for c in chunks)
        )
        yield _sse("token", text=fallback)
        yield _sse("done")
        return

    if not chunks:  # nothing to ground an answer on: the system refuses, no model call
        yield _sse("token", text=grounding.refusal_text(user_question))
        yield _sse("done", grounded=False, refused=True, regenerations=0)
        return

    tags = _tags(chunks)
    messages = _messages(context_xml, user_question)
    try:
        for attempt in range(grounding.MAX_REGENERATIONS + 1):
            if attempt:
                yield _sse("reset")
            parts: list[str] = []
            async with get_client().messages.stream(
                model=settings.llm_model,
                max_tokens=16000,
                output_config={"effort": _EFFORT},
                system=_SYSTEM_PROMPT,
                messages=messages,
            ) as stream:
                async for text_chunk in stream.text_stream:
                    parts.append(text_chunk)
                    yield _sse("token", text=text_chunk)
                final = await stream.get_final_message()
            if final.stop_reason == "refusal":
                yield _sse("error", message=_REFUSAL_ANSWER)
                return
            answer = "".join(parts)
            verdict = grounding.validate(answer, tags)
            if verdict.grounded:
                yield _sse("done", grounded=True, refused=False, regenerations=attempt)
                return
            logger.info("RAG answer not grounded (attempt %d): %s", attempt + 1, verdict)
            if not grounding.needs_regeneration(verdict) or attempt == grounding.MAX_REGENERATIONS:
                break
            messages = _retry(messages, answer, verdict, tags)
    except Exception as exc:
        logger.exception("Claude streaming error")
        yield _sse("error", message=f"LLM request failed: {type(exc).__name__}")
        return

    yield _sse("reset")
    yield _sse("citations", citations=[])
    yield _sse("token", text=grounding.refusal_text(user_question))
    yield _sse("done", grounded=False, refused=True, regenerations=attempt)


def _tags(chunks: list[ContextChunk]) -> list[str]:
    return [f"{'REG' if c.chunk_type == 'regulation' else 'CON'}-{c.ref_id}" for c in chunks]


def _messages(context_xml: str, question: str) -> list[dict]:
    return [{"role": "user", "content": f"<context>\n{context_xml}\n</context>\n\n{question}"}]


def _retry(messages: list[dict], answer: str, verdict: grounding.Verdict, tags: list[str]) -> list[dict]:
    return messages + [
        {"role": "assistant", "content": answer or "(no answer)"},
        {"role": "user", "content": grounding.feedback(verdict, tags)},
    ]


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def _retrieve(query_text: str, db: AsyncSession) -> list[ContextChunk]:
    """Hybrid search (semantic + keyword, rank-fused) over regulatory changes and contract clauses."""

    async def fetch(sql: str, params: dict):
        return (await db.execute(text(sql), params)).fetchall()

    vec = await retrieval.query_vector(query_text)
    changes = await retrieval.search_changes(fetch, query_text, limit=_TOP_K_CHANGES, vec=vec)
    clauses = await retrieval.search_clauses(fetch, query_text, limit=_TOP_K_CLAUSES, vec=vec)

    chunks: list[ContextChunk] = []
    ref_id = 1

    for row in changes:
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

    for row in clauses:
        chunks.append(ContextChunk(
            ref_id=ref_id,
            chunk_type="contract",
            title=row.name,
            source=row.area or "Internal",
            article_ref=row.clause_ref or "—",
            excerpt=row.text[:500],
            publication_date=None,
        ))
        ref_id += 1

    logger.info(
        "RAG retrieved %d change chunks + %d clause chunks (%s) for query (%d chars)",
        len(changes), len(clauses), "hybrid" if vec is not None else "keyword", len(query_text),
    )
    return chunks


_keywords = retrieval.keywords  # kept for callers of the old name


# ── Context assembly ──────────────────────────────────────────────────────────

def _build_context(chunks: list[ContextChunk]) -> tuple[str, list[Citation]]:
    """Format chunks as XML context block and build citation list."""
    lines: list[str] = []
    citations: list[Citation] = []

    for c in chunks:
        if c.chunk_type == "regulation":
            tag = f'REG-{c.ref_id}'
            lines.append(
                f'<regulation ref="{tag}" source="{_esc(c.source)}" '
                f'title="{_esc(c.title)}" article="{_esc(c.article_ref)}" '
                f'date="{c.publication_date or "unknown"}">'
            )
            lines.append(c.excerpt)
            lines.append("</regulation>")
        else:
            tag = f'CON-{c.ref_id}'
            lines.append(
                f'<contract ref="{tag}" name="{_esc(c.title)}" '
                f'area="{_esc(c.source)}" clause="{_esc(c.article_ref)}">'
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
