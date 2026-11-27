"""eCFR point-in-time loader: a CFR section's text as it read on any date.

Uses the public eCFR Versioner API (no key):

* ``/api/versioner/v1/versions/title-{t}.json?section=…`` — every version of a section, with the
  date it took effect and whether the change was substantive;
* ``/api/versioner/v1/full/{date}/title-{t}.xml?part=…&section=…`` — the section's XML on a date.

The XML is parsed into labelled paragraphs, ``("(b)(2)", "Security-based swaps; or")``, so two
versions can be compared paragraph by paragraph using the official labels. That comparison is the
ground truth for the change-detection eval; it does not use any of the app's NLP code.

Responses are cached on disk (``evals/.cache/``): the API asks for compression and is not meant
for repeated identical requests.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

BASE = "https://www.ecfr.gov/api/versioner/v1"
# Generic client name: no personal contact details go to public services.
USER_AGENT = "regulatory-change-analyzer-evals/0.1"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "ecfr"


@dataclass(frozen=True)
class Version:
    date: str            # the version is in force from this date
    issue_date: str
    substantive: bool
    removed: bool
    name: str


@dataclass
class SectionText:
    citation: str                        # "17 CFR 240.15c6-1"
    heading: str                         # "§ 240.15c6-1 Settlement cycle."
    on: str                              # date the text is as of
    paragraphs: list[tuple[str, str]] = field(default_factory=list)   # (label path, text)
    source_citation: str = ""            # the CITA line: "[58 FR 52903, …, as amended at 88 FR 13952 …]"

    def render(self) -> str:
        """Plain text, one paragraph per line, as a regulator's document would read."""
        return "\n".join([self.heading, *(text for _, text in self.paragraphs)])

    def by_path(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for path, text in self.paragraphs:
            out[path] = (out[path] + "\n" + text) if path in out else text
        return out

    def last_amendment(self) -> tuple[int, int, str] | None:
        """(volume, page, 'Mon. D, YYYY') of the most recent Federal Register reference in CITA.

        The eCFR dates a reference by publication or, for some rules, by effective date; callers
        must try both.
        """
        refs = re.findall(r"(\d+)\s+FR\s+(\d+),\s+([A-Z][a-z]{2,4}\.?\s+\d{1,2},\s+\d{4})", self.source_citation)
        dated = [(parse_fr_date(w), int(v), int(p), w) for v, p, w in refs]
        dated = [d for d in dated if d[0]]
        if not dated:
            return None
        _, vol, page, when = max(dated)
        return vol, page, when


class EcfrClient:
    def __init__(self, cache_dir: Path = CACHE_DIR, transport: httpx.BaseTransport | None = None):
        self.cache_dir = cache_dir
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},  # the API requires compression
            timeout=60.0, transport=transport, follow_redirects=True,
        )

    def _get(self, url: str, params: dict) -> str:
        key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:16]
        path = self.cache_dir / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        r = self._http.get(url, params=params)
        r.raise_for_status()
        if not r.text.lstrip().startswith(("<?xml", "<DIV", "{")):
            raise RuntimeError(f"unexpected eCFR response for {url}: {r.text[:120]!r}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text, encoding="utf-8")
        return r.text

    def versions(self, title: int, section: str) -> list[Version]:
        data = json.loads(self._get(f"{BASE}/versions/title-{title}.json", {"section": section}))
        return [
            Version(v["date"], v["issue_date"], bool(v["substantive"]), bool(v["removed"]), v["name"])
            for v in data.get("content_versions", []) if v.get("identifier") == section
        ]

    def section(self, title: int, section: str, on: str | date) -> SectionText:
        part = section.split(".", 1)[0]
        xml = self._get(f"{BASE}/full/{on}/title-{title}.xml", {"part": part, "section": section})
        return parse_section_xml(xml, citation=f"{title} CFR {section}", on=str(on))


def parse_fr_date(when: str) -> str | None:
    """'Mar. 6, 2023' / 'June 1, 2023' / 'Sept. 9, 2022' → '2023-03-06' (None if unparseable)."""
    from datetime import datetime

    clean = when.replace(".", "").replace("Sept ", "Sep ").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ── XML → labelled paragraphs ─────────────────────────────────────────────────

_LABELS = re.compile(r"^\s*((?:\(\s*[0-9A-Za-z]{1,6}\s*\)\s*)+)")
_ROMAN = re.compile(r"^(?=[ivxl]+$)m*(c[md]|d?c{0,3})(x[cl]|l?x{0,3})(i[xv]|v?i{0,3})$")


def parse_section_xml(xml: str, *, citation: str, on: str) -> SectionText:
    root = ET.fromstring(xml.encode("utf-8") if xml.startswith("<?xml") else xml)
    head = root.find("HEAD")
    heading = " ".join("".join(head.itertext()).split()) if head is not None else citation
    out = SectionText(citation=citation, heading=heading, on=on)
    # Long sections carry several CITA notes; keep them all, the newest reference is picked later
    out.source_citation = " ".join(" ".join("".join(c.itertext()).split()) for c in root.iter("CITA"))

    labeller = _Labeller()
    current = ""
    parents = {c: p for p in root.iter() for c in p}
    for el in root.iter():
        if el.tag not in ("P", "FP") or _inside(parents, el, {"CITA", "XREF"}):
            continue
        text = " ".join("".join(el.itertext()).split())
        if not text:
            continue
        m = _LABELS.match(text)
        if m:
            current = labeller.path(re.findall(r"\(\s*([0-9A-Za-z]{1,6})\s*\)", m.group(1)))
        out.paragraphs.append((current or "(intro)", text))
    return out


def _inside(parents: dict, el: ET.Element, tags: set[str]) -> bool:
    node = el
    while node in parents:
        node = parents[node]
        if node.tag in tags:
            return True
    return False


class _Labeller:
    """Turns successive paragraph labels into full paths, CFR style.

    Levels: (a) → (1) → (i) → (A) → (1) italic → (i) italic. The ambiguous case is a lone
    roman-looking letter: "(i)" after "(h)" is a letter; inside a numbered paragraph it is roman.
    """

    def __init__(self) -> None:
        self.stack: list[tuple[int, str]] = []

    def path(self, labels: list[str]) -> str:
        for lab in labels:
            level = self._level(lab)
            self.stack = [s for s in self.stack if s[0] < level] + [(level, lab)]
        return "".join(f"({lab})" for _, lab in self.stack)

    def _level(self, lab: str) -> int:
        top = self.stack[-1][0] if self.stack else -1
        if lab.isdigit():
            return 4 if top >= 3 else 1
        if lab.isupper():
            return 3
        letter_prev = next((s[1] for s in self.stack if s[0] == 0), None)
        is_next_letter = (len(lab) == 1 and letter_prev is not None and len(letter_prev) == 1
                          and ord(lab) == ord(letter_prev) + 1)
        if _ROMAN.match(lab) and top >= 1 and not is_next_letter:
            return 5 if top >= 4 else 2
        return 0


# ── Ground truth: paragraph-level comparison ──────────────────────────────────

def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def compare(before: SectionText, after: SectionText) -> dict[str, list[str]]:
    """Paragraph paths added, removed and modified between two versions (by official label)."""
    b, a = before.by_path(), after.by_path()
    return {
        "added": [p for p in a if p not in b],
        "removed": [p for p in b if p not in a],
        "modified": [p for p in a if p in b and _norm(a[p]) != _norm(b[p])],
    }
