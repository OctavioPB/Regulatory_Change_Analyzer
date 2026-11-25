# Engineering

How the codebase is organised, how to run and test it, the conventions that keep it working, and a log of
the engineering decisions behind the current state. For the component picture, see
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Stack

| Area | Technology |
|---|---|
| API | Python 3.11, FastAPI, Pydantic v2, async SQLAlchemy 2 + asyncpg |
| Data | PostgreSQL 16 + pgvector (HNSW), Alembic, Redis 7 |
| Jobs | Celery + beat (daily scrape); FastAPI background tasks for one-off analysis |
| NLP | difflib, regex extractors, rules engine; `bge-m3` embeddings via Ollama (sentence-transformers optional) |
| LLM | Anthropic SDK (`claude-opus-5-5`) or Ollama (`qwen3:4b-instruct-2507-q4_K_M`, `gemma4:26b-a4b-it-qat`) |
| Documents | pypdf, python-docx, ReportLab (PDF), openpyxl (XLSX) |
| Frontend | React 18, Vite, TypeScript, Tailwind, react-markdown (GFM, no raw HTML), Vitest |
| Quality | ruff, pytest (+ asyncio, hypothesis, coverage), CodeQL, GitHub Actions |

About 8,700 lines of Python in `src/` and 4,900 lines of TypeScript in `frontend/src/`.

## 2. Repository layout

```
src/
  api/routers/      HTTP layer: one router per feature, RBAC dependency on every route
  services/         orchestration: ingestion, nlp, impact, rag, retrieval, grounding, addendum, llm, ...
  repositories/     DB access
  ingestion/        CNBV + SEC scrapers
  nlp/              section splitter, comparator, extractor, classifier, regulation_id, trend extractor
  mapping/          rules engine, embedder, semantic + cross-jurisdiction mappers
  agents/           tool-use loop, read-only tools, research agent, drafting team
  models/           SQLAlchemy models
alembic/versions/   idempotent migrations on top of create_all
scripts/            seed_cnbv, reembed, run_analysis, map_impacts, ingest_source
evals/              model evals (cases, runner, stored runs)
frontend/           React app
tests/              unit tests; tests/integration/ hits a real Postgres
docs/               this documentation
```

## 3. Running it

```bash
pip install -e ".[dev]"
ollama pull bge-m3                                  # embeddings (and qwen/gemma for local LLMs)
cp .env.example .env
docker compose up -d                                # Postgres + Redis
alembic upgrade head
uvicorn src.api.main:app --reload --port 8000
cd frontend && npm install && npm run dev           # http://localhost:5173
```

For demo data, call `POST /api/v1/contracts/seed`, run `python scripts/seed_cnbv.py`, then
`POST /ingest/analyze` and `POST /ingest/map`. On Windows, `demo.ps1` does the whole launch.

The provider settings live in `.env`:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `ollama` for local models (no key needed) |
| `LLM_MODEL` | `claude-opus-5-5` | or an Ollama tag |
| `EMBEDDING_PROVIDER` | `ollama` | `sentence-transformers` (needs `[ml]`) or `none` |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `bge-m3` / `1024` | the dimension is the pgvector column size |

## 4. Testing

| Suite | Command | What it covers |
|---|---|---|
| Unit (249) | `python -m pytest` | Services, NLP, mapping, agents (scripted fake model), grounding, Ollama adapter, embedder, graders |
| Integration (18) | `DATABASE_URL=…_test python -m pytest -m integration` | Full HTTP pipeline against Postgres + pgvector, agent tools, migrations-sensitive paths |
| Frontend (10) | `cd frontend && npm test && npm run build` | SSE parser, Markdown rendering (no raw HTML), components; `tsc` type-check |
| Evals | `python -m evals.run --model ollama:<tag> [--embeddings on]` | Real models through the real endpoints, graded by code ([evals/README.md](../evals/README.md)) |

Testing rules:

- Integration tests and evals TRUNCATE every table, so the database name must end in `_test` or `_eval`.
- Tests force `EMBEDDING_PROVIDER=none` and the Anthropic provider with no key. A developer's running
  Ollama or `.env` must never change test results or spend tokens.
- Agents are tested with a scripted fake client. Each test asserts on the exact SSE event sequence,
  because that sequence is a contract with the UI.
