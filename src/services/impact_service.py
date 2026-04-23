"""Impact mapping service — Sprint 3.

Orchestrates the full pipeline from a detected RegulatoryChange to ImpactAlerts:

    1. Load the change + its parent document from DB.
    2. Run the semantic mapper to find similar contract clauses (pgvector).
    3. Run the rules engine to identify additional contracts by keyword.
    4. Deduplicate targets across both paths.
    5. Create ImpactAlert + ImpactItems, generating suggestions for each.
"""
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mapping.rules_engine import RuleMatch, apply_rules, contracts_targeted_by_rules
from src.models.document import RegulatoryChange, RegulatoryDocument
from src.models.impact import ImpactItem, Severity
from src.recommendations.generator import generate_suggestion
from src.repositories import contract_repo, impact_repo

logger = logging.getLogger(__name__)

# ── Optional embedding dependency ────────────────────────────────────────────

try:
    from src.mapping.semantic_mapper import ClauseMatch, find_similar_clauses
    _HAS_SEMANTIC = True
except Exception:  # sentence-transformers not installed
    _HAS_SEMANTIC = False
    logger.warning("semantic_mapper unavailable — clause-level mapping disabled")


# ── Result data classes ───────────────────────────────────────────────────────

@dataclass
class ImpactResult:
    """Result of mapping one RegulatoryChange to contracts."""

    change_id: uuid.UUID
    alerts_created: int = 0
    items_created: int = 0
    skipped: bool = False
    error: str | None = None


@dataclass
class DocumentImpactResult:
    """Aggregated result of mapping all changes for one document."""

    document_id: uuid.UUID
    changes_processed: int = 0
    alerts_created: int = 0
    items_created: int = 0
    errors: list[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

async def map_change_to_contracts(
    change_id: uuid.UUID,
    db: AsyncSession,
) -> ImpactResult:
    """Map a single RegulatoryChange to affected contracts and create ImpactItems.

    Args:
        change_id: Primary key of the RegulatoryChange to process.
        db: Async SQLAlchemy session.

    Returns:
        ImpactResult with counts of created alerts and items.
    """
    result = await db.execute(
        select(RegulatoryChange)
        .where(RegulatoryChange.id == change_id)
        .options(selectinload(RegulatoryChange.document))
    )
    change = result.scalar_one_or_none()
    if change is None:
        return ImpactResult(change_id=change_id, error="Change not found", skipped=True)

    doc: RegulatoryDocument = change.document
    change_text = change.new_text or change.summary or ""

    if not change_text:
        return ImpactResult(change_id=change_id, skipped=True, error="No text to map")

    # ── 1. Semantic matching (clause-level) ──────────────────────────────────
    clause_matches: list[ClauseMatch] = []
    if _HAS_SEMANTIC and change_text:
        try:
            clause_matches = await find_similar_clauses(change_text, db, top_k=10)
        except Exception as exc:
            logger.warning("Semantic mapping failed: %s", exc)

    # ── 2. Rules engine (contract-type/area-level) ───────────────────────────
    rule_matches: list[RuleMatch] = apply_rules(change_text)
    targeted_types, targeted_areas = contracts_targeted_by_rules(rule_matches)

    # Contracts flagged by rules but not already covered by clause matches
    clause_contract_names = {m.contract_name for m in clause_matches}
    rule_contracts = []
    if targeted_types or targeted_areas:
        rule_contracts = await contract_repo.get_by_types_or_areas(
            db, targeted_types, targeted_areas
        )
        rule_contracts = [c for c in rule_contracts if c.name not in clause_contract_names]

    # Early exit: nothing to flag
    if not clause_matches and not rule_contracts:
        logger.info(
            "No contract targets found for change %s — no alert created", change_id
        )
        return ImpactResult(change_id=change_id, skipped=True)

    # ── 3. Create ImpactAlert ─────────────────────────────────────────────────
    alert_title = f"{doc.title}: {change.summary[:120]}" if doc.title else change.summary[:120]
    alert = await impact_repo.create_alert(db, doc.id, alert_title)
    items_created = 0

    # ── 4. Create ImpactItems for clause-level matches ───────────────────────
    for cm in clause_matches:
        suggestion = generate_suggestion(
            change_type=change.change_type,
            severity=cm.severity,
            clause_ref=cm.clause_ref,
            article_ref=change.article_ref or change.summary[:60],
            source_title=doc.title,
        )
        await impact_repo.create_item(
            db,
            alert_id=alert.id,
            change_id=change.id,
            impact_type="contract",
            affected_name=cm.contract_name,
            severity=cm.severity,
            suggestion=suggestion,
            clause_id=cm.clause_id,
            affected_ref=cm.clause_ref,
        )
        items_created += 1

    # ── 5. Create ImpactItems for rule-flagged contracts ─────────────────────
    # Determine the severity from the highest-severity matching rule
    rule_severity = _max_severity(rule_matches)
    for contract in rule_contracts:
        suggestion = generate_suggestion(
            change_type=change.change_type,
            severity=rule_severity,
            clause_ref=f"{contract.name} (flagged by keyword rule)",
            article_ref=change.article_ref or change.summary[:60],
            source_title=doc.title,
        )
        await impact_repo.create_item(
            db,
            alert_id=alert.id,
            change_id=change.id,
            impact_type="contract",
            affected_name=contract.name,
            severity=rule_severity,
            suggestion=suggestion,
            clause_id=None,
            affected_ref=None,
        )
        items_created += 1

    await db.commit()

    logger.info(
        "Change %s → alert %s, %d items (clauses=%d rules=%d)",
        change_id, alert.id, items_created, len(clause_matches), len(rule_contracts)
    )
    return ImpactResult(
        change_id=change_id,
        alerts_created=1,
        items_created=items_created,
    )


async def map_document_impacts(
    document_id: uuid.UUID,
    db: AsyncSession,
) -> DocumentImpactResult:
    """Map all changes for a document to contracts and create ImpactAlerts.

    Args:
        document_id: Primary key of the RegulatoryDocument to process.
        db: Async SQLAlchemy session.

    Returns:
        DocumentImpactResult with aggregate counts.
    """
    result = await db.execute(
        select(RegulatoryChange).where(RegulatoryChange.document_id == document_id)
    )
    changes = list(result.scalars().all())

    if not changes:
        logger.info("No changes found for document %s", document_id)
        return DocumentImpactResult(document_id=document_id)

    agg = DocumentImpactResult(document_id=document_id)
    for change in changes:
        impact_result = await map_change_to_contracts(change.id, db)
        if impact_result.error and not impact_result.skipped:
            agg.errors.append(impact_result.error)
        elif not impact_result.skipped:
            agg.changes_processed += 1
            agg.alerts_created += impact_result.alerts_created
            agg.items_created += impact_result.items_created

    logger.info(
        "Document %s: %d changes processed, %d alerts, %d items, %d errors",
        document_id, agg.changes_processed, agg.alerts_created,
        agg.items_created, len(agg.errors),
    )
    return agg


# ── Helpers ───────────────────────────────────────────────────────────────────

_SEVERITY_ORDER = {Severity.high: 2, Severity.medium: 1, Severity.low: 0}


def _max_severity(matches: list[RuleMatch]) -> Severity:
    """Return the highest severity across a list of rule matches."""
    if not matches:
        return Severity.low
    return max(matches, key=lambda m: _SEVERITY_ORDER[m.severity]).severity
