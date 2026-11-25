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
python -m evals.run --regrade evals/runs/<run>/report.json   # re-grade stored outputs, no model calls
```

Results go to `evals/runs/<timestamp>-<label>/report.{json,md}`; the JSON keeps every answer and draft.

## Limits

- 9 Q&A cases, 3 alerts for single-call drafting, 1 alert for the team. One case moves a rate by
  10+ points, so small differences between models are noise.
- Synthetic corpus (3 CNBV circulars, 6 demo contracts), developer-written cases, no lawyer review.
- Retrieval is keyword-only (embeddings off) for determinism. Questions asked in English against
  Spanish circulars often retrieve nothing in `rag`; `answerable_without_context` counts those, so a
  retrieval miss is not read as a model failure.
- Local models run with temperature 0 and a fixed seed, and without "thinking".
