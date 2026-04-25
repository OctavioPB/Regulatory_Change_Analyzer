# Project: Regulatory Change Analyzer

## 1. Overview

The **Regulatory Change Analyzer** is an automated tool designed to monitor, interpret, and assess the impact of new legal provisions (laws, circulars, regulations) issued by bodies such as **CNBV** (Mexico’s National Banking and Securities Commission) or **SEC** (U.S. Securities and Exchange Commission), among others. Its purpose is to analyze how these changes affect existing contracts, internal business processes, and an organization’s compliance framework, generating concrete recommendations for adjusting documentation and workflows.

## 2. Objectives

- **Continuous monitoring**: Scan official sources (gazettes, bulletins, regulatory APIs) for new provisions.
- **Extract relevant changes**: Identify modified sections, new articles, requirements, or deadlines.
- **Impact mapping**: Relate changes to standard contracts, specific clauses, and predefined internal processes.
- **Suggest adjustments**: Generate textual recommendations to modify contracts, update policies, or adapt procedures.
- **History and traceability**: Maintain a record of analyzed changes and suggested actions for audits.

## 3. Scope

### Initial regulatory sources
- **CNBV**: Circulars, multi‑banking rules, investment funds, fintech.
- **SEC**: Final rules, proposed rules, no‑action letters.
- Extensible to other bodies (EUROPE, ESMA, CONDUSEF, etc.)

### Types of documents analyzed
- Contracts (loans, derivatives, fiduciary, service provision).
- Internal policies (AML, compliance, data protection, corporate governance).
- Operational processes (client onboarding, regulatory reporting, risk management).

### Deliverables per detected change
- Summary of the regulatory change.
- List of affected clauses/processes (with severity: high, medium, low).
- Suggested text for modifying contracts or policies.
- Optional flowchart of the adjusted process.

## 4. Workflow

1. **Source ingestion**  
   - Web scraping of official gazettes, RSS feeds from regulators, API integration (e.g., SEC EDGAR).  
   - Scheduled daily/weekly.

2. **Natural language processing (NLP)**  
   - Entity extraction (dates, obligations, prohibitions, penalties).  
   - Comparison with previous version of the regulatory text (difference detection).  
   - Classification of the change (new requirement, limit modification, repeal, etc.).

3. **Semantic mapping**  
   - Custom knowledge base: relationships between regulatory terms and contract clauses / process steps.  
   - Matching using embeddings and heuristic rules.  
   - Example: if a CNBV circular mentions “leverage limit for SOFOMs”, the system flags relevant loan contracts and the leverage measurement process.

4. **Recommendation generation**  
   - Predefined templates for adjustments (e.g., “In clause X, replace paragraph Y with: …”).  
   - If the change is complex, suggest manual legal review.

5. **Delivery to user**  
   - Web dashboard with alerts, impact details, and suggestions.  
   - Exportable to Excel/PDF.  
   - Integration with task management tools (Jira, Asana) to assign adjustments.

## 5. Suggested Architecture

```plaintext
[External sources] → [Ingestion layer] → [Raw storage]
                           ↓
                 [NLP + Comparator engine] → [Changes database]
                           ↓
              [Mapping engine rules/contracts] → [Impact graph]
                           ↓
                 [Suggestion generator] → [API / Dashboard]
```

### Technical components
- **Backend**: Python (FastAPI or Django) for scraping logic, NLP, and mapping.
- **NLP**: spaCy, transformers (Legal‑BERT), difflib for change detection.
- **Database**: PostgreSQL (documents, changes, mappings) + pgvector (embeddings).
- **Contract storage**: File system or S3 (PDF, DOCX) with text extractor.
- **Frontend**: React + Tailwind for dashboard.
- **Orchestration**: Celery + Redis for scheduled scanning tasks.

## 6. Key Technologies

| Layer | Technologies |
|-------|---------------|
| Scraping | BeautifulSoup, Scrapy, Selenium (if JS required) |
| Document processing | PyPDF2, python-docx, tika |
| NLP | Hugging Face Transformers (Legal‑BERT), spaCy, regex |
| Vectorization | Sentence-transformers, FAISS or pgvector |
| Mapping rules | JSON rules engine (e.g., json-rules-engine) |
| Backend | FastAPI, SQLAlchemy |
| Frontend | React, Chart.js, MUI |
| Infrastructure | Docker, Kubernetes (optional), GitHub Actions |

## 7. Input and Output Data

### Input
- URLs or feeds of regulatory sources.
- Contract repository (folder with files tagged by type/area).
- Internal process modelling (BPMN or step list).

