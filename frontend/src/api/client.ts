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

// ── Types ─────────────────────────────────────────────────────────────────────

export type Severity = "high" | "medium" | "low";
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
      request<ImpactAlert[]>(`/alerts?unread_only=${unreadOnly}`),
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
      request<RegulatoryDocument[]>(
        source ? `/documents?source=${source}` : "/documents"
      ),
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
};
