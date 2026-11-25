# Regulatory Change Analyzer

[![CI](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/ci.yml)
[![CodeQL](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/codeql.yml/badge.svg)](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/codeql.yml)
[![Docker](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/docker.yml/badge.svg)](https://github.com/OctavioPB/Regulatory_Change_Analyzer/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![React + Vite](https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=black)
![Claude](https://img.shields.io/badge/LLM-Claude-D97757?logo=anthropic&logoColor=white)
![Ollama](https://img.shields.io/badge/local-Ollama%20%C2%B7%20bge--m3-000000?logo=ollama&logoColor=white)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

An automated compliance tool that monitors regulatory publications from **CNBV** (Mexico's National Banking and Securities Commission) and the **SEC** (U.S. Securities and Exchange Commission), detects what changed between versions, maps the impact to your internal contracts and processes, and generates actionable recommendations — with a review workflow and PDF/Excel export for audit purposes.

This automated compliance tool solves the growing challenge of managing complex, cross-border regulatory shifts by replacing manual tracking with real-time, AI-driven monitoring. By instantly connecting updates from the CNBV and SEC to your specific internal contracts and workflows, the platform eliminates the risk of human error and prevents costly non-compliance penalties. It streamlines the entire audit trail through built-in review cycles and easy exports, allowing legal and operations teams to focus on strategy rather than hunting for changes. Ultimately, this project is a high-value investment in risk mitigation, ensuring the organization stays ahead of shifting laws while significantly reducing the man-hours required for regulatory oversight.

![Dashboard](docs/img/dashboard.png)

**Documentation:** [Architecture](docs/ARCHITECTURE.md) · [Engineering](docs/ENGINEERING.md) ·
[Applied AI](docs/APPLIED_AI.md) · [Business Value](docs/BUSINESS_VALUE.md) ·
[Knowledge Learned](docs/KNOWLEDGE_LEARNED.md) · [Screenshots](#screenshots) · [Evals](evals/README.md)

---

## What it does

```
[CNBV / SEC feeds] → Scrape → Parse → Store
                                         ↓
                              NLP: section diff + entity extraction
                                         ↓
                    Map to contracts (semantic similarity + keyword rules)
                                         ↓
                     ImpactAlert + suggestions per affected clause
                                         ↓
                 Compliance officer reviews → Approve / Modify / Reject
                                         ↓
                              Export to PDF or Excel
                                         ↓
                 Cross-mapping: detect SEC ↔ CNBV overlap automatically
```

1. **Ingestion** — fetches CNBV circulars (via DOF RSS, when available) and SEC press releases (via SEC RSS), extracts text from PDFs and HTML pages, and stores them in PostgreSQL.
2. **NLP pipeline** — splits regulatory text into sections, computes section-level diffs against the previous version of the same regulation (matched by circular number; documents without one are analysed on their own), extracts dates/articles/percentages/penalties, classifies change types (new requirement, limit modification, repeal, deadline, etc.), and detects specific numeric changes (e.g. 20% → 15%).
3. **Impact mapping** — finds similar contract clauses using pgvector cosine similarity (bge-m3 embeddings via Ollama) and applies a keyword rules engine to flag contract types/areas by regulatory domain (SOFOM/credit, derivatives, AML/PLD, data privacy, fintech, capital requirements, investment funds).
4. **Recommendations** — generates templated, human-readable suggestions per impacted clause, scored by severity (High / Medium / Low).
5. **Human-in-the-loop** — compliance officers Approve, Modify, or Reject each suggestion through the dashboard. All decisions are immutably logged.
6. **Export** — one-click PDF and Excel reports per alert, with severity color-coding and reviewer notes, ready for audit.
7. **Task integration** — push impact items directly to Jira or Asana as tickets with severity-mapped priority.
8. **Multi-jurisdictional cross-mapping** — automatically detects when an SEC rule change has secondary compliance implications for CNBV (and vice versa), using two-stage validation: pgvector cosine similarity + shared regulatory domain filtering. Zero LLM API cost.
9. **Policy chat (RAG)** — cited answers over regulations and contracts, with hybrid (semantic + keyword) retrieval and a citation validator; when an answer cannot be grounded, the system says so instead of guessing.
10. **Agents (Claude or local models)** — see [Agents](#agents) below: a research agent for multi-step questions and a multi-agent drafting team (drafter per contract + reviewer).

---

## Screenshots

| | |
|---|---|
| **Impact alerts** — one alert per changed article ![Impact alerts](docs/img/alerts.png) | **Review queue** — approve, modify or reject each suggestion ![Review queue](docs/img/reviews.png) |
| **Policy chat** — answers with validated `[REG-n]`/`[CON-n]` citations ![Policy chat](docs/img/chat-rag.png) | **Research agent** — visible tool steps, multi-hop answer ![Research agent](docs/img/chat-agent.png) |
| **Risk heatmap** — impacts by department and change type ![Risk heatmap](docs/img/heatmap.png) | **Drafting team** — drafter per contract + reviewer verdicts ![Drafting team](docs/img/addendum-team-progress.png) |

More (documents, trends, pipeline, audit trail, the drafted addendum, the system refusal) in the
[screenshot gallery](docs/README.md#screenshots). Captured from a demo database with local models
(gemma4 26B, qwen3 4B, bge-m3 via Ollama).

---

## Documentation

| Document | For | Covers |
|---|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Engineers, architects | Components, pipeline, data model, hybrid retrieval, grounding boundary, agents, providers, security, deployment |
| [Engineering](docs/ENGINEERING.md) | Contributors | Stack, layout, running and testing, conventions, CI, decision log ED-01 – ED-10 |
| [Applied AI](docs/APPLIED_AI.md) | AI/ML engineers, reviewers | Where AI is (and is not) used, calibrated thresholds, citation validation, agents, eval results |
| [Business Value](docs/BUSINESS_VALUE.md) | Compliance, risk, legal, sponsors | Problem, before/after, value drivers, safeguards, cost, limits |
| [Knowledge Learned](docs/KNOWLEDGE_LEARNED.md) | Maintainers | Lessons from building and evaluating, lessons from Legal_AI_Assistant, open findings |
| [Evals](evals/README.md) | Anyone comparing models | How the code-graded model evaluation works and how to run it |

The full business case is in [planning/Business.md](planning/Business.md) and the original design record in
[planning/Decisions.md](planning/Decisions.md).

---

## Agents

Two features use an LLM (Claude or a local model) with tools instead of a single prompt. Both run their
tool loop inside the API process ([src/agents/loop.py](src/agents/loop.py)), with **read-only** database tools
([src/agents/tools.py](src/agents/tools.py)): agents can look things up but never approve, edit or export.

| Feature | Endpoint | How it works |
|---------|----------|--------------|
| **Research agent** (Chat → *Agent mode*) | `POST /api/v1/agents/chat` | Claude decides what to look up and chains lookups — search regulations, open the full text, list alerts, open a contract, check the other jurisdiction — then answers citing `[REG-n]` / `[CON-n]`. Citations are validated (one correction turn, then a system-written refusal). The UI shows every step. Max 10 steps. |
| **Drafting team** (Addendum → *Multi-agent*) | `POST /api/v1/agents/addendum/{alert_id}` | An orchestrator fans out one **drafting subagent per contract** (3 in parallel, max 10 per alert). Each gets the full regulation text and every contract clause in its brief, loaded by code (small models skip optional lookups and invent clause numbers). A **reviewer agent** checks coverage, references, invented requirements and form, returning structured issues; blocker/major issues send the draft back to the same drafter, up to 2 revisions. Drafts that still have open issues are flagged, never hidden. |

Tools: `search_regulations`, `get_regulatory_change`, `find_cross_jurisdiction`, `search_contract_clauses`,
`get_contract`, `list_impact_alerts`, `get_impact_alert`.

| Research agent | Drafting team |
|---|---|
| ![Research agent](docs/img/chat-agent.png) | ![Drafting team](docs/img/addendum-team-progress.png) |

How the agents are built and what the evaluations found: [Applied AI §5–6](docs/APPLIED_AI.md#5-agents).

### Local models (Ollama)

Every LLM feature (RAG chat, addendum drafting, both agents) can run on a local model instead of Claude.
[src/services/ollama_client.py](src/services/ollama_client.py) exposes Ollama behind the same
`messages.stream` / `messages.create` surface the app already uses, translating tool calls and JSON-schema
output. Nothing leaves the machine and no API key is needed:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M      # or gemma4:26b-a4b-it-qat
# .env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b-instruct-2507-q4_K_M
OLLAMA_URL=http://localhost:11434
```

Model comparisons live in [evals/](evals/README.md) (`python -m evals.run --model ollama:<tag> ...`);
results are summarised in [Applied AI §6](docs/APPLIED_AI.md#6-evaluation).

Both endpoints need the **analyst** role and spend several model calls per request (the drafting team
reports its token usage when it finishes). With no LLM configured (no `ANTHROPIC_API_KEY` and
`LLM_PROVIDER=anthropic`) the research agent falls back to the classic RAG chat and the team returns template drafts, so demos and tests still work.

---

## Tech stack

| Layer | Technologies |
|-------|-------------|
| API | FastAPI, Pydantic v2, uvicorn |
| Auth | API key RBAC (viewer / analyst / compliance_officer / admin) |
| Database | PostgreSQL 16 + pgvector (cosine similarity search) |
| ORM | SQLAlchemy 2.x async, Alembic migrations |
| NLP | difflib (section comparison), regex patterns (entity extraction), `bge-m3` via Ollama (multilingual embeddings; sentence-transformers optional) |
| Scraping | httpx, feedparser, BeautifulSoup4, pypdf, python-docx |
| Task queue | Celery + Redis (scheduled scraping) |
| Task integration | Jira REST API v3, Asana REST API |
| Export | reportlab (PDF), openpyxl (Excel) |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Testing | pytest, pytest-asyncio, hypothesis, Vitest — 249 unit + 18 integration + 10 frontend tests |
| Infrastructure | Docker, docker compose (PostgreSQL + pgvector, Redis) |

---

## Project structure

```
├── src/
│   ├── api/                    # FastAPI app and routers
│   │   ├── middleware/         # rate_limit (sliding window on ingest endpoints)
│   │   └── routers/            # alerts, audit, contracts, cross_mapping,
│   │                           # dashboard, documents, export, health,
│   │                           # ingestion, tasks, chat, addendum, agents
│   ├── agents/                 # Claude tool-use loop, read-only DB tools,
│   │                           # research agent, drafting team
│   ├── ingestion/              # CNBV and SEC scrapers
│   ├── integrations/           # task manager adapters (Jira, Asana)
│   ├── mapping/                # embedder, semantic_mapper, rules_engine,
│   │                           # cross_mapper
│   ├── models/                 # SQLAlchemy ORM models (incl. cross_mapping)
│   ├── nlp/                    # section_splitter, comparator, extractor,
│   │                           # classifier, pipeline, regulation_id
│   ├── parsing/                # PDF and DOCX text extractors
│   ├── recommendations/        # suggestion template engine
│   ├── repositories/           # DB access (audit, contract, cross_mapping,
│   │                           # document, impact)
│   ├── services/               # ingestion, nlp, impact, export, cross_mapping,
│   │                           # task, rag, retrieval (hybrid), grounding,
│   │                           # addendum, llm + ollama_client
│   └── storage/                # local file storage (raw + processed)
├── frontend/                   # React dashboard (Vite + Tailwind + OPB brand)
│   └── src/
│       ├── pages/              # Dashboard, Alerts, Reviews, Documents,
│       │                       # AuditLog, Pipeline
│       └── components/         # AlertDrawer, AlertsTable, StatsCard, badges,
│                               # Navbar, Footer
├── scripts/                    # CLI runners
│   ├── ingest_source.py        # scrape one or all sources
│   ├── seed_cnbv.py            # insert synthetic CNBV docs (dev — DOF RSS offline)
│   ├── run_analysis.py         # run NLP pipeline on pending documents
│   ├── map_impacts.py          # map changes to contract impacts
│   └── reembed.py              # fill/refresh embeddings after a model change
├── evals/                      # model evals: cases, runner, stored runs
├── docs/                       # architecture, engineering, applied AI,
│                               # business value, knowledge learned, screenshots
├── tests/                      # 249 unit + 18 integration tests
├── alembic/                    # DB migrations
│   └── versions/
│       ├── 001_performance_indexes.py    # B-tree + HNSW vector indexes
│       ├── 002_cross_jurisdiction_links.py
│       ├── 003_trend_signals.py
│       └── 004_embedding_dimension.py    # resize vectors to EMBEDDING_DIM
├── docker-compose.yml
└── pyproject.toml
```

---

## Requirements

- Python 3.11+
- Docker (for PostgreSQL + Redis) — Docker Desktop v2+ uses `docker compose` (no hyphen)
- Node.js 18+ (for the React frontend)

---

## Installation

### 1. Clone and create environment

```bash
git clone https://github.com/yourusername/regulatory-change-analyzer.git
cd regulatory-change-analyzer

python -m venv .venv
# Windows (PowerShell — run once if needed: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser)
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Core app + test tooling (~250 MB)
pip install -e ".[dev]"

# Semantic features: bge-m3 through Ollama (multilingual es/en, 1024 dims, no torch)
ollama pull bge-m3
```

| Embeddings | Impact mapping | Chat / agent retrieval | Cross-jurisdiction |
|---|---|---|---|
| unavailable (`EMBEDDING_PROVIDER=none`, or Ollama down) | keyword rules engine (R001–R008) | keyword search | rules-only (shared domains) |
| `bge-m3` via Ollama (default) | rules **+** clause-level semantic similarity | **hybrid**: semantic + keyword, rank-fused (RRF) | embeddings + shared domains |

bge-m3 is multilingual, so an English question finds a Spanish circular; keyword search cannot.
`EMBEDDING_PROVIDER=sentence-transformers` (with `pip install -e ".[dev,ml]"`, `all-MiniLM-L6-v2`, `EMBEDDING_DIM=384`)
is the English-only alternative.

`GET /health` reports `"embeddings": "available"` or `"disabled"`. Rows embedded while embeddings were
unavailable keep a `NULL` vector: `python scripts/reembed.py` fills them. **Switching model or dimension**
(e.g. an existing 384-dim database): `alembic upgrade head` (resizes the columns, emptying old vectors),
then `python scripts/reembed.py`. Until then the startup check disables embeddings instead of failing inserts.

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:5432/regulatory_db
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...          # optional — reserved for future LLM features
EMBEDDING_PROVIDER=ollama              # bge-m3 via Ollama; none = keyword only
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
LOG_LEVEL=INFO

# RBAC — comma-separated key:role pairs. Leave as "{}" to disable auth (dev mode).
API_KEYS={"your-key-here":"compliance_officer"}

# Rate limiting — max POST requests to /ingest/* per minute per IP
INGEST_RATE_LIMIT=10

# Task integration (optional)
TASK_MANAGER=none    # jira | asana | none
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=COMP
# ASANA_ACCESS_TOKEN=...
# ASANA_PROJECT_GID=...
```

### 3. Start infrastructure

```bash
docker compose up -d
```

This starts:
- PostgreSQL 16 with the `pgvector` extension on port **5432**
- Redis 7 on port **6379**

To also run the API and the Celery worker (with the beat scheduler) in containers:
`docker compose --profile app up -d --build`.

### 4. Initialize the database schema

```bash
python -c "import asyncio; from src.database import init_db; asyncio.run(init_db())"
```

This creates all tables (including `cross_jurisdiction_links`) and enables the `pgvector` extension.

### 5. Run database migrations

```bash
alembic upgrade head
```

This applies performance indexes (B-tree on FK columns, HNSW vector index on clause embeddings) and resizes
the embedding columns to `EMBEDDING_DIM` if needed (then run `python scripts/reembed.py`).

### 6. Start the API server

```bash
uvicorn src.api.main:app --reload --port 8000
```

The interactive API docs are at `http://localhost:8000/docs`.

### 7. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:5173`.

---

## Usage

### Ingest regulatory documents

```bash
# Scrape all sources (CNBV + SEC)
python scripts/ingest_source.py --source all

# Scrape a single source
python scripts/ingest_source.py --source cnbv
python scripts/ingest_source.py --source sec
```

Or trigger via the API (requires `analyst` role or higher):

```bash
curl -X POST http://localhost:8000/api/v1/ingest/cnbv \
  -H "X-API-Key: your-key-here"
```

> **Note — DOF RSS (CNBV):** As of April 2026 the DOF restructured its website and the RSS feed at `/rss.php` returns 404. If the live feed is unavailable, seed realistic CNBV documents for development:
>
> ```bash
> python scripts/seed_cnbv.py
> ```
>
> This inserts three synthetic circulars (leverage limits, AML/PLD fintech, Basel III capital) directly into the database, covering the same regulatory domains as the SEC documents so the cross-mapper can find links between them. When the DOF restores its feed, update `DOF_RSS_URL` in `src/ingestion/cnbv.py`.

### Run the NLP analysis pipeline

```bash
# Analyze all documents not yet processed
python scripts/run_analysis.py

# Analyze a specific document
python scripts/run_analysis.py --document-id <uuid>
```

### Seed demo contracts (required for alerts to appear)

The impact mapper can only generate alerts if there are contracts in the database to match against. Seed six representative contracts (loan, investment, onboarding/AML, derivative, data processing, fintech service) in one step:

```bash
# Via the Pipeline page in the dashboard (Step 00 · Setup)
# or directly via the API:
curl -X POST http://localhost:8000/api/v1/contracts/seed \
  -H "X-API-Key: your-key-here"
```

This is **idempotent** — safe to run multiple times; existing contracts are skipped. Once seeded, you can add real contracts via upload:

```bash
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -H "X-API-Key: your-key-here" \
  -F "file=@contract.pdf" \
  -F "name=Master Loan Agreement" \
  -F "contract_type=loan" \
  -F "area=Risk"
```

### Map regulatory changes to contracts

Then run impact mapping:

```bash
# Map all analyzed documents with no alerts yet
python scripts/map_impacts.py

# Map a specific document
python scripts/map_impacts.py --document-id <uuid>

# Map a specific change
python scripts/map_impacts.py --change-id <uuid>
```

### Cross-jurisdictional scan

After ingesting changes from both CNBV and SEC, trigger the cross-mapping engine:

```bash
# Scan a single change for SEC ↔ CNBV overlap
curl -X POST http://localhost:8000/api/v1/cross-mapping/scan/<change-id> \
  -H "X-API-Key: your-key-here"

# Scan all changes in bulk (runs in background)
curl -X POST http://localhost:8000/api/v1/cross-mapping/scan-all \
  -H "X-API-Key: your-key-here"

# View cross-links
curl "http://localhost:8000/api/v1/cross-mapping/?source_jurisdiction=SEC&target_jurisdiction=CNBV" \
  -H "X-API-Key: your-key-here"
```

### Push impact items to Jira / Asana

```bash
curl -X POST http://localhost:8000/api/v1/tasks/push/<alert-id> \
  -H "X-API-Key: your-key-here"
```

Each high/medium/low impact item becomes a separate ticket with severity-mapped priority.

### Review and export

Open the dashboard at `http://localhost:5173`:

| Page | Purpose |
|------|---------|
| **Dashboard** | Stats overview: documents, changes, unread alerts, pending reviews; navy-gradient severity chart |
| **Alerts** | Paginated feed of all impact alerts, click to open detail drawer with suggestions |
| **Reviews** | All pending items in one place — Approve / Modify / Reject with notes |
| **Documents** | Browse ingested documents, view detected changes, trigger re-analysis |
| **Audit Trail** | Immutable log of every system action and reviewer decision |
| **Pipeline** | Run the full data pipeline from the browser — Step 00 (seed contracts) → Step 01 (fetch) → Step 02 (analyze) → Step 03 (map impacts) — with a live activity log panel |

The Pipeline page is the fastest way to go from zero data to populated alerts in a new environment.

Export from any alert drawer (Excel or PDF), or download all alerts as a workbook:

```bash
curl http://localhost:8000/api/v1/export/alerts.xlsx -o report.xlsx
curl "http://localhost:8000/api/v1/export/alerts/<alert-id>.pdf" -o alert.pdf
```

### Scheduled ingestion (Celery)

```bash
# Start the Celery worker
celery -A src.worker.celery_app worker --loglevel=info

# Start the beat scheduler (runs ingestion daily)
celery -A src.worker.celery_app beat --loglevel=info
```

---

## API reference

### Core

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/health` | — | Health check (includes DB ping) |
| `GET` | `/api/v1/dashboard/stats` | viewer | Aggregate counts for the dashboard |

### Documents

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/documents/` | viewer | List regulatory documents (`?page=1&page_size=20`) |
| `GET` | `/api/v1/documents/{id}/changes` | viewer | Changes detected in a document |
| `POST` | `/api/v1/documents/{id}/analyze` | analyst | Trigger NLP analysis (async) |

### Alerts

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/alerts/` | viewer | List impact alerts (`?unread_only=true&page=1&page_size=20`) |
| `GET` | `/api/v1/alerts/{id}` | viewer | Get alert detail (marks as read) |
| `POST` | `/api/v1/alerts/{id}/items/{item_id}/review` | compliance_officer | Submit Approve / Modify / Reject |

### Contracts

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/contracts/` | viewer | List uploaded contracts |
| `POST` | `/api/v1/contracts/upload` | analyst | Upload a PDF or DOCX contract |
| `POST` | `/api/v1/contracts/seed` | — | Seed six demo contracts (idempotent). Required once for alerts to generate. |

### Ingestion & Pipeline

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/v1/ingest/` | analyst | Trigger scraping for all sources (async, 202) |
| `POST` | `/api/v1/ingest/{source}` | analyst | Trigger scraping for `cnbv` or `sec` (async, 202). Rate-limited: 10 req/min. |
| `POST` | `/api/v1/ingest/analyze` | analyst | Run NLP on all documents pending analysis (async, 202) |
| `POST` | `/api/v1/ingest/map` | analyst | Map all unprocessed changes to contracts, generate alerts (async, 202) |

> **Route ordering note:** `/analyze` and `/map` are registered before the `/{source}` wildcard so FastAPI matches them correctly. If you add new static pipeline routes, keep them above `/{source}` in `ingestion.py`.

### Export

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/export/alerts/{id}.xlsx` | viewer | Download single alert as Excel |
| `GET` | `/api/v1/export/alerts/{id}.pdf` | viewer | Download single alert as PDF |
| `GET` | `/api/v1/export/alerts.xlsx` | viewer | Download all alerts as Excel |

### Cross-mapping

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/cross-mapping/` | viewer | List cross-jurisdiction links (`?source_jurisdiction=SEC&target_jurisdiction=CNBV&page=1`) |
| `GET` | `/api/v1/cross-mapping/change/{change_id}` | viewer | Links for a specific change (as source or target) |
| `POST` | `/api/v1/cross-mapping/scan/{change_id}` | analyst | Scan one change (async, 202) |
| `POST` | `/api/v1/cross-mapping/scan-all` | compliance_officer | Bulk scan all unscanned changes (async, 202) |

### Task integration

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/v1/tasks/push/{alert_id}` | compliance_officer | Push impact items to Jira or Asana |
| `GET` | `/api/v1/tasks/config` | viewer | Show active task manager and project config |

### Audit

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `GET` | `/api/v1/audit/` | viewer | List audit log entries |

### Agents

| Method | Endpoint | Role required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/v1/agents/chat` | analyst | Research agent (SSE: `step`, `token`, `citations`, `done`/`error`) |
| `POST` | `/api/v1/agents/addendum/{alert_id}` | analyst | Drafting team (SSE: `plan`, `agent`, `review`, `draft`, `done`/`error`) |

Full interactive docs: `http://localhost:8000/docs`

**RBAC roles** (hierarchy): `viewer` < `analyst` < `compliance_officer` < `admin`. Pass `X-API-Key: <key>` header. Set `API_KEYS={}` in `.env` to disable auth (development mode).

---

## Running tests

```bash
# Full suite
pytest tests/ -v

# Specific module
pytest tests/test_nlp_pipeline.py -v
pytest tests/test_cross_mapping.py -v
pytest tests/test_rbac.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Integration tests: real Postgres + pgvector through the HTTP API.
# The DB name MUST end in _test — every test truncates all tables.
docker run -d --rm --name rca-it-db -e POSTGRES_USER=rca_user -e POSTGRES_PASSWORD=rca_pass \
  -e POSTGRES_DB=regulatory_test -p 55432:5432 pgvector/pgvector:pg16
DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:55432/regulatory_test \
  pytest -m integration

# Frontend
cd frontend && npm test && npm run build
```

Current status: **249 unit + 18 integration + 10 frontend tests passing**.

### Continuous integration (`.github/workflows/`)

| Workflow | Runs on | What it does |
|---|---|---|
| `ci.yml` | every push / PR | ruff lint, unit tests with coverage, integration tests against a pgvector service, frontend tests + production build |
| `docker.yml` | changes to Dockerfile / deps | builds the image, smoke-tests the import, validates compose |
| `codeql.yml` | push, PR, weekly | security analysis for Python and TypeScript |
| `claude.yml` | `@claude` in an issue / PR comment (owner & collaborators only) | Claude answers or pushes a fix |

The Claude workflow needs the [Claude GitHub App](https://github.com/apps/claude) installed and an `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`) repository secret; without it, it is skipped unless someone mentions `@claude`. Dependabot (`.github/dependabot.yml`) opens weekly grouped updates for pip and npm.

---

## Troubleshooting

**`python -m json.tool` says "Expecting value" when piping `curl` output on Windows**

PowerShell's `curl` is an alias for `Invoke-WebRequest`, not the real curl binary. Its output is a structured object, not raw text. Use instead:

```powershell
Invoke-WebRequest http://localhost:8000/api/v1/dashboard/stats | Select-Object -ExpandProperty Content
```

Or install the real curl (ships with Windows 10+, available in Git Bash and WSL) and call it explicitly.

**`Invoke-WebRequest -Method POST` returns "connection was closed unexpectedly"**

PowerShell's WinHTTP stack sometimes drops the connection on POST requests with no body against uvicorn. Use the CLI script instead — it bypasses HTTP entirely:

```bash
python scripts/ingest_source.py --source cnbv
```

**`alembic upgrade head` fails with "relation does not exist"**

Alembic migrations assume tables already exist (they only add indexes). Run `init_db()` first:

```bash
python -c "import asyncio; from src.database import init_db; asyncio.run(init_db())"
alembic upgrade head
```

**Docker Desktop not running — `docker compose up -d` fails**

Start Docker Desktop from the Start menu and wait for the whale icon in the taskbar to stop animating before retrying. On first launch this can take 30–60 seconds.

**PowerShell execution policy blocks `.venv\Scripts\activate`**

Run once per user profile:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**DOF RSS returns 404 (CNBV scraper gets zero documents)**

The DOF restructured its website. Use the development seed script:

```bash
python scripts/seed_cnbv.py
```

Update `DOF_RSS_URL` in `src/ingestion/cnbv.py` when the DOF restores the feed.

**Dashboard shows documents and changes but zero alerts**

The impact mapper requires contracts in the database to match against. An empty contracts table causes every change to be skipped silently. Run the seed endpoint once:

```bash
curl -X POST http://localhost:8000/api/v1/contracts/seed
# or: open /pipeline in the dashboard → Step 00 · Setup → "Seed demo contracts"
```

After seeding, re-run impact mapping (`POST /api/v1/ingest/map` or Pipeline Step 03) to generate alerts from any already-analyzed documents.

**`POST /api/v1/ingest/analyze` returns 400 "Unknown source 'analyze'"**

The `/{source}` wildcard route was matching before the static `/analyze` route. Fixed by registering `/`, `/analyze`, and `/map` before `/{source}` in `src/api/routers/ingestion.py`. If you see this error, ensure you are running the latest version of the file.

---

## Architecture decisions

The main ones are summarised here. The complete log (ED-01 – ED-10, with context and consequences) is in
[docs/ENGINEERING.md](docs/ENGINEERING.md#7-engineering-decisions), and the component view in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

**Why positional matching for numeric changes?**
When "20% … 30%" appears in a 60-character sentence, both percentages share the same 80-character context window, making context-based matching ambiguous. Positional zip (`N`-th percentage in old ↔ `N`-th in new) is simpler and correct for amended provisions where sentence structure stays the same.

**Why `_SIMILARITY_THRESHOLD = 0.02` instead of 0.30?**
A single word change ("20%" → "15%") in a 40-character section produces a change ratio of ≈ 0.05. In compliance, every change matters — a higher threshold silently dropped real regulatory changes.

**Why bge-m3 via Ollama instead of all-MiniLM-L6-v2?**
The circulars are in Spanish and questions often come in English; `all-MiniLM-L6-v2` is English-only, so those
questions retrieved nothing (evals, 2026-11-25). `bge-m3` is multilingual, has an 8192-token window, runs in the
Ollama runtime the local LLMs already use (no torch, ~2 GB less to install) and is the embedder of the sibling
Legal_AI_Assistant project. Similarity floors were re-calibrated for it on the eval corpus (see
`src/services/retrieval.py`, `src/mapping/semantic_mapper.py`); the cross-jurisdiction floor still needs a
CNBV+SEC corpus to be re-measured.

**Why validate citations and let code write the refusal?**
Lessons from Legal_AI_Assistant (ADR-007): a model asked to "say you don't know" explains and still answers,
and small models cite tags they never saw. So every chat/agent answer goes through a pure validator
([src/services/grounding.py](src/services/grounding.py)): each `[REG-n]`/`[CON-n]` must be a source the model
was shown, example markers are rejected, at least one citation is required. A failing answer is regenerated
once with feedback written by code; if it still fails, or nothing was retrieved (no model call at all), the
system returns a fixed refusal. The validator proves provenance, not faithfulness.

**Why two mapping paths (semantic + rules engine)?**
Semantic similarity catches clauses that are conceptually related but don't share keywords (e.g. "exposure limit" ≈ "límite de contraparte"). The keyword rules engine catches contracts by type/area even before they've been embedded — useful when a new contract type is uploaded without re-running the full pipeline.

**Why two-stage cross-mapping instead of similarity alone?**
Stage 1 (pgvector cosine, threshold 0.60) retrieves candidates efficiently. Stage 2 (shared regulatory domain R001–R008) rejects false positives where documents are superficially similar but cover different regulatory domains (e.g. both mention "effective date" but one is AML and the other is data privacy). The combination achieves precision without any LLM call — zero API cost for the cross-mapping feature.

**Why hybrid `init_db()` + Alembic instead of pure Alembic?**
`CREATE EXTENSION IF NOT EXISTS vector` requires superuser privileges and runs in a raw connection, not a migration transaction. `init_db()` handles extension creation and table schema; Alembic handles indexes and schema evolution. All migrations use `IF NOT EXISTS` raw SQL to be safe whether or not `init_db()` has already run.

**Why in-memory rate limiting instead of Redis-backed?**
The ingest endpoints are low-volume (manual triggers or beat tasks), not a high-concurrency SaaS endpoint. A sliding-window in-memory dict is sufficient and adds zero infrastructure dependency. Redis-backed limiting (e.g. via `slowapi`) is the right choice if multiple API workers run in parallel.

---

## Roadmap

- [x] Sprint 1 — Foundation & Ingestion Engine
- [x] Sprint 2 — NLP & Change Detection
- [x] Sprint 3 — Knowledge Base & Semantic Mapping
- [x] Sprint 4 — Recommendation Engine & UI Core
- [x] Sprint 5 — Human-in-the-Loop & Export
- [x] Sprint 6 — Task integration (Jira/Asana), RBAC, pagination, performance indexes, rate limiting
- [x] Multi-jurisdictional cross-mapping (SEC ↔ CNBV), zero LLM cost
- [x] OPB brand system applied to dashboard (Fraunces / Plus Jakarta Sans, navy/gold, Pipeline page with live activity log)
- [x] Automated addendum drafting (single call, or multi-agent draft + review)
- [x] Predictive trend signals from proposed rules and no-action letters
- [x] Risk heatmap by department
- [x] "Chat with Policy" — RAG with validated citations, plus a research agent
- [x] Local models via Ollama (qwen, gemma) and multilingual embeddings (bge-m3)
- [x] Code-graded model evaluation ([evals/](evals/README.md))
- [ ] Lawyer-reviewed evaluation cases on real circulars and contracts
- [ ] Evaluate Claude against the local models; choose the model per feature on evidence
- [ ] Re-measure the cross-jurisdiction threshold with a CNBV + SEC corpus; top-5 vs top-8 retrieval
- [ ] CLM integration (DocuSign CLM, Icertis, Sirion)
- [ ] More sources (CONDUSEF, Banxico) and languages (Portuguese, French for ESMA)

Open findings with their evidence: [Knowledge Learned §7](docs/KNOWLEDGE_LEARNED.md#7-open-findings).

---

## License

[MIT](LICENSE) © 2026 Octavio Pérez Bravo — free for personal and commercial use.

---

*Built by Octavio Pérez Bravo · OPB AI Mastery Lab*
