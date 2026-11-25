"""Agent loop, research agent and drafting team — with a scripted fake Claude client."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services import grounding
from pydantic import BaseModel, ConfigDict

from src.agents import addendum_team, loop, research_agent
from src.agents.loop import Final, Tool, ToolCall, ToolResult, run_agent
from src.agents.tools import AgentContext
from src.services.addendum_service import AddendumContext, AddendumItem

# ── Fake Claude ───────────────────────────────────────────────────────────────


def text_block(t):
    return SimpleNamespace(type="text", text=t)


def tool_block(name, inp, id_="tu_1"):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


def msg(*blocks, stop="end_turn", inp=10, out=5):
    return SimpleNamespace(content=list(blocks), stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=inp, output_tokens=out))


class _Stream:
    def __init__(self, message):
        self._m = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for b in self._m.content:
                if b.type == "text":
                    yield b.text
        return gen()

    async def get_final_message(self):
        return self._m


class FakeClient:
    """``responder(kwargs) -> message`` decides each reply; every call is recorded."""

    def __init__(self, responder):
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(stream=self._stream)
        self._responder = responder

    def _stream(self, **kwargs):
        kwargs = {**kwargs, "messages": list(kwargs["messages"])}  # snapshot
        self.calls.append(kwargs)
        return _Stream(self._responder(kwargs))


def scripted(*messages):
    it = iter(messages)
    return FakeClient(lambda _kw: next(it))


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str


async def _echo(ctx, args):
    return {"echo": args.word, "cite_as": ctx.cite("regulation", "c1", title="Circular 1/2026",
                                                   source="CNBV", article_ref="Art. 5", excerpt="x")}


ECHO = Tool("echo", "Echo a word.", EchoInput, _echo)


async def _collect(gen):
    return [e async for e in gen]


# ── Loop ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loop_runs_tool_then_answers():
    client = scripted(
        msg(text_block("Let me check."), tool_block("echo", {"word": "hi"}), stop="tool_use"),
        msg(text_block("Done [REG-1]")),
    )
    ctx = AgentContext(db=AsyncMock())
    with patch.object(loop, "get_client", return_value=client):
        events = await _collect(run_agent(system="s", messages=[{"role": "user", "content": "q"}],
                                          tools=[ECHO], ctx=ctx))

    final = events[-1]
    assert isinstance(final, Final) and final.ok and final.turns == 2
    assert final.text == "Done [REG-1]"
    assert final.usage.input_tokens == 20 and final.usage.output_tokens == 10
    assert [type(e) for e in events if isinstance(e, ToolCall | ToolResult)] == [ToolCall, ToolResult]

    # Second request carries the assistant tool_use turn + the tool_result
    second = client.calls[1]["messages"]
    assert second[1]["role"] == "assistant"
    result = second[2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "tu_1"
    assert json.loads(result["content"])["echo"] == "hi"
    assert "is_error" not in result
    # Tool schema: strict-ish object with eager streaming on
    tool_param = client.calls[0]["tools"][0]
    assert tool_param["eager_input_streaming"] is True
    assert tool_param["input_schema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_loop_rejects_invalid_tool_input_without_running_it():
    handler = AsyncMock()
    tool = Tool("echo", "Echo.", EchoInput, handler)
    client = scripted(
        msg(tool_block("echo", {"wrd": "typo"}), stop="tool_use"),
        msg(text_block("ok")),
    )
    with patch.object(loop, "get_client", return_value=client):
        await _collect(run_agent(system="s", messages=[], tools=[tool], ctx=None))

    handler.assert_not_called()
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "invalid input" in result["content"]


@pytest.mark.asyncio
async def test_loop_unknown_tool_and_handler_errors_go_back_to_claude():
    async def boom(ctx, args):
        raise RuntimeError("db down")

    async def missing(ctx, args):
        raise LookupError("change 123 not found")

    tools = [Tool("boom", "x", EchoInput, boom), Tool("missing", "x", EchoInput, missing)]
    client = scripted(
        msg(tool_block("nope", {}, "a"), tool_block("boom", {"word": "w"}, "b"),
            tool_block("missing", {"word": "w"}, "c"), stop="tool_use"),
        msg(text_block("ok")),
    )
    with patch.object(loop, "get_client", return_value=client):
        await _collect(run_agent(system="s", messages=[], tools=tools, ctx=None))

    results = {r["tool_use_id"]: r for r in client.calls[1]["messages"][-1]["content"]}
    assert all(r["is_error"] for r in results.values())
    assert "unknown tool" in results["a"]["content"]
    assert "db down" not in results["b"]["content"]  # internals not leaked to the model
    assert "change 123 not found" in results["c"]["content"]


@pytest.mark.asyncio
async def test_loop_stops_at_turn_limit():
    client = FakeClient(lambda _kw: msg(tool_block("echo", {"word": "again"}), stop="tool_use"))
    with patch.object(loop, "get_client", return_value=client):
        events = await _collect(run_agent(system="s", messages=[], tools=[ECHO],
                                          ctx=AgentContext(db=AsyncMock()), max_turns=3))
    assert events[-1].stop_reason == "max_turns"
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_loop_truncates_large_tool_results():
    async def big(ctx, args):
        return "x" * (loop.MAX_TOOL_RESULT_CHARS + 500)

    client = scripted(msg(tool_block("big", {"word": "w"}), stop="tool_use"), msg(text_block("ok")))
    with patch.object(loop, "get_client", return_value=client):
        await _collect(run_agent(system="s", messages=[], tools=[Tool("big", "x", EchoInput, big)], ctx=None))
    content = client.calls[1]["messages"][-1]["content"][0]["content"]
    assert len(content) < loop.MAX_TOOL_RESULT_CHARS + 50 and content.endswith("[truncated]")


# ── Citation registry ─────────────────────────────────────────────────────────

def test_citation_registry_dedupes_and_filters_cited():
    ctx = AgentContext(db=AsyncMock())
    a = ctx.cite("regulation", "c1", title="T", source="CNBV", article_ref="A1", excerpt="e")
    b = ctx.cite("contract", "k1", title="Loan", source="Credit", article_ref="4.2", excerpt="e")
    assert ctx.cite("regulation", "c1", title="T", source="CNBV", article_ref="A1", excerpt="e") == a
    assert (a, b) == ("REG-1", "CON-2")
    assert [c["ref_id"] for c in ctx.cited_in("only [CON-2] here")] == [2]


# ── Research agent ────────────────────────────────────────────────────────────

def _events(chunks):
    return [json.loads(c[6:]) for c in chunks]


@pytest.mark.asyncio
async def test_research_agent_streams_steps_tokens_and_cited_sources(monkeypatch):
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(research_agent, "RESEARCH_TOOLS", [ECHO])
    client = scripted(
        msg(tool_block("echo", {"word": "aml"}), stop="tool_use"),
        msg(text_block("Answer [REG-1]")),
    )
    with patch.object(loop, "get_client", return_value=client):
        events = _events(await _collect(research_agent.stream_research("q", AsyncMock())))

    types = [e["type"] for e in events]
    assert types == ["step", "step", "token", "citations", "done"]
    assert events[0]["status"] == "running" and events[1]["status"] == "ok"
    assert events[3]["citations"][0]["title"] == "Circular 1/2026"
    assert events[4]["turns"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["refusal", "max_turns"])
async def test_research_agent_ends_with_single_error(monkeypatch, stop):
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "sk-test")

    async def fake_run(**_kw):
        yield Final("", stop, 1, loop.Usage())

    monkeypatch.setattr(research_agent, "run_agent", fake_run)
    events = _events(await _collect(research_agent.stream_research("q", AsyncMock())))
    assert [e["type"] for e in events] == ["error"]


@pytest.mark.asyncio
async def test_research_agent_without_key_falls_back_to_rag(monkeypatch):
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "")

    async def fake_rag(q, db):
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr(research_agent.rag_service, "stream_query", fake_rag)
    events = _events(await _collect(research_agent.stream_research("q", AsyncMock())))
    assert events == [{"type": "done"}]


# ── Drafting team ─────────────────────────────────────────────────────────────

def _contract(name):
    item = AddendumItem(
        affected_name=name, affected_ref="Clause 4.2", suggestion="Lower leverage to 3x",
        original_clause_text="Leverage up to 5x", change_summary="Leverage cap 3x",
        article_ref="Art. 7", change_type="limit_modification", doc_title="Circular 5/2026",
        source="CNBV", publication_date="May 01, 2026", contract_area="Credit",
        change_id="11111111-1111-1111-1111-111111111111",
    )
    return AddendumContext(contract_name=name, contract_area="Credit", items=[item])


def _team_client(reject_first_review_of: str):
    """Drafters echo their contract; the reviewer rejects one contract's first draft."""
    reviews: dict[str, int] = {}

    def respond(kw):
        first = kw["messages"][0]["content"]
        name = "Alpha Loan" if "Alpha Loan" in first else "Beta Swap"
        if kw["system"] == addendum_team.REVIEWER_SYSTEM:
            assert kw["output_config"]["format"]["type"] == "json_schema"
            n = reviews[name] = reviews.get(name, 0) + 1
            issues = ([{"severity": "major", "section": "Art. 1", "problem": "wrong article",
                        "fix": "cite Art. 7"}] if name == reject_first_review_of and n == 1 else [])
            return msg(text_block(json.dumps({"summary": "checked", "issues": issues})))
        revised = len(kw["messages"]) > 1
        return msg(text_block(f"ADDENDUM TO {name.upper()}{' v2' if revised else ''}"))

    return FakeClient(respond)