- The eval graders have their own unit tests. Two grader bugs were caught that way: a `\b` written as a
  backspace character, and "12.0%" compared against "12%" as text.

## 5. Conventions that are easy to break

These are enforced by tests or by review. The full list is in [CLAUDE.md](../CLAUDE.md).

- **Every route has a role.** `test_all_routes_require_role` fails otherwise.
- **Static routes are declared before `/{param}` routes** in each router.
- **Background work goes through `run_with_session`.** It commits, rolls back and logs.
- **Never block the event loop.** Embeddings, difflib, and PDF/DOCX parsing run in `asyncio.to_thread`.
- **Use `selectinload` for any relationship you will touch.** Async sessions cannot lazy-load.
- **Escape all dynamic text** passed to ReportLab, which parses XML.
- **SSE event shapes are a UI contract.** Each stream ends with exactly one `done` or `error`; `reset`
  discards streamed text.
- **Agent tools only `SELECT`.** Their inputs are validated by pydantic with `extra="forbid"`, and tool
  errors go back to the model as `is_error` results.
- **Embeddings go through `embedder.available()`**, and every caller must work without them.
  Vectors are sent to SQL with `vector_literal()`, never `str()`.
- **Similarity thresholds are measured.** Re-calibrate them on the eval corpus whenever the embedder
  changes.

## 6. CI

| Workflow | Runs |
|---|---|
| `ci.yml` | ruff; unit tests with coverage; integration tests on a `pgvector/pgvector:pg16` service (schema plus `alembic upgrade head`); frontend tests and build |
| `codeql.yml` | CodeQL for Python and TypeScript |
| `docker.yml` | Image build, an import smoke test, and `docker compose config` validation |
| `claude.yml` | Claude Code when someone mentions `@claude` (needs an `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` secret) |

## 7. Engineering decisions

The original design record is [planning/Decisions.md](../planning/Decisions.md). The entries below
cover the hardening, multi-agent and local-model work that came after it.

| ID | Decision | Status |
|---|---|---|
| ED-01 | Diff baseline = same regulation, matched by circular number | Accepted |
| ED-02 | Agents run a self-hosted tool loop over read-only DB tools | Accepted |
| ED-03 | Drafting team orchestrated by code, reviewer returns a JSON schema | Accepted |
| ED-04 | One client interface over Claude and Ollama; two-phase tools + schema on Ollama | Accepted |
| ED-05 | Citations are validated; the refusal is written by code | Accepted |
| ED-06 | The drafter's brief carries the contract clauses, loaded by code | Accepted |
| ED-07 | bge-m3 via Ollama replaces all-MiniLM-L6-v2; hybrid RRF retrieval | Accepted |
| ED-08 | Embedding dimension is configuration, guarded at startup | Accepted |
| ED-09 | Vectors are serialised with `vector_literal()` | Accepted |
| ED-10 | Evals are code-graded and recorded with commit and retrieval mode | Accepted |

### ED-01: Diff baseline = same regulation, matched by circular number

**Context.** `_find_previous_text` diffed each circular against the previous circular from the same
*source*. Circular 15/2025 (AML) was diffed against Circular 12/2025 (SOFOM limits). That produced
false "section removed (possible repeal)" alerts and mixed the two texts, and it confused both local
models in the evals.

**Decision.** `src/nlp/regulation_id.py` derives a key from the title, such as `circular:12/2025` or
`circular-unica:bancos`. A document is diffed only against the latest earlier document with the same
source and key. A title without a key gets no baseline.

**Consequences.** False repeals are gone, and the eval corpus went from 10 alerts to 8. A real
amendment whose title does not cite the circular number is analysed as all-new; that is safe, but noisier.

### ED-02: Agents run a self-hosted tool loop over read-only DB tools

**Context.** Multi-step questions, such as circular → alert → contract clause → SEC equivalent, need
several lookups.

**Decision.** `agents/loop.run_agent` streams text, runs tool calls in sequence, feeds results back
and stops on end_turn, refusal, max_tokens or the turn limit. Tool inputs are pydantic models; results
are truncated to 12,000 characters. Seven tools, all `SELECT`.

**Consequences.** Agents can never change data. Hosting the loop ourselves keeps database access inside
the API process.

### ED-03: Drafting team orchestrated by code, reviewer returns a JSON schema

