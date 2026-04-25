"""Regulatory RAG chat API — streaming and non-streaming endpoints."""
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import RequireViewer
from src.database import get_db
from src.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ── Request / response schemas ────────────────────────────────────────────────

class ChatQuery(BaseModel):
    query: str


class CitationOut(BaseModel):
    type: str
    ref_id: int
    title: str
    source: str
    article_ref: str
    excerpt: str
    publication_date: str | None = None


class ChatResponseOut(BaseModel):
    answer: str
    citations: list[CitationOut]
    tokens_used: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/query", response_model=ChatResponseOut, dependencies=[RequireViewer])
async def chat_query(
    body: ChatQuery,
    db: AsyncSession = Depends(get_db),
) -> ChatResponseOut:
    """Non-streaming RAG query. Returns the full answer and citations at once."""
    result = await rag_service.query(body.query, db)
    return ChatResponseOut(
        answer=result.answer,
        citations=[
            CitationOut(
                type=c.type,
                ref_id=c.ref_id,
                title=c.title,
                source=c.source,
                article_ref=c.article_ref,
                excerpt=c.excerpt,
                publication_date=c.publication_date,
            )
            for c in result.citations
        ],
        tokens_used=result.tokens_used,
    )


@router.post("/stream", dependencies=[RequireViewer])
async def chat_stream(
    body: ChatQuery,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Streaming RAG query via Server-Sent Events.

    Returns a text/event-stream where each line is:
        data: {"type": "token"|"citations"|"done"|"error", ...}
    """
    async def _generate() -> AsyncIterator[str]:
        async for chunk in rag_service.stream_query(body.query, db):
            yield chunk

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