@pytest.mark.asyncio
async def test_team_drafts_reviews_and_revises(monkeypatch):
    monkeypatch.setattr(addendum_team.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(addendum_team.addendum_service, "fetch_context",
                        AsyncMock(return_value=[_contract("Alpha Loan"), _contract("Beta Swap")]))
    client = _team_client(reject_first_review_of="Alpha Loan")
    with patch.object(loop, "get_client", return_value=client):
        events = _events(await _collect(addendum_team.stream_team_draft("a1", AsyncMock())))

    assert events[0]["type"] == "plan" and len(events[0]["contracts"]) == 2
    assert events[-1]["type"] == "done" and events[-1]["approved"] == 2
    assert sum(e["type"] in ("done", "error") for e in events) == 1

    drafts = {e["contract_name"]: e for e in events if e["type"] == "draft"}
    assert drafts["Alpha Loan"]["text"].endswith("v2") and drafts["Alpha Loan"]["rounds"] == 2
    assert drafts["Beta Swap"]["rounds"] == 1 and drafts["Beta Swap"]["approved"] is True

    # The revision went back to the same drafter conversation with the reviewer's feedback
    revision_calls = [c for c in client.calls
                      if c["system"] == addendum_team.DRAFTER_SYSTEM and len(c["messages"]) > 1]
    assert len(revision_calls) == 1
    assert "wrong article" in revision_calls[0]["messages"][-1]["content"]
    # Drafter brief carries the ids its tools need
    assert "11111111-1111-1111-1111-111111111111" in client.calls[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_team_stops_after_max_revisions(monkeypatch):
    monkeypatch.setattr(addendum_team.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(addendum_team.addendum_service, "fetch_context",
                        AsyncMock(return_value=[_contract("Alpha Loan")]))

    def respond(kw):
        if kw["system"] == addendum_team.REVIEWER_SYSTEM:
            return msg(text_block(json.dumps({"summary": "no", "issues": [
                {"severity": "blocker", "section": "all", "problem": "p", "fix": "f"}]})))
        return msg(text_block("DRAFT"))

    with patch.object(loop, "get_client", return_value=FakeClient(respond)):
        events = _events(await _collect(addendum_team.stream_team_draft("a1", AsyncMock())))

    reviews = [e for e in events if e["type"] == "review"]
    assert len(reviews) == addendum_team.MAX_REVISIONS + 1
    draft = next(e for e in events if e["type"] == "draft")
    assert draft["approved"] is False and draft["open_issues"][0]["severity"] == "blocker"
    assert events[-1]["type"] == "done" and events[-1]["approved"] == 0


@pytest.mark.asyncio
async def test_team_without_key_returns_template_drafts(monkeypatch):
    monkeypatch.setattr(addendum_team.settings, "anthropic_api_key", "")
    monkeypatch.setattr(addendum_team.addendum_service, "fetch_context",
                        AsyncMock(return_value=[_contract("Alpha Loan")]))
    events = _events(await _collect(addendum_team.stream_team_draft("a1", AsyncMock())))
    assert [e["type"] for e in events] == ["plan", "draft", "done"]
    assert "ADDENDUM TO ALPHA LOAN" in events[1]["text"]


@pytest.mark.asyncio
async def test_team_with_no_contract_items_errors(monkeypatch):
    monkeypatch.setattr(addendum_team.addendum_service, "fetch_context", AsyncMock(return_value=[]))
    events = _events(await _collect(addendum_team.stream_team_draft("a1", AsyncMock())))
    assert [e["type"] for e in events] == ["error"]


def test_review_approval_ignores_minor_issues():
    minor = addendum_team.Review("ok", [{"severity": "minor"}])
    major = addendum_team.Review("no", [{"severity": "minor"}, {"severity": "major"}])
    assert minor.approved and not major.approved


# ── RBAC ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/api/v1/agents/chat",
                                  "/api/v1/agents/addendum/00000000-0000-0000-0000-000000000000"])
def test_agent_endpoints_require_analyst(monkeypatch, path):
    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.auth import dependencies
    from src.config import settings

    monkeypatch.setattr(settings, "api_keys", '{"k-view": "viewer"}')
    dependencies._key_map.cache_clear()
    try:
        res = TestClient(app).post(path, json={"query": "q"}, headers={"X-API-Key": "k-view"})
        assert res.status_code == 403
    finally:
        dependencies._key_map.cache_clear()



@pytest.mark.asyncio
async def test_research_agent_empty_answer_ends_in_system_refusal(monkeypatch):
    """Seen with gemma in evals: an empty final message. One correction turn, then the system refuses."""
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "sk-test")
    calls = []

    async def fake_run(**kw):
        calls.append(kw)
        yield Final("  ", "end_turn", 2, loop.Usage(), messages=[*kw["messages"],
                                                                {"role": "assistant", "content": []}])

    monkeypatch.setattr(research_agent, "run_agent", fake_run)
    events = _events(await _collect(research_agent.stream_research("¿Cuál es el plazo?", AsyncMock())))
    assert [e["type"] for e in events] == ["reset", "reset", "citations", "token", "done"]
    assert events[3]["text"] == grounding.REFUSAL_ES
    assert events[4]["refused"] and events[4]["turns"] == 4
    retry = calls[1]["messages"]
    assert retry[-1]["role"] == "user" and "did not write an answer" in retry[-1]["content"]
    assert all(m["role"] != "assistant" for m in retry)  # the empty assistant turn is dropped


