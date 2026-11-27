# Evals

Model comparison for the four LLM features, through the real HTTP endpoints:

| Suite | Endpoint | Graded on |
|---|---|---|
| `rag` | `POST /chat/stream` | expected facts present, ≥1 valid `[REG-n]`/`[CON-n]` citation, no invented tags; refusal on unanswerable questions |
| `agent` | `POST /agents/chat` | same, plus steps taken and tool errors; includes two multi-step questions |
| `addendum` | `POST /addendum/draft/{alert}` | structure (recitals, operative clause, articles, general provisions, signature), names the contract, cites the circular number, no percentage absent from the sources |
| `team` | `POST /agents/addendum/{alert}` | same as `addendum`, plus reviewer verdicts, revision rounds and agent failures |

Everything is graded by code ([run.py](run.py), cases in [cases.py](cases.py)). No LLM judge is used.
`references_real_clause` (does the draft cite a clause number that really exists in the contract) is
reported but not part of `pass`: rules-engine impacts carry no clause, so only an agent that reads
the contract can get it right.

## Run

```bash
# Throwaway database (the eval TRUNCATEs it; the name must end in _eval or _test)
docker run -d --rm --name rca-eval-db -e POSTGRES_USER=rca_user -e POSTGRES_PASSWORD=rca_pass \
  -e POSTGRES_DB=regulatory_eval -p 55432:5432 pgvector/pgvector:pg16

export DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:55432/regulatory_eval
python -m evals.run \
  --model ollama:qwen3:4b-instruct-2507-q4_K_M \
  --model ollama:gemma4:26b-a4b-it-qat \
  --model anthropic:claude-opus-5-5          # skipped unless ANTHROPIC_API_KEY is set (billed)

python -m evals.run --suites rag,agent --model ollama:qwen3:4b-instruct-2507-q4_K_M   # a subset
python -m evals.run --embeddings on --model ...   # hybrid retrieval with bge-m3 (needs `ollama pull bge-m3`)
python -m evals.run --regrade evals/runs/<run>/report.json   # re-grade stored outputs, no model calls
```

Results go to `evals/runs/<timestamp>-<label>/report.{json,md}`; the JSON keeps every answer and draft,
plus the commit, whether the tree had uncommitted changes, and the retrieval mode. Q&A rows record
`regenerations` and `system_refusal` (the validator in `src/services/grounding.py`).

## Change detection on real SEC amendments (eCFR)

A separate, offline suite grades the NLP pipeline (diff + classification) on real rule amendments:
a CFR section the day before an amendment took effect vs the day it did, from the eCFR
point-in-time API, with the Federal Register rule and its amendatory instruction as evidence.

```bash
python -m evals.change_detection build   # fetch + freeze fixtures to evals/data/ecfr/ (network; cached in evals/.cache/)
python -m evals.change_detection run     # grade src.nlp.pipeline.analyze on them (offline)
```

Cases live in [ecfr_cases.py](ecfr_cases.py): T+1 (2023) and T+2 (2017) settlement, the Marketing Rule
(2021), Rule 10b5-1 (2023), Schedule 13D/G deadlines (2024), the Names Rule (2023), electronic
recordkeeping (2023), and two controls with identical text.

- **Ground truth**: which paragraphs changed, aligned by official label ((a), (b)(2)…) — computed
  without the app's NLP; it matches the Federal Register's own amendatory instruction where that
  lists paragraphs (e.g. Schedule 13D). Plus verbatim **facts** ("second business day" → "first
  business day") that must sit on the right side of a reported change; `build` refuses a case whose
  facts are not in the fetched text.
- **Metrics**: change detected; controls quiet; facts found; acceptable change type (developer
  judgment); whether the change is localised below the section; share of the section flagged vs share
  that really changed; whether the app would pair the two versions at all (`regulation_key`).
- Results (2026-11-27): the first run passed **7/9**. It missed T+3 → T+2, flagged whole sections,
  typed a deadline change as a new requirement, and paired 0/9 versions. After the fixes it passes
  **9/9**: 7/7 detected, 13/13 facts, 7/7 localised, 9/9 paired. Runs are in
  `evals/runs/*-change-detection-*`.
- Fixtures are US government works (public domain) and are committed. The Federal Register text
  comes from the GovInfo API (`GOVINFO_API_KEY`, or the rate-limited public `DEMO_KEY`).

## Limits

- 9 Q&A cases, 3 alerts for single-call drafting, 1 alert for the team. One case moves a rate by
  10+ points, so small differences between models are noise.
- Synthetic corpus (3 CNBV circulars, 6 demo contracts), developer-written cases, no lawyer review.
- `--embeddings off` (default) is keyword-only retrieval, deterministic. `--embeddings on` uses the
  configured embedder (bge-m3 via Ollama) with hybrid retrieval. Questions asked in English against
  Spanish circulars often retrieve nothing in `rag`; `answerable_without_context` counts those, so a
  retrieval miss is not read as a model failure.
- Local models run with temperature 0 and a fixed seed, and without "thinking".
