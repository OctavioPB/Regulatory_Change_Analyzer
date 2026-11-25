"""Embedding backends (Ollama bge-m3 by default) and hybrid rank fusion."""
from types import SimpleNamespace

import httpx
import pytest

from src.config import settings
from src.mapping import embedder
from src.services.retrieval import rrf


@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "ollama")
    monkeypatch.setattr(settings, "embedding_model", "bge-m3")
    monkeypatch.setattr(settings, "embedding_dim", 3)
    embedder.reset_probe()
    calls = []

    def get(url, **kw):
        calls.append(url)
        return httpx.Response(200, json={"models": [{"name": "bge-m3:latest"}]}, request=httpx.Request("GET", url))

    def post(url, json, **kw):
        calls.append(json)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]] * len(json["input"])},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(embedder.httpx, "get", get)
    monkeypatch.setattr(embedder.httpx, "post", post)
    yield calls
    embedder.reset_probe()


def test_ollama_batch_embeds_without_silent_truncation(ollama):
    assert embedder.available()
    assert embedder.embed_batch(["a", "b"]) == [[0.1, 0.2, 0.3]] * 2
    body = ollama[-1]
    assert body == {"model": "bge-m3", "input": ["a", "b"], "truncate": False}


def test_availability_probe_is_cached(ollama):
    embedder.available()
    embedder.available()
    assert sum(isinstance(c, str) for c in ollama) == 1


def test_wrong_dimension_raises_instead_of_storing(ollama, monkeypatch):
    monkeypatch.setattr(settings, "embedding_dim", 1024)
    with pytest.raises(embedder.EmbeddingsUnavailable, match="1024"):
        embedder.embed_text("x")


def test_model_not_pulled_or_ollama_down_means_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "ollama")
    monkeypatch.setattr(settings, "embedding_model", "bge-m3")
    embedder.reset_probe()
    monkeypatch.setattr(embedder.httpx, "get", lambda url, **kw: httpx.Response(
        200, json={"models": [{"name": "qwen3:4b"}]}, request=httpx.Request("GET", url)))
    assert not embedder.available()
    embedder.reset_probe()

    def down(url, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(embedder.httpx, "get", down)
    assert not embedder.available()
    embedder.reset_probe()


def test_provider_none_is_never_available():
    assert settings.embedding_provider == "none"  # forced by conftest
    assert not embedder.available()
    with pytest.raises(embedder.EmbeddingsUnavailable):
        embedder.embed_batch(["x"])


@pytest.mark.asyncio
async def test_schema_mismatch_disables_embeddings(monkeypatch, ollama):
    class Conn:
        async def execute(self, *_a, **_k):
            return SimpleNamespace(first=lambda: (384,))

    dims = await embedder.check_schema(Conn())
    assert dims == {"regulatory_changes": 384, "contract_clauses": 384}
    assert not embedder.available()
    monkeypatch.setattr(settings, "embedding_dim", 384)
    await embedder.check_schema(Conn())
    embedder.reset_probe()
    assert embedder.available()


def _r(i):
    return SimpleNamespace(id=i)


def test_rrf_uses_ranks_and_breaks_ties_by_id():
    semantic = [_r("b"), _r("a"), _r("c")]
    lexical = [_r("a"), _r("d")]
    assert [r.id for r in rrf([semantic, lexical], key=lambda r: r.id)] == ["a", "b", "d", "c"]
    # same inputs → same order; symmetric ties resolved by id, not by arm order
    assert [r.id for r in rrf([[_r("y")], [_r("x")]], key=lambda r: r.id)] == ["x", "y"]
    assert rrf([[], []], key=lambda r: r.id) == []


def test_vector_literal_writes_every_component_of_a_1024_dim_numpy_vector():
    """str(numpy) elides arrays > 1000 items — the cross-mapper query broke with bge-m3."""
    import numpy as np

    vec = np.linspace(-1, 1, 1024, dtype=np.float32)
    lit = embedder.vector_literal(vec)
    assert "..." not in lit and lit.startswith("[") and lit.count(",") == 1023
    assert embedder.vector_literal([0.5, -1]) == "[0.5,-1.0]"
