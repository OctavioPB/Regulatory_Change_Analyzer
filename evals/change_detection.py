"""Change-detection eval on real amendments: SEC rules (eCFR) and Mexican federal laws (DOF).

    python -m evals.change_detection build [--case id]   # fetch sources, freeze fixtures (network)
    python -m evals.change_detection run [--label x]     # grade the app's NLP pipeline (offline)

``build`` writes one fixture per case — both versions split into units (CFR paragraphs / law
articles), the ground truth, and the official evidence (Federal Register amendatory instruction / DOF
decree clause) — to ``evals/data/ecfr/*.json`` and ``evals/data/mx/*.json.gz``. It refuses a case whose
annotated facts are not in the fetched text.

``run`` feeds each pair to ``src.nlp.pipeline.analyze(new, old)`` — what the app does once it has the
previous version — and grades it, including which units (paragraphs / articles) it flags against the
ones that really changed. It also checks whether the app would pair the two versions at all
(``regulation_key`` on the document title).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import unicodedata
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "data" / "ecfr"
FIXTURES_MX = ROOT / "evals" / "data" / "mx"
RUNS = ROOT / "evals" / "runs"
# A substantive case passes only if at least half of the units the app flags really changed.
MIN_UNIT_PRECISION = 0.5


# ── text helpers ──────────────────────────────────────────────────────────────

def _squash(text: str) -> str:
    """Case-, accent- and whitespace-insensitive: PDF text layers split words ("fo ndo")."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return re.sub(r"\s+", "", folded.lower())


def _missing_facts(case, before_text: str, after_text: str) -> list[str]:
    b, a = _squash(before_text), _squash(after_text)
    out = []
    for f in case.facts:
        if f.old and _squash(f.old) not in b:
            out.append(f"old: {f.old}")
        if f.new and _squash(f.new) not in a:
            out.append(f"new: {f.new}")
    return out


def render(side: dict, heading: str) -> str:
    return "\n".join([heading, *(text for _, text in side["paragraphs"])])


def _write(path: Path, fixture: dict) -> None:
    data = json.dumps(fixture, ensure_ascii=False, indent=1).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def load_fixtures() -> list[dict]:
    out = []
    for p in sorted(FIXTURES.glob("*.json")) + sorted(FIXTURES_MX.glob("*.json.gz")):
        raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
        out.append(json.loads(raw))
    return out


# ── build: SEC (eCFR + Federal Register) ──────────────────────────────────────

