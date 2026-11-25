"""Shared async Anthropic client.

A single AsyncAnthropic instance reuses its HTTP connection pool across
requests, and being async it never blocks the event loop while Claude
streams (the previous sync client froze every other request for the full
duration of a chat answer or addendum draft).
"""
from functools import lru_cache

import anthropic

from src.config import settings


@lru_cache(maxsize=1)
def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def response_text(message) -> str:
    """Join the text blocks of a Message (skips thinking / other block types)."""
    return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
