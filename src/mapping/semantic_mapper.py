import logging
import uuid
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.mapping.embedder import embed_text
from src.models.contract import ContractClause
from src.models.impact import Severity

logger = logging.getLogger(__name__)

# Similarity thresholds for severity assignment
_HIGH_THRESHOLD = 0.80
_MEDIUM_THRESHOLD = 0.65


@dataclass
class ClauseMatch:
    """A clause that semantically matches a regulatory change."""

    clause_id: uuid.UUID
    clause_ref: str
    contract_name: str
    similarity: float
    severity: Severity


async def find_similar_clauses(
    change_text: str,
    db: AsyncSession,
    top_k: int = 10,
) -> list[ClauseMatch]:
    """Find contract clauses semantically similar to a regulatory change.

    Uses pgvector cosine similarity over pre-computed clause embeddings.

    Args:
        change_text: Text of the detected regulatory change.
        db: Async SQLAlchemy session.
        top_k: Maximum number of results to return.

    Returns:
        List of ClauseMatch sorted by descending similarity.
    """
    query_vector = embed_text(change_text)

    stmt = text(
        """
        SELECT
            cc.id,
            cc.clause_ref,
            c.name AS contract_name,
            1 - (cc.embedding <=> CAST(:vec AS vector)) AS similarity
        FROM contract_clauses cc
        JOIN contracts c ON c.id = cc.contract_id
        WHERE cc.embedding IS NOT NULL
        ORDER BY cc.embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )

    result = await db.execute(stmt, {"vec": str(query_vector), "top_k": top_k})
    rows = result.fetchall()

    matches: list[ClauseMatch] = []
    for row in rows:
        similarity = float(row.similarity)
        if similarity < _MEDIUM_THRESHOLD:
            continue
        severity = (
            Severity.high if similarity >= _HIGH_THRESHOLD
            else Severity.medium if similarity >= _MEDIUM_THRESHOLD
            else Severity.low
        )
        matches.append(
            ClauseMatch(
                clause_id=row.id,
                clause_ref=row.clause_ref or "",
                contract_name=row.contract_name,
                similarity=similarity,
                severity=severity,
            )
        )

    logger.info("Found %d clause matches for change text (%d chars)", len(matches), len(change_text))
    return matches
