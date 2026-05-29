import { useState } from "react";
import type { ReactNode } from "react";
import { Eyebrow } from "../components/Eyebrow";

type InfoTab = "business" | "engineering";

// ---- Shared helpers ----------------------------------------------------------

function SectionCard({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      className="rounded-xl"
      style={{
        background: "var(--white)",
        border: "1px solid var(--primary-10)",
        boxShadow: "var(--shadow-card)",
        padding: "20px 24px",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function SectionHeading({ eyebrow, title, sub }: { eyebrow: string; title: ReactNode; sub?: string }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 style={{ fontFamily: "var(--fd)", fontSize: 19, fontWeight: 300, color: "var(--dark)", marginBottom: sub ? 6 : 0 }}>
        {title}
      </h2>
      {sub && (
        <p style={{ fontFamily: "var(--fb)", fontSize: 12, color: "var(--mid)", lineHeight: 1.65 }}>
          {sub}
        </p>
      )}
    </div>
  );
}

// ---- Pipeline flow (shared between both views) --------------------------------

const PIPELINE_STAGES = [
  { num: "01", label: "Ingest",   detail: "SEC RSS · CNBV scraper",        bg: "#003366" },
  { num: "02", label: "Analyze",  detail: "NLP · classify · extract",       bg: "#1A4D80" },
  { num: "03", label: "Embed",    detail: "384-dim sentence vectors",        bg: "#336699" },
  { num: "04", label: "Map",      detail: "Cosine sim + rules engine",       bg: "#336699" },
  { num: "05", label: "Alert",    detail: "Severity score · group",          bg: "#1A4D80" },
  { num: "06", label: "Review",   detail: "Approve · modify · audit",        bg: "#C8982A" },
];

function PipelineFlow() {
  return (
    <div style={{ display: "flex", alignItems: "stretch", gap: 5 }}>
      {PIPELINE_STAGES.map((s, i) => (
        <div key={s.num} style={{ display: "flex", alignItems: "center", flex: 1, gap: 5 }}>
          <div
            style={{
              flex: 1,
              background: s.bg,
              borderRadius: 8,
              padding: "10px 6px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 7, letterSpacing: 2, color: "rgba(255,255,255,0.4)", fontFamily: "var(--fb)", fontWeight: 600, marginBottom: 4 }}>
              {s.num}
            </div>
            <div style={{ fontSize: 11, color: "#fff", fontFamily: "var(--fb)", fontWeight: 600, marginBottom: 3 }}>
              {s.label}
            </div>
            <div style={{ fontSize: 9, color: "rgba(255,255,255,0.6)", fontFamily: "var(--fb)", lineHeight: 1.4 }}>
              {s.detail}
            </div>
          </div>
          {i < PIPELINE_STAGES.length - 1 && (
            <div style={{ color: "var(--primary-30)", fontSize: 14, flexShrink: 0 }}>›</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// BUSINESS VIEW
// ============================================================================

const PAIN_POINTS = [
  {
    title: "Regulatory Volume & Velocity",
    body: "Financial institutions in Mexico and the US must track CNBV and SEC publications continuously — circulars, proposed rules, no-action letters, and enforcement actions. Each generates dozens of specific change events per year, all requiring expert human review before a compliance decision can be made.",
    stat: "Compliance teams spend 60-70% of capacity reading documents, not acting on them.",
  },
  {
    title: "Contract Impact Assessment Latency",
    body: "When a regulation changes, identifying which contracts, clauses, and internal processes are affected requires cross-referencing regulatory language against the full contract library. This depends on individual expertise and takes weeks — often compressing the window available to actually implement the required changes.",
    stat: "Average 4-6 weeks for a thorough impact assessment after a significant regulatory change.",
  },
  {
    title: "Audit Trail Gaps",
    body: "Regulators expect documented evidence that every relevant regulatory change was reviewed, assessed for impact, and acted upon with a recorded rationale. Manual processes — shared spreadsheets, email threads — produce records that are incomplete, difficult to search, and hard to produce under examination.",
    stat: "Incomplete regulatory response documentation contributes to 34% of exam findings at mid-size institutions.",
  },
];

const CAPABILITIES = [
  { label: "Automated Ingestion", desc: "Monitors SEC EDGAR RSS feeds and the CNBV website continuously. Documents are fetched, deduplicated, parsed (HTML or PDF), and stored without manual intervention." },
  { label: "Change Detection & Classification", desc: "NLP pipeline identifies what changed in each regulatory publication, classifies the change type (new requirement, limit modification, repeal, clarification, or deadline), and extracts article references." },
  { label: "Semantic Impact Mapping", desc: "pgvector cosine similarity matches regulation text to contract clause embeddings — finding connections even when regulatory and contract language use different terminology for the same concept." },
  { label: "Prioritized Alert Queue", desc: "Impact items are grouped by regulatory document and severity-scored (high / medium / low). Compliance officers work a structured, ranked queue instead of a raw document pile." },
  { label: "Human-in-the-Loop Review", desc: "Each impact item is explicitly approved, modified with reviewer notes, or rejected. All decisions are attributed to a named reviewer, timestamped, and logged to an immutable audit trail." },
  { label: "6-12 Month Trend Signals", desc: "Proposed rules and no-action letters are analyzed to extract forward-looking regulatory signals by domain, giving compliance teams early warning of regulatory directions before they become mandatory." },
  { label: "Departmental Risk Heatmap", desc: "Aggregates impact volume by business department (AML, Risk, Compliance, Legal, Treasury, IT) and visualizes regulatory churn intensity to inform staffing and remediation prioritization." },
  { label: "RAG Policy Chat", desc: "Compliance officers ask natural-language questions and receive answers grounded in ingested regulations and contracts, with inline citations to the exact document and clause supporting each statement." },
  { label: "Addendum Drafting", desc: "For approved impact items, the system generates contract addendum language incorporating the specific regulatory requirement and the relevant clause — formatted as a draft ready for legal review and signature." },
];

const ROLE_IMPACT = [
  {
    role: "Compliance Officer",
    before: "Reads every regulatory publication manually. Maintains a personal spreadsheet of potentially affected contracts. Writes impact reports from scratch.",
    after: "Works a pre-analyzed, prioritized queue of impact items — each with a suggested action, citation to the source regulation, and draft addendum language.",
  },
  {
    role: "Contract Manager",
    before: "Manually cross-references new regulation text against the contract library, relying on keyword searches and domain knowledge to find affected clauses.",
    after: "Reviews a precise list of affected contracts and clauses, with AI-drafted modification language and a direct link to the regulatory trigger.",
  },
  {
    role: "Risk Manager",
    before: "Produces quarterly regulatory exposure summaries by compiling ad-hoc reports from the compliance team.",
    after: "Views a live departmental risk heatmap with monthly trend data and 6-12 month predictive signals across regulatory domains.",
  },
  {
    role: "Internal Auditor",
    before: "Reconstructs regulatory response history from email threads, meeting notes, and versioned documents — often with attribution and timing gaps.",
    after: "Queries a complete, structured audit trail: every change ingested, every impact assessed, every approval or rejection, with timestamp and reviewer name.",
  },
];

function BusinessView() {
  return (
    <div className="flex flex-col gap-8">

      {/* Problem */}
      <section>
        <SectionHeading
          eyebrow="The Problem"
          title={<>What compliance teams face <em style={{ color: "var(--gold)", fontStyle: "italic" }}>today</em></>}
          sub="Financial institutions operating under multi-jurisdictional regulatory oversight face three compounding problems."
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {PAIN_POINTS.map((p) => (
            <SectionCard key={p.title}>
              <div style={{ display: "flex", alignItems: "stretch", gap: 12, marginBottom: 12 }}>
                <div style={{ width: 3, background: "var(--gold)", borderRadius: 2, flexShrink: 0 }} />
                <h3 style={{ fontFamily: "var(--fb)", fontSize: 13, fontWeight: 600, color: "var(--dark)" }}>
                  {p.title}
                </h3>
              </div>
              <p style={{ fontFamily: "var(--fb)", fontSize: 12, color: "var(--dark)", lineHeight: 1.7, marginBottom: 12 }}>
                {p.body}
              </p>
              <div
                style={{
                  background: "rgba(0,51,102,0.04)",
                  borderRadius: 6,
                  padding: "8px 12px",
                  fontSize: 11,
                  fontFamily: "var(--fb)",
                  color: "var(--primary-60)",
                  fontStyle: "italic",
                  lineHeight: 1.5,
                }}
              >
                {p.stat}
              </div>
            </SectionCard>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section>
        <SectionHeading
          eyebrow="How It Works"
          title="Six stages from raw regulation to reviewed action"
          sub="Every regulatory publication flows through a fixed pipeline. No step is skipped; every output is recorded."
        />
        <SectionCard>
          <PipelineFlow />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 6, marginTop: 14 }}>
            {[
              "SEC and CNBV documents are fetched automatically. No manual download.",
              "NLP extracts what changed: the change type, article reference, old and new text.",
              "Each change and each contract clause is converted to a 384-dimensional semantic vector.",
              "Cosine similarity and deterministic rules identify which contracts are affected and why.",
              "Impact items are grouped into alerts and scored by severity (high / medium / low).",
              "A compliance officer approves, modifies, or rejects each item. Decision is logged.",
            ].map((desc, i) => (
              <p key={i} style={{ fontSize: 10, fontFamily: "var(--fb)", color: "var(--mid)", lineHeight: 1.55 }}>
                {desc}
              </p>
            ))}
          </div>
        </SectionCard>
      </section>

      {/* Capabilities */}
      <section>
        <SectionHeading
          eyebrow="Capabilities"
          title="What the system does"
          sub="Nine functional areas, each accessible through the navigation bar."
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {CAPABILITIES.map((c) => (
            <SectionCard key={c.label}>
              <p
                style={{
                  fontFamily: "var(--fb)",
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                  color: "var(--primary)",
                  marginBottom: 8,
                }}
              >
                {c.label}
              </p>
              <p style={{ fontFamily: "var(--fb)", fontSize: 12, color: "var(--dark)", lineHeight: 1.7 }}>
                {c.desc}
              </p>
            </SectionCard>
          ))}
        </div>
      </section>

      {/* Role impact */}
      <section>
        <SectionHeading
          eyebrow="Impact by Role"
          title={<>Before and <em style={{ color: "var(--gold)", fontStyle: "italic" }}>after</em></>}
          sub="The same four roles — different workflows."
        />
        <SectionCard style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--primary)" }}>
                {["Role", "Without the system", "With the system"].map((h) => (
                  <th
                    key={h}
                    style={{
                      fontFamily: "var(--fb)",
                      fontSize: 9,
                      fontWeight: 600,
                      letterSpacing: "2px",
                      textTransform: "uppercase",
                      color: "#fff",
                      padding: "10px 16px",
                      textAlign: "left",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROLE_IMPACT.map((r, i) => (
                <tr key={r.role} style={{ background: i % 2 === 0 ? "var(--white)" : "rgba(0,51,102,0.02)" }}>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, fontWeight: 600, color: "var(--dark)", padding: "10px 16px", whiteSpace: "nowrap", verticalAlign: "top" }}>
                    {r.role}
                  </td>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--mid)", padding: "10px 16px", lineHeight: 1.65, verticalAlign: "top" }}>
                    {r.before}
                  </td>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--dark)", padding: "10px 16px", lineHeight: 1.65, verticalAlign: "top" }}>
                    {r.after}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      </section>

    </div>
  );
}

// ============================================================================
// ENGINEERING VIEW
// ============================================================================

const TECH_STACK = [
  { layer: "API Framework",     tech: "FastAPI 0.115+",                notes: "Async endpoints, dependency injection, Pydantic v2 validation, auto OpenAPI/Swagger docs" },
  { layer: "Database",          tech: "PostgreSQL 16 + pgvector",      notes: "UUID PKs, native enum types, TIMESTAMPTZ columns, vector cosine distance index (IVFFlat)" },
  { layer: "ORM & Migrations",  tech: "SQLAlchemy 2.0 + Alembic",      notes: "Mapped column syntax, async session factory (asyncpg driver), versioned migration chain" },
  { layer: "Task Queue",        tech: "Celery 5.4 + Redis 7",          notes: "Background NLP jobs, Redis as broker and result backend, isolated async DB sessions per task" },
  { layer: "Embeddings",        tech: "sentence-transformers 3.0",     notes: "all-MiniLM-L6-v2 · 384-dim dense vectors · runs entirely local (no external API call)" },
  { layer: "NLP & Parsing",     tech: "spaCy 3.7 · transformers 4.40", notes: "Entity extraction, change classification, pypdf for PDF parsing, feedparser for RSS" },
  { layer: "HTTP & Scraping",   tech: "httpx 0.27 · BeautifulSoup4",   notes: "Async HTTP client, SEC EDGAR RSS ingestion, CNBV HTML scraping with tenacity retry" },
  { layer: "LLM",               tech: "Anthropic Claude (SDK 0.40+)",  notes: "RAG answer generation, addendum drafting; client.messages.stream() for SSE token streaming" },
  { layer: "Export",            tech: "ReportLab · openpyxl · python-docx", notes: "Branded PDF reports, Excel impact matrices, A4 DOCX addendums with OPB letterhead" },
  { layer: "Frontend",          tech: "React 18 · TypeScript 5.5 · Vite 5", notes: "SPA with react-router v6, SSE streaming client (ReadableStream + TextDecoder), Tailwind CSS" },
  { layer: "Auth / RBAC",       tech: "Custom API key middleware",      notes: "Roles: viewer · analyst · compliance_officer · admin — resolved per endpoint via FastAPI Depends" },
];

const DESIGN_DECISIONS = [
  {
    title: "pgvector over keyword search for impact mapping",
    problem: "Regulatory language and contract language use different vocabulary for the same concept. \"Customer due diligence\" in a CNBV circular maps to \"KYC procedures\" in a loan agreement. Exact keyword matching produces false negatives on every vocabulary divergence.",
    solution: "Both regulatory change text and contract clause text are encoded with the same sentence-transformers model (all-MiniLM-L6-v2). Cosine distance in the shared 384-dimensional space captures semantic equivalence regardless of surface terminology. A minimum similarity threshold of 0.35 filters low-signal matches.",
    tradeoff: "Model load takes 1-2 s on first inference. Each embedding call adds ~100 ms. This runs inside a background Celery task, not on the HTTP request path, so latency is acceptable.",
  },
  {
    title: "Hybrid mapping: semantic search + deterministic rules engine",
    problem: "Embedding similarity is probabilistic and opaque. High-confidence categorical matches — any limit_modification change type necessarily affects Treasury department contracts — do not need a probabilistic retrieval step. Relying only on embeddings would make certain matches non-deterministic across model versions.",
    solution: "Eight rules (R001–R008) handle unambiguous change-type-to-department patterns with full precision. The embedding search runs in parallel and catches matches the rules miss. Both paths produce ImpactItem records; a deduplication step merges overlapping results before alert creation.",
    tradeoff: "Rules require maintenance as new regulatory patterns emerge. This is intentional: deterministic rules are auditable and explainable to examiners; embedding-only results are not.",
  },
  {
    title: "SSE over WebSocket for LLM streaming",
    problem: "Claude generates tokens incrementally. Waiting for a complete response before displaying anything can mean 10-30 seconds of silence for addendum drafts — unacceptable for a review workflow. The frontend needs to display output as it arrives.",
    solution: "FastAPI's StreamingResponse with media_type='text/event-stream' sends each token as a data: JSON line. The React client reads the stream with ReadableStream + TextDecoder, parsing events line by line. Citation metadata is emitted as a separate citations event before text streaming begins, so the sources panel renders immediately.",
    tradeoff: "SSE is unidirectional HTTP/1.1. Each streaming session holds one open connection. Sufficient for the expected concurrency profile (< 20 simultaneous analysts). WebSocket would add bidirectional complexity with no benefit for this use case.",
  },
  {
    title: "Local embedding inference",
    problem: "Contract and regulatory documents contain confidential financial information subject to data residency and banking secrecy obligations. Sending document text to an external embedding API requires data processing agreements and may be prohibited by internal policy.",
    solution: "sentence-transformers runs entirely within the deployment host. No document content leaves the environment for embedding. The only external API call is to Anthropic for RAG and addendum features, where the text is explicitly selected by the compliance team for that specific purpose.",
    tradeoff: "CPU inference at ~100 ms per chunk is adequate for batch processing. A GPU would reduce this to ~10 ms but is not required. The model is cached in memory after first load — subsequent calls are fast.",
  },
  {
    title: "Async SQLAlchemy with per-task session isolation",
    problem: "The API handles concurrent operations: document ingestion, NLP processing, LLM streaming, and UI queries all run simultaneously. Synchronous database I/O would serialize these operations, creating a bottleneck at the busiest points. Background Celery tasks cannot safely share database sessions with the request context that enqueued them.",
    solution: "asyncpg provides non-blocking PostgreSQL access. HTTP request handlers receive a scoped session via FastAPI's Depends(get_db). Celery tasks open independent sessions via AsyncSessionLocal() context managers, ensuring complete isolation across process and thread boundaries.",
    tradeoff: "Async ORM requires explicit session lifecycle management (async with, commit/rollback boundaries). Circular import risk if routers and background tasks import session factories from the same module — resolved by importing AsyncSessionLocal locally inside background task functions.",
  },
];

function ArchitectureDiagram() {
  const W = 700;
  const layers: {
    label: string;
    line1: string;
    line2: string;
    fill: string;
    labelColor: string;
    textColor: string;
  }[] = [
    { label: "Data Sources", line1: "SEC EDGAR RSS Feed", line2: "CNBV Website · Web Scraper", fill: "#1C1C2E", labelColor: "rgba(255,255,255,0.35)", textColor: "#fff" },
    { label: "Ingestion Engine", line1: "feedparser · httpx · BeautifulSoup · pypdf · lxml", line2: "Celery background tasks · Redis broker · rate limiting", fill: "#003366", labelColor: "rgba(255,255,255,0.35)", textColor: "rgba(255,255,255,0.9)" },
    { label: "NLP + Embedding", line1: "spaCy · transformers · change detection · entity extraction", line2: "sentence-transformers — all-MiniLM-L6-v2 (384 dimensions)", fill: "#1A4D80", labelColor: "rgba(255,255,255,0.35)", textColor: "rgba(255,255,255,0.9)" },
    { label: "Persistence", line1: "PostgreSQL 16 + pgvector  (documents · changes · contracts · embeddings · alerts)", line2: "Redis 7  (task broker · result backend · rate limit counters)", fill: "#99BBDD", labelColor: "rgba(0,51,102,0.5)", textColor: "#003366" },
    { label: "FastAPI REST API", line1: "SQLAlchemy 2.0 async · Alembic · Pydantic v2 · RBAC middleware", line2: "14 routers · SSE streaming · OpenAPI docs", fill: "#336699", labelColor: "rgba(255,255,255,0.35)", textColor: "rgba(255,255,255,0.9)" },
    { label: "Intelligence Services", line1: "Impact Mapper · Trend Extractor · Heatmap Service · RAG Service · Addendum Service", line2: "Anthropic Claude (SDK) — RAG answers + addendum generation via SSE", fill: "#003366", labelColor: "rgba(255,255,255,0.35)", textColor: "rgba(255,255,255,0.9)" },
    { label: "React Frontend", line1: "React 18 · TypeScript 5.5 · Vite 5 · Tailwind CSS · react-router v6", line2: "SSE streaming client · 10 pages · OPB design system", fill: "#C8982A", labelColor: "rgba(255,255,255,0.45)", textColor: "rgba(255,255,255,0.95)" },
  ];
  const rH = 62, gap = 8, padY = 14;
  const totalH = layers.length * rH + (layers.length - 1) * gap + 2 * padY;
  return (
    <svg viewBox={`0 0 ${W} ${totalH}`} width="100%" style={{ display: "block" }}>
      <defs>
        <marker id="archArrow" markerWidth="7" markerHeight="7" refX="3" refY="3.5" orient="auto">
          <polygon points="0,0.5 6,3.5 0,6.5" fill="#99BBDD" />
        </marker>
      </defs>
      {layers.map((l, i) => {
        const y = padY + i * (rH + gap);
        const cx = W / 2;
        return (
          <g key={l.label}>
            {i > 0 && (
              <line
                x1={cx} y1={y - gap + 1} x2={cx} y2={y - 1}
                stroke="#99BBDD" strokeWidth={1.5} markerEnd="url(#archArrow)"
              />
            )}
            <rect x={18} y={y} width={W - 36} height={rH} rx={8} fill={l.fill} />
            <text x={cx} y={y + 15} textAnchor="middle"
              fill={l.labelColor} fontSize={7.5} letterSpacing={2.5}
              fontFamily="Plus Jakarta Sans, sans-serif" fontWeight={700}>
              {l.label.toUpperCase()}
            </text>
            <text x={cx} y={y + 34} textAnchor="middle"
              fill={l.textColor} fontSize={10}
              fontFamily="Plus Jakarta Sans, sans-serif" fontWeight={600}>
              {l.line1}
            </text>
            <text x={cx} y={y + 50} textAnchor="middle"
              fill={l.textColor} fontSize={9} opacity={0.75}
              fontFamily="Plus Jakarta Sans, sans-serif">
              {l.line2}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function DataModelDiagram() {
  // Six entity boxes arranged as: 3 top + 3 bottom, with relationship lines
  const W = 700, H = 220;
  const entities = [
    { id: "doc",     label: "RegulatoryDocument", fields: "source · title · url · publication_date",             x: 20,  y: 20,  w: 200, h: 60 },
    { id: "change",  label: "RegulatoryChange",   fields: "change_type · summary · embedding (384-dim)",         x: 250, y: 20,  w: 200, h: 60 },
    { id: "alert",   label: "ImpactAlert",         fields: "title · is_read · created_at",                       x: 480, y: 20,  w: 200, h: 60 },
    { id: "item",    label: "ImpactItem",           fields: "impact_type · severity · suggestion · approval_status", x: 250, y: 140, w: 200, h: 60 },
    { id: "contract",label: "Contract",             fields: "name · contract_type · area",                        x: 20,  y: 140, w: 200, h: 60 },
    { id: "clause",  label: "ContractClause",       fields: "clause_ref · text · embedding (384-dim)",           x: 480, y: 140, w: 200, h: 60 },
  ];
  const rels = [
    { x1: 120,  y1: 80, x2: 120,  y2: 140, label: "has many clauses" },
    { x1: 220,  y1: 50, x2: 250,  y2: 50,  label: "has many changes" },
    { x1: 450,  y1: 50, x2: 480,  y2: 50,  label: "has many alerts" },
    { x1: 350,  y1: 80, x2: 350,  y2: 140, label: "has many items" },
    { x1: 480,  y1: 50, x2: 490,  y2: 140, label: "" },
    { x1: 450,  y1: 170, x2: 480, y2: 170, label: "optionally has clause" },
  ];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
      <defs>
        <marker id="relArrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <polygon points="0,0.5 5,3 0,5.5" fill="#99BBDD" />
        </marker>
      </defs>
      {/* Relationship lines */}
      {/* doc → change */}
      <line x1={220} y1={50} x2={250} y2={50} stroke="#99BBDD" strokeWidth={1.2} markerEnd="url(#relArrow)" />
      {/* change → alert */}
      <line x1={450} y1={50} x2={480} y2={50} stroke="#99BBDD" strokeWidth={1.2} markerEnd="url(#relArrow)" />
      {/* change → item */}
      <line x1={350} y1={80} x2={350} y2={140} stroke="#99BBDD" strokeWidth={1.2} markerEnd="url(#relArrow)" />
      {/* alert → item */}
      <polyline points="580,80 580,110 350,110 350,140" fill="none" stroke="#99BBDD" strokeWidth={1.2} markerEnd="url(#relArrow)" />
      {/* contract → clause */}
      <line x1={220} y1={170} x2={480} y2={170} stroke="#99BBDD" strokeWidth={1.2} markerEnd="url(#relArrow)" />
      {/* clause → item (optional) */}
      <polyline points="580,140 580,110" fill="none" stroke="rgba(153,187,221,0.5)" strokeWidth={1} strokeDasharray="4,3" />
      {/* Entities */}
      {entities.map((e) => (
        <g key={e.id}>
          <rect x={e.x} y={e.y} width={e.w} height={e.h} rx={6}
            fill="#003366" stroke="rgba(153,187,221,0.3)" strokeWidth={1} />
          <text x={e.x + e.w / 2} y={e.y + 22} textAnchor="middle"
            fill="#fff" fontSize={10} fontFamily="Plus Jakarta Sans, sans-serif" fontWeight={700}>
            {e.label}
          </text>
          <text x={e.x + e.w / 2} y={e.y + 38} textAnchor="middle"
            fill="rgba(255,255,255,0.55)" fontSize={8.5}
            fontFamily="Plus Jakarta Sans, sans-serif">
            {e.fields.length > 36 ? e.fields.slice(0, 34) + "…" : e.fields}
          </text>
          <text x={e.x + e.w / 2} y={e.y + 52} textAnchor="middle"
            fill="rgba(255,255,255,0.4)" fontSize={8}
            fontFamily="Plus Jakarta Sans, sans-serif">
            {e.fields.length > 36 ? "…" + e.fields.slice(34) : ""}
          </text>
        </g>
      ))}
    </svg>
  );
}

function EngineeringView() {
  const [openDecision, setOpenDecision] = useState<number | null>(null);
  return (
    <div className="flex flex-col gap-8">

      {/* Architecture */}
      <section>
        <SectionHeading
          eyebrow="System Architecture"
          title={<>Layered architecture from <em style={{ color: "var(--gold)", fontStyle: "italic" }}>source to screen</em></>}
          sub="Seven layers: each only communicates with the layers directly adjacent. The persistence layer is the only shared state boundary."
        />
        <SectionCard>
          <ArchitectureDiagram />
        </SectionCard>
      </section>

      {/* Pipeline */}
      <section>
        <SectionHeading
          eyebrow="Processing Pipeline"
          title="Six-stage data pipeline"
          sub="Every regulatory document follows the same deterministic path. Stages 1-3 run as background Celery tasks. Stages 4-5 run within the same task chain. Stage 6 is synchronous: a human makes a decision in the UI."
        />
        <SectionCard>
          <PipelineFlow />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8, marginTop: 14 }}>
            {[
              { stage: "Ingest", detail: "feedparser reads SEC RSS. httpx + BeautifulSoup scrapes CNBV. pypdf extracts PDF text. Documents stored as RegulatoryDocument rows." },
              { stage: "Analyze", detail: "spaCy + transformers classify each document section into a ChangeType (new_requirement, limit_modification, repeal, clarification, deadline, other). Article references extracted." },
              { stage: "Embed", detail: "Each RegulatoryChange.new_text and each ContractClause.text is encoded by all-MiniLM-L6-v2 (384-dim). Vectors stored in pgvector columns." },
              { stage: "Map", detail: "Eight deterministic rules run first. Then pgvector cosine similarity (threshold 0.35) finds clause matches. Both paths deduped into ImpactItem rows." },
              { stage: "Alert", detail: "ImpactItems grouped by RegulatoryDocument into ImpactAlert. High/medium/low severity scored from change_type + matched clause criticality." },
              { stage: "Review", detail: "Compliance officer opens the alert, reads each item, and marks approved / modified / rejected. Decision logged to audit_log with reviewer + timestamp." },
            ].map((s) => (
              <div key={s.stage}>
                <p style={{ fontFamily: "var(--fb)", fontSize: 9, fontWeight: 700, color: "var(--primary)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 4 }}>
                  {s.stage}
                </p>
                <p style={{ fontFamily: "var(--fb)", fontSize: 10, color: "var(--mid)", lineHeight: 1.6 }}>
                  {s.detail}
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      </section>

      {/* Data model */}
      <section>
        <SectionHeading
          eyebrow="Data Model"
          title="Core entities and relationships"
          sub="Six mapped SQLAlchemy models. All primary keys are UUID. Embeddings stored as pgvector Vector(384) columns."
        />
        <SectionCard>
          <DataModelDiagram />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 16 }}>
            {[
              { entity: "RegulatoryDocument", note: "One per publication. Source field identifies CNBV vs SEC. Anchor for the full processing chain." },
              { entity: "RegulatoryChange", note: "One per detected change within a document. Has a change_type enum and a 384-dim embedding. FK to RegulatoryDocument." },
              { entity: "ImpactAlert", note: "Groups all impact items for one regulatory document into a reviewable unit. Has is_read flag and created_at timestamp." },
              { entity: "ImpactItem", note: "The atomic impact record. Links a RegulatoryChange to an affected contract or process. Holds the suggestion text and approval_status." },
              { entity: "Contract + ContractClause", note: "Internal contract library. Each clause has a 384-dim embedding. Semantic matching runs against the clause level, not the contract level." },
              { entity: "TrendSignal", note: "Extracted from proposed rules and no-action letters. Has domain, signal_strength, horizon_months, and key_themes (JSON array)." },
            ].map((e) => (
              <div key={e.entity}>
                <p style={{ fontFamily: "var(--fb)", fontSize: 10, fontWeight: 700, color: "var(--primary)", marginBottom: 4 }}>{e.entity}</p>
                <p style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--mid)", lineHeight: 1.6 }}>{e.note}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </section>

      {/* Tech stack */}
      <section>
        <SectionHeading
          eyebrow="Tech Stack"
          title="Dependencies and rationale"
        />
        <SectionCard style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--primary)" }}>
                {["Layer", "Technology", "Notes"].map((h) => (
                  <th key={h} style={{ fontFamily: "var(--fb)", fontSize: 9, fontWeight: 600, letterSpacing: "2px", textTransform: "uppercase", color: "#fff", padding: "10px 16px", textAlign: "left" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TECH_STACK.map((row, i) => (
                <tr key={row.layer} style={{ background: i % 2 === 0 ? "var(--white)" : "rgba(0,51,102,0.02)" }}>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, fontWeight: 600, color: "var(--dark)", padding: "9px 16px", whiteSpace: "nowrap", verticalAlign: "top" }}>
                    {row.layer}
                  </td>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--primary)", padding: "9px 16px", whiteSpace: "nowrap", verticalAlign: "top" }}>
                    {row.tech}
                  </td>
                  <td style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--mid)", padding: "9px 16px", lineHeight: 1.6, verticalAlign: "top" }}>
                    {row.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      </section>

      {/* Design decisions */}
      <section>
        <SectionHeading
          eyebrow="Design Decisions"
          title="Five choices worth explaining"
          sub="Each decision below has an alternative — and a reason the alternative was rejected."
        />
        <div className="flex flex-col gap-3">
          {DESIGN_DECISIONS.map((d, i) => {
            const isOpen = openDecision === i;
            return (
              <SectionCard key={d.title} style={{ padding: 0, overflow: "hidden" }}>
                <button
                  onClick={() => setOpenDecision(isOpen ? null : i)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "14px 20px",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontFamily: "var(--fb)", fontSize: 9, fontWeight: 700, letterSpacing: 2, color: "var(--gold)", flexShrink: 0 }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span style={{ fontFamily: "var(--fb)", fontSize: 12, fontWeight: 600, color: "var(--dark)" }}>
                      {d.title}
                    </span>
                  </div>
                  <span style={{ fontSize: 10, color: "var(--mid)", flexShrink: 0, transform: isOpen ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>
                    ▾
                  </span>
                </button>

                {isOpen && (
                  <div style={{ padding: "0 20px 16px", borderTop: "1px solid var(--primary-10)" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 14 }}>
                      {[
                        { label: "Problem", text: d.problem, accent: "#E03448" },
                        { label: "Solution", text: d.solution, accent: "#003366" },
                        { label: "Trade-off", text: d.tradeoff, accent: "#C8982A" },
                      ].map((col) => (
                        <div key={col.label}>
                          <p style={{ fontFamily: "var(--fb)", fontSize: 9, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", color: col.accent, marginBottom: 8 }}>
                            {col.label}
                          </p>
                          <p style={{ fontFamily: "var(--fb)", fontSize: 11, color: "var(--dark)", lineHeight: 1.7 }}>
                            {col.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </SectionCard>
            );
          })}
        </div>
      </section>

    </div>
  );
}

// ============================================================================
// MAIN PAGE
// ============================================================================

export function Info() {
  const [activeTab, setActiveTab] = useState<InfoTab>("business");

  const tabs: { id: InfoTab; label: string }[] = [
    { id: "business",    label: "Business View" },
    { id: "engineering", label: "Engineering View" },
  ];

  return (
    <div className="flex flex-col">
      {/* Hero with tab bar */}
      <div className="hero-bg px-6 shrink-0" style={{ paddingTop: 16, paddingBottom: 0 }}>
        <Eyebrow light>About This System</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Regulatory Change{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Analyzer</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px", maxWidth: 560 }}>
          A compliance intelligence system for financial institutions monitoring CNBV and SEC regulatory output. Select a view below.
        </p>

        {/* Tab strip */}
        <div style={{ display: "flex", gap: 2, marginTop: 20 }}>
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "var(--fb)",
                  fontSize: 10,
                  fontWeight: 500,
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                  padding: "10px 18px",
                  marginBottom: -1,
                  borderBottom: `2px solid ${isActive ? "var(--gold-light)" : "transparent"}`,
                  color: isActive ? "var(--gold-light)" : "rgba(255,255,255,0.4)",
                  transition: "color 0.15s",
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="section-divider" />

      {/* Body */}
      <div className="px-6 py-5">
        {activeTab === "business" ? <BusinessView /> : <EngineeringView />}
      </div>
    </div>
  );
}
