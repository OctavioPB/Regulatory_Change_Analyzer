"""Risk heatmap aggregation — regulatory churn by business department."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contract import Contract
from src.models.document import ChangeType, RegulatoryChange
from src.models.impact import ImpactAlert, ImpactItem, Severity

logger = logging.getLogger(__name__)

# ── Department catalogue ──────────────────────────────────────────────────────

# Canonical departments shown in the heatmap (order preserved)
DEPARTMENTS = ["AML", "Risk", "Compliance", "Legal", "Treasury", "IT"]

# Fallback: map ChangeType to department for process-type impact items
# (which have no contract → no area → need manual assignment)
_CHANGE_TYPE_DEPT: dict[str, str] = {
    ChangeType.new_requirement: "Compliance",
    ChangeType.limit_modification: "Risk",
    ChangeType.repeal: "Legal",
    ChangeType.clarification: "Legal",
    ChangeType.deadline: "Compliance",
    ChangeType.other: "Compliance",
}

# Severity weights for computing a single "churn score" per department
_SEVERITY_WEIGHT: dict[str, float] = {
    Severity.high: 3.0,
    Severity.medium: 1.5,
    Severity.low: 0.5,
}


# ── Public API ────────────────────────────────────────────────────────────────

async def get_department_summary(db: AsyncSession) -> list[dict]:
    """Return per-department impact counts, severity breakdown, and churn score.

    Merges contract-type impacts (joined through Contract.area) with
    process-type impacts (department derived from change_type).
    """
    accum: dict[str, dict] = {
        dept: {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        for dept in DEPARTMENTS
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # ── Contract-type impacts: join on affected_name = Contract.name ──────────
    contract_q = await db.execute(
        select(
            Contract.area.label("dept"),
            ImpactItem.severity,
            ImpactAlert.created_at,
        )
        .join(ImpactItem, ImpactItem.affected_name == Contract.name)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactItem.impact_type == "contract")
        .where(Contract.area.isnot(None))
    )
    for row in contract_q.fetchall():
        dept = _normalise_dept(row.dept)
        if dept not in accum:
            accum[dept] = {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        _tally(accum[dept], row.severity, row.created_at, cutoff)

    # ── Process-type impacts: derive dept from change_type ────────────────────
    process_q = await db.execute(
        select(
            RegulatoryChange.change_type,
            ImpactItem.severity,
            ImpactAlert.created_at,
        )
        .join(ImpactItem, ImpactItem.change_id == RegulatoryChange.id)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactItem.impact_type == "process")
    )
    for row in process_q.fetchall():
        dept = _CHANGE_TYPE_DEPT.get(row.change_type, "Compliance")
        if dept not in accum:
            accum[dept] = {"total": 0, "high": 0, "medium": 0, "low": 0, "recent_30d": 0}
        _tally(accum[dept], row.severity, row.created_at, cutoff)

    # ── Compute churn score and build output list ─────────────────────────────
    max_weighted = 1.0  # avoid div-by-zero
    results = []
    for dept, counts in accum.items():
        weighted = (
            counts["high"] * _SEVERITY_WEIGHT[Severity.high]
            + counts["medium"] * _SEVERITY_WEIGHT[Severity.medium]
            + counts["low"] * _SEVERITY_WEIGHT[Severity.low]
        )
        if weighted > max_weighted:
            max_weighted = weighted
        results.append({"department": dept, **counts, "_weighted": weighted})

    for r in results:
        r["churn_score"] = round(r.pop("_weighted") / max_weighted, 3)

    # Sort by churn_score desc, then alphabetically
    results.sort(key=lambda x: (-x["churn_score"], x["department"]))
    return results


async def get_matrix(db: AsyncSession) -> list[dict]:
    """Return department × change_type matrix with impact counts.

    Each row: {"department": str, "change_type": str, "count": int, "severity_score": float}
    """
    rows: dict[tuple[str, str], dict] = {}

    # Contract-type
    q = await db.execute(
        select(
            Contract.area.label("dept"),
            RegulatoryChange.change_type,
            ImpactItem.severity,
            func.count(ImpactItem.id).label("n"),
        )
        .join(ImpactItem, ImpactItem.affected_name == Contract.name)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .join(RegulatoryChange, RegulatoryChange.id == ImpactItem.change_id)
        .where(ImpactItem.impact_type == "contract")
        .where(Contract.area.isnot(None))
        .group_by(Contract.area, RegulatoryChange.change_type, ImpactItem.severity)
    )
    for row in q.fetchall():
        dept = _normalise_dept(row.dept)
        key = (dept, row.change_type.value)
        _add_matrix_row(rows, key, row.severity, row.n)

    # Process-type
    q2 = await db.execute(
        select(
            RegulatoryChange.change_type,
            ImpactItem.severity,
            func.count(ImpactItem.id).label("n"),
        )
        .join(ImpactItem, ImpactItem.change_id == RegulatoryChange.id)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactItem.impact_type == "process")
        .group_by(RegulatoryChange.change_type, ImpactItem.severity)
    )
    for row in q2.fetchall():
        dept = _CHANGE_TYPE_DEPT.get(row.change_type, "Compliance")
        key = (dept, row.change_type.value)
        _add_matrix_row(rows, key, row.severity, row.n)

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
    """Return department × month counts for the last N months.

    Each row: {"department": str, "month": "YYYY-MM", "count": int}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)

    # Contract-type
    q = await db.execute(
        select(
            Contract.area.label("dept"),
            func.to_char(ImpactAlert.created_at, "YYYY-MM").label("month"),
            func.count(ImpactItem.id).label("n"),
        )
        .join(ImpactItem, ImpactItem.affected_name == Contract.name)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactItem.impact_type == "contract")
        .where(Contract.area.isnot(None))
        .where(ImpactAlert.created_at >= cutoff)
        .group_by(Contract.area, func.to_char(ImpactAlert.created_at, "YYYY-MM"))
    )

    # Process-type
    q2 = await db.execute(
        select(
            RegulatoryChange.change_type,
            func.to_char(ImpactAlert.created_at, "YYYY-MM").label("month"),
            func.count(ImpactItem.id).label("n"),
        )
        .join(ImpactItem, ImpactItem.change_id == RegulatoryChange.id)
        .join(ImpactAlert, ImpactAlert.id == ImpactItem.alert_id)
        .where(ImpactItem.impact_type == "process")
        .where(ImpactAlert.created_at >= cutoff)
        .group_by(RegulatoryChange.change_type, func.to_char(ImpactAlert.created_at, "YYYY-MM"))
    )

    monthly: dict[tuple[str, str], int] = {}
    for row in q.fetchall():
        k = (_normalise_dept(row.dept), row.month)
        monthly[k] = monthly.get(k, 0) + row.n
    for row in q2.fetchall():
        dept = _CHANGE_TYPE_DEPT.get(row.change_type, "Compliance")
        k = (dept, row.month)
        monthly[k] = monthly.get(k, 0) + row.n

    return [
        {"department": dept, "month": month, "count": count}
        for (dept, month), count in sorted(monthly.items())
    ]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_dept(raw: str | None) -> str:
    if not raw:
        return "General"
    stripped = raw.strip().title()
    # Canonical mappings for common abbreviations / variants
    _aliases = {
        "Aml": "AML",
        "It": "IT",
    }
    return _aliases.get(stripped, stripped)


def _tally(d: dict, severity: Severity, created_at: datetime, cutoff: datetime) -> None:
    d["total"] += 1
    d[severity.value] += 1
    if created_at and created_at.replace(tzinfo=timezone.utc) >= cutoff:
        d["recent_30d"] += 1


def _add_matrix_row(
    rows: dict,
    key: tuple[str, str],
    severity: Severity,
    n: int,
) -> None:
    if key not in rows:
        rows[key] = {"count": 0, "weighted": 0.0}
    rows[key]["count"] += n
    rows[key]["weighted"] += n * _SEVERITY_WEIGHT.get(severity, 1.0)
