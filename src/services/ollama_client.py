"""Local models (Qwen, Gemma, …) through Ollama's /api/chat, behind the Anthropic SDK's shape.

The app calls ``get_client().messages.stream(...)`` / ``.create(...)`` and reads
``.text_stream``, ``get_final_message()``, ``content`` blocks, ``stop_reason``
and ``usage``. This adapter implements exactly that subset on top of Ollama,
so RAG chat, addendum drafting and the agents run unchanged on a local model.

Translation:
    system / messages / tool_use / tool_result  →  Ollama chat messages + tool calls
    tools[].input_schema                        →  tools[].function.parameters
    output_config.format.schema                 →  format (JSON-schema constrained output)
    max_tokens                                  →  options.num_predict (capped)
    output_config.effort, eager_input_streaming →  ignored (no local equivalent)

Generation is deterministic (temperature 0, fixed seed) so eval runs are
reproducible, and model "thinking" is off: it would eat the answer budget.
Nothing here reaches an external provider.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx

# A local model has no use for Claude-sized budgets; long generations on a
# partly CPU-offloaded model would take many minutes.
_MAX_PREDICT = 8192


class OllamaError(RuntimeError):
    pass


def _get(block: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dict block (built by our code) or an object block (from a response)."""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _blocks(content: Any) -> list:
    return [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])


def to_ollama_messages(system: str | None, messages: list) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    tool_names: dict[str, str] = {}
    for m in messages:
        role = m["role"]
        blocks = _blocks(m["content"])
        if role == "assistant":
            text = "".join(_get(b, "text", "") for b in blocks if _get(b, "type") == "text")
            calls = []
            for b in blocks:
                if _get(b, "type") == "tool_use":
                    tool_names[_get(b, "id")] = _get(b, "name")
                    calls.append({"id": _get(b, "id"),
                                  "function": {"name": _get(b, "name"), "arguments": _get(b, "input") or {}}})
            msg: dict = {"role": "assistant", "content": text}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
            continue
        texts = []
        for b in blocks:
            kind = _get(b, "type")
            if kind == "tool_result":
                content = _get(b, "content", "")
                if not isinstance(content, str):
                    content = "".join(_get(c, "text", "") for c in content)
                if _get(b, "is_error"):
                    content = f"[tool error] {content}"
                tid = _get(b, "tool_use_id")
                out.append({"role": "tool", "tool_call_id": tid,
                            "tool_name": tool_names.get(tid, ""), "content": content})
            elif kind == "text":
                texts.append(_get(b, "text", ""))
        if texts:
            out.append({"role": "user", "content": "\n".join(texts)})
    return out


def to_ollama_tools(tools: list | None) -> list[dict] | None:
    if not tools:
        return None
    return [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t["input_schema"],
        }}
        for t in tools
    ]