def build_ecfr(case_ids: set[str] | None = None) -> int:
    from evals.ecfr_cases import CASES
    from evals.sources.ecfr import EcfrClient, compare
    from evals.sources.federal_register import FederalRegisterClient, amendatory_instruction, published_iso

    ecfr, fr = EcfrClient(), FederalRegisterClient()
    failures = 0
    for case in CASES:
        if case_ids and case.id not in case_ids:
            continue
        before_on = case.before or (date.fromisoformat(case.after) - timedelta(days=1)).isoformat()
        before = ecfr.section(case.title, case.section, before_on)
        after = ecfr.section(case.title, case.section, case.after)
        missing = _missing_facts(case, before.render(), after.render())
        if missing:
            print(f"✗ {case.id}: annotated facts not found in the eCFR text: {missing}", file=sys.stderr)
            failures += 1
            continue

        rule = instruction = None
        if case.substantive:
            doc = None
            ref = after.last_amendment()
            if ref:
                vol, page, when = ref
                doc = fr.find_rule(agency=case.agency, published=published_iso(when), page=page)
            # Some sections list old references only: fall back to the rule effective around the
            # version date (the eCFR and the FR can differ by a day)
            day = date.fromisoformat(case.after)
            for d in (day, day - timedelta(days=1)):
                if doc:
                    break
                doc = fr.find_rule(agency=case.agency, published=d.isoformat(), page=-1)
            if doc:
                rule = asdict(doc)
                try:
                    instruction = amendatory_instruction(fr.full_text(doc), case.section)
                except Exception as exc:  # GovInfo rate limit (DEMO_KEY) — keep the case, flag it
                    print(f"  {case.id}: no amendatory instruction ({exc})", file=sys.stderr)
        fixture = {
            "id": case.id, "jurisdiction": "US", "unit": "paragraph",
            "citation": after.citation, "heading": after.heading,
            "note": case.note, "substantive": case.substantive,
            "before": {"on": before.on, "paragraphs": before.paragraphs, "source_citation": before.source_citation},
            "after": {"on": after.on, "paragraphs": after.paragraphs, "source_citation": after.source_citation},
            "truth": compare(before, after),
            "facts": [asdict(f) for f in case.facts],
            "change_types": sorted(case.change_types),
            "federal_register": rule, "amendatory_instruction": instruction,
            "versions": [asdict(v) for v in ecfr.versions(case.title, case.section)],
            "sources": {
                "before": f"https://www.ecfr.gov/api/versioner/v1/full/{before.on}/title-{case.title}.xml"
                          f"?part={case.section.split('.')[0]}&section={case.section}",
                "after": f"https://www.ecfr.gov/api/versioner/v1/full/{after.on}/title-{case.title}.xml"
                         f"?part={case.section.split('.')[0]}&section={case.section}",
            },
        }
        if case.substantive and not any(fixture["truth"].values()):
            print(f"✗ {case.id}: marked substantive but the two versions are identical", file=sys.stderr)
            failures += 1
            continue
        _write(FIXTURES / f"{case.id}.json", fixture)
        t = fixture["truth"]
        print(f"✓ {case.id:28} {case.section:14} {before.on} → {after.on}  "
              f"+{len(t['added'])} -{len(t['removed'])} ~{len(t['modified'])}  "
              f"FR {rule['citation'] if rule else '—'}")
    return failures


# ── build: Mexico (Diputados + Internet Archive + DOF decree) ─────────────────

def build_mx(case_ids: set[str] | None = None) -> int:
    from evals.mx_cases import CASES
    from evals.sources.mx_laws import DIPUTADOS, WAYBACK, MxLawsClient, compare, decree_articles

    client = MxLawsClient()
    captures: dict[str, list[str]] = {}
    failures = 0
    for case in CASES:
        if case_ids and case.id not in case_ids:
            continue
        caps = captures.setdefault(case.law, client.captures(case.law))
        try:
            ts_before = next(t for t in caps if t.startswith(case.before))
            ts_after = next(t for t in caps if t.startswith(case.after))
            before, after = client.law_text(case.law, ts_before), client.law_text(case.law, ts_after)
        except Exception as exc:  # missing or truncated archive copy
            print(f"✗ {case.id}: archived text unavailable ({exc})", file=sys.stderr)
            failures += 1
            continue

        def units(t):
            return ([("__preamble__", t.preamble)] if t.preamble else []) + t.articles

        missing = _missing_facts(case, "\n".join(x for _, x in units(before)), "\n".join(x for _, x in units(after)))
        if missing:
            print(f"✗ {case.id}: annotated facts not found in the law text: {missing}", file=sys.stderr)
            failures += 1
            continue

        computed = compare(before, after)
        reforms = client.reforms(case.slug)
        between = [d for d, _ in reforms if ts_before[:8] < d <= ts_after[:8]]
        decree_keys, clause, decree_href = [], "", None
        if case.substantive:
            decree_href = next((h for _, h in reforms if h.endswith(f"_{case.decree}.pdf")), None)
            if decree_href:
                decree_keys, clause = decree_articles(client.decree_text(case.slug, decree_href), after.name)
        if len(between) != (1 if case.substantive else 0):
            print(f"✗ {case.id}: {len(between)} reforms between the captures ({between})", file=sys.stderr)
            failures += 1
            continue
        # Ground truth = the decree's article list, placed on the article keys of each version
        bk, ak = before.by_key(), after.by_key()
        if case.substantive:
            truth = {"added": [k for k in decree_keys if k in ak and k not in bk],
                     "removed": [k for k in decree_keys if k in bk and k not in ak],
                     "modified": [k for k in decree_keys if k in ak and k in bk]}
            unlisted = sorted(set(sum(computed.values(), [])) - set(decree_keys))
            unchanged = sorted(set(decree_keys) - set(sum(computed.values(), [])))
            if not decree_keys or unchanged:
                print(f"✗ {case.id}: decree lists {decree_keys}, text changed in {computed}", file=sys.stderr)
                failures += 1
                continue
        else:
            truth, unlisted = {"added": [], "removed": [], "modified": []}, sorted(set(sum(computed.values(), [])))
        pdf = f"https://www.diputados.gob.mx/LeyesBiblio/pdf/{case.law}.pdf"
        fixture = {
            "id": case.id, "jurisdiction": "MX", "unit": "article",
            "citation": f"{case.law} — DOF {case.decree}" if case.decree else f"{case.law} (no reform)",
            "heading": after.name, "note": case.note, "substantive": case.substantive,
            "before": {"on": ts_before, "paragraphs": units(before)},
            "after": {"on": ts_after, "paragraphs": units(after)},
            "truth": truth,
            "computed_from_text": computed,
            "text_changes_not_in_decree": unlisted,
            "facts": [asdict(f) for f in case.facts],
            "change_types": sorted(case.change_types),
            "decree": {"file": f"{DIPUTADOS}/ref/{decree_href}" if decree_href else None,
                       "clause": clause, "articles": decree_keys},
            "sources": {"before": f"{WAYBACK}/web/{ts_before}id_/{pdf}", "after": f"{WAYBACK}/web/{ts_after}id_/{pdf}"},
        }
        _write(FIXTURES_MX / f"{case.id}.json.gz", fixture)
        print(f"✓ {case.id:28} {case.law:7} {ts_before[:8]} → {ts_after[:8]}  decree {decree_keys or '—'}"
              + (f"  (text also differs in {unlisted})" if unlisted else ""))
    return failures