**Decision.** The fan-out (one drafter per contract, concurrency 3) and the review loop (up to 2
revisions on blocker or major issues) are plain asyncio code. The reviewer's output is constrained by a
JSON schema.

**Consequences.** It is predictable and cheap: an LLM orchestrator would add latency and cost without
making any real decision. Drafts with open issues are flagged, never hidden.

### ED-04: One client interface over Claude and Ollama; two-phase tools + schema on Ollama

**Context.** Local models (qwen, gemma) were already in use in a sibling project. qwen returned nothing
when a request carried both `tools` and a JSON `format`.

**Decision.** `AsyncOllama` mirrors `messages.stream` and `messages.create`. Such a turn runs in two
phases: first with tools only, then, if the model called no tool, again with the schema only. Usage is
summed across both phases.

**Consequences.** All four LLM features run on either provider without changes, and the reviewer works
on qwen.

### ED-05: Citations are validated; the refusal is written by code

**Context.** This lesson comes from Legal_AI_Assistant, ADR-007. A model told to "say you don't know"
explains itself and answers anyway, and small models cite tags they never saw (`[CON-7]`).

**Decision.** `services/grounding.validate()` is a pure function. A valid answer cites at least one tag,
every tag is among the shown sources, and there are no example markers. When nothing is retrieved, the
model is not called. A failing answer gets one regeneration with feedback written by code; after that,
the fixed refusal in the language of the question is returned.

**Consequences.** No invalid citation reached a user in any later eval run. The validator checks
provenance, not faithfulness: a valid tag on a wrong paraphrase still passes.

### ED-06: The drafter's brief carries the contract clauses, loaded by code

**Context.** gemma's drafter made 0 tool calls and invented "Clause [X]". Only 1/9 (qwen) and 2/9
(gemma) of the single-call drafts named a clause that exists.

**Decision.** `fetch_context` loads every clause of each contract (8,000-character budget) and up to
3,000 characters of the regulation text into the brief. Tools become optional.

**Consequences.** Real clause references rose to 9/9 for both models.

### ED-07: bge-m3 via Ollama replaces all-MiniLM-L6-v2; hybrid RRF retrieval

**Context.** The circulars are in Spanish and the questions are often in English. MiniLM is
English-only, and keyword search cannot cross languages: both models refused 2/5 answerable questions
for lack of context.

**Decision.** Embeddings default to `bge-m3` through Ollama: multilingual, 8,192-token window, no torch.
Retrieval fuses a semantic arm and a keyword arm with RRF (k=60, rank-only, ties broken by id).
The similarity floors were calibrated: 0.52 for changes, 0.55 for clauses, and 0.60/0.70 for the
clause mapper.

**Consequences.** RAG went from 5/7 to 7/7 for both models. Answers are slower, because the embedder
and the LLM share an 8 GB GPU. The cross-jurisdiction floor (0.60) is not re-measured yet, since the
eval corpus has no SEC data. The Docker image dropped torch.

### ED-08: Embedding dimension is configuration, guarded at startup

**Decision.** `EMBEDDING_DIM` sizes the pgvector columns. Migration 004 resizes them, emptying the old
vectors rather than truncating or padding them, and `scripts/reembed.py` refills them.
`embedder.check_schema()` disables embeddings when a column does not match.

**Consequences.** Switching models is a migration plus a batch job. A stale database degrades to
keyword search instead of failing inserts. This path was verified on a 384-dimension database.

### ED-09: Vectors are serialised with `vector_literal()`

**Context.** Found while launching the demo. pgvector hands ORM vectors back as numpy arrays, and
`str()` elides arrays longer than 1,000 items (`[a b ... z]`). With 1024 dimensions the cross-mapping
query failed to parse; at 384 dimensions it had always worked.

**Decision.** Every query builds the literal with `embedder.vector_literal()`. A regression test covers
a 1024-dimension numpy vector.

### ED-10: Evals are code-graded and recorded with commit and retrieval mode

**Decision.** `evals/run.py` drives the real endpoints over `httpx.ASGITransport` and grades with code,
with no LLM judge. Each report stores the commit, the dirty flag, the retrieval mode and every answer.
`--regrade` re-scores stored outputs without calling any model.

**Consequences.** Comparisons can be reproduced and tied to code. With 9 cases, a difference of one case
is noise.
