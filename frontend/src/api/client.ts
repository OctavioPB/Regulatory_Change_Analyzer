const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type Severity = "high" | "medium" | "low";
export type DocType =
  | "proposed_rule"
  | "no_action_letter"
  | "interim_rule"
  | "final_rule"
  | "guidance"
  | "other";

export interface TrendSignal {
  id: string;
  document_id: string;
  doc_type: DocType;
  domain: string;
  signal_strength: number;
  horizon_months: number;
  predicted_effective_date: string | null;
  key_themes: string[];
  confidence_score: number;
  extracted_at: string;
}

export interface DomainForecast {
  domain: string;
  signal_count: number;
  avg_strength: number;
  avg_confidence: number;
  avg_horizon_months: number;
}

export interface TrendStats {
  total_signals: number;
  by_doc_type: Record<string, number>;
  top_domain: string | null;
}

export interface DepartmentSummary {
  department: string;
  total: number;
  high: number;
  medium: number;
  low: number;
  recent_30d: number;
  churn_score: number;
}

export interface MatrixCell {
  department: string;
  change_type: string;
  count: number;
  severity_score: number;
}

export interface MonthlyPoint {
  department: string;
  month: string;
  count: number;
}

export interface ChatCitation {
  type: "regulation" | "contract";
  ref_id: number;
  title: string;
  source: string;
  article_ref: string;
  excerpt: string;
  publication_date: string | null;
}
export type ApprovalStatus = "pending" | "approved" | "modified" | "rejected";
export type ChangeType =
  | "new_requirement"
  | "limit_modification"
  | "repeal"
  | "clarification"
  | "deadline"
  | "other";

export interface ImpactItem {
  id: string;
  impact_type: string;
  affected_name: string;
  affected_ref: string | null;
  severity: Severity;
  suggestion: string;
  approval_status: ApprovalStatus;
  reviewer_notes: string | null;
  reviewed_at: string | null;
}

export interface ImpactAlert {
  id: string;
  document_id: string;
  title: string;
  is_read: boolean;
  created_at: string;
  items: ImpactItem[];
}

export interface RegulatoryDocument {
  id: string;
  source: string;
  external_id: string;
  title: string;
  url: string | null;
  publication_date: string;
  fetched_at: string;
}

export interface RegulatoryChange {
  id: string;
  document_id: string;
  article_ref: string | null;
  change_type: ChangeType;
  summary: string;
  old_text: string | null;
  new_text: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  detail: string | null;
  created_at: string;
}

export interface DashboardStats {
  documents: { total: number; by_source: Record<string, number> };
  changes: { total: number; by_type: Record<string, number> };
  alerts: { total: number; unread: number };
  impact_items: {
    total: number;
    by_severity: Record<string, number>;
    pending_review: number;
  };
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  stats: () => request<DashboardStats>("/dashboard/stats"),

  alerts: {
    list: (unreadOnly = false) =>
      request<Page<ImpactAlert>>(`/alerts/?unread_only=${unreadOnly}`).then((p) => p.items),
    get: (id: string) => request<ImpactAlert>(`/alerts/${id}`),
    review: (alertId: string, itemId: string, status: ApprovalStatus, notes?: string) =>
      request<{ detail: string; status: string }>(
        `/alerts/${alertId}/items/${itemId}/review`,
        {
          method: "POST",
          body: JSON.stringify({ status, reviewer_notes: notes ?? null }),
        }
      ),
  },

  documents: {
    list: (source?: string) =>
      request<Page<RegulatoryDocument>>(
        source ? `/documents/?source=${source}` : "/documents/"
      ).then((p) => p.items),
    get: (id: string) => request<RegulatoryDocument>(`/documents/${id}`),
    changes: (id: string) => request<RegulatoryChange[]>(`/documents/${id}/changes`),
    analyze: (id: string) =>
      request<{ detail: string }>(`/documents/${id}/analyze`, { method: "POST" }),
  },

  ingestion: {
    sources: () => request<{ sources: string[] }>("/ingest/sources"),
    trigger: (source: string) =>
      request<{ detail: string }>(`/ingest/${source}`, { method: "POST" }),
    triggerAll: () =>
      request<{ detail: string }>("/ingest/", { method: "POST" }),
  },

  pipeline: {
    seedContracts: () =>
      request<{ detail: string; skipped: number }>("/contracts/seed", { method: "POST" }),
    ingest: (source?: string) =>
      source
        ? request<{ detail: string }>(`/ingest/${source}`, { method: "POST" })
        : request<{ detail: string }>("/ingest/", { method: "POST" }),
    analyze: () =>
      request<{ detail: string }>("/ingest/analyze", { method: "POST" }),
    mapImpacts: () =>
      request<{ detail: string }>("/ingest/map", { method: "POST" }),
  },

  chat: {
    stream: (query: string): Promise<Response> =>
      fetch(`${BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      }),
  },

  heatmap: {
    departments: () => request<DepartmentSummary[]>("/heatmap/departments"),
    matrix: () => request<MatrixCell[]>("/heatmap/matrix"),
    trend: (months = 6) => request<MonthlyPoint[]>(`/heatmap/trend?months=${months}`),
  },

  trends: {
    list: (params?: { doc_type?: string; domain?: string; min_confidence?: number }) => {
      const qs = new URLSearchParams();
      if (params?.doc_type) qs.set("doc_type", params.doc_type);
      if (params?.domain) qs.set("domain", params.domain);
      if (params?.min_confidence !== undefined) qs.set("min_confidence", String(params.min_confidence));
      qs.set("page_size", "50");
      return request<{ items: TrendSignal[]; total: number }>(`/trends/?${qs}`).then((p) => p.items);
    },
    forecast: () => request<DomainForecast[]>("/trends/forecast"),
    stats: () => request<TrendStats>("/trends/stats"),
    extractAll: () => request<{ detail: string }>("/trends/extract-all", { method: "POST" }),
  },

  export: {
    alertXlsx: (alertId: string) => `${BASE}/export/alerts/${alertId}.xlsx`,
    alertPdf: (alertId: string) => `${BASE}/export/alerts/${alertId}.pdf`,
    allAlertsXlsx: () => `${BASE}/export/alerts.xlsx`,
  },

  audit: {
    list: (entityType?: string, limit = 100) =>
      request<AuditEntry[]>(
        `/audit/?limit=${limit}` + (entityType ? `&entity_type=${entityType}` : "")
      ),
  },
};
