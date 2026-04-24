# Regulatory Change Analyzer

An automated compliance tool that monitors regulatory publications from **CNBV** (Mexico's National Banking and Securities Commission) and the **SEC** (U.S. Securities and Exchange Commission), detects what changed between versions, maps the impact to your internal contracts and processes, and generates actionable recommendations — with a review workflow and PDF/Excel export for audit purposes.

Built as a portfolio project demonstrating production-grade Python backend engineering: async FastAPI, SQLAlchemy 2.x, pgvector, NLP pipelines, and a React dashboard.

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
```

1. **Ingestion** — fetches CNBV circulars (via DOF RSS) and SEC press releases (via SEC RSS), extracts text from PDFs and HTML pages, and stores them in PostgreSQL.
2. **NLP pipeline** — splits regulatory text into sections, computes section-level diffs against the previous version, extracts dates/articles/percentages/penalties, classifies change types (new requirement, limit modification, repeal, deadline, etc.), and detects specific numeric changes (e.g. 20% → 15%).
3. **Impact mapping** — finds similar contract clauses using pgvector cosine similarity (sentence-transformers embeddings) and applies a keyword rules engine to flag contract types/areas by regulatory domain (SOFOM/credit, derivatives, AML/PLD, data privacy, fintech, capital requirements, investment funds).
4. **Recommendations** — generates templated, human-readable suggestions per impacted clause, scored by severity (High / Medium / Low).
5. **Human-in-the-loop** — compliance officers Approve, Modify, or Reject each suggestion through the dashboard. All decisions are immutably logged.
6. **Export** — one-click PDF and Excel reports per alert, with severity color-coding and reviewer notes, ready for audit.

---

## Tech stack

| Layer | Technologies |
|-------|-------------|
| API | FastAPI, Pydantic v2, uvicorn |
| Database | PostgreSQL 16 + pgvector (cosine similarity search) |
| ORM | SQLAlchemy 2.x async, Alembic migrations |
| NLP | difflib (section comparison), regex patterns (entity extraction), sentence-transformers `all-MiniLM-L6-v2` (embeddings) |
| Scraping | httpx, feedparser, BeautifulSoup4, pypdf, python-docx |
| Task queue | Celery + Redis (scheduled scraping) |
| Export | reportlab (PDF), openpyxl (Excel) |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Testing | pytest, pytest-asyncio, hypothesis, 118 tests |
| Infrastructure | Docker, docker-compose (PostgreSQL + pgvector, Redis) |

---

## Project structure

```
├── src/
│   ├── api/                    # FastAPI app and routers
│   │   └── routers/            # alerts, audit, contracts, dashboard,
│   │                           # documents, export, health, ingestion
│   ├── ingestion/              # CNBV and SEC scrapers
│   ├── mapping/                # embedder, semantic_mapper, rules_engine
│   ├── models/                 # SQLAlchemy ORM models
│   ├── nlp/                    # section_splitter, comparator, extractor,
│   │                           # classifier, pipeline
│   ├── parsing/                # PDF and DOCX text extractors
│   ├── recommendations/        # suggestion template engine
│   ├── repositories/           # DB access (audit, contract, document, impact)
│   ├── services/               # ingestion, nlp, impact, export services
│   └── storage/                # local file storage (raw + processed)
├── frontend/                   # React dashboard (Vite + Tailwind)
│   └── src/
│       ├── pages/              # Dashboard, Alerts, Reviews, Documents, AuditLog
│       └── components/         # AlertDrawer, AlertsTable, StatsCard, badges
├── scripts/                    # CLI runners
│   ├── ingest_source.py        # scrape one or all sources
│   ├── run_analysis.py         # run NLP pipeline on pending documents
│   └── map_impacts.py          # map changes to contract impacts
├── tests/                      # 118 tests (unit + integration)
├── alembic/                    # DB migrations
├── docker-compose.yml
└── pyproject.toml
```

---

## Requirements

- Python 3.11+
- Docker and docker-compose (for PostgreSQL + Redis)
- Node.js 18+ (for the React frontend)

---

## Installation

### 1. Clone and create environment

```bash
git clone https://github.com/yourusername/regulatory-change-analyzer.git
cd regulatory-change-analyzer

python -m venv .venv
# Windows
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
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/regulatory_db
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...          # optional — reserved for future LLM features
EMBEDDING_MODEL=all-MiniLM-L6-v2
LOG_LEVEL=INFO
```

### 3. Start infrastructure

```bash
docker-compose up -d
```

This starts:
- PostgreSQL 16 with the `pgvector` extension on port **5432**
- Redis 7 on port **6379**

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the API server

```bash
uvicorn src.api.main:app --reload --port 8000
```

The interactive API docs are at `http://localhost:8000/docs`.

### 6. Start the frontend

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

Or trigger via the API:

```bash
curl -X POST http://localhost:8000/api/v1/ingest/cnbv
```

### Run the NLP analysis pipeline

```bash
# Analyze all documents not yet processed
python scripts/run_analysis.py

# Analyze a specific document
python scripts/run_analysis.py --document-id <uuid>
```

### Map regulatory changes to contracts

Upload your contracts first through the dashboard (`/contracts` → Upload) or via the API:

```bash
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -F "file=@contract.pdf" \
  -F "name=Master Loan Agreement" \
  -F "contract_type=loan" \
  -F "area=Risk"
```

Then run impact mapping:

```bash
# Map all analyzed documents with no alerts yet
python scripts/map_impacts.py

# Map a specific document
python scripts/map_impacts.py --document-id <uuid>

# Map a specific change
python scripts/map_impacts.py --change-id <uuid>
```

### Review and export

Open the dashboard at `http://localhost:5173`:

| Page | Purpose |
|------|---------|
| **Dashboard** | Stats overview: documents, changes, unread alerts, pending reviews |
| **Alerts** | Feed of all impact alerts, click to open detail drawer with suggestions |
| **Reviews** | All pending items in one place — Approve / Modify / Reject with notes |
| **Documents** | Browse ingested documents, view detected changes, trigger re-analysis |
| **Audit Trail** | Immutable log of every system action and reviewer decision |

Export from any alert drawer (Excel or PDF), or download all alerts as a workbook:

```bash
curl http://localhost:8000/api/v1/export/alerts.xlsx -o report.xlsx
curl http://localhost:8000/api/v1/export/alerts/<alert-id>.pdf -o alert.pdf
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

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/dashboard/stats` | Aggregate counts for the dashboard |
| `GET` | `/api/v1/documents/` | List regulatory documents |
| `GET` | `/api/v1/documents/{id}/changes` | Changes detected in a document |
| `POST` | `/api/v1/documents/{id}/analyze` | Trigger NLP analysis (async) |
| `GET` | `/api/v1/alerts/` | List impact alerts (`?unread_only=true`) |
| `GET` | `/api/v1/alerts/{id}` | Get alert detail (marks as read) |
| `POST` | `/api/v1/alerts/{id}/items/{item_id}/review` | Submit a review decision |
| `GET` | `/api/v1/contracts/` | List uploaded contracts |
| `POST` | `/api/v1/contracts/upload` | Upload a PDF or DOCX contract |
| `POST` | `/api/v1/ingest/{source}` | Trigger scraping (`cnbv` or `sec`) |
| `GET` | `/api/v1/export/alerts/{id}.xlsx` | Download single alert as Excel |
| `GET` | `/api/v1/export/alerts/{id}.pdf` | Download single alert as PDF |
| `GET` | `/api/v1/export/alerts.xlsx` | Download all alerts as Excel |
| `GET` | `/api/v1/audit/` | List audit log entries |

Full interactive docs: `http://localhost:8000/docs`

---

## Running tests

```bash
# Full suite
pytest tests/ -v

# Specific module
pytest tests/test_nlp_pipeline.py -v
pytest tests/test_export_service.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

Current status: **118 tests passing**.

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

---

## Roadmap

- [ ] Sprint 6 — Jira/Asana task creation, RBAC, performance tuning
- [ ] Automated addendum drafting via Claude API
- [ ] Multi-jurisdictional cross-mapping (SEC ↔ CNBV)
- [ ] Predictive alerts from proposed rules
- [ ] "Chat with Policy" — RAG interface for compliance officers
- [ ] Multilingual support (Portuguese, French for ESMA)

---

## License

MIT — free for personal and commercial use.

---

*Built by Octavio Pérez Bravo · OPB AI Mastery Lab*
