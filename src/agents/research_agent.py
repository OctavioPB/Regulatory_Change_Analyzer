"""Research agent — chat where Claude decides what to look up.

Unlike the classic RAG chat (retrieve once, answer once), the agent can chain
lookups: find the circular, read its full text, list the impacted contracts,
open a clause, check the SEC equivalent, then answer with citations.

SSE contract (consumed by ``frontend/src/pages/Chat.tsx`` in agent mode):
    {"type": "step", "id", "tool", "input", "status": "running"}
    {"type": "step", "id", "tool", "status": "ok"|"error", "summary"}
    {"type": "token", "text"}            — answer text (text before a step is the agent's note)
    {"type": "citations", "citations"}   — sources actually cited, ChatCitation shape
    {"type": "done", "turns", "usage"}   — or a single {"type": "error", "message"}
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.loop import Final, TextDelta, ToolCall, ToolResult, run_agent
from src.agents.tools import RESEARCH_TOOLS, AgentContext
from src.config import settings
from src.services import rag_service

logger = logging.getLogger(__name__)

MAX_TURNS = 10

SYSTEM_PROMPT = """You are a regulatory compliance research agent for a financial institution.
You answer compliance officers' questions about CNBV (Mexico) and SEC (US) regulation and how it
affects the institution's contracts and processes.

You have read-only tools over the institution's database of ingested regulatory changes, impact
alerts, internal contracts and cross-jurisdiction links. Look things up before answering: search,
then open the full text of the most relevant hits rather than relying on excerpts. Chain lookups
when the question needs it (e.g. a circular → its impact alert → the affected contract clauses →
the equivalent change in the other jurisdiction). Stop searching once you can answer.

Answer rules:
1. Ground every claim in tool results. Never invent regulatory content, dates or thresholds.
2. Cite with the `cite_as` tag of the result you rely on, in brackets: [REG-3], [CON-7].
3. If the database does not contain the answer, say so plainly and suggest consulting the source.
4. Call out high-severity items and pending reviews that need action.
5. Answer in the language of the question (English or Spanish). Be concise and structured."""


def _sse(event_type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs}, ensure_ascii=False, default=str)}\n\n"


async def stream_research(question: str, db: AsyncSession) -> AsyncIterator[str]:
    """Run the research agent and yield SSE events (see module docstring)."""
    if not settings.llm_enabled:
        # Agent mode needs Claude; fall back to the classic RAG stream, which
        # has its own no-key behaviour and the same token/citations/done events.
        async for chunk in rag_service.stream_query(question, db):
            yield chunk
        return

    ctx = AgentContext(db=db)
    try:
        async for event in run_agent(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
            tools=RESEARCH_TOOLS,
            ctx=ctx,
            max_turns=MAX_TURNS,
            effort="medium",
        ):
            if isinstance(event, TextDelta):
                yield _sse("token", text=event.text)
            elif isinstance(event, ToolCall):
                yield _sse("step", id=event.id, tool=event.name, input=event.input, status="running")
            elif isinstance(event, ToolResult):
                yield _sse("step", id=event.id, tool=event.name,
                           status="ok" if event.ok else "error", summary=event.summary)
            elif isinstance(event, Final):
                async for chunk in _finish(event, ctx):
                    yield chunk
                return
    except Exception as exc:
        logger.exception("Research agent failed")
        yield _sse("error", message=f"Agent request failed: {type(exc).__name__}")


async def _finish(final: Final, ctx: AgentContext) -> AsyncIterator[str]:
    if final.stop_reason == "refusal":
        yield _sse("error", message="The model declined to answer this question.")
        return
    if final.stop_reason == "max_turns":
        yield _sse("error", message=f"The agent hit its limit of {MAX_TURNS} steps without finishing. "
                                    "Try a narrower question.")
        return
    if not final.text.strip():
        yield _sse("error", message="The agent finished without writing an answer. Try rephrasing the question.")
        return
    if final.stop_reason == "max_tokens":
        yield _sse("token", text="\n\n[Answer truncated — output limit reached]")
    yield _sse("citations", citations=ctx.cited_in(final.text))
    yield _sse("done", turns=final.turns, usage={
        "input_tokens": final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
    })
