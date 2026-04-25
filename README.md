# Regulatory Change Analyzer

An automated compliance tool that monitors regulatory publications from **CNBV** (Mexico's National Banking and Securities Commission) and the **SEC** (U.S. Securities and Exchange Commission), detects what changed between versions, maps the impact to your internal contracts and processes, and generates actionable recommendations — with a review workflow and PDF/Excel export for audit purposes.

Built as a portfolio project demonstrating production-grade Python backend engineering: async FastAPI, SQLAlchemy 2.x, pgvector, NLP pipelines, RBAC, and a React dashboard styled with the **OPB brand system** (Fraunces + Plus Jakarta Sans, navy/gold palette).

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
2. **NLP pipeline** — splits regulatory text into sections, computes section-level diffs against the previous version, extracts dates/articles/percentages/penalties, classifies change types (new requirement, limit modification, repeal, deadline, etc.), and detects specific numeric changes (e.g. 20% → 15%).
3. **Impact mapping** — finds similar contract clauses using pgvector cosine similarity (sentence-transformers embeddings) and applies a keyword rules engine to flag contract types/areas by regulatory domain (SOFOM/credit, derivatives, AML/PLD, data privacy, fintech, capital requirements, investment funds).
4. **Recommendations** — generates templated, human-readable suggestions per impacted clause, scored by severity (High / Medium / Low).
5. **Human-in-the-loop** — compliance officers Approve, Modify, or Reject each suggestion through the dashboard. All decisions are immutably logged.
6. **Export** — one-click PDF and Excel reports per alert, with severity color-coding and reviewer notes, ready for audit.
7. **Task integration** — push impact items directly to Jira or Asana as tickets with severity-mapped priority.
8. **Multi-jurisdictional cross-mapping** — automatically detects when an SEC rule change has secondary compliance implications for CNBV (and vice versa), using two-stage validation: pgvector cosine similarity + shared regulatory domain filtering. Zero LLM API cost.

---

## Tech stack

| Layer | Technologies |
|-------|-------------|
| API | FastAPI, Pydantic v2, uvicorn |
| Auth | API key RBAC (viewer / analyst / compliance_officer / admin) |
| Database | PostgreSQL 16 + pgvector (cosine similarity search) |
| ORM | SQLAlchemy 2.x async, Alembic migrations |
| NLP | difflib (section comparison), regex patterns (entity extraction), sentence-transformers `all-MiniLM-L6-v2` (embeddings) |
| Scraping | httpx, feedparser, BeautifulSoup4, pypdf, python-docx |
| Task queue | Celery + Redis (scheduled scraping) |
| Task integration | Jira REST API v3, Asana REST API |
| Export | reportlab (PDF), openpyxl (Excel) |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Testing | pytest, pytest-asyncio, hypothesis, 169 tests |
| Infrastructure | Docker, docker compose (PostgreSQL + pgvector, Redis) |

---

## Project structure

```
├── src/
│   ├── api/                    # FastAPI app and routers
│   │   ├── middleware/         # rate_limit (sliding window on ingest endpoints)
│   │   └── routers/            # alerts, audit, contracts, cross_mapping,
│   │                           # dashboard, documents, export, health,
│   │                           # ingestion, tasks
│   ├── ingestion/              # CNBV and SEC scrapers
│   ├── integrations/           # task manager adapters (Jira, Asana)
│   ├── mapping/                # embedder, semantic_mapper, rules_engine,
│   │                           # cross_mapper
│   ├── models/                 # SQLAlchemy ORM models (incl. cross_mapping)
│   ├── nlp/                    # section_splitter, comparator, extractor,
│   │                           # classifier, pipeline
│   ├── parsing/                # PDF and DOCX text extractors
│   ├── recommendations/        # suggestion template engine
│   ├── repositories/           # DB access (audit, contract, cross_mapping,
│   │                           # document, impact)
│   ├── services/               # ingestion, nlp, impact, export,
│   │                           # cross_mapping, task services
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
│   └── map_impacts.py          # map changes to contract impacts
├── tests/                      # 169 tests (unit + integration)
├── alembic/                    # DB migrations
│   └── versions/
│       ├── 001_performance_indexes.py    # B-tree + HNSW vector indexes
│       └── 002_cross_jurisdiction_links.py
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

pip install -e ".[dev]"
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
DATABASE_URL=postgresql+asyncpg://rca_user:rca_pass@localhost:5432/regulatory_db
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...          # optional — reserved for future LLM features
EMBEDDING_MODEL=all-MiniLM-L6-v2
LOG_LEVEL=INFO

# RBAC — comma-separated key:role pairs. Leave as "{}" to disable auth (dev mode).
API_KEYS={"your-key-here":"compliance_officer"}

# Rate limiting — max POST requests to /ingest/* per minute per IP
INGEST_RATE_LIMIT=10

# Task integration (optional)
TASK_MANAGER=none    # jira | asana | none
JIRA_URL=https://yourorg.atlassian.net
JIRA_USER=you@example.com
JIRA_TOKEN=...
JIRA_PROJECT_KEY=COMP
# ASANA_TOKEN=...
# ASANA_PROJECT_GID=...
```

### 3. Start infrastructure

```bash
docker compose up -d
```

This starts:
- PostgreSQL 16 with the `pgvector` extension on port **5432**
- Redis 7 on port **6379**

### 4. Initialize the database schema

```bash
python -c "import asyncio; from src.database import init_db; asyncio.run(init_db())"
```

This creates all tables (including `cross_jurisdiction_links`) and enables the `pgvector` extension.

### 5. Run database migrations

```bash
alembic upgrade head
```

This applies performance indexes (B-tree on FK columns, HNSW vector index on clause embeddings).

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
celery -A src.worker worker --loglevel=info

# Start the beat scheduler (runs ingestion daily)
celery -A src.worker beat --loglevel=info
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
```

Current status: **169 tests passing**.

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

**Why positional matching for numeric changes?**
When "20% … 30%" appears in a 60-character sentence, both percentages share the same 80-character context window, making context-based matching ambiguous. Positional zip (`N`-th percentage in old ↔ `N`-th in new) is simpler and correct for amended provisions where sentence structure stays the same.

**Why `_SIMILARITY_THRESHOLD = 0.02` instead of 0.30?**
A single word change ("20%" → "15%") in a 40-character section produces a change ratio of ≈ 0.05. In compliance, every change matters — a higher threshold silently dropped real regulatory changes.

**Why sentence-transformers instead of Legal-BERT?**
`all-MiniLM-L6-v2` is already used in the OPB AI Mastery Lab stack (ChromaDB), produces 384-dim embeddings compatible with pgvector, runs on CPU for this use case, and doesn't require fine-tuning for Spanish/English financial text at this scale.

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
- [ ] Automated addendum drafting via Claude API
- [ ] Predictive alerts from proposed rules
- [ ] "Chat with Policy" — RAG interface for compliance officers
- [ ] Multilingual support (Portuguese, French for ESMA)

---

## License

MIT — free for personal and commercial use.

---

*Built by Octavio Pérez Bravo · OPB AI Mastery Lab*
