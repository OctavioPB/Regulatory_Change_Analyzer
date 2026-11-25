"""Agentic endpoints — tool-using research chat and the multi-agent drafting team.

Both spend noticeably more tokens than their single-call counterparts
(``/chat/stream``, ``/addendum/draft``), so both require analyst+.
"""
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents import addendum_team, research_agent
from src.api.routers.chat import ChatQuery
from src.auth.dependencies import RequireAnalyst
from src.database import get_db

router = APIRouter(prefix="/agents", tags=["agents"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse_response(gen: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/chat", dependencies=[RequireAnalyst])
async def agent_chat(body: ChatQuery, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Research agent: Claude chains database lookups before answering (SSE).

    Events: step · token · citations · done | error — see ``src/agents/research_agent.py``.
    """
    return _sse_response(research_agent.stream_research(body.query, db))


@router.post("/addendum/{alert_id}", dependencies=[RequireAnalyst])
async def agent_addendum(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Drafting team: one drafting subagent per contract + reviewer loop (SSE).

    Events: plan · agent · review · draft · done | error — see ``src/agents/addendum_team.py``.
    """
    return _sse_response(addendum_team.stream_team_draft(str(alert_id), db))
