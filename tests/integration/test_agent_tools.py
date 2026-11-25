"""Agent tools against a real database — the SQL is only verifiable here."""
import json

import pytest

from tests.integration.test_api_pipeline import API, _run_pipeline

pytestmark = pytest.mark.integration


async def test_every_research_tool_runs_against_postgres(client, session):
    from src.agents import tools as t

    doc_id = await _run_pipeline(client, session)
    ctx = t.AgentContext(db=session)

    alerts = await t.list_impact_alerts(ctx, t.ListAlertsInput())
    assert alerts and alerts[0]["items"] > 0
    assert await t.list_impact_alerts(ctx, t.ListAlertsInput(severity="high", unread_only=True)) is not None

    alert = await t.get_impact_alert(ctx, t.AlertIdInput(alert_id=alerts[0]["alert_id"]))
    assert alert["items"] and alert["items"][0]["change_id"]

    hits = await t.search_regulations(ctx, t.SearchRegulationsInput(query="capital mínimo SOFOM", source="CNBV"))
    assert hits and hits[0]["cite_as"].startswith("REG-")
    assert await t.search_regulations(ctx, t.SearchRegulationsInput(query="capital", source="SEC")) == []

    change = await t.get_regulatory_change(ctx, t.ChangeIdInput(change_id=hits[0]["change_id"]))
    assert "12%" in change["new_text"]
    assert await t.find_cross_jurisdiction(ctx, t.ChangeIdInput(change_id=hits[0]["change_id"])) == []

    contract = await t.get_contract(ctx, t.ContractInput(contract_name="SOFOM XYZ Loan"))
    assert contract["contract"] == "SOFOM XYZ Loan Portfolio Agreement" and contract["clauses"]

    clauses = await t.search_contract_clauses(
        ctx, t.SearchClausesInput(query="capital", contract_name="SOFOM"))
    assert all("SOFOM" in c["contract"] for c in clauses)

    with pytest.raises(LookupError):
        await t.get_contract(ctx, t.ContractInput(contract_name="does-not-exist"))
    with pytest.raises(LookupError):
        await t.get_regulatory_change(ctx, t.ChangeIdInput(change_id="not-a-uuid"))
    assert str(doc_id)  # pipeline really ran


async def test_agent_chat_without_key_falls_back_to_rag(client, session):
    await _run_pipeline(client, session)
    res = await client.post(f"{API}/agents/chat", json={"query": "capital mínimo SOFOM"})
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "citations" and events[-1]["type"] == "done"


async def test_agent_addendum_without_key_streams_plan_and_drafts(client, session):
    await _run_pipeline(client, session)
    alert = (await client.get(f"{API}/alerts/")).json()["items"][0]
    res = await client.post(f"{API}/agents/addendum/{alert['id']}")
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "plan" and types[-1] == "done"
    assert types.count("draft") == len(events[0]["contracts"]) >= 1
