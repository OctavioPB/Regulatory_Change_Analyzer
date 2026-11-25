"""Read-only database tools for the agents.

Every tool only SELECTs — agents can look things up but never change data
(approvals, reviews and exports stay with humans through the normal API).

Concurrency: an ``AsyncSession`` must not run two statements at once, but the
addendum team runs several subagents in parallel. All tools therefore go
through :class:`AgentContext`, which serialises DB access with a lock while the
(slow) model calls overlap freely.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.loop import Tool
from src.services import retrieval

logger = logging.getLogger(__name__)


# ── Run context + citation registry ───────────────────────────────────────────

@dataclass
class AgentContext:
    """Per-request state shared by all tools of a run (and its subagents)."""
    db: AsyncSession
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # (kind, key) → citation payload in the chat UI's ChatCitation shape
    sources: dict[tuple[str, str], dict] = field(default_factory=dict)

    async def fetch(self, sql: str, params: dict) -> list:
        async with self.lock:
            result = await self.db.execute(text(sql), params)
            return result.fetchall()

    def cite(self, kind: str, key: str, *, title: str, source: str, article_ref: str | None,
             excerpt: str | None, publication_date: str | None = None) -> str:
        """Register a source and return the tag Claude should cite (REG-3, CON-4)."""
        existing = self.sources.get((kind, key))
        if existing is None:
            existing = {
                "type": kind,
                "ref_id": len(self.sources) + 1,
                "title": title,
                "source": source,
                "article_ref": article_ref or "—",
                "excerpt": (excerpt or "")[:300],
                "publication_date": publication_date,
            }
            self.sources[(kind, key)] = existing
        prefix = "REG" if kind == "regulation" else "CON"
        return f"{prefix}-{existing['ref_id']}"

    def tags(self) -> list[str]:
        """Every tag handed to the model so far, in registration order."""
        return [f"{'REG' if c['type'] == 'regulation' else 'CON'}-{c['ref_id']}" for c in self.sources.values()]

    def cited_in(self, answer: str) -> list[dict]:
        """Sources whose tag appears in the final answer, in ref order."""
        out = []
        for c in self.sources.values():
            prefix = "REG" if c["type"] == "regulation" else "CON"
            if f"{prefix}-{c['ref_id']}" in answer:
                out.append(c)
        return sorted(out, key=lambda c: c["ref_id"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uuid(value: str, what: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise LookupError(f"'{value}' is not a valid {what} id") from None


def _date(dt) -> str | None:
    return dt.strftime("%Y-%m-%d") if dt else None


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── search_regulations ────────────────────────────────────────────────────────

class SearchRegulationsInput(_Input):
    query: str = Field(min_length=1, max_length=300, description="What to look for, in natural language or keywords.")
    source: Literal["CNBV", "SEC"] | None = Field(None, description="Restrict to one regulator.")
    limit: int = Field(5, ge=1, le=10)


async def search_regulations(ctx: AgentContext, args: SearchRegulationsInput) -> list[dict]:
    rows = await retrieval.search_changes(ctx.fetch, args.query, limit=args.limit, source=args.source)
    return [
        {
            "cite_as": ctx.cite("regulation", str(r.id), title=r.doc_title, source=r.source,
                                article_ref=r.article_ref, excerpt=r.new_text or r.summary,
                                publication_date=_date(r.publication_date)),
            "change_id": str(r.id),
            "document": r.doc_title,
            "source": r.source,
            "publication_date": _date(r.publication_date),
            "article_ref": r.article_ref,
            "change_type": r.change_type,
            "summary": r.summary,
            "excerpt": (r.new_text or "")[:400],
        }
        for r in rows
    ]


# ── get_regulatory_change ─────────────────────────────────────────────────────

class ChangeIdInput(_Input):
    change_id: str = Field(description="regulatory change id (UUID) from another tool's result")


async def get_regulatory_change(ctx: AgentContext, args: ChangeIdInput) -> dict:
    cid = _uuid(args.change_id, "change")
    rows = await ctx.fetch(
        """
        SELECT rc.id, rc.article_ref, rc.change_type, rc.summary, rc.old_text, rc.new_text,
               rd.title AS doc_title, rd.source, rd.publication_date, rd.url
        FROM regulatory_changes rc JOIN regulatory_documents rd ON rd.id = rc.document_id
        WHERE rc.id = CAST(:id AS uuid)
        """,
        {"id": cid},
    )
    if not rows:
        raise LookupError(f"regulatory change {cid} not found")
    r = rows[0]
    return {
        "cite_as": ctx.cite("regulation", cid, title=r.doc_title, source=r.source,
                            article_ref=r.article_ref, excerpt=r.new_text or r.summary,
                            publication_date=_date(r.publication_date)),
        "change_id": cid,
        "document": r.doc_title,
        "source": r.source,
        "url": r.url,
        "publication_date": _date(r.publication_date),
        "article_ref": r.article_ref,
        "change_type": r.change_type,
        "summary": r.summary,
        "previous_text": (r.old_text or "")[:3000] or None,
        "new_text": (r.new_text or "")[:5000] or None,
    }


# ── find_cross_jurisdiction ───────────────────────────────────────────────────

async def find_cross_jurisdiction(ctx: AgentContext, args: ChangeIdInput) -> list[dict]:
    cid = _uuid(args.change_id, "change")
    rows = await ctx.fetch(
        """
        SELECT l.similarity_score, l.analysis, l.shared_rule_ids,
               CASE WHEN l.source_change_id = CAST(:id AS uuid) THEN l.target_change_id
                    ELSE l.source_change_id END AS other_id,
               CASE WHEN l.source_change_id = CAST(:id AS uuid) THEN l.target_jurisdiction
                    ELSE l.source_jurisdiction END AS other_jurisdiction,
               rd.title AS other_document, rc.article_ref AS other_article
        FROM cross_jurisdiction_links l
        JOIN regulatory_changes rc ON rc.id = CASE WHEN l.source_change_id = CAST(:id AS uuid)
                                                   THEN l.target_change_id ELSE l.source_change_id END
        JOIN regulatory_documents rd ON rd.id = rc.document_id
        WHERE l.source_change_id = CAST(:id AS uuid) OR l.target_change_id = CAST(:id AS uuid)
        ORDER BY l.similarity_score DESC
        LIMIT 10
        """,
        {"id": cid},
    )
    return [
        {
            "other_change_id": str(r.other_id),
            "jurisdiction": r.other_jurisdiction,
            "document": r.other_document,
            "article_ref": r.other_article,
            "similarity": round(float(r.similarity_score), 3),
            "shared_rules": r.shared_rule_ids,
            "analysis": r.analysis,
        }
        for r in rows
    ]


# ── search_contract_clauses ───────────────────────────────────────────────────

class SearchClausesInput(_Input):
    query: str = Field(min_length=1, max_length=300)
    contract_name: str | None = Field(None, max_length=300, description="Restrict to one contract (partial name ok).")
    limit: int = Field(5, ge=1, le=10)


async def search_contract_clauses(ctx: AgentContext, args: SearchClausesInput) -> list[dict]:
    rows = await retrieval.search_clauses(ctx.fetch, args.query, limit=args.limit,
                                          contract_name=args.contract_name)
    return [
        {
            "cite_as": ctx.cite("contract", str(r.id), title=r.name, source=r.area or "Internal",
                                article_ref=r.clause_ref, excerpt=r.text),
            "clause_id": str(r.id),
            "contract": r.name,
            "area": r.area,
            "clause_ref": r.clause_ref,
            "text": r.text[:800],
        }
        for r in rows
    ]


# ── get_contract ──────────────────────────────────────────────────────────────

class ContractInput(_Input):
    contract_name: str = Field(min_length=1, max_length=300, description="Exact or partial contract name.")


async def get_contract(ctx: AgentContext, args: ContractInput) -> dict:
    contracts = await ctx.fetch(
        """
        SELECT id, name, contract_type, area FROM contracts
        WHERE name ILIKE :like
        ORDER BY (lower(name) = lower(:exact)) DESC, length(name)
        LIMIT 5
        """,
        {"like": f"%{args.contract_name}%", "exact": args.contract_name},
    )
    if not contracts:
        raise LookupError(f"no contract matches '{args.contract_name}'")
    c = contracts[0]
    clauses = await ctx.fetch(
        "SELECT id, clause_ref, text FROM contract_clauses WHERE contract_id = :id ORDER BY clause_ref",
        {"id": c.id},
    )
    return {
        "contract": c.name,
        "contract_type": c.contract_type,
        "area": c.area,
        "other_matches": [o.name for o in contracts[1:]],
        "clauses": [
            {
                "cite_as": ctx.cite("contract", str(cl.id), title=c.name, source=c.area or "Internal",
                                    article_ref=cl.clause_ref, excerpt=cl.text),
                "clause_ref": cl.clause_ref,
                "text": cl.text[:1500],
            }
            for cl in clauses[:40]
        ],
    }


# ── list_impact_alerts / get_impact_alert ─────────────────────────────────────

class ListAlertsInput(_Input):
    limit: int = Field(10, ge=1, le=25)
    severity: Literal["high", "medium", "low"] | None = Field(None, description="Only alerts with at least one item of this severity.")
    unread_only: bool = False


async def list_impact_alerts(ctx: AgentContext, args: ListAlertsInput) -> list[dict]:
    rows = await ctx.fetch(
        """
        SELECT ia.id, ia.title, ia.is_read, ia.created_at, rd.source, rd.title AS doc_title,
               count(ii.id) AS items,
               count(ii.id) FILTER (WHERE ii.severity = 'high')    AS high,
               count(ii.id) FILTER (WHERE ii.severity = 'medium')  AS medium,
               count(ii.id) FILTER (WHERE ii.approval_status = 'pending') AS pending
        FROM impact_alerts ia
        JOIN regulatory_documents rd ON rd.id = ia.document_id
        LEFT JOIN impact_items ii ON ii.alert_id = ia.id
        WHERE (:unread = false OR ia.is_read = false)
        GROUP BY ia.id, rd.source, rd.title
        HAVING CAST(:severity AS text) IS NULL
            OR count(ii.id) FILTER (WHERE CAST(ii.severity AS text) = :severity) > 0
        ORDER BY ia.created_at DESC
        LIMIT :limit
        """,
        {"limit": args.limit, "severity": args.severity, "unread": args.unread_only},
    )
    return [
        {
            "alert_id": str(r.id),
            "title": r.title,
            "document": r.doc_title,
            "source": r.source,
            "created_at": _date(r.created_at),
            "unread": not r.is_read,
            "items": r.items,
            "high_severity_items": r.high,
            "medium_severity_items": r.medium,
            "pending_review": r.pending,
        }
        for r in rows
    ]


class AlertIdInput(_Input):
    alert_id: str = Field(description="impact alert id (UUID)")


async def get_impact_alert(ctx: AgentContext, args: AlertIdInput) -> dict:
    aid = _uuid(args.alert_id, "alert")
    rows = await ctx.fetch(
        """
        SELECT ia.title, rd.title AS doc_title, rd.source,
               ii.impact_type, ii.affected_name, ii.affected_ref, ii.severity, ii.suggestion,
               ii.approval_status, ii.change_id, rc.article_ref, rc.summary
        FROM impact_alerts ia
        JOIN regulatory_documents rd ON rd.id = ia.document_id
        LEFT JOIN impact_items ii ON ii.alert_id = ia.id
        LEFT JOIN regulatory_changes rc ON rc.id = ii.change_id
        WHERE ia.id = CAST(:id AS uuid)
        ORDER BY ii.severity, ii.affected_name
        """,
        {"id": aid},
    )
    if not rows:
        raise LookupError(f"impact alert {aid} not found")
    head = rows[0]
    return {
        "alert_id": aid,
        "title": head.title,
        "document": head.doc_title,
        "source": head.source,
        "items": [
            {
                "impact_type": r.impact_type,
                "affected": r.affected_name,
                "affected_ref": r.affected_ref,
                "severity": r.severity,
                "suggestion": r.suggestion,
                "review_status": r.approval_status,
                "change_id": str(r.change_id),
                "article_ref": r.article_ref,
                "change_summary": r.summary,
            }
            for r in rows if r.affected_name is not None
        ],
    }


# ── Tool sets ─────────────────────────────────────────────────────────────────

SEARCH_REGULATIONS = Tool(
    "search_regulations",
    "Search ingested CNBV/SEC regulatory changes. Returns change ids, document, article, summary and an "
    "excerpt. Use get_regulatory_change for the full text of a hit.",
    SearchRegulationsInput, search_regulations,
)
GET_REGULATORY_CHANGE = Tool(
    "get_regulatory_change",
    "Full previous and new text of one regulatory change, with its document, source and date.",
    ChangeIdInput, get_regulatory_change,
)
FIND_CROSS_JURISDICTION = Tool(
    "find_cross_jurisdiction",
    "Equivalent changes in the other jurisdiction (CNBV↔SEC) for a change id, with similarity and analysis. "
    "Empty when cross-mapping has not been run for it.",
    ChangeIdInput, find_cross_jurisdiction,
)
SEARCH_CONTRACT_CLAUSES = Tool(
    "search_contract_clauses",
    "Search internal contract clauses by topic, optionally within one contract.",
    SearchClausesInput, search_contract_clauses,
)
GET_CONTRACT = Tool(
    "get_contract",
    "A contract's type, area and the full text of all its clauses, by (partial) name.",
    ContractInput, get_contract,
)
LIST_IMPACT_ALERTS = Tool(
    "list_impact_alerts",
    "Most recent impact alerts (one per regulatory document) with item counts by severity and review status.",
    ListAlertsInput, list_impact_alerts,
)
GET_IMPACT_ALERT = Tool(
    "get_impact_alert",
    "Every impacted contract clause / process of one alert: severity, suggested action, review status, change id.",
    AlertIdInput, get_impact_alert,
)

RESEARCH_TOOLS = [
    SEARCH_REGULATIONS, GET_REGULATORY_CHANGE, FIND_CROSS_JURISDICTION,
    SEARCH_CONTRACT_CLAUSES, GET_CONTRACT, LIST_IMPACT_ALERTS, GET_IMPACT_ALERT,
]
DRAFTING_TOOLS = [GET_REGULATORY_CHANGE, GET_CONTRACT, SEARCH_REGULATIONS]
REVIEW_TOOLS = [GET_REGULATORY_CHANGE, GET_CONTRACT]
