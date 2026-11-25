"""End-to-end tests through the HTTP API against a real database."""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration

API = "/api/v1"

_CIRCULAR = """Artículo 1. Las SOFOM deberán mantener un coeficiente de capital mínimo del 12%
para todo crédito otorgado a partir de la entrada en vigor de esta circular.

Artículo 2. Las instituciones deberán presentar un reporte regulatorio trimestral
de apalancamiento ante la CNBV, a más tardar 30 días después del cierre.
"""


async def _insert_document(session, *, source="CNBV", title="Circular CNBV 7/2026", text=_CIRCULAR,
                           published=None) -> uuid.UUID:
    from src.models.document import RegulatoryDocument

    doc = RegulatoryDocument(
        source=source,
        external_id=f"{source}-{uuid.uuid4().hex[:12]}",
        title=title,
        url="https://example.org/doc",
        publication_date=published or datetime.now(timezone.utc),
        raw_text=text,
    )
    session.add(doc)
    await session.commit()
    return doc.id


async def _run_pipeline(client, session) -> uuid.UUID:
    assert (await client.post(f"{API}/contracts/seed")).status_code == 201
    doc_id = await _insert_document(session)
    assert (await client.post(f"{API}/documents/{doc_id}/analyze")).status_code == 202
    assert (await client.post(f"{API}/ingest/map")).status_code == 202
    return doc_id


async def test_health_reports_db_ok(client):
    body = (await client.get("/health")).json()
    assert body["status"] == "ok" and body["db"] == "ok"
    assert body["embeddings"] in {"available", "disabled"}


async def test_seed_contracts_is_idempotent(client):
    first = (await client.post(f"{API}/contracts/seed")).json()
    second = (await client.post(f"{API}/contracts/seed")).json()
    assert first["detail"].startswith("6 ")
    assert second["detail"].startswith("0 ") and second["skipped"] == 6
    assert len((await client.get(f"{API}/contracts/")).json()) == 6


async def test_full_pipeline_creates_alerts_and_supports_review(client, session):
    doc_id = await _run_pipeline(client, session)

    changes = (await client.get(f"{API}/documents/{doc_id}/changes")).json()
    assert {c["article_ref"] for c in changes} == {"artículo 1", "artículo 2"}

    page = (await client.get(f"{API}/alerts/")).json()
    assert page["total"] >= 1
    alert = page["items"][0]
    assert alert["document_id"] == str(doc_id)
    affected = {i["affected_name"] for i in alert["items"]}
    # Credit + capital keywords must reach the loan portfolio contract (rules R001/R007)
    assert "SOFOM XYZ Loan Portfolio Agreement" in affected

    item = alert["items"][0]
    ok = await client.post(
        f"{API}/alerts/{alert['id']}/items/{item['id']}/review",
        json={"status": "approved", "reviewer_notes": "Checked & approved <ok>"},
    )
    assert ok.status_code == 200

    # The item must belong to the alert in the URL
    wrong = await client.post(
        f"{API}/alerts/{uuid.uuid4()}/items/{item['id']}/review", json={"status": "rejected"},
    )
    assert wrong.status_code == 404

    detail = (await client.get(f"{API}/alerts/{alert['id']}")).json()
    reviewed = next(i for i in detail["items"] if i["id"] == item["id"])
    assert reviewed["approval_status"] == "approved"
    assert detail["is_read"] is True

    stats = (await client.get(f"{API}/dashboard/stats")).json()
    assert stats["documents"]["total"] == 1
    assert stats["changes"]["total"] == 2
    assert stats["alerts"]["total"] == page["total"]

    actions = {e["action"] for e in (await client.get(f"{API}/audit/")).json()}
    assert {"document_analyzed", "impact_alert_created", "item_approved"} <= actions


