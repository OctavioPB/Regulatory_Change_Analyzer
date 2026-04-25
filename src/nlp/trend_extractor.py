"""Trend signal extraction from Proposed Rules and No-Action Letters."""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── Doc-type classification ───────────────────────────────────────────────────

_PROPOSED_RULE_KW = [
    "proposed rule", "proposes rule", "notice of proposed rulemaking",
    "request for comment", "propone", "propuesta de", "nprm",
]
_NO_ACTION_KW = [
    "no-action", "no action letter", "no-action letter",
    "relief", "exemptive", "exemption request",
]
_INTERIM_KW = [
    "interim final rule", "interim rule", "temporary rule",
]
_FINAL_KW = [
    "final rule", "adopts rule", "adopting release",
    "regla final", "disposición final",
]
_GUIDANCE_KW = [
    "guidance", "staff bulletin", "staff notice", "interpretive",
    "frequently asked questions", "faq",
]

# ── Domain classification ─────────────────────────────────────────────────────

_DOMAIN_PATTERNS: list[tuple[str, list[str]]] = [
    ("fintech", ["fintech", "digital asset", "cryptocurrency", "crypto", "blockchain",
                  "stablecoin", "defi", "robo-advisor", "crowdfunding"]),
    ("investment_funds", ["investment fund", "mutual fund", "hedge fund", "etf",
                           "investment adviser", "adviser", "fondo de inversión",
                           "investment company", "40 act"]),
    ("derivatives", ["derivative", "swap", "futures", "options", "cds",
                      "cleared", "clearing", "margin requirement", "counterparty"]),
    ("aml_kyc", ["anti-money laundering", "aml", "know your customer", "kyc",
                  "beneficial owner", "bsa", "bank secrecy", "suspicious activity"]),
    ("capital_adequacy", ["capital requirement", "capital adequacy", "leverage ratio",
                           "tier 1", "basel", "stress test", "capital buffer"]),
    ("securities_trading", ["securities", "equity", "trading", "market maker",
                              "short selling", "insider trading", "disclosure",
                              "reporting obligation"]),
    ("data_privacy", ["data privacy", "data protection", "personal data", "gdpr",
                       "cybersecurity", "data breach", "information security"]),
    ("consumer_protection", ["consumer protection", "consumer", "retail investor",
                              "suitability", "best interest", "reg bi", "fiduciary"]),
]

# ── Temporal signal patterns ──────────────────────────────────────────────────

_COMMENT_PERIOD = re.compile(
    r"comment\s+period\s+(?:of\s+)?(\d+)\s+days?",
    re.IGNORECASE,
)
_EFFECTIVE_DATE = re.compile(
    r"effective\s+(?:on|date[:\s]+)?(?:(?:\w+\s+){0,2})(\d{1,2}[,\s]+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_COMPLIANCE_DATE = re.compile(
    r"(?:compliance|implementation)\s+date[:\s]+(?:\w+\s*){0,3}(\d{4})",
    re.IGNORECASE,
)
_MONTHS_HORIZON = re.compile(
    r"(\d+)\s+months?\s+(?:after|following|from)\s+(?:publication|effective|enactment|adoption)",
    re.IGNORECASE,
)

# ── Theme extraction ──────────────────────────────────────────────────────────

