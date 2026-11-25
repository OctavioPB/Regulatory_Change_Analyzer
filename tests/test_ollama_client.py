"""Ollama adapter: Anthropic-shaped requests in, Anthropic-shaped messages out."""
import json
from types import SimpleNamespace

import httpx
import pytest

from src.agents import loop
from src.agents.loop import Tool, run_agent
from src.services import llm
from src.services.ollama_client import AsyncOllama, OllamaError, to_ollama_messages


def _ndjson(*objs) -> bytes:
    return b"\n".join(json.dumps(o).encode() for o in objs) + b"\n"


def _client(handler) -> tuple[AsyncOllama, list[dict]]:
    seen: list[dict] = []

    def wrapped(request: httpx.Request):
        seen.append(json.loads(request.content))
        return handler(request)

    return AsyncOllama("http://ollama", transport=httpx.MockTransport(wrapped)), seen


def test_message_translation_round_trips_tool_calls():
    out = to_ollama_messages("sys", [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": [
            SimpleNamespace(type="thinking", thinking="…"),
            SimpleNamespace(type="text", text="Looking."),
            SimpleNamespace(type="tool_use", id="t1", name="get_contract", input={"contract_name": "X"}),
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "not found", "is_error": True},
        ]},
    ])
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1] == {"role": "user", "content": "q"}
    assert out[2]["content"] == "Looking."  # thinking dropped
    assert out[2]["tool_calls"][0]["function"] == {"name": "get_contract", "arguments": {"contract_name": "X"}}
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "tool_name": "get_contract",
                      "content": "[tool error] not found"}


@pytest.mark.asyncio
async def test_stream_yields_text_and_maps_usage_and_options():
    client, seen = _client(lambda r: httpx.Response(200, content=_ndjson(
        {"message": {"content": "Hola "}, "done": False},
        {"message": {"content": "mundo"}, "done": False},
        {"message": {"content": ""}, "done": True, "done_reason": "stop",
         "prompt_eval_count": 12, "eval_count": 3},
    )))
    async with client.messages.stream(model="qwen3:4b", max_tokens=32000, system="s",
                                      messages=[{"role": "user", "content": "hi"}],
                                      output_config={"effort": "high", "format": {
                                          "type": "json_schema", "schema": {"type": "object"}}}) as s:
        chunks = [c async for c in s.text_stream]
        final = await s.get_final_message()

    assert chunks == ["Hola ", "mundo"]
    assert final.stop_reason == "end_turn" and final.content[0].text == "Hola mundo"
    assert (final.usage.input_tokens, final.usage.output_tokens) == (12, 3)
    body = seen[0]
    assert body["think"] is False and body["options"]["temperature"] == 0
    assert body["options"]["num_predict"] == 8192  # capped
    assert body["format"] == {"type": "object"}


@pytest.mark.asyncio
@pytest.mark.parametrize("done_reason,expected", [("length", "max_tokens"), ("stop", "end_turn")])
async def test_stop_reason_mapping(done_reason, expected):
    client, _ = _client(lambda r: httpx.Response(200, content=_ndjson(
        {"message": {"content": "x"}, "done": True, "done_reason": done_reason})))
    msg = await client.messages.create(model="m", max_tokens=10, messages=[{"role": "user", "content": "q"}])
    assert msg.stop_reason == expected


@pytest.mark.asyncio
async def test_http_error_raises_ollama_error():
    client, _ = _client(lambda r: httpx.Response(404, content=b'{"error":"model not found"}'))
    with pytest.raises(OllamaError, match="404"):
        await client.messages.create(model="nope", max_tokens=10, messages=[{"role": "user", "content": "q"}])


@pytest.mark.asyncio
async def test_agent_loop_runs_on_ollama_tool_calls(monkeypatch):
    """The real agent loop, unchanged, driving a local model's tool calls."""
    from pydantic import BaseModel

    class Inp(BaseModel):
        word: str

    async def echo(ctx, args):
        return f"echo:{args.word}"

    replies = iter([
        _ndjson({"message": {"content": "", "tool_calls": [
            {"id": "c1", "function": {"name": "echo", "arguments": {"word": "hi"}}}]},
            "done": True, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2}),
        _ndjson({"message": {"content": "final answer"}, "done": True, "done_reason": "stop"}),
    ])
    client, seen = _client(lambda r: httpx.Response(200, content=next(replies)))
    monkeypatch.setattr(loop, "get_client", lambda: client)

    events = [e async for e in run_agent(system="s", messages=[{"role": "user", "content": "q"}],
                                         tools=[Tool("echo", "Echo", Inp, echo)], ctx=None)]
    assert events[-1].ok and events[-1].text == "final answer"
    assert seen[0]["tools"][0]["function"]["name"] == "echo"
    tool_msg = seen[1]["messages"][-1]
    assert tool_msg == {"role": "tool", "tool_call_id": "c1", "tool_name": "echo", "content": "echo:hi"}


def test_get_client_follows_provider(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    assert isinstance(llm.get_client(), AsyncOllama)
    assert settings.llm_enabled
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert not settings.llm_enabled
    assert not isinstance(llm.get_client(), AsyncOllama)


@pytest.mark.asyncio
async def test_tools_plus_schema_runs_in_two_phases():
    """Phase 1 offers tools without the schema; a tool-less answer is re-asked with the schema."""
    replies = iter([
        _ndjson({"message": {"content": "free text"}, "done": True, "done_reason": "stop",
                 "prompt_eval_count": 10, "eval_count": 4}),
        _ndjson({"message": {"content": '{"ok": true}'}, "done": True, "done_reason": "stop",
                 "prompt_eval_count": 12, "eval_count": 5}),
    ])
    client, seen = _client(lambda r: httpx.Response(200, content=next(replies)))
    tool = {"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    fmt = {"type": "json_schema", "schema": {"type": "object"}}
    async with client.messages.stream(model="m", max_tokens=100, messages=[{"role": "user", "content": "q"}],
                                      tools=[tool], output_config={"format": fmt}) as s:
        streamed = [c async for c in s.text_stream]
        final = await s.get_final_message()

    assert "format" not in seen[0] and "tools" in seen[0]
    assert seen[1]["format"] == {"type": "object"} and "tools" not in seen[1]
    assert streamed == ['{"ok": true}'] and final.content[0].text == '{"ok": true}'
    assert (final.usage.input_tokens, final.usage.output_tokens) == (22, 9)


@pytest.mark.asyncio
async def test_tools_plus_schema_keeps_tool_calls_without_second_phase():
    client, seen = _client(lambda r: httpx.Response(200, content=_ndjson(
        {"message": {"content": "", "tool_calls": [{"id": "c", "function": {"name": "t", "arguments": {}}}]},
         "done": True, "done_reason": "stop"})))
    tool = {"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    msg = await client.messages.create(model="m", max_tokens=100, messages=[{"role": "user", "content": "q"}],
                                       tools=[tool], output_config={"format": {"type": "json_schema", "schema": {}}})
    assert msg.stop_reason == "tool_use" and len(seen) == 1