### Output (example JSON for an alert)
```json
{
  "change_id": "CNBV-2025-042",
  "title": "Circular 10/2025 - Investment limits in fintech",
  "publication_date": "2025-03-20",
  "detected_change": "Article 5: The counterparty limit is reduced from 20% to 15%",
  "impact": [
    {
      "type": "contract",
      "name": "Master Investment Agreement - Fintech ABC",
      "clause": "Clause 4.2 - Exposure limits",
      "severity": "high",
      "suggestion": "Change the value '20%' to '15%' and add an automatic adaptation clause."
    },
    {
      "type": "process",
      "name": "Counterparty exposure calculation",
      "affected_step": "Step 3: Internal limit validation",
      "severity": "high",
      "suggestion": "Update threshold in risk system to 15% and reschedule daily validation."
    }
  ]
}
```

## 8. Security and Compliance Considerations

- **Controlled access**: Only authorized users (compliance, legal, risk) can view contract details.
- **Audit trail**: Log of all generated suggestions and actions taken.
- **Confidentiality**: Contracts must not be exposed to external LLMs; use local or proprietary models.
- **Human validation**: Automatic suggestions require approval by a lawyer or compliance officer before applying changes.

## 9. Success Metrics

- **Coverage rate**: % of relevant regulatory changes detected vs. expected manually.
- **Mapping accuracy**: % of clauses/processes correctly identified as affected.
- **Time reduction**: Person‑days saved in impact analysis (comparative).
- **Suggestion adoption rate**: % of recommendations accepted without major modification.

## 10. Possible Extensions

- Integration with contract management systems (Sirion, Icertis, DocuSign CLM).
- Automated drafting of addendums using LLM with oversight.
- Predictive alerts based on regulatory trends (analysis of proposed rules).
- Multilingual support (Spanish, English, Portuguese).

## 11. Suggested Team for Implementation

- 1 Product Owner (legal/regulatory knowledge)
- 1 Data Engineer (scraping, ETL)
- 1 NLP/ML Engineer
- 1 Backend Developer
- 1 Frontend Developer
- 1 Regulatory Attorney (domain expert)

---

**Note:** This document serves as an initial vision and scope statement. It can be refined during development sprints.

---

## Sprint Status

```
Sprint 1 — Foundation & Ingestion Engine   [x] Completado (2026-04-23)
Sprint 2 — NLP & Change Detection         [x] Completado (2026-04-23)
Sprint 3 — Knowledge Base & Semantic Mapping [x] Completado (2026-04-22)
Sprint 4 — Recommendation Engine & UI Core  [x] Completado (2026-04-24)
Sprint 5 — Human-in-the-Loop & Export      [x] Completado (2026-04-24)
Sprint 6 — Integration & Final Polish      [x] Completado (2026-04-23)
Sprint 7 — Trend Analysis                  [x] Completado (2026-04-24)
Sprint 8 — Risk Heatmaps                   [x] Completado (2026-04-25)
```

## Lecciones aprendidas — Sprint 1

**`_SCRAPERS` dict captura la referencia de clase en tiempo de importación**
`patch("src.services.ingestion_service.CNBVScraper")` parchea el nombre en el
namespace del módulo, pero el dict `_SCRAPERS` ya tiene la referencia original.
Regla: cuando el objeto a parchear vive en un dict de nivel de módulo, usar
`patch.dict(svc._SCRAPERS, {"key": MockClass})` en lugar de parchear el nombre.

**La aserción sobre un `patch.object` debe estar dentro del bloque `with`**
Después de salir del `with`, el mock es restaurado a la función original.
`svc.document_repo.create_from_raw.assert_called_once()` fuera del bloque
falla con `AttributeError: 'function' object has no attribute 'assert_called_once'`.
Regla: capturar el mock en una variable (`mock_fn = AsyncMock()`) y pasarlo
como `new=mock_fn` para poder hacer aserciones después del bloque.

**URL del feed SEC EDGAR era HTML, no Atom**
`browse-edgar?output=atom` devuelve HTML en la práctica. El feed correcto es
`https://www.sec.gov/rss/news/press.xml` (press releases), filtrado por keywords.

**`external_id` basado en slice de URL produce colisiones**
`entry.get('id', '')[:100]` puede truncar al mismo prefijo para URLs distintas.
Usar `sha1(url.encode()).hexdigest()[:12]` garantiza unicidad con longitud fija.

**PyMuPDF (AGPL) reemplazado por pypdf (MIT)**
Para un portafolio público, ambos son viables, pero pypdf no requiere
dependencias de sistema (`libmupdf-dev`) y su instalación es más simple.

## Lecciones aprendidas — Sprint 2

