"""Shared async LLM client.

A single client instance reuses its HTTP connection pool across requests, and
being async it never blocks the event loop while a model streams.

``settings.llm_provider`` picks the backend:
  * ``anthropic`` — ``anthropic.AsyncAnthropic`` (Claude API)
  * ``ollama``    — :class:`src.services.ollama_client.AsyncOllama`, local models
    behind the same ``messages.stream`` / ``messages.create`` surface
The model name is passed on every call (``settings.llm_model``).
"""
from functools import lru_cache

import anthropic

from src.config import settings


def get_client():
    if settings.llm_provider == "ollama":
        return _ollama(settings.ollama_url, settings.ollama_num_ctx, settings.ollama_timeout_s)
    return _anthropic(settings.anthropic_api_key)


@lru_cache(maxsize=4)
def _anthropic(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key)


@lru_cache(maxsize=4)
def _ollama(base_url: str, num_ctx: int, timeout_s: float):
    from src.services.ollama_client import AsyncOllama

    return AsyncOllama(base_url, num_ctx=num_ctx, timeout_s=timeout_s)


def response_text(message) -> str:
    """Join the text blocks of a Message (skips thinking / other block types)."""
    return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
