"""Regression tests for bugs fixed during the code audit."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── PDF exports must survive markup characters in user/LLM text ─────────────

def test_alert_pdf_escapes_markup_in_text():
    from src.models.impact import ApprovalStatus, ImpactAlert, ImpactItem, Severity
    from src.services.export_service import export_alert_pdf

    item = MagicMock(spec=ImpactItem)
    item.severity = Severity.high
    item.affected_name = "AT&T <Master> Agreement"
    item.affected_ref = "Clause <4.2>"
    item.impact_type = "contract"
    item.approval_status = ApprovalStatus.modified
    item.suggestion = "Limit must be < 20% & reviewed"
    item.reviewer_notes = "ok <b>unclosed"

    alert = MagicMock(spec=ImpactAlert)
    alert.id = uuid.uuid4()
    alert.document_id = uuid.uuid4()
    alert.title = "Circular & <test>"
    alert.items = [item]

    pdf = export_alert_pdf(alert)
    assert pdf.startswith(b"%PDF")


def test_addendum_pdf_and_docx_escape_markup():
    from src.services.addendum_service import export_docx, export_pdf

    draft = "ADDENDUM TO AT&T <CONTRACT>\n----\nWHEREAS limits < 20% & more\n----\nBody & <tag>"
    assert export_pdf(draft, "R&D <Addendum>").startswith(b"%PDF")
    assert export_docx(draft, "R&D <Addendum>")[:2] == b"PK"


# ── Addendum SSE contract matches the frontend (contract_name) ──────────────

@pytest.mark.asyncio
async def test_addendum_stream_meta_uses_contract_name_and_single_done():
    from src.services import addendum_service as svc

    ctx = svc.AddendumContext(contract_name="Loan Agreement", contract_area="Risk")
    ctx.items.append(svc.AddendumItem(
        affected_name="Loan Agreement", affected_ref="Clause 1", suggestion="Update",
        original_clause_text=None, change_summary="x", article_ref="Art 1",
        change_type="other", doc_title="Doc", source="CNBV", publication_date=None,
        contract_area="Risk",
    ))

    with (
        patch.object(svc, "fetch_context", new=AsyncMock(return_value=[ctx, ctx])),
        patch.object(svc.settings, "anthropic_api_key", ""),
    ):
        events = [json.loads(chunk[6:]) async for chunk in svc.stream_draft("id", AsyncMock())]

    metas = [e for e in events if e["type"] == "meta"]
    assert metas and all(m["contract_name"] == "Loan Agreement" for m in metas)
    assert [e["type"] for e in events].count("done") == 1
    assert events[-1]["type"] == "done"


# ── Rules engine: "land" is not an AML keyword ──────────────────────────────

def test_aml_rule_ignores_land_but_matches_laundering():
    from src.mapping.rules_engine import apply_rules

    assert "R003" not in {m.rule_id for m in apply_rules("Rules for agricultural land use")}
    assert "R003" in {m.rule_id for m in apply_rules("New anti money laundering duties")}


# ── Feed dates are always timezone-aware ────────────────────────────────────

def test_parse_feed_date_gmt_is_aware():
    from src.ingestion.base import parse_feed_date

    d = parse_feed_date("Mon, 20 Jan 2025 12:00:00 GMT")
    assert d == datetime(2025, 1, 20, 12, tzinfo=timezone.utc)
    assert parse_feed_date("not a date") is None


# ── Trend horizon no longer hard-coded to 2025–2030 ─────────────────────────

def test_trend_horizon_year_relative_to_publication():
    from src.nlp.trend_extractor import _estimate_horizon

    pub = datetime(2031, 1, 1, tzinfo=timezone.utc)
    months, pred = _estimate_horizon("compliance date: June 2032", pub, "proposed_rule")
    assert pred is not None and pred.year == 2032
    assert months > 0


# ── Rate limiter drops idle buckets ─────────────────────────────────────────

def test_rate_limiter_prunes_expired_buckets():
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from src.api.middleware.rate_limit import IngestRateLimitMiddleware

    async def ok(_):
        return Response("ok", status_code=202)

    app = Starlette(routes=[Route("/api/v1/ingest/x", ok, methods=["POST"])])
    app.add_middleware(IngestRateLimitMiddleware, max_requests=5, window_seconds=60)
    client = TestClient(app)
    assert client.post("/api/v1/ingest/x").status_code == 202

    mw = app.middleware_stack
    while not isinstance(mw, IngestRateLimitMiddleware):
        mw = mw.app
    mw._buckets["10.0.0.1"] = __import__("collections").deque([-1e9])  # long expired
    client.post("/api/v1/ingest/x")
    assert "10.0.0.1" not in mw._buckets


# ── Every API route except /health enforces RBAC ────────────────────────────

def test_all_routes_require_role():
    """Every operation must carry the X-API-Key security scheme (added by Require*).

    Uses the public OpenAPI schema rather than app.routes, whose structure
    changed across FastAPI versions (included routers became lazy objects).
    """
    from src.api.main import app

    paths = app.openapi()["paths"]
    unprotected = sorted(
        f"{method.upper()} {path}"
        for path, ops in paths.items()
        for method, op in ops.items()
        if not op.get("security")
    )
    assert unprotected == ["GET /health"]
    assert len(paths) > 30  # sanity: routers really were included


# ── LLM streams surface refusals instead of ending silently ─────────────────

class _FakeStream:
    def __init__(self, chunks, stop_reason):
        self._chunks, self._stop = chunks, stop_reason

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for c in self._chunks:
                yield c
        return gen()

    async def get_final_message(self):
        return MagicMock(stop_reason=self._stop)


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_reason,last_type", [("end_turn", "done"), ("refusal", "error")])
async def test_rag_stream_handles_stop_reason(stop_reason, last_type):
    from src.services import rag_service as svc

    client = MagicMock()
    client.messages.stream = MagicMock(return_value=_FakeStream(["Hi"], stop_reason))
    with (
        patch.object(svc, "_retrieve", new=AsyncMock(return_value=[])),
        patch.object(svc, "get_client", return_value=client),
        patch.object(svc.settings, "anthropic_api_key", "sk-test"),
    ):
        events = [json.loads(c[6:]) async for c in svc.stream_query("q", AsyncMock())]

    assert events[-1]["type"] == last_type
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == svc.settings.llm_model
    assert kwargs["output_config"] == {"effort": "medium"}


def test_addendum_draft_requires_analyst(monkeypatch):
    """A viewer key is rejected before the endpoint (and the LLM) ever runs."""
    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.auth import dependencies
    from src.config import settings

    monkeypatch.setattr(settings, "api_keys", '{"k-view": "viewer"}')
    dependencies._key_map.cache_clear()
    try:
        # No `with` block: lifespan (init_db) is not started, so no DB is needed
        client = TestClient(app)
        res = client.post(f"/api/v1/addendum/draft/{uuid.uuid4()}", headers={"X-API-Key": "k-view"})
        assert res.status_code == 403
        assert "analyst" in res.json()["detail"]
    finally:
        dependencies._key_map.cache_clear()
