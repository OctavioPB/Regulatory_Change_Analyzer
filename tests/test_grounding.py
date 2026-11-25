"""Citation validator, system refusal and the regenerate-once loop (RAG chat)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services import grounding
from src.services.grounding import feedback, is_spanish, refusal_text, validate

TAGS = ["REG-1", "REG-2", "CON-3"]


def test_valid_citations_are_grounded_and_deduped_in_order():
    v = validate("A [REG-2]. B [REG-1, CON-3]. C [REG-2].", TAGS)
    assert v.cited == ("REG-2", "REG-1", "CON-3") and v.grounded


@pytest.mark.parametrize("answer,field", [
    ("Limit is 15% [REG-9].", "invalid"),
    ("Limit is 15% [REG-N].", "placeholders"),
])
def test_bad_tags_are_not_grounded(answer, field):
    v = validate(answer, TAGS)
    assert getattr(v, field) and not v.grounded and grounding.needs_regeneration(v)


def test_uncited_answer_is_retried_but_prose_refusal_is_not():
    uncited = validate("The limit is 15%.", TAGS)
    assert not uncited.grounded and grounding.needs_regeneration(uncited)
    declined = validate("Los documentos no contienen información suficiente sobre el plazo.", TAGS)
    assert declined.refused and not grounding.needs_regeneration(declined)
    empty = validate("   ", TAGS)
    assert empty.empty and grounding.needs_regeneration(empty)


def test_partial_answer_with_citation_is_not_a_refusal():
    v = validate("The circular does not contain information on fees, but sets a 15% limit [REG-1].", TAGS)
    assert v.grounded and not v.refused


def test_refusal_language_follows_the_question():
    assert is_spanish("¿Cuál es el nuevo límite?") and is_spanish("cual es el plazo para las SOFOM")
    assert not is_spanish("What is the new SOFOM limit?")
    assert refusal_text("¿Qué plazo?") == grounding.REFUSAL_ES
    assert refusal_text("Which deadline?") == grounding.REFUSAL_EN


def test_feedback_is_written_by_code_and_lists_the_real_tags():
    text = feedback(validate("x [REG-9] [CON-N]", TAGS), TAGS)
    assert "REG-9" in text and "CON-N" in text and "REG-1, REG-2, CON-3" in text


# ── RAG stream ────────────────────────────────────────────────────────────────

class _Stream:
    def __init__(self, text):
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            yield self._text
        return gen()

    async def get_final_message(self):
        return MagicMock(stop_reason="end_turn")


async def _run(answers, chunks):
    from src.services import rag_service as svc

    client = MagicMock()
    client.messages.stream = MagicMock(side_effect=[_Stream(a) for a in answers])
    with (
        patch.object(svc, "_retrieve", new=AsyncMock(return_value=chunks)),
        patch.object(svc, "get_client", return_value=client),
        patch.object(svc.settings, "anthropic_api_key", "sk-test"),
    ):
        events = [json.loads(c[6:]) async for c in svc.stream_query("What is the limit?", AsyncMock())]
    return events, client


def _chunk():
    from src.services.rag_service import ContextChunk
    return ContextChunk(1, "regulation", "Circular 12/2025", "CNBV", "Art 5", "15%")


@pytest.mark.asyncio
async def test_no_sources_means_system_refusal_without_a_model_call():
    events, client = await _run([], [])
    assert not client.messages.stream.called
    assert events[-2] == {"type": "token", "text": grounding.REFUSAL_EN}
    assert events[-1]["refused"] is True


@pytest.mark.asyncio
async def test_invalid_citation_is_regenerated_once_with_feedback():
    events, client = await _run(["15% [REG-7]", "15% [REG-1]"], [_chunk()])
    assert [e["type"] for e in events] == ["citations", "token", "reset", "token", "done"]
    assert events[-1] == {"type": "done", "grounded": True, "refused": False, "regenerations": 1}
    retry_msgs = client.messages.stream.call_args_list[1].kwargs["messages"]
    assert retry_msgs[1] == {"role": "assistant", "content": "15% [REG-7]"}
    assert "REG-7" in retry_msgs[2]["content"]


@pytest.mark.asyncio
async def test_still_ungrounded_after_retry_becomes_system_refusal():
    events, client = await _run(["15%", "fifteen percent"], [_chunk()])
    assert client.messages.stream.call_count == 2
    assert events[-4:] == [
        {"type": "reset"}, {"type": "citations", "citations": []},
        {"type": "token", "text": grounding.REFUSAL_EN},
        {"type": "done", "grounded": False, "refused": True, "regenerations": 1},
    ]


@pytest.mark.asyncio
async def test_model_prose_refusal_is_replaced_without_retry():
    events, client = await _run(["Sorry, I could not find that in the documents."], [_chunk()])
    assert client.messages.stream.call_count == 1
    assert events[-2]["text"] == grounding.REFUSAL_EN and events[-1]["refused"]
