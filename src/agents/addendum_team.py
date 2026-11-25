"""Multi-agent addendum drafting: orchestrator → drafting subagents → reviewer.

Flow for one impact alert:

1. **Orchestrator** (this module, plain code): loads the alert's contract
   impacts, groups them by contract and fans out one job per contract, at
   most ``CONCURRENCY`` at a time. The split is known in advance (one
   addendum per contract), so coordination is deterministic code — an LLM
   orchestrator would add cost and latency without deciding anything.
2. **Drafting subagent** (one per contract): gets the full regulatory text
   and every contract clause in its brief (loaded by code), then writes the addendum.
3. **Reviewer agent**: independently checks the draft against the source
   regulation and the clause text, returning structured issues. Blocker or
   major issues send the draft back to the same drafter (it keeps its
   context) for up to ``MAX_REVISIONS`` revisions.

Nothing is approved automatically: the reviewer only gates *revisions*; the
output still goes to human legal review like any other draft.

SSE contract (consumed by ``frontend/src/pages/Addendum.tsx`` in team mode):
    {"type": "plan",   "contracts": [{contract_name, doc_title, modifications}], "skipped": [...], "max_revisions"}
    {"type": "agent",  "contract_name", "role": "drafter"|"reviewer", "status": "started"|"tool"|"finished"|"failed", "round", "tool"?, "detail"?}
    {"type": "review", "contract_name", "round", "approved", "summary", "issues": [...]}
    {"type": "draft",  "contract_name", "doc_title", "text", "approved": bool|null, "rounds", "open_issues": [...]}
    {"type": "done",   "total", "approved", "usage"}   — or a single {"type": "error", "message"}
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.loop import Final, ToolCall, Usage, run_agent
from src.agents.tools import DRAFTING_TOOLS, REVIEW_TOOLS, AgentContext
from src.config import settings
from src.services import addendum_service
from src.services.addendum_service import AddendumContext

logger = logging.getLogger(__name__)

CONCURRENCY = 3      # drafting subagents running at once
MAX_CONTRACTS = 10   # per alert — the rest are reported as skipped
MAX_REVISIONS = 2    # reviewer → drafter round-trips per contract
_BLOCKING = {"blocker", "major"}

# ── Prompts ───────────────────────────────────────────────────────────────────

DRAFTER_SYSTEM = addendum_service._SYSTEM_PROMPT + """

SOURCES: the request already contains the full text of each triggering regulatory change and
every clause of the contract. Draft from them; quote clause references and article numbers
exactly as they appear there. Use the tools only if something you need is missing.

OUTPUT: your final message must contain only the complete addendum text — no preamble,
no commentary, no markdown code fences."""

REVIEWER_SYSTEM = """You are a senior compliance counsel reviewing an AI-drafted contract addendum
before it reaches the legal team. Be rigorous and specific; do not rewrite the draft.

Check against the regulation text and the contract clauses included in the brief (use the tools
only if something is missing):
1. COVERAGE — every required clause modification in the brief is addressed by an article.
2. ACCURACY — regulator, document title, dates, article and clause references match the sources.
3. FIDELITY — no obligation, threshold or deadline that the regulation does not contain.
4. CONSISTENCY — amended text does not contradict other clauses of the contract.
5. FORM — header, recitals, NOW THEREFORE, numbered articles, general provisions, signature block;
   placeholders ([DATE], [PARTY A], [PARTY B], [JURISDICTION]) for unknown facts.

