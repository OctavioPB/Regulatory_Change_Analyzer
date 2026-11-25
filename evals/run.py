"""Evaluate the LLM features of the app against one or more models.

Suites (each goes through the real HTTP endpoints, in-process):
    rag       classic RAG chat          POST /chat/stream
    agent     research agent            POST /agents/chat
    addendum  single-call drafting      POST /addendum/draft/{alert}
    team      multi-agent drafting      POST /agents/addendum/{alert}

Everything is graded by code (facts present, citations valid, refusals, addendum
structure, clause coverage, unsupported percentages) — see evals/cases.py.

Usage:
    DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:55432/regulatory_eval \\
    python -m evals.run --model ollama:qwen3:4b-instruct-2507-q4_K_M \\
                        --model ollama:gemma4:26b-a4b-it-qat [--model anthropic:claude-opus-5-5]
                        [--suites rag,agent,addendum,team] [--team-alerts 1] [--label note]

Safety: the database is TRUNCATEd, so its name must end in ``_eval`` or ``_test``.
Embeddings are disabled (keyword retrieval) so runs are deterministic and fast.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "evals" / "runs"
API = "/api/v1"
ALL_SUITES = ("rag", "agent", "addendum", "team")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Normalisation / grading helpers ───────────────────────────────────────────

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"(?<=\d)[,\s](?=\d{3}\b)", "", s)  # 100,000 / 100 000 → 100000


def has_any(text: str, alternatives: list[str]) -> bool:
    t = norm(text)
    return any(norm(a) in t for a in alternatives)


_TAG_RE = re.compile(r"\b(REG|CON)-(\d+)\b")
_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s?%")
_CIRCULAR_RE = re.compile(r"\b(\d{1,3}/\d{4})\b")


def _canon(num: str) -> str:
    """"12.0" and "12" are the same figure; "10.50" and "10.5" too."""
    num = num.replace(",", ".")
    return num.rstrip("0").rstrip(".") if "." in num else num


def _pct_values(text: str) -> set[str]:
    return {_canon(m) for m in _PCT_RE.findall(text or "")}


def _numbers(text: str) -> set[str]:
    return {_canon(m) for m in re.findall(r"\d+(?:[.,]\d+)?", norm(text))}


def parse_sse(body: str) -> list[dict]:
    out = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                out.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return out


# ── Corpus ────────────────────────────────────────────────────────────────────

async def build_corpus(client) -> dict:
    """Fresh DB → seed contracts + synthetic circulars → analyze → map. Returns ground truth."""
    import importlib.util

    from sqlalchemy import text

    from src.database import AsyncSessionLocal, Base, engine, init_db
    from src.models.document import RegulatoryDocument

    await init_db()
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    spec = importlib.util.spec_from_file_location("seed_cnbv", ROOT / "scripts" / "seed_cnbv.py")
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)

    assert (await client.post(f"{API}/contracts/seed")).status_code == 201
    async with AsyncSessionLocal() as s:
        for raw in seed._CNBV_SAMPLES:
            s.add(RegulatoryDocument(source=raw.source, external_id=raw.external_id, title=raw.title,
                                     url=raw.url, publication_date=raw.publication_date,
                                     raw_text=raw.raw_text))
        await s.commit()
    assert (await client.post(f"{API}/ingest/analyze")).status_code == 202
    assert (await client.post(f"{API}/ingest/map")).status_code == 202
    return await load_truth()


async def load_truth() -> dict:
    """Ground truth (alerts, affected contracts, clause texts) read from the eval database."""
    from sqlalchemy import text

    from src.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        alerts = (await s.execute(text("""
            SELECT ia.id, rd.title, rd.raw_text FROM impact_alerts ia
            JOIN regulatory_documents rd ON rd.id = ia.document_id ORDER BY rd.publication_date
        """))).fetchall()
        items = (await s.execute(text("""
            SELECT ii.alert_id, ii.affected_name, ii.affected_ref FROM impact_items ii
            WHERE ii.impact_type = 'contract'
        """))).fetchall()
        clauses = (await s.execute(text("""
            SELECT c.name, cc.clause_ref, cc.text FROM contract_clauses cc JOIN contracts c ON c.id = cc.contract_id
        """))).fetchall()

    truth = {"alerts": []}
    for a in alerts:
        contracts: dict[str, list[str]] = {}
        for it in items:
            if it.alert_id == a.id:
                contracts.setdefault(it.affected_name, [])
                if it.affected_ref and it.affected_ref not in contracts[it.affected_name]:
                    contracts[it.affected_name].append(it.affected_ref)
        truth["alerts"].append({
            "id": str(a.id), "title": a.title, "raw_text": a.raw_text,
            "contracts": contracts,
        })
    truth["clauses"] = {}
    for c in clauses:
        truth["clauses"].setdefault(c.name, []).append(f"{c.clause_ref}: {c.text}")
    return truth


# ── Q&A suites ────────────────────────────────────────────────────────────────

def grade_answer(case, facts, answer: str, citations: list[dict], error: str | None) -> dict:
    valid = {f"{'REG' if c['type'] == 'regulation' else 'CON'}-{c['ref_id']}" for c in citations}
    tags = {f"{p}-{n}" for p, n in _TAG_RE.findall(answer)}
    from evals.cases import REFUSAL_MARKERS

    refused = has_any(answer, REFUSAL_MARKERS)
    facts_ok = all(has_any(answer, g) for g in facts) if facts else None
    if error:
        passed = False
    elif case.answerable:
        passed = bool(facts_ok) and bool(tags) and not (tags - valid)
    else:
        passed = refused
    return {
        "passed": passed,
        "facts_ok": facts_ok,
        "facts_missing": [g[0] for g in facts if not has_any(answer, g)],
        "cited": bool(tags),
        "invalid_citations": sorted(tags - valid),
        "refused": refused,
        "false_refusal": case.answerable and refused and not facts_ok,
        "error": error,
    }


async def run_qa(client, suite: str, truth: dict) -> list[dict]:
    from evals.cases import QA_CASES

    path = f"{API}/chat/stream" if suite == "rag" else f"{API}/agents/chat"
    results = []
    for case in QA_CASES:
        if case.agent_only and suite == "rag":
            continue
        t0 = time.monotonic()
        res = await client.post(path, json={"query": case.question})
        elapsed = time.monotonic() - t0
        events = parse_sse(res.text) if res.status_code == 200 else []
        error = None if res.status_code == 200 else f"HTTP {res.status_code}"
        tokens, citations, steps, done, retrieved = [], [], [], None, 0
        for e in events:
            if e["type"] == "token":
                tokens.append(e["text"])
            elif e["type"] == "reset":
                tokens.clear()  # the server rejected that answer; a corrected one or the refusal follows
            elif e["type"] == "citations":
                citations = e["citations"]
                retrieved = max(retrieved, len(citations))
            elif e["type"] == "step" and e.get("status") == "running":
                tokens.clear()  # text before a tool call is narration, not the answer
                steps.append({"tool": e["tool"], "input": e.get("input")})
            elif e["type"] == "step":
                if steps:
                    steps[-1]["status"] = e["status"]
            elif e["type"] == "error":
                error = e["message"]
            elif e["type"] == "done":
                done = e
        answer = "".join(tokens)
        facts = case.facts
        grade = grade_answer(case, facts, answer, citations, error)
        row = {"case": case.id, "answerable": case.answerable, "seconds": round(elapsed, 1),
               "retrieved_sources": retrieved, "answer": answer,
               "regenerations": (done or {}).get("regenerations", 0),
               "system_refusal": bool((done or {}).get("refused")), **grade}
        if suite == "agent":
            row.update({
                "steps": len(steps),
                "tool_errors": sum(1 for s in steps if s.get("status") == "error"),
                "tools": [s["tool"] for s in steps],
                "usage": (done or {}).get("usage"),
            })
        results.append(row)
        log(f"  {suite:5} {case.id:32} {'PASS' if grade['passed'] else 'FAIL'}  {elapsed:6.1f}s"
            + (f"  steps={row['steps']}" if suite == "agent" else "")
            + (f"  error={error}" if error else ""))
    return results


# ── Addendum suites ───────────────────────────────────────────────────────────

def grade_draft(draft: str, contract: str, alert: dict, truth: dict) -> dict:
    from evals.cases import ADDENDUM_SECTIONS

    refs = alert["contracts"].get(contract, [])
    ref_nums = [re.sub(r"^[A-Za-z]+\s*", "", r) for r in refs]
    circular = (_CIRCULAR_RE.search(alert["title"]) or [None])[0]
    sources = alert["raw_text"] + "\n" + "\n".join(truth["clauses"].get(contract, []))
    # Percentages in the draft that appear nowhere in the regulation or the contract
    source_nums = _numbers(sources) | {"100"}  # "100%" is generic legal phrasing
    unsupported = sorted(p for p in _pct_values(draft) if p not in source_nums)
    sections = {label: has_any(draft, alts) for label, alts in ADDENDUM_SECTIONS}
    coverage = (sum(1 for n in ref_nums if n and n in draft) / len(ref_nums)) if ref_nums else 1.0
    # Rules-engine items carry no clause ref, so check whether the draft names a REAL clause of
    # the contract (the team's drafters can read it with get_contract; a single call cannot)
    real_refs = [c.split(":", 1)[0] for c in truth["clauses"].get(contract, [])]
    real_nums = [re.sub(r"^[A-Za-z]+\s*", "", r) for r in real_refs]
    out = {
        "contract": contract,
        "references_real_clause": any(n and re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", draft) for n in real_nums),
        "chars": len(draft),
        "sections": sections,
        "structure": round(sum(sections.values()) / len(sections), 2),
        "names_contract": has_any(draft, [contract]),
        "clause_coverage": round(coverage, 2),
        "cites_circular": bool(circular and circular in draft),
        "unsupported_percentages": unsupported,
        "placeholders": bool(re.search(r"\[(DATE|PARTY|JURISDICTION|FECHA)", draft, re.I)),
    }
    out["passed"] = (out["structure"] == 1.0 and out["names_contract"] and out["clause_coverage"] == 1.0
                     and out["cites_circular"] and not unsupported and len(draft) > 400)
    return out


def pick_alerts(truth: dict) -> list[dict]:
    """One alert per regulatory document (the first with contract impacts) — alerts are per article."""
    seen, picked = set(), []
    for a in truth["alerts"]:
        doc = a["title"].split(":")[0]
        if a["contracts"] and doc not in seen:
            seen.add(doc)
            picked.append(a)
    return picked


async def run_addendum(client, truth: dict) -> list[dict]:
    results = []
    for alert in pick_alerts(truth):
        t0 = time.monotonic()
        res = await client.post(f"{API}/addendum/draft/{alert['id']}")
        elapsed = time.monotonic() - t0
        events = parse_sse(res.text)
        drafts: dict[str, list[str]] = {}
        current, error = None, None
        for e in events:
            if e["type"] == "meta":
                current = e["contract_name"]
                drafts[current] = []
            elif e["type"] == "token" and current:
                drafts[current].append(e["text"])
            elif e["type"] == "error":
                error = e["message"]
        for contract in alert["contracts"]:
            text_ = "".join(drafts.get(contract, [])).strip().strip("-").strip()
            g = grade_draft(text_, contract, alert, truth)
            g.update({"alert": alert["title"], "error": error, "draft": text_})
            if error:
                g["passed"] = False
            results.append(g)
        log(f"  addendum {alert['title'][:48]:48} {len(alert['contracts'])} contract(s) {elapsed:6.1f}s"
            + (f" error={error}" if error else ""))
        for g in results[-len(alert["contracts"]):]:
            log(f"      {'PASS' if g['passed'] else 'FAIL'} {g['contract'][:40]:40} struct={g['structure']} "
                f"realclause={g['references_real_clause']} circ={g['cites_circular']} unsup={g['unsupported_percentages']}")
        results[-1]["alert_seconds"] = round(elapsed, 1)
    return results


async def run_team(client, truth: dict, n_alerts: int) -> list[dict]:
    results = []
    # Smallest alerts first: every contract costs a drafter + reviewer loop
    candidates = sorted(pick_alerts(truth), key=lambda a: len(a["contracts"]))[:n_alerts]
    for alert in candidates:
        t0 = time.monotonic()
        res = await client.post(f"{API}/agents/addendum/{alert['id']}")
        elapsed = time.monotonic() - t0
        events = parse_sse(res.text)
        reviews: dict[str, list[dict]] = {}
        failures: dict[str, list[str]] = {}
        tools: dict[str, int] = {}
        done, error = None, None
        drafts = {}
        for e in events:
            if e["type"] == "review":
                reviews.setdefault(e["contract_name"], []).append(
                    {"round": e["round"], "approved": e["approved"], "issues": e["issues"]})
            elif e["type"] == "agent" and e["status"] == "failed":
                failures.setdefault(e["contract_name"], []).append(f"{e['role']}:{e.get('detail')}")
            elif e["type"] == "agent" and e["status"] == "tool":
                tools[e["contract_name"]] = tools.get(e["contract_name"], 0) + 1
            elif e["type"] == "draft":
                drafts[e["contract_name"]] = e
            elif e["type"] == "done":
                done = e
            elif e["type"] == "error":
                error = e["message"]
        for contract in alert["contracts"]:
            d = drafts.get(contract)
            g = grade_draft(d["text"] if d else "", contract, alert, truth)
            g.update({
                "alert": alert["title"],
                "review_approved": d["approved"] if d else None,
                "rounds": d["rounds"] if d else 0,
                "reviews": reviews.get(contract, []),
                "agent_failures": failures.get(contract, []),
                "tool_calls": tools.get(contract, 0),
                "error": error,
                "draft": d["text"] if d else "",
            })
            if error or not d:
                g["passed"] = False
            results.append(g)
        if results:
            results[-1]["alert_seconds"] = round(elapsed, 1)
            results[-1]["usage"] = (done or {}).get("usage")
        log(f"  team {alert['title'][:48]:48} {elapsed:7.1f}s" + (f" error={error}" if error else ""))
        for g in results[-len(alert["contracts"]):]:
            log(f"      {'PASS' if g['passed'] else 'FAIL'} {g['contract'][:40]:40} rounds={g['rounds']} "
                f"approved={g['review_approved']} tools={g['tool_calls']} fails={g['agent_failures']}")
    return results


# ── Summary ───────────────────────────────────────────────────────────────────

def _rate(rows, key="passed") -> str:
    return f"{sum(1 for r in rows if r.get(key))}/{len(rows)}" if rows else "—"


def summarize(model_results: dict) -> dict:
    s = {}
    for model, suites in model_results.items():
        row = {}
        for name in ("rag", "agent"):
            rows = suites.get(name)
            if rows is None:
                continue
            ans = [r for r in rows if r["answerable"]]
            una = [r for r in rows if not r["answerable"]]
            row[name] = {
                "pass": _rate(rows),
                "answerable_pass": _rate(ans),
                "refusal_accuracy": _rate(una, "refused"),
                "false_refusals": sum(1 for r in ans if r["false_refusal"]),
                "invalid_citations": sum(len(r["invalid_citations"]) for r in rows),
                "errors": sum(1 for r in rows if r["error"]),
                # rag: answerable cases where retrieval found nothing (the model never saw the facts)
                "answerable_without_context": (sum(1 for r in ans if r["retrieved_sources"] == 0)
                                               if name == "rag" else None),
                "p50_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2] if rows else None,
            }
            if name == "agent":
                row[name]["avg_steps"] = round(sum(r["steps"] for r in rows) / len(rows), 1)
                row[name]["tool_errors"] = sum(r["tool_errors"] for r in rows)
        for name in ("addendum", "team"):
            rows = suites.get(name)
            if rows is None:
                continue
            row[name] = {
                "pass": _rate(rows),
                "avg_structure": round(sum(r["structure"] for r in rows) / len(rows), 2) if rows else None,
                "avg_clause_coverage": round(sum(r["clause_coverage"] for r in rows) / len(rows), 2) if rows else None,
                "cites_circular": _rate(rows, "cites_circular"),
                "drafts_with_unsupported_pct": sum(1 for r in rows if r["unsupported_percentages"]),
                "references_real_clause": _rate(rows, "references_real_clause"),
                "seconds": round(sum(r.get("alert_seconds", 0) for r in rows), 1),
            }
            if name == "team":
                row[name]["review_approved"] = _rate(rows, "review_approved")
                row[name]["avg_rounds"] = round(sum(r["rounds"] for r in rows) / len(rows), 1) if rows else None
                row[name]["agent_failures"] = sum(len(r["agent_failures"]) for r in rows)
        s[model] = row
    return s


def write_markdown(path: Path, meta: dict, summary: dict) -> None:
    lines = [f"# Eval run {meta['run_id']}", "",
             f"- Started: {meta['started']}  ·  finished: {meta['finished']}",
             f"- Suites: {', '.join(meta['suites'])}  ·  retrieval: "
             f"{meta.get('retrieval', 'keyword (embeddings off)')}",
             f"- Code: commit {meta.get('commit', '?')}" + (" + uncommitted changes" if meta.get("dirty") else ""),
             "- Cases: developer-written over synthetic data, graded by code. Not lawyer-reviewed.", ""]
    for suite, cols in (
        ("rag", ["pass", "answerable_pass", "refusal_accuracy", "false_refusals", "answerable_without_context",
                 "invalid_citations", "errors", "p50_seconds"]),
        ("agent", ["pass", "answerable_pass", "refusal_accuracy", "false_refusals", "invalid_citations",
                   "avg_steps", "tool_errors", "errors", "p50_seconds"]),
        ("addendum", ["pass", "avg_structure", "cites_circular", "references_real_clause",
                      "drafts_with_unsupported_pct", "seconds"]),
        ("team", ["pass", "review_approved", "avg_rounds", "avg_structure", "cites_circular",
                  "references_real_clause", "drafts_with_unsupported_pct", "agent_failures", "seconds"]),
    ):
        models = [m for m in summary if suite in summary[m]]
        if not models:
            continue
        lines += [f"## {suite}", "", "| model | " + " | ".join(cols) + " |",
                  "|---|" + "---|" * len(cols)]
        for m in models:
            lines.append(f"| {m} | " + " | ".join(str(summary[m][suite].get(c)) for c in cols) + " |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

async def warm_up(provider: str, model: str) -> None:
    """Load a local model before timing anything (first load can take a minute)."""
    if provider != "ollama":
        return
    from src.services.llm import get_client

    t0 = time.monotonic()
    await get_client().messages.create(model=model, max_tokens=5,
                                       messages=[{"role": "user", "content": "ok"}])
    log(f"  warm-up {model}: {time.monotonic() - t0:.1f}s")


async def regrade(path: Path) -> int:
    """Re-grade the stored drafts of a report with the current graders (no model calls)."""
    truth = await load_truth()
    by_title = {a["title"]: a for a in truth["alerts"]}
    data = json.loads(path.read_text(encoding="utf-8"))
    for suites in data["results"].values():
        for suite in ("addendum", "team"):
            for row in suites.get(suite, []):
                extra = {k: row[k] for k in ("alert_seconds", "usage") if k in row}
                g = grade_draft(row.get("draft", ""), row["contract"], by_title[row["alert"]], truth)
                failed = bool(row.get("error")) or (suite == "team" and not row.get("draft"))
                row.update(g, **extra)
                if failed:
                    row["passed"] = False
    data["summary"] = summarize(data["results"])
    data["meta"]["regraded"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(path.with_suffix(".md"), data["meta"], data["summary"])
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))
    return 0


async def main(args) -> int:
    db_name = urlparse(os.environ.get("DATABASE_URL", "")).path.lstrip("/")
    if not (db_name.endswith("_eval") or db_name.endswith("_test")):
        print("DATABASE_URL must point at a *_eval or *_test database (it is TRUNCATEd).", file=sys.stderr)
        return 2

    sys.stdout.reconfigure(encoding="utf-8")
    import logging
    import httpx

    from src.api.main import app
    from src.config import settings
    from src.mapping import embedder

    logging.disable(logging.INFO)  # keep the progress log readable; warnings still show
    if args.embeddings == "off":  # keyword-only retrieval, rules-only mapping
        settings.embedding_provider = "none"
    elif not embedder.available():
        print(f"--embeddings on, but {settings.embedding_provider}:{settings.embedding_model} is not "
              "available (Ollama running? model pulled?)", file=sys.stderr)
        return 2

    if args.regrade:
        return await regrade(Path(args.regrade))

    suites = [s for s in args.suites.split(",") if s]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + (f"-{args.label}" if args.label else "")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"run_id": run_id, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "suites": suites, "models": args.model, **_git_state(),
            "retrieval": ("keyword (embeddings off)" if settings.embedding_provider == "none" else
                          f"hybrid: {settings.embedding_provider}:{settings.embedding_model} + keyword, RRF")}
    if not args.model:
        print("--model is required (or --regrade)", file=sys.stderr)
        return 2

    results: dict[str, dict] = {}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://eval", timeout=None) as client:
        log("Building corpus")
        truth = await build_corpus(client)
        log(f"  {len(truth['alerts'])} alerts: " + "; ".join(
            f"{a['title'][:30]}→{len(a['contracts'])} contracts" for a in truth["alerts"]))

        for spec in args.model:
            provider, _, model = spec.partition(":")
            if provider not in ("ollama", "anthropic") or not model:
                print(f"bad --model {spec!r}: use ollama:<tag> or anthropic:<model-id>", file=sys.stderr)
                return 2
            if provider == "anthropic" and not settings.anthropic_api_key:
                log(f"SKIP {spec}: ANTHROPIC_API_KEY is not set")
                continue
            settings.llm_provider, settings.llm_model = provider, model
            log(f"Model {spec}")
            await warm_up(provider, model)
            results[spec] = {}
            for suite in suites:
                t0 = time.monotonic()
                if suite in ("rag", "agent"):
                    results[spec][suite] = await run_qa(client, suite, truth)
                elif suite == "addendum":
                    results[spec][suite] = await run_addendum(client, truth)
                elif suite == "team":
                    results[spec][suite] = await run_team(client, truth, args.team_alerts)
                log(f"  {suite} done in {time.monotonic() - t0:.0f}s")
                # Persist after every suite: a long run that dies still leaves results
                summary = summarize(results)
                (out_dir / "report.json").write_text(json.dumps(
                    {"meta": meta, "summary": summary, "results": results}, ensure_ascii=False, indent=2),
                    encoding="utf-8")

    meta["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary = summarize(results)
    (out_dir / "report.json").write_text(json.dumps(
        {"meta": meta, "summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(out_dir / "report.md", meta, summary)
    log(f"Report: {out_dir / 'report.md'}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _git_state() -> dict:
    """Commit and dirty flag, so a report can be tied to the code that produced it."""
    import subprocess

    def git(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT).stdout.strip()

    try:
        return {"commit": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except OSError:
        return {}


def _parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--regrade", help="re-grade an existing report.json against the same eval DB")
    p.add_argument("--model", action="append",
                   help="ollama:<tag> or anthropic:<model-id>; repeat to compare")
    p.add_argument("--suites", default=",".join(ALL_SUITES))
    p.add_argument("--team-alerts", type=int, default=1, help="alerts to run the drafting team on")
    p.add_argument("--label", default="")
    p.add_argument("--embeddings", choices=["off", "on"], default="off",
                   help="off: keyword retrieval (deterministic); on: hybrid with the configured "
                        "embedder (default bge-m3 via Ollama)")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(_parse())))
