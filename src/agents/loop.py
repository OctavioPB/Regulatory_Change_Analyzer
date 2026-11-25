"""Generic Claude tool-use loop.

The loop runs inside the API process because every tool is a query against
this app's own database. It streams text deltas, executes the tool calls
Claude requests, feeds the results back and stops on ``end_turn``, a refusal,
``max_tokens`` or the turn limit — whichever comes first.

Callers consume a stream of :class:`AgentEvent` objects and translate them
into whatever their transport needs (SSE for the UI).
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from src.config import settings
from src.services.llm import get_client, response_text

logger = logging.getLogger(__name__)

# Tool results are truncated before they go back to Claude: a whole regulation
# or contract can be tens of thousands of tokens and most of it is irrelevant.
MAX_TOOL_RESULT_CHARS = 12_000


# ── Tool definition ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Tool:
    """A client-side tool: typed input model + async handler.

    ``handler(ctx, args)`` receives the per-run context object (whatever the
    agent passes as ``ctx``) and the validated pydantic input.
    """
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any, Any], Awaitable[Any]]

    def to_param(self) -> dict:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
            # Streamed requests: emit tool input as it is generated. Inputs are
            # validated against input_model below before the handler runs.
            "eager_input_streaming": True,
        }


# ── Events ────────────────────────────────────────────────────────────────────

@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ToolResult:
    id: str
    name: str
    ok: bool
    summary: str


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0


@dataclass
class Final:
    """Last event of every run."""
    text: str
    # end_turn | refusal | max_tokens | max_turns
    stop_reason: str
    turns: int
    usage: Usage
    messages: list = field(default_factory=list)  # full transcript, for follow-ups

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"


AgentEvent = TextDelta | ToolCall | ToolResult | Final


# ── Loop ──────────────────────────────────────────────────────────────────────

async def run_agent(
    *,
    system: str,
    messages: list,
    tools: list[Tool],
    ctx: Any,
    max_turns: int = 8,
    max_tokens: int = 16000,
    effort: str = "medium",
    output_format: dict | None = None,
) -> AsyncIterator[AgentEvent]:
    """Run Claude with ``tools`` until it stops asking for them.

    Args:
        system: System prompt.
        messages: Conversation so far (mutated copy is returned in ``Final``).
        tools: Tools Claude may call.
        ctx: Opaque per-run context handed to every tool handler.
        max_turns: Upper bound on model requests (each tool round-trip is one).
        max_tokens: Per-request output budget (thinking counts against it).
        effort: ``output_config.effort``.
        output_format: Optional ``output_config.format`` (structured output).

    Yields:
        TextDelta / ToolCall / ToolResult events, then exactly one Final.
    """
    by_name = {t.name: t for t in tools}
    params = [t.to_param() for t in tools]
    messages = list(messages)
    output_config: dict = {"effort": effort}
    if output_format:
        output_config["format"] = output_format

    usage = Usage()
    for turn in range(1, max_turns + 1):
        async with get_client().messages.stream(
            model=settings.llm_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=params,
            output_config=output_config,
        ) as stream:
            async for chunk in stream.text_stream:
                yield TextDelta(chunk)
            message = await stream.get_final_message()

        usage.add(message.usage)
        # Thinking + tool_use blocks go back unchanged — the API requires it
        messages.append({"role": "assistant", "content": message.content})

        if message.stop_reason == "pause_turn":
            continue
        if message.stop_reason != "tool_use":
            yield Final(response_text(message), message.stop_reason, turn, usage, messages)
            return

        results = []
        for block in message.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            yield ToolCall(block.id, block.name, dict(block.input or {}))
            content, ok = await _execute(by_name.get(block.name), block.input, ctx)
            yield ToolResult(block.id, block.name, ok, content[:200])
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                **({} if ok else {"is_error": True}),
            })
        messages.append({"role": "user", "content": results})

    # Turn budget exhausted while Claude still wanted tools
    yield Final("", "max_turns", max_turns, usage, messages)


async def run_to_completion(**kwargs) -> Final:
    """Run an agent without streaming its events (used by subagents)."""
    final: Final | None = None
    async for event in run_agent(**kwargs):
        if isinstance(event, Final):
            final = event
    assert final is not None  # run_agent always ends with Final
    return final


async def _execute(tool: Tool | None, raw_input: Any, ctx: Any) -> tuple[str, bool]:
    """Validate input and run a tool. Errors go back to Claude, never raise."""
    if tool is None:
        return "Error: unknown tool.", False
    try:
        args = tool.input_model.model_validate(raw_input or {})
    except ValidationError as exc:
        # Includes inputs truncated by eager streaming — Claude can retry
        return f"Error: invalid input — {exc.errors(include_url=False)}", False
    try:
        result = await tool.handler(ctx, args)
    except LookupError as exc:
        return f"Error: {exc}", False
    except Exception:
        logger.exception("Tool %s failed", tool.name)
        return "Error: the tool failed unexpectedly.", False
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + "\n…[truncated]"
    return text, True
