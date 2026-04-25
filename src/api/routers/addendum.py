"""Addendum drafting API — streaming LLM draft + PDF/DOCX export."""
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import RequireViewer
from src.database import get_db
from src.services import addendum_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/addendum", tags=["addendum"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExportBody(BaseModel):
    draft_text: str
    title: str
    format: str  # "pdf" | "docx"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/draft/{alert_id}", dependencies=[RequireViewer])
async def draft_addendum(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a Claude-generated addendum for the given alert as SSE.

    Event types:
      {"type": "meta",  "contract_name": "...", "doc_title": "..."}
      {"type": "token", "text": "..."}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    async def _generate() -> AsyncIterator[str]:
        async for chunk in addendum_service.stream_draft(str(alert_id), db):
            yield chunk

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/export", dependencies=[RequireViewer])
async def export_addendum(body: ExportBody) -> Response:
    """Export draft text as PDF or DOCX binary."""
    if body.format == "docx":
        data = addendum_service.export_docx(body.draft_text, body.title)
        return Response(
            content=data,
            media_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            headers={"Content-Disposition": 'attachment; filename="addendum.docx"'},
        )
    data = addendum_service.export_pdf(body.draft_text, body.title)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="addendum.pdf"'},
    )
