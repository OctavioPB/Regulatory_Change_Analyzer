"""Change-detection eval on real SEC rule amendments (eCFR + Federal Register).

    python -m evals.change_detection build           # fetch eCFR/FR, freeze fixtures (network)
    python -m evals.change_detection run [--label x] # grade the app's NLP pipeline (offline)

``build`` writes one JSON fixture per case to ``evals/data/ecfr/``: both versions as labelled
paragraphs, the paragraph-level ground truth, the Federal Register rule and its amendatory
instruction. It refuses to write a case whose annotated facts are not in the fetched text.

``run`` feeds each pair to ``src.nlp.pipeline.analyze(new, old)`` — exactly what the app does once
it has found a document's previous version — and grades it. It also checks that the app would
find that previous version at all (``regulation_key`` on the document title).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "data" / "ecfr"
RUNS = ROOT / "evals" / "runs"


# ── build ─────────────────────────────────────────────────────────────────────

def build(case_ids: set[str] | None = None) -> int:
    from evals.ecfr_cases import CASES
    from evals.sources.ecfr import EcfrClient, compare
    from evals.sources.federal_register import FederalRegisterClient, amendatory_instruction, published_iso

    ecfr, fr = EcfrClient(), FederalRegisterClient()
    FIXTURES.mkdir(parents=True, exist_ok=True)
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
            "id": case.id, "citation": after.citation, "heading": after.heading,
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
        (FIXTURES / f"{case.id}.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
        t = fixture["truth"]
        print(f"✓ {case.id:24} {case.section:14} {before.on} → {after.on}  "
              f"+{len(t['added'])} -{len(t['removed'])} ~{len(t['modified'])}  "
              f"FR {rule['citation'] if rule else '—'}")
    return 1 if failures else 0


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _missing_facts(case, before_text: str, after_text: str) -> list[str]:
    b, a = _norm(before_text), _norm(after_text)
    out = []
    for f in case.facts:
        if f.old and _norm(f.old) not in b:
            out.append(f"old: {f.old}")
        if f.new and _norm(f.new) not in a:
            out.append(f"new: {f.new}")
    return out


# ── grade ─────────────────────────────────────────────────────────────────────

def render(side: dict, heading: str) -> str:
    return "\n".join([heading, *(text for _, text in side["paragraphs"])])


def grade_case(fixture: dict, result) -> dict:
    """Grade one ``AnalysisResult`` against a fixture (pure; unit-tested)."""
    after_text = render(fixture["after"], fixture["heading"])
    changes = result.changes
    detected = bool(changes)

    facts = []
    for f in fixture["facts"]:
        ok = any((not f["old"] or _norm(f["old"]) in _norm(c.old_text))
                 and (not f["new"] or _norm(f["new"]) in _norm(c.new_text)) for c in changes)
        facts.append({**f, "found": ok})

    types = sorted({c.change_type.value for c in changes})
    type_ok = bool(set(types) & set(fixture["change_types"])) if fixture["change_types"] else True

    # How much text the app flags as "changed", against how much really changed. A reviewer has to
    # read everything flagged; 1.0 = the whole section.
    reported = sum(len(c.new_text or "") for c in changes)
    truth = fixture["truth"]
    after_paras = dict((p, t) for p, t in fixture["after"]["paragraphs"])
    changed_chars = sum(len(after_paras.get(p, "")) for p in truth["added"] + truth["modified"])
    total = max(len(after_text), 1)

    sections = [c.section_ref for c in changes]
    if fixture["substantive"]:
        passed = detected and all(f["found"] for f in facts) and type_ok
    else:
        passed = not detected
    return {
        "id": fixture["id"], "citation": fixture["citation"], "substantive": fixture["substantive"],
        "passed": passed, "detected": detected,
        "facts_found": f"{sum(f['found'] for f in facts)}/{len(facts)}", "facts": facts,
        "change_types": types, "expected_types": fixture["change_types"], "type_ok": type_ok,
        "sections_reported": sections,
        "localized": bool(sections) and "__document__" not in sections,
        "flagged_share": round(min(reported / total, 1.0), 2),
        "truly_changed_share": round(min(changed_chars / total, 1.0), 2),
        "truth_paragraphs": {k: len(v) for k, v in truth.items()},
        "numeric_changes": [f"{n.old_value} → {n.new_value}" for c in changes for n in c.numeric_changes],
    }


def identity_check(fixture: dict) -> dict:
    """Would the app pair these two versions? It diffs a document only against an earlier one with
    the same ``regulation_key`` (title-derived)."""
    from src.nlp.regulation_id import regulation_key

    title = f"{fixture['citation']} — {fixture['heading']}"
    key = regulation_key(title)
    return {"title": title, "regulation_key": key, "pairs_versions": key is not None}


def run(label: str = "") -> int:
    import logging

    from src.nlp.pipeline import analyze

    logging.disable(logging.INFO)
    sys.stdout.reconfigure(encoding="utf-8")
    fixtures = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*.json"))]
    if not fixtures:
        print("No fixtures — run `python -m evals.change_detection build` first.", file=sys.stderr)
        return 2
    rows = []
    for fx in fixtures:
        result = analyze(render(fx["after"], fx["heading"]), render(fx["before"], fx["heading"]))
        row = grade_case(fx, result) | {"identity": identity_check(fx)}
        rows.append(row)
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['id']:24} detected={row['detected']!s:5} "
              f"facts={row['facts_found']:4} types={','.join(row['change_types']) or '—':28} "
              f"flagged={row['flagged_share']:.2f} vs changed={row['truly_changed_share']:.2f}  "
              f"key={row['identity']['regulation_key']}")
    summary = summarize(rows)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-change-detection" + (f"-{label}" if label else "")
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)
    from evals.run import _git_state

    meta = {"run_id": run_id, "suite": "change_detection (eCFR, SEC)", **_git_state(),
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
    return {
        "pass": f"{sum(r['passed'] for r in rows)}/{len(rows)}",
        "changes_detected": f"{sum(r['detected'] for r in subst)}/{len(subst)}",
        "controls_quiet": f"{sum(not r['detected'] for r in controls)}/{len(controls)}",
        "facts_found": f"{sum(f['found'] for r in subst for f in r['facts'])}/{n_facts}",
        "change_type_acceptable": f"{sum(r['type_ok'] for r in subst)}/{len(subst)}",
        "localized_below_section": f"{sum(r['localized'] for r in subst)}/{len(subst)}",
        "avg_flagged_share": round(sum(r["flagged_share"] for r in subst) / max(len(subst), 1), 2),
        "avg_truly_changed_share": round(sum(r["truly_changed_share"] for r in subst) / max(len(subst), 1), 2),
        "versions_paired_by_title": f"{sum(r['identity']['pairs_versions'] for r in rows)}/{len(rows)}",
    }


def markdown(meta: dict, summary: dict, rows: list[dict]) -> str:
    lines = [f"# Change detection — {meta['run_id']}", "",
             f"- Real SEC amendments from the eCFR ({meta['fixtures']} fixtures), graded by code.",
             f"- Code: commit {meta.get('commit', '?')}" + (" + uncommitted changes" if meta.get("dirty") else ""),
             "", "## Summary", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "## Cases", "",
              "| case | citation | pass | detected | facts | types (expected) | flagged / truly changed | regulation_key |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['citation']} | {'✓' if r['passed'] else '✗'} | {r['detected']} | {r['facts_found']} | "
            f"{', '.join(r['change_types']) or '—'} ({', '.join(r['expected_types']) or 'none'}) | "
            f"{r['flagged_share']:.2f} / {r['truly_changed_share']:.2f} | {r['identity']['regulation_key']} |")
    lines += ["", "*flagged* = share of the section the app reports as changed (what a reviewer must read); "
              "*truly changed* = share of paragraphs that changed, by official label.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="fetch eCFR / Federal Register and freeze fixtures (network)")
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
