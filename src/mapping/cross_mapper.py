"""Multi-jurisdictional cross-mapping algorithm.

Detects when a regulatory change in one jurisdiction (e.g. SEC/USA) has
secondary compliance implications in another jurisdiction (e.g. CNBV/Mexico).

Algorithm (two-stage validation):
  Stage 1 — Semantic: pgvector cosine similarity between change embeddings.
             Requires both changes to have embeddings populated by nlp_service.
  Stage 2 — Domain:   rules-engine overlap. Candidates that share at least one
             regulatory domain (R001–R008) with the source change are retained;
             the rest are discarded regardless of similarity score.

If the source change has no embedding, Stage 1 is replaced by a rules-only scan
that loads recent changes from other jurisdictions and checks domain overlap.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.mapping.rules_engine import _RULES, apply_rules
from src.models.document import EMBEDDING_DIM, RegulatoryChange, RegulatoryDocument

logger = logging.getLogger(__name__)

# Cosine similarity thresholds
_HIGH_SIM = 0.75
_MIN_SIM = 0.60  # discard candidates below this

# When using rules-only fallback, scan at most this many recent changes
_RULES_ONLY_SCAN_LIMIT = 100


@dataclass
class CrossCandidate:
    """A candidate cross-jurisdictional link found by the mapper."""

    source_change_id: str
    target_change_id: str
    source_jurisdiction: str
    target_jurisdiction: str
    similarity_score: float
    shared_rule_ids: list[str]
    analysis: str


async def find_cross_links(
    change: RegulatoryChange,
    source_jurisdiction: str,
    db: AsyncSession,
    top_k: int = 10,
) -> list[CrossCandidate]:
    """Find changes from other jurisdictions that overlap with *change*.

    Args:
        change: The source RegulatoryChange to map.
        source_jurisdiction: The jurisdiction string of the source (e.g. "CNBV").
        db: Async SQLAlchemy session.
        top_k: Maximum number of candidates to evaluate.

    Returns:
        List of CrossCandidate, one per confirmed cross-link (after both stages).
        Empty list if nothing passes the double-validation filter.
    """
    source_text = change.new_text or change.summary or ""
    source_rules = apply_rules(source_text)
    source_rule_ids = {m.rule_id for m in source_rules}

    if not source_rule_ids:
        logger.debug(
            "Change %s fires no rules — skipping cross-mapping (no regulatory domain)", change.id
        )
        return []

    if change.embedding is not None:
        raw_candidates = await _embedding_candidates(
            change, source_jurisdiction, db, top_k
        )
    else:
        logger.info(
            "Change %s has no embedding — falling back to rules-only cross-mapping", change.id
        )
        raw_candidates = await _rules_only_candidates(
            change, source_jurisdiction, db, _RULES_ONLY_SCAN_LIMIT
        )

    # Stage 2 — filter by shared rule domains
    confirmed: list[CrossCandidate] = []
    for cand_change, sim in raw_candidates:
        cand_text = cand_change.new_text or cand_change.summary or ""
        cand_rules = apply_rules(cand_text)
        cand_rule_ids = {m.rule_id for m in cand_rules}
        shared = sorted(source_rule_ids & cand_rule_ids)
        if not shared:
            continue

        target_jurisdiction = cand_change.document.source
        analysis = _build_analysis(
            change, source_jurisdiction, cand_change, target_jurisdiction, sim, shared
        )
        confirmed.append(
            CrossCandidate(
                source_change_id=str(change.id),
                target_change_id=str(cand_change.id),
                source_jurisdiction=source_jurisdiction,
                target_jurisdiction=target_jurisdiction,
                similarity_score=round(sim, 4),
                shared_rule_ids=shared,
                analysis=analysis,
            )
        )

    logger.info(
        "Cross-mapping change %s (%s): %d/%d candidates passed double-validation",
        change.id, source_jurisdiction, len(confirmed), len(raw_candidates),
    )
    return confirmed


# ── Stage 1a: embedding-based candidate retrieval ────────────────────────────

async def _embedding_candidates(
    change: RegulatoryChange,
    source_jurisdiction: str,
    db: AsyncSession,
    top_k: int,
) -> list[tuple[RegulatoryChange, float]]:
    """Return (change, similarity) pairs from other jurisdictions via pgvector."""
    stmt = text(
        """
        SELECT
            rc.id,
            1 - (rc.embedding <=> CAST(:vec AS vector)) AS similarity
        FROM regulatory_changes rc
        JOIN regulatory_documents rd ON rd.id = rc.document_id
        WHERE rc.embedding IS NOT NULL
          AND rd.source != :source_jurisdiction
          AND rc.id != :source_id
        ORDER BY rc.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )
    rows = await db.execute(
        stmt,
        {
            "vec": str(change.embedding),
            "source_jurisdiction": source_jurisdiction,
            "source_id": str(change.id),
            "top_k": top_k,
        },
    )
    raw = rows.fetchall()

    pairs: list[tuple[RegulatoryChange, float]] = []
    for row in raw:
        sim = float(row.similarity)
        if sim < _MIN_SIM:
            continue
        target = await _load_change_with_doc(row.id, db)
        if target is not None:
            pairs.append((target, sim))
    return pairs