def build(case_ids: set[str] | None = None) -> int:
    failures = build_ecfr(case_ids) + build_mx(case_ids)
    return 1 if failures else 0


# ── grade ─────────────────────────────────────────────────────────────────────

def _unit_of_ref(ref: str, unit: str) -> str:
    """App section ref → the fixture's unit key ('artículo 8o' → '8', 'artículo 17-h' → '17-h')."""
    if unit != "article":
        return ref
    folded = "".join(c for c in unicodedata.normalize("NFKD", ref) if not unicodedata.combining(c)).lower()
    m = re.match(r"articulo\s+(\d+)(?:o\b)?\s*(.*)$", folded)
    if not m:
        return ref
    rest = " ".join(m.group(2).replace(" -", "-").replace("- ", "-").split())
    return f"{int(m.group(1))}{rest}" if rest.startswith("-") else f"{int(m.group(1))} {rest}".strip()


def truth_units(fixture: dict) -> set[str]:
    t = fixture["truth"]
    keys = t["added"] + t["modified"] + t["removed"]
    if fixture.get("unit", "paragraph") == "article":
        return set(keys)
    out = set()
    for path in keys:  # CFR: the app works at top-level paragraph granularity
        m = re.match(r"\([a-z]{1,2}\)", path)
        out.add(m.group(0) if m else "__preamble__")
    return out