async def test_exports_render_with_markup_characters(client, session):
    await _run_pipeline(client, session)
    alert = (await client.get(f"{API}/alerts/")).json()["items"][0]
    item = alert["items"][0]
    await client.post(
        f"{API}/alerts/{alert['id']}/items/{item['id']}/review",
        json={"status": "modified", "reviewer_notes": "Limit < 20% & AT&T <clause>"},
    )

    pdf = await client.get(f"{API}/export/alerts/{alert['id']}.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    xlsx = await client.get(f"{API}/export/alerts/{alert['id']}.xlsx")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    bulk = await client.get(f"{API}/export/alerts.xlsx")
    assert bulk.status_code == 200


async def test_map_is_not_repeated_for_already_mapped_documents(client, session):
    await _run_pipeline(client, session)
    before = (await client.get(f"{API}/alerts/")).json()["total"]
    await client.post(f"{API}/ingest/map")
    assert (await client.get(f"{API}/alerts/")).json()["total"] == before


async def test_heatmap_endpoints_after_pipeline(client, session):
    await _run_pipeline(client, session)
    departments = (await client.get(f"{API}/heatmap/departments")).json()
    assert any(d["total"] > 0 for d in departments)
    assert max(d["churn_score"] for d in departments) == 1.0
    assert (await client.get(f"{API}/heatmap/matrix")).status_code == 200
    assert (await client.get(f"{API}/heatmap/trend?months=3")).status_code == 200


async def test_addendum_fallback_draft_streams_without_llm(client, session):
    await _run_pipeline(client, session)
    alert = (await client.get(f"{API}/alerts/")).json()["items"][0]

    res = await client.post(f"{API}/addendum/draft/{alert['id']}")
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "meta" and events[0]["contract_name"]
    assert events[-1]["type"] == "done"
    draft = "".join(e["text"] for e in events if e["type"] == "token")
    assert "IN WITNESS WHEREOF" in draft

    exported = await client.post(
        f"{API}/addendum/export", json={"draft_text": draft, "title": "A&B <x>", "format": "pdf"},
    )
    assert exported.status_code == 200 and exported.content.startswith(b"%PDF")


async def test_chat_stream_uses_text_fallback_and_cites_sources(client, session):
    await _run_pipeline(client, session)
    res = await client.post(f"{API}/chat/stream", json={"query": "What changed for SOFOM capital?"})
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "citations" and events[0]["citations"]
    assert events[-1]["type"] == "done"


async def test_chat_rejects_empty_query(client):
    assert (await client.post(f"{API}/chat/stream", json={"query": ""})).status_code == 422


async def test_trend_extraction_for_proposed_rule(client, session):
    await _insert_document(
        session, source="SEC", title="SEC Proposes Rule on Crypto Asset Custody",
        text="Notice of proposed rulemaking. Comment period of 60 days. Digital asset custody "
             "requirements for investment advisers, including disclosure obligations.",
        published=datetime.now(timezone.utc) - timedelta(days=3),
    )
    await _insert_document(session, title="Unrelated final rule", text="Final rule adopted.")
    assert (await client.post(f"{API}/trends/extract-all")).status_code == 202

    stats = (await client.get(f"{API}/trends/stats")).json()
    assert stats["total_signals"] == 1
    assert stats["by_doc_type"] == {"proposed_rule": 1}
    signal = (await client.get(f"{API}/trends/")).json()["items"][0]
    assert signal["domain"] == "fintech"
    assert signal["horizon_months"] == 8  # 60-day comment period → 2 + 6 months


async def test_cross_mapping_links_jurisdictions_by_shared_domain(client, session):
    from src.models.document import ChangeType, RegulatoryChange

    sec_doc = await _insert_document(session, source="SEC", title="SEC capital rule", text="x")
    cnbv_doc = await _insert_document(session, source="CNBV", title="CNBV capital rule", text="y")
    session.add_all([
        RegulatoryChange(document_id=sec_doc, change_type=ChangeType.new_requirement,
                         summary="Basel III leverage capital buffer", new_text="Basel III leverage capital buffer"),
        RegulatoryChange(document_id=cnbv_doc, change_type=ChangeType.limit_modification,
                         summary="Coeficiente de capital Basilea", new_text="Coeficiente de capital Basilea"),
    ])
    await session.commit()

    assert (await client.post(f"{API}/cross-mapping/scan-all")).status_code == 202
    links = (await client.get(f"{API}/cross-mapping/")).json()
    assert links["total"] >= 2  # SEC→CNBV and CNBV→SEC
    assert "R007" in json.loads(links["items"][0]["shared_rule_ids"])


async def test_contract_upload_ignores_client_path(client, tmp_path, monkeypatch):
    from docx import Document

    from src.config import settings

    monkeypatch.setattr(settings, "contracts_dir", tmp_path)
    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Clause one: the borrower shall maintain a leverage ratio below the regulatory threshold.")
    d.save(buf)

    res = await client.post(
        f"{API}/contracts/upload",
        params={"name": "Uploaded", "contract_type": "loan", "area": "Risk"},
        files={"file": ("../../escape.docx", buf.getvalue(), "application/octet-stream")},
    )
    assert res.status_code == 201, res.text
    assert not any(tmp_path.parent.parent.glob("escape.docx"))
    assert list(tmp_path.iterdir()) == []  # parsed in memory, nothing written


async def test_contract_upload_rejects_unknown_type(client):
    res = await client.post(
        f"{API}/contracts/upload",
        params={"name": "x", "contract_type": "loan"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400


async def test_rbac_enforced_when_api_keys_configured(client, monkeypatch):
    from src.auth import dependencies
    from src.config import settings

    monkeypatch.setattr(settings, "api_keys", '{"k-view": "viewer", "k-analyst": "analyst"}')
    dependencies._key_map.cache_clear()
    try:
        assert (await client.get(f"{API}/dashboard/stats")).status_code == 401
        assert (await client.get(f"{API}/dashboard/stats", headers={"X-API-Key": "nope"})).status_code == 403
        assert (await client.get(f"{API}/dashboard/stats", headers={"X-API-Key": "k-view"})).status_code == 200
        assert (await client.post(f"{API}/contracts/seed", headers={"X-API-Key": "k-view"})).status_code == 403
        assert (await client.post(f"{API}/contracts/seed", headers={"X-API-Key": "k-analyst"})).status_code == 201
        assert (await client.get(f"{API}/export/alerts.xlsx", headers={"X-API-Key": "k-analyst"})).status_code == 403
        assert (await client.get("/health")).status_code == 200
    finally:
        dependencies._key_map.cache_clear()


async def test_diff_baseline_is_the_same_circular_not_the_previous_one(client, session):
    """Circular 15 must not be diffed against Circular 12; a new version of 12 must be."""
    from sqlalchemy import select

    from src.models.document import RegulatoryChange

    t0 = datetime(2025, 3, 1, tzinfo=timezone.utc)
    v1 = "Artículo 5. El límite de contraparte es del 20% del capital neto.\n\nArtículo 6. Plazo de 90 días."
    v2 = "Artículo 5. El límite de contraparte es del 15% del capital neto.\n\nArtículo 6. Plazo de 90 días."
    other = "Artículo 1. Umbral de reporte de MXN 100,000 para operaciones electrónicas."
    c12 = await _insert_document(session, title="Circular 12/2025 — SOFOM", text=v1, published=t0)
    c15 = await _insert_document(session, title="Circular 15/2025 — PLD", text=other,
                                 published=t0 + timedelta(days=10))
    c12b = await _insert_document(session, title="Resolución que modifica la Circular 12/2025", text=v2,
                                  published=t0 + timedelta(days=20))
    for doc_id in (c12, c15, c12b):
        assert (await client.post(f"{API}/documents/{doc_id}/analyze")).status_code == 202

    async def changes(doc_id):
        rows = await session.execute(select(RegulatoryChange).where(RegulatoryChange.document_id == doc_id))
        return list(rows.scalars())

    pld = await changes(c15)
    assert all(c.old_text is None for c in pld)  # analysed on its own, nothing "removed"
    assert all("removed" not in c.summary.lower() for c in pld)
    amended = await changes(c12b)
    assert [c.article_ref for c in amended] == ["artículo 5"]  # only the modified article
    assert "20%" in (amended[0].old_text or "")