# ── Stage 1b: rules-only candidate retrieval (no embedding fallback) ──────────

async def _rules_only_candidates(
    change: RegulatoryChange,
    source_jurisdiction: str,
    db: AsyncSession,
    limit: int,
) -> list[tuple[RegulatoryChange, float]]:
    """Return recent changes from other jurisdictions (similarity_score=0.0 placeholder)."""
    result = await db.execute(
        select(RegulatoryChange)
        .join(RegulatoryDocument, RegulatoryChange.document_id == RegulatoryDocument.id)
        .where(RegulatoryDocument.source != source_jurisdiction)
        .where(RegulatoryChange.id != change.id)
        .order_by(RegulatoryChange.created_at.desc())
        .limit(limit)
    )
    changes = list(result.scalars().all())

    # Eager-load documents (they may be lazy)
    pairs: list[tuple[RegulatoryChange, float]] = []
    for c in changes:
        if c.document is None:
            c = await _load_change_with_doc(c.id, db)
            if c is None:
                continue
        pairs.append((c, 0.0))
    return pairs


async def _load_change_with_doc(
    change_id, db: AsyncSession
) -> RegulatoryChange | None:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(RegulatoryChange)
        .options(selectinload(RegulatoryChange.document))
        .where(RegulatoryChange.id == change_id)
    )
    return result.scalar_one_or_none()


# ── Analysis text generation ──────────────────────────────────────────────────

_RULE_DESCRIPTIONS: dict[str, str] = {
    r["id"]: r["description"] for r in _RULES
}


def _build_analysis(
    source: RegulatoryChange,
    source_jur: str,
    target: RegulatoryChange,
    target_jur: str,
    similarity: float,
    shared_rule_ids: list[str],
) -> str:
    domain_descs = [
        _RULE_DESCRIPTIONS.get(rid, rid) for rid in shared_rule_ids
    ]
    domains_text = "; ".join(domain_descs)
    rule_ids_text = ", ".join(shared_rule_ids)

    sim_label = "high" if similarity >= _HIGH_SIM else "moderate" if similarity > 0 else "rule-based"
    sim_note = (
        f"Semantic similarity: {similarity:.2f} ({sim_label})."
        if similarity > 0
        else "Match identified via shared regulatory domain (no embedding available)."
    )

    return (
        f"{source_jur} change — \"{source.summary[:100]}\" — "
        f"may have secondary compliance implications in {target_jur}.\n\n"
        f"Related {target_jur} regulation: \"{target.summary[:100]}\".\n\n"
        f"Shared regulatory domains: {domains_text} (Rules: {rule_ids_text}).\n"
        f"{sim_note}\n\n"
        f"Recommended action: A {target_jur} compliance officer should verify whether "
        f"this {source_jur} change requires corresponding adjustments to {target_jur} "
        f"policies, contracts, or reporting obligations."
    )