class _Stream:
    """Async context manager mirroring ``AsyncMessageStreamManager`` / ``AsyncMessageStream``.

    Tools + JSON schema in one request make some local models (seen with qwen3) emit nothing
    until the token limit. So when both are requested the turn runs in two phases: tools only;
    then, if the model called no tool, the turn is re-asked with the schema and no tools.
    Phase-1 text is not streamed in that case (the schema-constrained answer replaces it).
    """

    def __init__(self, http: httpx.AsyncClient, payload: dict):
        self._http, self._payload = http, payload
        self._deferred_format = payload.pop("format") if "tools" in payload and "format" in payload else None
        self._cm = None
        self._resp: httpx.Response | None = None
        self._text: list[str] = []
        self._calls: list[dict] = []
        self._final: dict = {}
        self._consumed = False

    async def __aenter__(self) -> _Stream:
        self._cm = self._http.stream("POST", "/api/chat", json=self._payload)
        try:
            self._resp = await self._cm.__aenter__()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise OllamaError(f"Ollama unreachable: {type(exc).__name__}") from exc
        if self._resp.status_code >= 400:
            body = (await self._resp.aread()).decode(errors="replace")[:300]
            await self._cm.__aexit__(None, None, None)
            raise OllamaError(f"Ollama {self._resp.status_code}: {body}")
        return self

    async def __aexit__(self, *exc) -> bool:
        await self._cm.__aexit__(*exc)
        return False

    async def _read(self, resp: httpx.Response, *, emit: bool):
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("error"):
                raise OllamaError(str(data["error"]))
            msg = data.get("message") or {}
            if msg.get("tool_calls"):
                self._calls.extend(msg["tool_calls"])
            piece = msg.get("content") or ""
            if piece:
                self._text.append(piece)
                if emit:
                    yield piece
            if data.get("done"):
                # Usage accumulates across the two phases
                for key in ("prompt_eval_count", "eval_count"):
                    data[key] = int(data.get(key, 0)) + int(self._final.get(key, 0))
                self._final = data

    async def _chunks(self):
        if self._consumed:
            return
        self._consumed = True
        async for piece in self._read(self._resp, emit=self._deferred_format is None):
            yield piece
        if self._deferred_format is None or self._calls:
            return
        # Phase 2: the model answered without tools — ask again, schema-constrained
        self._text = []
        payload = {k: v for k, v in self._payload.items() if k != "tools"}
        payload["format"] = self._deferred_format
        async with self._http.stream("POST", "/api/chat", json=payload) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode(errors="replace")[:300]
                raise OllamaError(f"Ollama {resp.status_code}: {body}")
            async for piece in self._read(resp, emit=True):
                yield piece

    @property
    def text_stream(self):
        return self._chunks()

    async def get_final_message(self) -> SimpleNamespace:
        async for _ in self._chunks():  # drain if the caller did not iterate
            pass
        content: list = []
        text = "".join(self._text)
        if text:
            content.append(SimpleNamespace(type="text", text=text))
        for i, call in enumerate(self._calls):
            fn = call.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):  # some models emit arguments as a JSON string
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            content.append(SimpleNamespace(type="tool_use", id=call.get("id") or f"call_{i}",
                                           name=fn.get("name", ""), input=args))
        if self._calls:
            stop = "tool_use"
        elif self._final.get("done_reason") == "length":
            stop = "max_tokens"
        else:
            stop = "end_turn"
        usage = SimpleNamespace(input_tokens=int(self._final.get("prompt_eval_count", 0)),
                                output_tokens=int(self._final.get("eval_count", 0)))
        return SimpleNamespace(content=content, stop_reason=stop, usage=usage,
                               model=self._payload["model"])


class _Messages:
    def __init__(self, http: httpx.AsyncClient, num_ctx: int, seed: int):
        self._http, self._num_ctx, self._seed = http, num_ctx, seed

    def _payload(self, *, model: str, max_tokens: int, messages: list, system: str | None = None,
                 tools: list | None = None, output_config: dict | None = None, **_ignored) -> dict:
        payload: dict = {
            "model": model,
            "stream": True,
            "think": False,
            "messages": to_ollama_messages(system, messages),
            "options": {
                "temperature": 0,
                "seed": self._seed,
                "num_predict": min(max_tokens, _MAX_PREDICT),
                "num_ctx": self._num_ctx,
            },
        }
        if (ollama_tools := to_ollama_tools(tools)) is not None:
            payload["tools"] = ollama_tools
        schema = ((output_config or {}).get("format") or {}).get("schema")
        if schema:
            payload["format"] = schema
        return payload

    def stream(self, **kwargs) -> _Stream:
        return _Stream(self._http, self._payload(**kwargs))

    async def create(self, **kwargs) -> SimpleNamespace:
        async with self.stream(**kwargs) as s:
            return await s.get_final_message()


class AsyncOllama:
    """Drop-in for the ``messages`` surface of ``anthropic.AsyncAnthropic``."""

    def __init__(self, base_url: str, *, num_ctx: int = 32768, timeout_s: float = 900.0, seed: int = 7,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_s, connect=10.0), transport=transport)
        self.messages = _Messages(self._http, num_ctx, seed)
