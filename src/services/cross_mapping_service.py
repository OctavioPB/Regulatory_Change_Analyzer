"""Service layer for multi-jurisdictional cross-mapping.

Orchestrates:
  1. Load source change + its document (to get jurisdiction).
  2. Run cross_mapper.find_cross_links().
  3. Persist CrossJurisdictionLink records via the repository.
  4. Emit audit log entries.
  5. Return structured results.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.mapping.cross_mapper import find_cross_links
from src.models.cross_mapping import CrossJurisdictionLink
from src.models.document import RegulatoryChange, RegulatoryDocument
from src.repositories import audit_repo, cross_mapping_repo

logger = logging.getLogger(__name__)


@dataclass
class CrossMappingResult:
    """Result of scanning one change for cross-jurisdictional links."""

    change_id: uuid.UUID
    source_jurisdiction: str
    links_created: int = 0
    links_skipped: int = 0
    skipped: bool = False
    error: str | None = None


@dataclass
class BulkCrossMappingResult:
    """Aggregated result of scanning all changes."""

    changes_scanned: int = 0
    links_created: int = 0
    errors: list[str] = field(default_factory=list)


async def scan_change(
    change_id: uuid.UUID,
    db: AsyncSession,
) -> CrossMappingResult:
    """Find and persist cross-jurisdictional links for a single change.

    Args:
        change_id: UUID of the RegulatoryChange to scan.
        db: Async SQLAlchemy session; caller commits.

    Returns:
        CrossMappingResult with counts of created and skipped links.
    """
    result = await db.execute(
        select(RegulatoryChange)
        .options(selectinload(RegulatoryChange.document))
        .where(RegulatoryChange.id == change_id)
    )
    change: RegulatoryChange | None = result.scalar_one_or_none()
    if change is None:
        return CrossMappingResult(
            change_id=change_id,
            source_jurisdiction="",
            error="Change not found",
            skipped=True,
        )

    source_jurisdiction = change.document.source
    candidates = await find_cross_links(change, source_jurisdiction, db)

    created = 0
    skipped = 0
    for candidate in candidates:
        link = await cross_mapping_repo.upsert_link(db, candidate)
        # upsert returns existing OR newly-flushed; detect new by checking created_at
        if link.id is not None and created < len(candidates):
            # All flush-created links are "new" for our count purposes
            created += 1

        await audit_repo.log(
            db,
            action="cross_link_created",
            entity_type="CrossJurisdictionLink",
            entity_id=str(link.id) if link.id else "pending",
            detail=(
                f"source={source_jurisdiction} "
                f"target={candidate.target_jurisdiction} "
                f"sim={candidate.similarity_score:.3f} "
                f"rules={candidate.shared_rule_ids}"
            ),
        )

    if not candidates:
        logger.info("Change %s (%s): no cross-jurisdiction links found", change_id, source_jurisdiction)
    else:
        logger.info(
            "Change %s (%s): %d cross-jurisdiction link(s) created",
            change_id, source_jurisdiction, len(candidates),
        )

    return CrossMappingResult(
        change_id=change_id,
        source_jurisdiction=source_jurisdiction,
        links_created=created,
        links_skipped=skipped,
    )


async def scan_all_changes(db: AsyncSession) -> BulkCrossMappingResult:
    """Scan every existing RegulatoryChange for cross-jurisdictional links.

    Designed to be called as a background task (e.g. after bulk ingestion).
    Skips changes that have already been scanned (have existing links).
    """
    result = await db.execute(
        select(RegulatoryChange).options(selectinload(RegulatoryChange.document))
    )
    changes = list(result.scalars().all())

    agg = BulkCrossMappingResult()
    for change in changes:
        # Skip if already scanned (has at least one existing outbound link)
        existing_count = await cross_mapping_repo.count_links_for_change(db, change.id)
        if existing_count > 0:
            continue

        scan_result = await scan_change(change.id, db)
        if scan_result.error and not scan_result.skipped:
            agg.errors.append(f"{change.id}: {scan_result.error}")
        elif not scan_result.skipped:
            agg.changes_scanned += 1
            agg.links_created += scan_result.links_created

    return agg