**`_SIMILARITY_THRESHOLD = 0.30` filtra cambios regulatorios reales**
Cambiar "20%" → "15%" en una sección de 40 chars produce `change_ratio ≈ 0.05`.
Con umbral en 0.30, el artículo modificado no se reportaba como cambiado.
Valor correcto: `0.02`. En compliance, incluso un 2% de cambio en el texto es significativo.

**`_MIN_SECTION_LENGTH = 60` descarta provisiones legítimas cortas**
"El límite es del 15%." tiene 24 chars — se filtraba como ruido.
Valor correcto: `20` chars. Los números de página tienen ≤5 chars; las provisiones reales, ≥20.

**Matching de cambios numéricos: posicional > contextual**
`extract_numeric_changes` con ventana de 80 chars: si la oración completa cabe en 80 chars,
"20%" y "30%" tienen el mismo contexto → matching ambiguo → solo se detecta uno de los dos.
Solución: zip por posición (N-ésimo % en old ↔ N-ésimo % en new). Más simple y correcto.

## Lecciones aprendidas — Sprint 3

**Regex plurales en el rules engine: `fondos? de inversión` no es lo mismo que `fondo de inversión`**
El patrón `\bfondo de inversión\b` no coincide con "fondos de inversión" porque `fondos` ≠ `fondo`.
Regla: al escribir patrones para nombres de entidades en español, incluir variantes de plural/singular
con `s?` o alternativas explícitas. Verificar con el texto exacto de los tests antes de declarar el patrón correcto.

**Deduplicación entre semantic mapper y rules engine es responsabilidad del servicio, no del mapper**
El `find_similar_clauses()` devuelve matches por nombre de contrato. El rules engine devuelve contratos
por tipo/área. Si un contrato aparece en ambas rutas, se generaría un `ImpactItem` duplicado.
Solución: en `impact_service`, construir `clause_contract_names = {m.contract_name for m in clause_matches}`
y filtrar los contratos del rules engine que ya estén cubiertos. El mapper y el engine son stateless
y no deben conocerse entre sí.

**`patch("src.services.impact_service._HAS_SEMANTIC", False)` es el patrón correcto para desactivar embedding**
El flag `_HAS_SEMANTIC` se resuelve en tiempo de importación del módulo (try/except en nivel de módulo).
Para tests que no requieren sentence-transformers, hacer `patch` sobre el bool es suficiente — no es
necesario parchear la función `find_similar_clauses` directamente cuando el código tiene `if _HAS_SEMANTIC`.

**`selectinload` es necesario cuando se accede a relaciones lazy desde un contexto async**
`change.document` cargado sin `selectinload` en un contexto async lanza `MissingGreenlet` o devuelve
`None` porque SQLAlchemy lazy-loading requiere un contexto síncrono.
Regla: en cualquier query async que necesite acceder a relaciones ORM, agregar
`.options(selectinload(Model.relation))` explícitamente en la query.

## Lecciones aprendidas — Sprint 4

**Node.js no disponible en el entorno de desarrollo de Claude Code**
La scaffolding de Vite requiere npm. Sin él, el frontend se escribe a mano.
Para proyectos de portafolio, la estructura manual es válida; el usuario ejecuta
`npm install && npm run dev` después de que Claude genera todos los archivos.

**`BackgroundTasks` de FastAPI vs Celery para tareas de análisis**
`BackgroundTasks` es suficiente para tareas de análisis únicas (POST /analyze).
No requiere broker ni worker externo. Celery sigue siendo la opción correcta
para scraping programado (beat schedule) y cargas de trabajo paralelas masivas.

## Lecciones aprendidas — Sprint 5

**`db.add()` en `audit_repo.log` no debe llamarse sobre un `AsyncMock`**
Cuando `db = AsyncMock()`, todos sus atributos son también `AsyncMock`.
`db.add(entry)` crea una coroutine que nunca se espera → RuntimeWarning.
Regla: en tests que ejerciten rutas de código que llaman `audit_repo.log`,
parchear `audit_repo.log` con `patch("...audit_repo.log", new_callable=AsyncMock)`.
No intentar fijar `db.add = MagicMock()` después del hecho — es más limpio
eliminar la dependencia desde el test.

**`export_service` usa `hexval()` de ReportLab — verificar compatibilidad de versión**
`colors.HexColor.hexval()` retorna un string de 8 chars (AARRGGBB) en ReportLab ≥ 4.0.
El slice `[2:]` descarta el canal alpha. Si la versión de ReportLab cambia la
firma, las celdas de severidad en el PDF pueden mostrar color incorrecto.
Regla: fijar `reportlab>=4.0.0` en pyproject.toml (ya está) y cubrir con test
que verifique el magic byte `%PDF` sin depender del color específico.