Severity: "blocker" = legally wrong or missing a required modification; "major" = inaccurate
reference or invented requirement; "minor" = wording or formatting. Return an empty issues list
if the draft is ready for legal review."""

REVIEW_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                        "section": {"type": "string"},
                        "problem": {"type": "string"},
                        "fix": {"type": "string"},
                    },
                    "required": ["severity", "section", "problem", "fix"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "issues"],
        "additionalProperties": False,
    },
}


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class Review:
    summary: str
    issues: list[dict]

    @property
    def approved(self) -> bool:
        return not any(i.get("severity") in _BLOCKING for i in self.issues)


@dataclass
class ContractResult:
    contract_name: str
    doc_title: str
    text: str = ""
    approved: bool | None = None  # None = review unavailable
    rounds: int = 0
    open_issues: list[dict] = field(default_factory=list)
    failed: bool = False


Emit = Callable[[str], None]


def _sse(event_type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs}, ensure_ascii=False, default=str)}\n\n"


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def stream_team_draft(alert_id: str, db: AsyncSession) -> AsyncIterator[str]:
    """Run the drafting team for an alert and yield SSE events (see module docstring)."""
    contexts = await addendum_service.fetch_context(alert_id, db)
    if not contexts:
        yield _sse("error", message="No contract-type impact items found for this alert.")
        return

    skipped = [c.contract_name for c in contexts[MAX_CONTRACTS:]]
    contexts = contexts[:MAX_CONTRACTS]
    yield _sse(
        "plan",
        contracts=[
            {"contract_name": c.contract_name, "doc_title": c.primary_doc_title, "modifications": len(c.items)}
            for c in contexts
        ],
        skipped=skipped,
        max_revisions=MAX_REVISIONS if settings.llm_enabled else 0,
    )

    if not settings.llm_enabled:
        for c in contexts:
            yield _sse("draft", contract_name=c.contract_name, doc_title=c.primary_doc_title,
                       text=addendum_service._fallback_draft(c), approved=None, rounds=0, open_issues=[])
        yield _sse("done", total=len(contexts), approved=0, usage={"input_tokens": 0, "output_tokens": 0})
        return

    agent_ctx = AgentContext(db=db)
    usage = Usage()
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    sem = asyncio.Semaphore(CONCURRENCY)

    async def job(contract: AddendumContext) -> ContractResult:
        async with sem:
            try:
                return await draft_with_review(contract, agent_ctx, usage, queue.put_nowait)
            except Exception as exc:
                logger.exception("Drafting team failed for %s", contract.contract_name)
                queue.put_nowait(_sse("agent", contract_name=contract.contract_name, role="drafter",
                                      status="failed", round=0, detail=type(exc).__name__))
                return ContractResult(contract.contract_name, contract.primary_doc_title, failed=True)

    tasks = [asyncio.create_task(job(c)) for c in contexts]
    gather = asyncio.gather(*tasks)
    gather.add_done_callback(lambda _: queue.put_nowait(None))

    try:
        while (item := await queue.get()) is not None:
            yield item
        results: list[ContractResult] = gather.result()
    finally:
        # Client disconnected mid-run → stop spending tokens
        for t in tasks:
            t.cancel()

    finished = [r for r in results if not r.failed]
    for r in finished:
        yield _sse("draft", contract_name=r.contract_name, doc_title=r.doc_title, text=r.text,
                   approved=r.approved, rounds=r.rounds, open_issues=r.open_issues)
    if not finished:
        yield _sse("error", message="Every drafting agent failed — see server logs.")
        return
    yield _sse("done", total=len(results), approved=sum(1 for r in finished if r.approved),
               usage={"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})


# ── One contract: draft → review → revise ─────────────────────────────────────

async def draft_with_review(
    contract: AddendumContext,
    agent_ctx: AgentContext,
    usage: Usage,
    emit: Emit,
) -> ContractResult:
    name = contract.contract_name
    result = ContractResult(name, contract.primary_doc_title)

    messages: list = [{"role": "user", "content": _drafting_brief(contract)}]
    final = await _run_drafter(contract, messages, agent_ctx, usage, emit, round_=1)
    if final is None:
        result.failed = True
        return result

    for round_ in range(1, MAX_REVISIONS + 2):
        result.text, result.rounds = final.text.strip(), round_
        review = await _run_reviewer(contract, result.text, agent_ctx, usage, emit, round_)
        if review is None:  # reviewer unavailable: keep the draft, flag it
            result.approved = None
            return result
        emit(_sse("review", contract_name=name, round=round_, approved=review.approved,
                  summary=review.summary, issues=review.issues))
        result.approved, result.open_issues = review.approved, review.issues
        if review.approved or round_ > MAX_REVISIONS:
            return result

        # Same drafter, same context: it already read the sources
        messages = final.messages + [{"role": "user", "content": _revision_request(review)}]
        revised = await _run_drafter(contract, messages, agent_ctx, usage, emit, round_=round_ + 1)
        if revised is None:  # keep the last complete draft
            return result
        final = revised
    return result


async def _run_drafter(contract, messages, agent_ctx, usage, emit, *, round_: int) -> Final | None:
    name = contract.contract_name
    emit(_sse("agent", contract_name=name, role="drafter", status="started", round=round_))
    final = await _forward(
        run_agent(system=DRAFTER_SYSTEM, messages=messages, tools=DRAFTING_TOOLS, ctx=agent_ctx,
                  max_turns=8, max_tokens=32000, effort="high"),
        name, "drafter", round_, emit,
    )
    usage.input_tokens += final.usage.input_tokens
    usage.output_tokens += final.usage.output_tokens
    if not final.ok or not final.text.strip():
        emit(_sse("agent", contract_name=name, role="drafter", status="failed", round=round_,
                  detail=final.stop_reason))
        return None
    emit(_sse("agent", contract_name=name, role="drafter", status="finished", round=round_))
    return final


async def _run_reviewer(contract, draft, agent_ctx, usage, emit, round_: int) -> Review | None:
    name = contract.contract_name
    emit(_sse("agent", contract_name=name, role="reviewer", status="started", round=round_))
    final = await _forward(
        run_agent(system=REVIEWER_SYSTEM,
                  messages=[{"role": "user", "content": _review_request(contract, draft)}],
                  tools=REVIEW_TOOLS, ctx=agent_ctx, max_turns=6, max_tokens=16000,
                  effort="high", output_format=REVIEW_FORMAT),
        name, "reviewer", round_, emit,
    )
    usage.input_tokens += final.usage.input_tokens
    usage.output_tokens += final.usage.output_tokens
    try:
        if not final.ok:
            raise ValueError(final.stop_reason)
        data = json.loads(final.text)
        review = Review(summary=str(data.get("summary", "")), issues=list(data.get("issues", [])))
    except (ValueError, TypeError) as exc:
        logger.warning("Reviewer output unusable for %s: %s", name, exc)
        emit(_sse("agent", contract_name=name, role="reviewer", status="failed", round=round_,
                  detail="review unavailable"))
        return None
    emit(_sse("agent", contract_name=name, role="reviewer", status="finished", round=round_))
    return review


async def _forward(events, contract_name: str, role: str, round_: int, emit: Emit) -> Final:
    """Drain an agent run, surfacing its tool calls as progress events."""
    final: Final | None = None
    async for event in events:
        if isinstance(event, ToolCall):
            emit(_sse("agent", contract_name=contract_name, role=role, status="tool",
                      round=round_, tool=event.name, detail=event.input))
        elif isinstance(event, Final):
            final = event
    assert final is not None
    return final


# ── Prompt builders ───────────────────────────────────────────────────────────

def _sources_block(contract: AddendumContext) -> str:
    ids = sorted({i.change_id for i in contract.items if i.change_id})
    return (
        "\nSOURCE IDS (for the tools, if needed):\n"
        f"  contract_name: {contract.contract_name}\n"
        + "".join(f"  change_id: {cid}\n" for cid in ids)
    )


def _drafting_brief(contract: AddendumContext) -> str:
    return addendum_service._build_prompt(contract) + "\n" + _sources_block(contract)


def _review_request(contract: AddendumContext, draft: str) -> str:
    return (
        "BRIEF GIVEN TO THE DRAFTER:\n"
        + addendum_service._build_prompt(contract)
        + "\n" + _sources_block(contract)
        + "\n<draft>\n" + draft + "\n</draft>\n\nReview the draft."
    )


def _revision_request(review: Review) -> str:
    lines = ["A compliance reviewer found these issues in your draft:", ""]
    for i, issue in enumerate(review.issues, 1):
        lines.append(f"{i}. [{issue.get('severity')}] {issue.get('section')}: {issue.get('problem')}"
                     f" — Fix: {issue.get('fix')}")
    lines += ["", "Revise the addendum to resolve every blocker and major issue (and minor ones where easy).",
              "Return the complete revised addendum only."]
    return "\n".join(lines)
