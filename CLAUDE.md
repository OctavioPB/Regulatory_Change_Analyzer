# CLAUDE.md

Regulatory Change Analyzer: ingests CNBV/SEC publications, detects changes (NLP diff + rules),
maps them to internal contracts, and drafts addenda / answers questions with Claude.
Backend: FastAPI + async SQLAlchemy + PostgreSQL/pgvector (`src/`). Frontend: React + Vite + Tailwind (`frontend/`).

## Commands

```bash
pip install -e ".[dev]"                # add ,ml for embeddings (torch + sentence-transformers, ~2 GB)
python -m pytest                       # unit tests (default excludes integration)
python -m pytest -m integration        # needs DATABASE_URL=...regulatory_test (name must end in _test)
ruff check src tests scripts alembic evals   # lint (CI enforces)
cd frontend && npm test && npm run build
docker compose up -d                   # Postgres + Redis only; add --profile app for api + worker
```

Integration tests TRUNCATE every table — never point them at a dev or prod database.

## Layout

- `src/api/routers/` HTTP layer → `src/services/` orchestration → `src/repositories/` DB access
- `src/nlp/` section diff + change classification; `src/mapping/` rules engine, embeddings, cross-jurisdiction
- `src/services/llm.py` shared `AsyncAnthropic` client; model from `settings.llm_model`
- `src/agents/` tool-use agents: `loop.run_agent` (generic loop), `tools.py` (read-only DB tools behind
  `AgentContext`, whose lock serialises the shared session for parallel subagents), `research_agent`, `addendum_team`
- ML is an optional extra: only `src/mapping/embedder.py` imports sentence-transformers. Every caller must keep working when it is missing (rules-only mapping, keyword RAG); tests and CI run without it
- Schema is created by `init_db()` (create_all); `alembic/versions/` adds indexes/tables idempotently on top

## Conventions (non-obvious, keep them)

- **RBAC on every route** except `/health`: `dependencies=[RequireViewer|RequireAnalyst|RequireComplianceOfficer]`.
  `tests/test_regressions.py::test_all_routes_require_role` fails otherwise. Anything that spends LLM tokens or writes data needs analyst+; exports need compliance_officer.
- **Static routes before `/{param}` routes** in a router, or FastAPI captures them (`/ingest/analyze` vs `/ingest/{source}`).
- **Background work** goes through `src/api/background.run_with_session(label, fn)` — it commits, rolls back and logs.
- **Never block the event loop**: embeddings, difflib analysis, PDF/DOCX parsing run via `asyncio.to_thread`; Claude calls use the async client.
- **Async sessions can't lazy-load**: use `selectinload(...)` for any relationship you will touch.
- **ReportLab `Paragraph` parses XML**: escape all dynamic text (`xml.sax.saxutils.escape`) or `&`/`<` crash the PDF.
- **SSE event shapes are a contract with the frontend** (`Chat.tsx`, `Addendum.tsx`): addendum `meta` uses `contract_name`; streams end with exactly one `done` or an `error`. Agent event shapes are documented in each `src/agents/*` module docstring.
- **Agent tools are read-only** (SELECT only) and validate input with a pydantic model (`extra="forbid"`); tool errors go back to Claude as `is_error` results, never raise. Agent endpoints need analyst+.
- **Datetimes are timezone-aware UTC** (`datetime.now(timezone.utc)`, `ingestion.base.parse_feed_date`); every column is timestamptz.
- `TrendSignal.key_themes` is a JSON string column — serialize through `TrendSignalOut.from_orm()`.
- Impact mapping produces zero alerts when the contracts table is empty — seed with `POST /api/v1/contracts/seed` in demos.
- Frontend brand colours (navy/gold) go through CSS variables in inline `style`, not dynamic Tailwind classes (JIT purges them).