def grade_case(fixture: dict, result) -> dict:
    """Grade one ``AnalysisResult`` against a fixture (pure; unit-tested)."""
    unit = fixture.get("unit", "paragraph")
    after_text = render(fixture["after"], fixture["heading"])
    changes = result.changes
    detected = bool(changes)

    facts = []
    for f in fixture["facts"]:
        ok = any((not f["old"] or _squash(f["old"]) in _squash(c.old_text))
                 and (not f["new"] or _squash(f["new"]) in _squash(c.new_text)) for c in changes)
        facts.append({**f, "found": ok})

    expected = truth_units(fixture)
    types = sorted({c.change_type.value for c in changes})
    # Judge the type on the changes that sit on truly changed units: with 100 false units flagged,
    # "some flagged change has an acceptable type" is always true and means nothing.
    true_types = sorted({c.change_type.value for c in changes if _unit_of_ref(c.section_ref, unit) in expected})
    judged = true_types or types
    type_ok = bool(set(judged) & set(fixture["change_types"])) if fixture["change_types"] else True

    # How much text the app flags as "changed", against how much really changed. A reviewer has to
    # read everything flagged; 1.0 = the whole document.
    reported = sum(len(c.new_text or "") for c in changes)
    truth = fixture["truth"]
    after_units = dict((p, t) for p, t in fixture["after"]["paragraphs"])
    changed_chars = sum(len(after_units.get(p, "")) for p in truth["added"] + truth["modified"])
    total = max(len(after_text), 1)

    sections = [c.section_ref for c in changes]
    predicted = {_unit_of_ref(s, unit) for s in sections}
    hits = predicted & expected
    precision = len(hits) / len(predicted) if predicted else None
    if fixture["substantive"]:
        # a reviewer drowning in false alerts is a failure even when the real change is among them
        passed = (detected and all(f["found"] for f in facts) and type_ok
                  and precision is not None and precision >= MIN_UNIT_PRECISION)
    else:
        passed = not detected
    return {
        "id": fixture["id"], "jurisdiction": fixture.get("jurisdiction", "US"), "unit": unit,
        "citation": fixture["citation"], "substantive": fixture["substantive"],
        "passed": passed, "detected": detected,
        "facts_found": f"{sum(f['found'] for f in facts)}/{len(facts)}", "facts": facts,
        "change_types": types, "types_on_true_units": true_types,
        "expected_types": fixture["change_types"], "type_ok": type_ok,
        "sections_reported": sections,
        "units_expected": sorted(expected), "units_flagged": len(predicted),
        "unit_recall": round(len(hits) / len(expected), 2) if expected else None,
        "unit_precision": round(precision, 2) if precision is not None else None,
        "false_units": sorted(predicted - expected)[:20],
        "localized": bool(sections) and "__document__" not in sections,
        "flagged_share": round(min(reported / total, 1.0), 3),
        "truly_changed_share": round(min(changed_chars / total, 1.0), 3),
        "numeric_changes": [f"{n.old_value} → {n.new_value}" for c in changes for n in c.numeric_changes],
    }


def identity_check(fixture: dict) -> dict:
    """Would the app pair these two versions? It diffs a document only against an earlier one with
    the same ``regulation_key`` (title-derived)."""
    from src.nlp.regulation_id import regulation_key

    title = (f"{fixture['citation']} — {fixture['heading']}" if fixture.get("jurisdiction", "US") == "US"
             else fixture["heading"])
    key = regulation_key(title)
    return {"title": title, "regulation_key": key, "pairs_versions": key is not None}