@pytest.mark.asyncio
async def test_research_agent_invalid_citation_gets_one_correction(monkeypatch):
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(research_agent, "RESEARCH_TOOLS", [ECHO])
    client = scripted(
        msg(tool_block("echo", {"word": "aml"}), stop="tool_use"),
        msg(text_block("Answer [CON-7]")),       # never returned by a tool
        msg(text_block("Answer [REG-1]")),
    )
    with patch.object(loop, "get_client", return_value=client):
        events = _events(await _collect(research_agent.stream_research("q", AsyncMock())))
    assert [e["type"] for e in events] == ["step", "step", "token", "reset", "token", "citations", "done"]
    assert events[-1]["grounded"] and events[-1]["regenerations"] == 1
    assert "CON-7" in client.calls[2]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_research_agent_prose_refusal_is_replaced_by_the_system(monkeypatch):
    monkeypatch.setattr(research_agent.settings, "anthropic_api_key", "sk-test")
    client = scripted(msg(text_block("The database does not contain information about that.")))
    with patch.object(loop, "get_client", return_value=client):
        events = _events(await _collect(research_agent.stream_research("Which fee?", AsyncMock())))
    assert len(client.calls) == 1
    assert events[-2]["text"] == grounding.REFUSAL_EN and events[-1]["refused"]


def test_addendum_prompt_carries_regulation_text_not_diff_metric():
    """Evals: without the text, qwen turned 'ratio=0.96' into a '96% capital ratio' obligation."""
    from src.services.addendum_service import _build_prompt

    ctx = _contract("Alpha Loan")
    item = ctx.items[0]
    object.__setattr__(item, "change_summary", "Artículo 1: content modified (new_requirement, ratio=0.96)")
    object.__setattr__(item, "regulation_text", "El CCN mínimo se incrementa del 10.5% al 12%.")
    prompt = _build_prompt(ctx)
    assert "ratio=" not in prompt and "0.96" not in prompt
    assert "del 10.5% al 12%" in prompt


def test_drafting_brief_carries_every_contract_clause():
    """Evals: gemma's drafter never called get_contract and invented "Clause [X]"."""
    ctx = _contract("Alpha Loan")
    ctx.clauses = [("Clause 3.1", "Leverage up to 5x"), ("Clause 8.2", "Automatic adaptation")]
    brief = addendum_team._drafting_brief(ctx)
    assert "CURRENT CONTRACT TEXT" in brief
    assert "Clause 3.1: Leverage up to 5x" in brief and "Clause 8.2: Automatic adaptation" in brief
