"""Federal Register: the final rule behind an eCFR version, and its amendatory instruction.

* Metadata comes from the FederalRegister.gov JSON API (no key). Its full-text URLs sit behind bot
  protection, so the text itself comes from the GovInfo API (``api.govinfo.gov``), which needs an
  api.data.gov key: set ``GOVINFO_API_KEY`` or the public, heavily rate-limited ``DEMO_KEY`` is used.
* The amendatory instruction ("5. Revise § 240.15c6-1 to read as follows:") is the official
  statement of what the rule changed; the eval stores it next to each case as evidence.

Responses are cached on disk like the eCFR loader's.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from evals.sources.ecfr import USER_AGENT

FR_API = "https://www.federalregister.gov/api/v1/documents.json"
GOVINFO = "https://api.govinfo.gov/packages"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "federal_register"

_FIELDS = ["document_number", "title", "citation", "start_page", "end_page", "publication_date",
           "effective_on", "type", "html_url", "abstract"]


@dataclass(frozen=True)
class FrDocument:
    document_number: str
    title: str
    citation: str            # "88 FR 13872"
    publication_date: str
    effective_on: str | None
    start_page: int
    end_page: int
    html_url: str
    abstract: str


class FederalRegisterClient:
    def __init__(self, cache_dir: Path = CACHE_DIR, transport: httpx.BaseTransport | None = None,
                 govinfo_key: str | None = None):
        self.cache_dir = cache_dir
        self.govinfo_key = govinfo_key or os.environ.get("GOVINFO_API_KEY") or "DEMO_KEY"
        self._http = httpx.Client(headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
                                  timeout=90.0, transport=transport, follow_redirects=True)

    def _get(self, url: str, params: list[tuple[str, str]] | dict, *, cache_params: object = None) -> str:
        # the API key never goes into the cache key (or onto disk)
        ident = json.dumps(cache_params if cache_params is not None else params, sort_keys=True, default=str)
        path = self.cache_dir / f"{hashlib.sha1((url + ident).encode()).hexdigest()[:16]}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        r = self._http.get(url, params=params)
        r.raise_for_status()
        if "unblock.federalregister.gov" in str(r.url) or "/error" in str(r.url):
            raise RuntimeError(f"blocked or error page for {url}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text, encoding="utf-8")
        return r.text

    def find_rule(self, *, agency: str, published: str, page: int) -> FrDocument | None:
        """The rule behind an eCFR reference like '88 FR 13952, Mar. 6, 2023'.

        The eCFR dates some references by publication and others by effective date, and its page can
        fall outside the rule's own range (corrections). So: a rule containing the page, published
        or effective that day; else the only rule from the agency that day.
        """
        candidates: list[dict] = []
        for cond in ("publication_date", "effective_date"):
            params = [("conditions[agencies][]", agency), ("conditions[type][]", "RULE"),
                      (f"conditions[{cond}][is]", published), ("per_page", "50")]
            params += [("fields[]", f) for f in _FIELDS]
            results = json.loads(self._get(FR_API, params)).get("results", [])
            for d in results:
                if d["start_page"] <= page <= d["end_page"]:
                    return _doc(d)
            candidates += results
        unique = {d["document_number"]: d for d in candidates}
        return _doc(next(iter(unique.values()))) if len(unique) == 1 else None

    def full_text(self, doc: FrDocument) -> str:
        url = f"{GOVINFO}/FR-{doc.publication_date}/granules/{doc.document_number}/htm"
        raw = self._get(url, {"api_key": self.govinfo_key}, cache_params={"doc": doc.document_number})
        return html.unescape(re.sub(r"<[^>]+>", "", raw))


def _doc(d: dict) -> FrDocument:
    return FrDocument(d["document_number"], d["title"], d["citation"], d["publication_date"],
                      d.get("effective_on"), d["start_page"], d["end_page"], d["html_url"],
                      d.get("abstract") or "")


def published_iso(when: str) -> str:
    """'Mar. 6, 2023' / 'June 1, 2023' → '2023-03-06'."""
    clean = when.replace(".", "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).date().isoformat()
        except ValueError:
            continue
    if clean.startswith("Sept"):
        return published_iso(clean.replace("Sept", "Sep", 1))
    raise ValueError(f"unrecognised date {when!r}")


def amendatory_instruction(full_text: str, section: str) -> str | None:
    """The numbered instruction that amends ``section``, with its lettered sub-steps.

    FR rule text reads, e.g.::

        5. Revise Sec.  240.15c6-1 to read as follows:
        8. Amend Sec.  240.13d-1 by:
            a. Revising paragraphs (a) and (b); and
            b. Adding paragraph (k).
    """
    sec = re.escape(section)
    m = re.search(rf"(?m)^[ \t]*\d+\.\s+[^\n]*?(?:Secs?\.|§§?|Sections?)\s+{sec}(?![\w(-])", full_text)
    if not m:
        return None
    lines: list[str] = []
    for line in full_text[m.start():].splitlines():
        s = line.strip()
        if s == "0":  # FR text marks each amendatory paragraph with a bare "0" line
            continue
        if lines and (not s or re.match(r"^(?:\d+\.\s|Sec\.|§|\* \* \*|\[\[Page)", s)):
            if not s and lines and not lines[-1].endswith(":"):
                break
            if s and not re.match(r"^[a-z]\.\s", s):
                break
            continue
        if s:
            lines.append(s)
        if len(" ".join(lines)) > 1500:
            break
    return " ".join(" ".join(lines).split()) or None