def run(label: str = "") -> int:
    import logging

    from src.nlp.pipeline import analyze

    logging.disable(logging.INFO)
    sys.stdout.reconfigure(encoding="utf-8")
    fixtures = load_fixtures()
    if not fixtures:
        print("No fixtures — run `python -m evals.change_detection build` first.", file=sys.stderr)
        return 2
    rows = []
    for fx in fixtures:
        result = analyze(render(fx["after"], fx["heading"]), render(fx["before"], fx["heading"]))
        row = grade_case(fx, result) | {"identity": identity_check(fx)}
        rows.append(row)
        rec = "—" if row["unit_recall"] is None else f"{row['unit_recall']:.2f}"
        prec = "—" if row["unit_precision"] is None else f"{row['unit_precision']:.2f}"
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['id']:28} detected={row['detected']!s:5} "
              f"facts={row['facts_found']:4} types={','.join(row['types_on_true_units'] or row['change_types']) or '—':30} "
              f"units R={rec} P={prec} (flagged {row['units_flagged']})  "
              f"text {row['flagged_share']:.3f} vs {row['truly_changed_share']:.3f}  "
              f"key={row['identity']['regulation_key']}")
    summary = {"all": summarize(rows)}
    for j in sorted({r["jurisdiction"] for r in rows}):
        summary[j] = summarize([r for r in rows if r["jurisdiction"] == j])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-change-detection" + (f"-{label}" if label else "")
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    from evals.run import _git_state

    meta = {"run_id": run_id, "suite": "change_detection (eCFR SEC + DOF Mexico)", **_git_state(),
            "fixtures": len(fixtures)}
    (out / "report.json").write_text(json.dumps({"meta": meta, "summary": summary, "results": rows},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(markdown(meta, summary, rows), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Report: {out / 'report.md'}")
    return 0


def summarize(rows: list[dict]) -> dict:
    subst = [r for r in rows if r["substantive"]]
    controls = [r for r in rows if not r["substantive"]]
    n_facts = sum(len(r["facts"]) for r in subst)

    def avg(key):
        vals = [r[key] for r in subst if r[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "pass": f"{sum(r['passed'] for r in rows)}/{len(rows)}",
        "changes_detected": f"{sum(r['detected'] for r in subst)}/{len(subst)}",
        "controls_quiet": f"{sum(not r['detected'] for r in controls)}/{len(controls)}",
        "facts_found": f"{sum(f['found'] for r in subst for f in r['facts'])}/{n_facts}",
        "change_type_acceptable": f"{sum(r['type_ok'] for r in subst)}/{len(subst)}",
        "avg_unit_recall": avg("unit_recall"),
        "avg_unit_precision": avg("unit_precision"),
        "avg_flagged_share": avg("flagged_share"),
        "avg_truly_changed_share": avg("truly_changed_share"),
        "versions_paired_by_title": f"{sum(r['identity']['pairs_versions'] for r in rows)}/{len(rows)}",
    }


def markdown(meta: dict, summary: dict, rows: list[dict]) -> str:
    lines = [f"# Change detection — {meta['run_id']}", "",
             f"- Real amendments: SEC rules from the eCFR and Mexican federal laws from the DOF "
             f"({meta['fixtures']} fixtures), graded by code.",
             f"- Code: commit {meta.get('commit', '?')}" + (" + uncommitted changes" if meta.get("dirty") else ""),
             "", "## Summary", ""]
    keys = list(next(iter(summary.values())).keys())
    lines += ["| metric | " + " | ".join(summary) + " |", "|---|" + "---|" * len(summary)]
    lines += [f"| {k} | " + " | ".join(str(summary[s][k]) for s in summary) + " |" for k in keys]
    header = ("| case | citation | pass | detected | facts | types (expected) | units R / P (flagged) | "
              "text flagged / truly changed | regulation_key |")
    lines += ["", "## Cases", "", header, "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        rp = f"{r['unit_recall']} / {r['unit_precision']} ({r['units_flagged']})"
        lines.append(
            f"| {r['id']} | {r['citation']} | {'✓' if r['passed'] else '✗'} | {r['detected']} | {r['facts_found']} | "
            f"{', '.join(r['change_types']) or '—'} ({', '.join(r['expected_types']) or 'none'}) | {rp} | "
            f"{r['flagged_share']:.3f} / {r['truly_changed_share']:.3f} | {r['identity']['regulation_key']} |")
    legend = ("*units* = paragraphs (CFR) or articles (Mexican laws) the app flags, against those that "
              "really changed: R = recall, P = precision. *text flagged* = share of the document the app "
              "reports as changed (what a reviewer must read).")
    lines += ["", legend, ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="fetch sources and freeze fixtures (network)")
    b.add_argument("--case", action="append", help="only these case ids")
    r = sub.add_parser("run", help="grade the app's NLP pipeline on the fixtures (offline)")
    r.add_argument("--label", default="")
    args = p.parse_args(argv)
    if args.cmd == "build":
        sys.stdout.reconfigure(encoding="utf-8")
        return build(set(args.case) if args.case else None)
    return run(args.label)


if __name__ == "__main__":
    sys.exit(main())