_THEME_PATTERNS: list[tuple[str, str]] = [
    ("capital_requirements", r"\bcapital\s+requirement\b"),
    ("disclosure", r"\bdisclosure\b"),
    ("reporting", r"\breporting\s+obligation\b|\breport(?:ing)?\s+requirement\b"),
    ("limit_change", r"\blimit(?:s)?\s+(?:is|are|changed|modified|reduced|increased)\b|\bthreshold\b"),
    ("new_obligation", r"\bshall\s+(?:be\s+)?(?:required|obligated|subject)\b|\bmust\b.{0,30}\bcomply\b"),
    ("registration", r"\bregistration?\b|\blicense\b|\bauthorization\b"),
    ("enforcement", r"\benforcement\b|\bpenalt(?:y|ies)\b|\bsanction\b"),
    ("systemic_risk", r"\bsystemic\s+risk\b|\bsystemic(?:ally)\b"),
    ("esg", r"\besg\b|\bsustainab\w+\b|\bclimate\s+risk\b|\bgreen\b"),
    ("digital_assets", r"\bdigital\s+asset\b|\bcryptocurrency\b|\btoken\b"),
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TrendExtractionResult:
    doc_type: str
    domain: str
    signal_strength: float
    horizon_months: int
    predicted_effective_date: datetime | None
    key_themes: list[str]
    confidence_score: float


# ── Public API ────────────────────────────────────────────────────────────────

def extract_trend(
    title: str,
    text: str,
    publication_date: datetime,
) -> TrendExtractionResult | None:
    """Extract a trend signal from a regulatory document.

    Returns None if the document does not look like a forward-looking signal
    (i.e., it is a final rule or enforcement action with no predictive value).

    Args:
        title: Document title.
        text: Full body text.
        publication_date: Date the document was published.

    Returns:
        TrendExtractionResult or None.
    """
    combined = (title + " " + (text or "")).lower()
    doc_type = _classify_doc_type(combined)

    # Only proposed rules and no-action letters have predictive value
    if doc_type not in ("proposed_rule", "no_action_letter", "interim_rule", "guidance"):
        return None

    domain = _classify_domain(combined)
    themes = _extract_themes(text or "")
    horizon, predicted_date = _estimate_horizon(text or "", publication_date, doc_type)
    signal_strength = _compute_signal_strength(doc_type, themes, text or "")
    confidence = _compute_confidence(doc_type, horizon, predicted_date, themes)

    return TrendExtractionResult(
        doc_type=doc_type,
        domain=domain,
        signal_strength=round(signal_strength, 3),
        horizon_months=horizon,
        predicted_effective_date=predicted_date,
        key_themes=themes,
        confidence_score=round(confidence, 3),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _classify_doc_type(combined_lower: str) -> str:
    if any(kw in combined_lower for kw in _INTERIM_KW):
        return "interim_rule"
    if any(kw in combined_lower for kw in _NO_ACTION_KW):
        return "no_action_letter"
    if any(kw in combined_lower for kw in _PROPOSED_RULE_KW):
        return "proposed_rule"
    if any(kw in combined_lower for kw in _GUIDANCE_KW):
        return "guidance"
    if any(kw in combined_lower for kw in _FINAL_KW):
        return "final_rule"
    return "other"


def _classify_domain(combined_lower: str) -> str:
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_PATTERNS:
        score = sum(1 for kw in keywords if kw in combined_lower)
        if score > 0:
            scores[domain] = score
    if not scores:
        return "general"
    return max(scores, key=lambda d: scores[d])


def _extract_themes(text: str) -> list[str]:
    themes: list[str] = []
    for theme, pattern in _THEME_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            themes.append(theme)
    return themes[:6]  # cap at 6 themes


def _estimate_horizon(
    text: str,
    pub_date: datetime,
    doc_type: str,
) -> tuple[int, datetime | None]:
    """Return (horizon_months, predicted_effective_date)."""

    # Explicit "N months after" language
    m = _MONTHS_HORIZON.search(text)
    if m:
        months = int(m.group(1))
        pred = pub_date + timedelta(days=months * 30)
        return months, pred

    # Comment period → add 6 months for rulemaking process
    m = _COMMENT_PERIOD.search(text)
    if m:
        comment_days = int(m.group(1))
        months = max(6, (comment_days // 30) + 6)
        pred = pub_date + timedelta(days=months * 30)
        return months, pred

    # Year extraction from effective/compliance date patterns
    for pattern in (_EFFECTIVE_DATE, _COMPLIANCE_DATE):
        m = pattern.search(text)
        if m:
            year_match = re.search(r"\d{4}", m.group(0))
            if year_match:
                year = int(year_match.group(0))
                if 2025 <= year <= 2030:
                    pred = datetime(year, 6, 1, tzinfo=timezone.utc)
                    months = max(1, (pred - pub_date.replace(tzinfo=timezone.utc)).days // 30)
                    return months, pred

    # Fallback heuristics by doc_type
    defaults = {
        "proposed_rule": (12, None),
        "no_action_letter": (6, None),
        "interim_rule": (3, None),
        "guidance": (6, None),
        "other": (12, None),
    }
    return defaults.get(doc_type, (12, None))


def _compute_signal_strength(doc_type: str, themes: list[str], text: str) -> float:
    base = {
        "proposed_rule": 0.70,
        "no_action_letter": 0.45,
        "interim_rule": 0.80,
        "guidance": 0.35,
        "other": 0.20,
    }.get(doc_type, 0.30)

    # Boost for more themes (more scope = stronger signal)
    theme_boost = min(0.15, len(themes) * 0.025)

    # Boost if the document mentions specific numeric thresholds
    if re.search(r"\d+(?:\.\d+)?\s*%", text):
        theme_boost += 0.05

    return min(1.0, base + theme_boost)


def _compute_confidence(
    doc_type: str,
    horizon: int,
    predicted_date: datetime | None,
    themes: list[str],
) -> float:
    base = {
        "proposed_rule": 0.60,
        "no_action_letter": 0.50,
        "interim_rule": 0.75,
        "guidance": 0.40,
        "other": 0.25,
    }.get(doc_type, 0.30)

    if predicted_date is not None:
        base += 0.15  # explicit date found increases confidence

    if themes:
        base += 0.05  # having classified themes increases confidence

    # Shorter horizon = higher confidence (less uncertainty)
    if horizon <= 6:
        base += 0.05

    return min(0.95, base)
