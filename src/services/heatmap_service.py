"""Risk heatmap aggregation -- regulatory churn by business department."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import ChangeType
from src.models.impact import Severity

logger = logging.getLogger(__name__)

# ---- Department catalogue ----------------------------------------------------

DEPARTMENTS = ["AML", "Risk", "Compliance", "Legal", "Treasury", "IT"]

_CHANGE_TYPE_DEPT: dict[str, str] = {
    "new_requirement": "Compliance",
    "limit_modification": "Risk",
    "repeal": "Legal",
    "clarification": "Legal",
    "deadline": "Compliance",
    "other": "Compliance",
}

_SEVERITY_WEIGHT: dict[str, float] = {
    "high": 3.0,
    "medium": 1.5,
    "low": 0.5,
}


# ---- Public API --------------------------------------------------------------

async def get_department_summary(db: AsyncSession) -> list[dict]:
    """Return per-department impact counts, severity breakdown, and churn score."""
    accum: dict[str, dict] = {
        dept: {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        for dept in DEPARTMENTS
    }
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Contract-type: join via affected_name = contracts.name
    contract_rows = await db.execute(text("""
        SELECT c.area         AS dept,
               ii.severity    AS severity,
               ia.created_at  AS created_at
        FROM contracts c
        INNER JOIN impact_items  ii ON ii.affected_name = c.name
                                   AND ii.impact_type   = 'contract'
        INNER JOIN impact_alerts ia ON ia.id = ii.alert_id
        WHERE c.area IS NOT NULL
    """))
    for row in contract_rows.mappings():
        dept = _normalise_dept(row["dept"])
        if dept not in accum:
            accum[dept] = {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        _tally(accum[dept], row["severity"], row["created_at"], cutoff)

    # Process-type: derive dept from change_type
    process_rows = await db.execute(text("""
        SELECT rc.change_type  AS change_type,
               ii.severity     AS severity,
               ia.created_at   AS created_at
        FROM regulatory_changes rc
        INNER JOIN impact_items  ii ON ii.change_id  = rc.id
                                   AND ii.impact_type = 'process'
        INNER JOIN impact_alerts ia ON ia.id = ii.alert_id
    """))
    for row in process_rows.mappings():
        dept = _CHANGE_TYPE_DEPT.get(str(row["change_type"]), "Compliance")
        if dept not in accum:
            accum[dept] = {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        _tally(accum[dept], row["severity"], row["created_at"], cutoff)

    # Compute churn score
    max_weighted = 1.0
    results = []
    for dept, counts in accum.items():
        weighted = (
            counts["high"]   * _SEVERITY_WEIGHT["high"]
            + counts["medium"] * _SEVERITY_WEIGHT["medium"]
            + counts["low"]    * _SEVERITY_WEIGHT["low"]
        )
        if weighted > max_weighted:
            max_weighted = weighted
        results.append({"department": dept, **counts, "_weighted": weighted})

    for r in results:
        r["churn_score"] = round(r.pop("_weighted") / max_weighted, 3)

    results.sort(key=lambda x: (-x["churn_score"], x["department"]))
    return results


async def get_matrix(db: AsyncSession) -> list[dict]:
    """Return department x change_type matrix with impact counts."""
    rows: dict[tuple[str, str], dict] = {}

    # Contract-type
    contract_rows = await db.execute(text("""
        SELECT c.area          AS dept,
               rc.change_type  AS change_type,
               ii.severity     AS severity,
               COUNT(*)        AS n
        FROM contracts c
        INNER JOIN impact_items     ii ON ii.affected_name = c.name
                                      AND ii.impact_type   = 'contract'
        INNER JOIN impact_alerts    ia ON ia.id  = ii.alert_id
        INNER JOIN regulatory_changes rc ON rc.id = ii.change_id
        WHERE c.area IS NOT NULL
        GROUP BY c.area, rc.change_type, ii.severity
    """))
    for row in contract_rows.mappings():
        dept = _normalise_dept(row["dept"])
        key  = (dept, str(row["change_type"]))
        _add_matrix_row(rows, key, str(row["severity"]), int(row["n"]))

    # Process-type
    process_rows = await db.execute(text("""
        SELECT rc.change_type  AS change_type,
               ii.severity     AS severity,
               COUNT(*)        AS n
        FROM regulatory_changes rc
        INNER JOIN impact_items  ii ON ii.change_id  = rc.id
                                   AND ii.impact_type = 'process'
        INNER JOIN impact_alerts ia ON ia.id = ii.alert_id
        GROUP BY rc.change_type, ii.severity
    """))
    for row in process_rows.mappings():
        dept = _CHANGE_TYPE_DEPT.get(str(row["change_type"]), "Compliance")
        key  = (dept, str(row["change_type"]))
        _add_matrix_row(rows, key, str(row["severity"]), int(row["n"]))

    out = []
    for (dept, ct), data in rows.items():
        total = data["count"]
        score = data["weighted"] / total if total else 0.0
        out.append({
            "department": dept,
            "change_type": ct,
            "count": total,
            "severity_score": round(score, 2),
        })
    return out


async def get_monthly_trend(db: AsyncSession, months: int = 6) -> list[dict]:
    """Return department x month counts for the last N months."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    contract_rows = await db.execute(
        text("""
            SELECT c.area                                     AS dept,
                   TO_CHAR(ia.created_at, 'YYYY-MM')         AS month,
                   COUNT(*)                                   AS n
            FROM contracts c
            INNER JOIN impact_items  ii ON ii.affected_name = c.name
                                       AND ii.impact_type   = 'contract'
            INNER JOIN impact_alerts ia ON ia.id = ii.alert_id
            WHERE c.area IS NOT NULL
              AND ia.created_at >= :cutoff
            GROUP BY c.area, TO_CHAR(ia.created_at, 'YYYY-MM')
        """),
        {"cutoff": cutoff},
    )

    process_rows = await db.execute(
        text("""
            SELECT rc.change_type                             AS change_type,
                   TO_CHAR(ia.created_at, 'YYYY-MM')         AS month,
                   COUNT(*)                                   AS n
            FROM regulatory_changes rc
            INNER JOIN impact_items  ii ON ii.change_id  = rc.id
                                       AND ii.impact_type = 'process'
            INNER JOIN impact_alerts ia ON ia.id = ii.alert_id
            WHERE ia.created_at >= :cutoff
            GROUP BY rc.change_type, TO_CHAR(ia.created_at, 'YYYY-MM')
        """),
        {"cutoff": cutoff},
    )

    monthly: dict[tuple[str, str], int] = {}
    for row in contract_rows.mappings():
        k = (_normalise_dept(row["dept"]), row["month"])
        monthly[k] = monthly.get(k, 0) + int(row["n"])
    for row in process_rows.mappings():
        dept = _CHANGE_TYPE_DEPT.get(str(row["change_type"]), "Compliance")
        k = (dept, row["month"])
        monthly[k] = monthly.get(k, 0) + int(row["n"])

    return [
        {"department": dept, "month": month, "count": count}
        for (dept, month), count in sorted(monthly.items())
    ]


# ---- Internal helpers --------------------------------------------------------

def _normalise_dept(raw: str | None) -> str:
    if not raw:
        return "General"
    stripped = raw.strip().title()
    _aliases = {"Aml": "AML", "It": "IT"}
    return _aliases.get(stripped, stripped)


def _tally(d: dict, severity, created_at, cutoff: datetime) -> None:
    """Increment counters for one impact row."""
    sev = severity.value if isinstance(severity, Severity) else str(severity)
    d["total"] += 1
    if sev in d:
        d[sev] += 1
    if created_at:
        aware = created_at if getattr(created_at, "tzinfo", None) else created_at.replace(tzinfo=timezone.utc)
        if aware >= cutoff:
            d["recent_30d"] += 1


def _add_matrix_row(rows: dict, key: tuple[str, str], severity: str, n: int) -> None:
    if key not in rows:
        rows[key] = {"count": 0, "weighted": 0.0}
    rows[key]["count"] += n
    rows[key]["weighted"] += n * _SEVERITY_WEIGHT.get(severity, 1.0)
