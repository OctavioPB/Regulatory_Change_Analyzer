"""Mexican federal laws at two points in time, and the DOF decree that amended them.

Sources (no key needed):

* **Cámara de Diputados** publishes each law's current consolidated text and, per reform, the DOF
  decree (``LeyesBiblio/ref/<law>.htm`` → ``<law>/<LAW>_refNN_<ddmmmyy>.pdf``). It does not keep
  the intermediate consolidated texts.
* **Internet Archive** snapshots of the consolidated PDF (``web.archive.org/web/<ts>id_/<url>``)
  supply the text before and after a reform. Only intervals containing exactly one reform decree
  are usable; ``capture_intervals`` finds them.

Text handling — what the official PDF adds that is not law:
page headers ("CÁMARA DE DIPUTADOS…", "Última Reforma DOF …", "12 de 234"), editorial notes
("Fracción reformada DOF 09-03-2018"), and the transitory articles of every past decree appended at
the end. All are removed before comparing; otherwise every page would "change" with each reform.

Ground truth = articles whose wording changed (whitespace-insensitive, so PDF re-layout and broken
words like "efici ente" are not changes), cross-checked with the article numbers the decree lists for
that law.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from evals.sources.ecfr import USER_AGENT

DIPUTADOS = "https://www.diputados.gob.mx/LeyesBiblio"
WAYBACK = "https://web.archive.org"
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "mx_laws"
_MONTHS = {m: i for i, m in enumerate(
    ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"], 1)}


@dataclass
class LawText:
    law: str                      # "LMV"
    name: str                     # "LEY DEL MERCADO DE VALORES"
    on: str                       # capture timestamp (YYYYMMDD…)
    articles: list[tuple[str, str]] = field(default_factory=list)   # (article key, text)
    preamble: str = ""

    def by_key(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, text in self.articles:
            out[key] = (out[key] + "\n" + text) if key in out else text
        return out


class MxLawsClient:
    def __init__(self, cache_dir: Path = CACHE_DIR, transport: httpx.BaseTransport | None = None):
        self.cache_dir = cache_dir
        self._http = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=180.0,
                                  transport=transport, follow_redirects=True)

    def _get(self, url: str, params: dict | None = None) -> bytes:
        key = hashlib.sha256((url + repr(sorted((params or {}).items()))).encode()).hexdigest()[:16]
        path = self.cache_dir / f"{key}.bin"
        if path.exists():
            return path.read_bytes()
        r = self._http.get(url, params=params)
        r.raise_for_status()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return r.content

    def reforms(self, slug: str) -> list[tuple[str, str]]:
        """(YYYYMMDD, decree PDF path) for every reform of a law, oldest first."""
        page = self._get(f"{DIPUTADOS}/ref/{slug}.htm").decode("latin-1")
        out = set()
        for href, d, mon, y in re.findall(r'href="([^"]*_ref\d+_(\d{2})([a-z]{3})(\d{2})\.pdf)"', page):
            year = int(y) + (2000 if int(y) < 70 else 1900)
            out.add((f"{year}{_MONTHS[mon]:02d}{d}", href))
        return sorted(out)

    def captures(self, law: str) -> list[str]:
        """Archive timestamps of distinct versions of the consolidated PDF (HTTP 200 only)."""
        rows = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120).get(
            f"{WAYBACK}/cdx/search/cdx",
            params={"url": f"www.diputados.gob.mx/LeyesBiblio/pdf/{law}.pdf", "output": "json",
                    "fl": "timestamp", "collapse": "digest", "filter": "statuscode:200"},
        ).json()
        return [r[0] for r in rows[1:]]

    def law_text(self, law: str, timestamp: str) -> LawText:
        url = f"{WAYBACK}/web/{timestamp}id_/https://www.diputados.gob.mx/LeyesBiblio/pdf/{law}.pdf"
        return parse_law(pdf_text(self._get(url)), law=law, on=timestamp)

    def decree_text(self, slug: str, href: str) -> str:
        return pdf_text(self._get(f"{DIPUTADOS}/ref/{href}"))


def capture_intervals(captures: list[str], reforms: list[tuple[str, str]]) -> list[tuple[str, str, list[str]]]:
    """(before, after, reform dates in between) for consecutive captures."""
    return [(a, b, [d for d, _ in reforms if a[:8] < d <= b[:8]]) for a, b in zip(captures, captures[1:])]


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)


# ── cleaning + article split ──────────────────────────────────────────────────

_PAGE_NOISE = re.compile(
    r"^\s*(?:CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN|Secretaría General|"
    r"Secretaría de Servicios Parlamentarios|Última [Rr]eforma(?: publicada)? DOF.*|TEXTO VIGENTE|"
    r"\d+\s+de\s+\d+)\s*$"
)
_NOTE_HEAD = (r"(?:Art[íi]culos?|P[áa]rrafos?|Fracci(?:ón|ones)|Incisos?|Subincisos?|Apartados?|Cap[íi]tulos?|"
              r"Secci(?:ón|ones)|T[íi]tulos?|Denominaci[óo]n|Numerales?|Fe de erratas|Reforma|Nota|Libro)")
_EDITORIAL_NOTE = re.compile(rf"^\s*{_NOTE_HEAD}\b[^\n]{{0,240}}\bDOF\s+\d{{2}}-\d{{2}}-\d{{4}}[^\n]*$")
_TRANSITORIOS = re.compile(r"(?m)^\s*(?:ART[ÍI]CULOS\s+)?TRANSITORIOS?\b")
_SUFFIX = r"(?:Bis|Ter|Qu[áa]ter|Quinquies|Sexies|Septies|Octies|Nonies|Decies)"
_ARTICLE = re.compile(
    # digits may come apart in the PDF text layer: "Artículo 2 79.-" is article 279
    rf"(?m)^[ \t]*(?:Art[íi]culo|ART[ÍI]CULO|Articulo|ARTICULO)\s+(\d(?: ?\d){{0,3}})\s*(?:o\.|º\.?|°\.?)?"
    rf"((?:\s*-?\s*[A-Z](?=\s*[.\-]))?(?:\s+{_SUFFIX}(?:\s*\d{{1,2}})?)?)\s*[.\-]"
)


def _fold(text: str) -> str:
    d = unicodedata.normalize("NFKD", text)
    return "".join(c for c in d if not unicodedata.combining(c)).lower()


def article_key(number: str, suffix: str = "") -> str:
    """'48', ' Bis 1' → '48 bis 1'; '87', '-D' → '87-d'; '2 79' → '279'."""
    number = str(int(number.replace(" ", "")))
    suffix = " ".join(_fold(suffix).replace(" - ", "-").replace(" -", "-").split())
    if suffix.startswith("-"):
        return f"{number}{suffix.replace(' ', '')}"
    return f"{number} {suffix}".strip()


def clean(text: str, law_name: str = "") -> str:
    title = " ".join(law_name.split()).upper()
    keep = []
    for line in text.splitlines():
        stripped = " ".join(line.split())
        if not stripped or _PAGE_NOISE.match(stripped) or (title and stripped.upper() == title):
            continue
        if _EDITORIAL_NOTE.match(stripped):
            continue
        keep.append(line.rstrip())
    body = "\n".join(keep)
    m = _TRANSITORIOS.search(body)
    return body[: m.start()].rstrip() if m else body


def parse_law(raw: str, *, law: str, on: str) -> LawText:
    name = next((" ".join(line.split()) for line in raw.splitlines() if line.strip()), law)
    body = clean(raw, name)
    out = LawText(law=law, name=name, on=on)
    matches = list(_ARTICLE.finditer(body))
    out.preamble = body[: matches[0].start()].strip() if matches else body
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.articles.append((article_key(m.group(1), m.group(2) or ""), body[m.start():end].strip()))
    return out


def _squash(text: str) -> str:
    """Whitespace-free, case-folded: PDF re-layout and split words are not changes."""
    return re.sub(r"\s+", "", _fold(text))


def compare(before: LawText, after: LawText) -> dict[str, list[str]]:
    b, a = before.by_key(), after.by_key()
    return {
        "added": [k for k in a if k not in b],
        "removed": [k for k in b if k not in a],
        "modified": [k for k in a if k in b and _squash(a[k]) != _squash(b[k])],
    }


# ── decree: which articles of this law it amends ─────────────────────────────

_DECREE_CLAUSE = re.compile(
    r"Art[íi]culo\s+[A-Za-zÁÉÍÓÚáéíóú]+(?:\s+[A-Za-zÁÉÍÓÚáéíóú]+)?\s*\.?\s*-?\s*(Se\s+(?:reforma|adiciona|deroga).*?)"
    r"para\s+quedar\s+como\s+sigue", re.S | re.I)
# no trailing \s* after the number: it would swallow the space the "Bis" suffix needs
_DECREE_ARTICLE = re.compile(rf"\b(\d{{1,4}})(?:\s*(?:o\.|º|°))?((?:\s*-\s*[A-Z]\b)?(?:\s+{_SUFFIX}(?:\s*\d{{1,2}})?)?)")


def decree_articles(decree: str, law_name: str) -> tuple[list[str], str]:
    """Article keys the decree amends in ``law_name``, and the clause they come from."""
    target = _squash(law_name)
    for m in _DECREE_CLAUSE.finditer(decree):
        clause = " ".join(m.group(1).split())
        if target not in _squash(clause):
            continue
        cut = _fold(clause).rfind(" de la ley") if "ley" in _fold(law_name) else _fold(clause).rfind(" del codigo")
        listed = clause[:cut] if cut > 0 else clause
        listed = re.sub(r"(?<=\d) (?=\d)", "", listed)  # "2 0" → "20" (split by the PDF text layer)
        keys = []
        for num, suffix in _DECREE_ARTICLE.findall(listed):
            k = article_key(num, suffix)
            if k not in keys:
                keys.append(k)
        return keys, clause
    return [], ""
