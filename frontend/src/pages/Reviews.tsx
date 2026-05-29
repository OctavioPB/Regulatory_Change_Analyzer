import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, Pencil } from "lucide-react";
import { api, type ApprovalStatus, type ImpactAlert, type ImpactItem } from "../api/client";
import { Eyebrow } from "../components/Eyebrow";
import { SeverityBadge } from "../components/SeverityBadge";
import { StatusBadge } from "../components/StatusBadge";

interface PendingItem {
  alert: ImpactAlert;
  item: ImpactItem;
}

export function Reviews() {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const alerts = await api.alerts.list();
      const items: PendingItem[] = [];
      for (const alert of alerts) {
        for (const item of alert.items) {
          if (item.approval_status === "pending") items.push({ alert, item });
        }
      }
      setPending(items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function review(p: PendingItem, status: ApprovalStatus) {
    setSubmitting(p.item.id);
    try {
      await api.alerts.review(p.alert.id, p.item.id, status, notes[p.item.id]);
      setPending((prev) => prev.filter((x) => x.item.id !== p.item.id));
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-6 py-4">
        <Eyebrow light>Human Review</Eyebrow>
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
            Pending{" "}
            <em className="italic" style={{ color: "var(--gold-light)" }}>Reviews</em>
          </h1>
          {!loading && (
            <span
              className="opb-badge"
              style={{ background: "var(--gold)", color: "#fff", fontWeight: 600 }}
            >
              {pending.length}
            </span>
          )}
        </div>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Approve, modify, or reject each suggested compliance action.
        </p>
      </div>

      <div className="section-divider" />

      <div className="px-6 py-5 flex flex-col gap-5">
        <p className="eyebrow mb-1.5">Action items</p>
        <p className="font-body mb-2" style={{ fontSize: "13px", color: "var(--mid)" }}>
          Approve each suggestion as-is, modify it before accepting, or reject it entirely.
        </p>

        {loading ? (
          <p className="text-center py-12 font-body" style={{ color: "var(--mid)", fontSize: "14px" }}>
            Loading…
          </p>
        ) : pending.length === 0 ? (
          <div
            className="rounded-xl py-16 text-center font-body"
            style={{ border: "1px dashed var(--primary-30)" }}
          >
            <CheckCircle size={28} className="mx-auto mb-3" style={{ color: "#27B97C" }} />
            <p style={{ color: "var(--mid)", fontSize: "14px" }}>
              All impact items have been reviewed.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pending.map((p) => (
              <div
                key={p.item.id}
                className="rounded-xl bg-white shadow-sm overflow-hidden"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <div className="accent-bar" />
                <div className="px-5 py-4">
                  {/* Alert context */}
                  <p
                    className="font-body mb-2 truncate"
                    style={{ fontSize: "11px", color: "var(--mid)", letterSpacing: "0.3px" }}
                  >
                    {p.alert.title}
                  </p>

                  {/* Item info */}
                  <div className="flex items-center gap-2 mb-3 flex-wrap">
                    <SeverityBadge severity={p.item.severity} />
                    <StatusBadge status={p.item.approval_status} />
                    <span className="font-body font-medium" style={{ fontSize: "14px", color: "var(--dark)" }}>
                      {p.item.affected_name}
                    </span>
                    {p.item.affected_ref && (
                      <span className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                        · {p.item.affected_ref}
                      </span>
                    )}
                  </div>

                  <p className="font-body mb-4" style={{ fontSize: "14px", color: "var(--dark)", lineHeight: "1.7" }}>
                    {p.item.suggestion}
                  </p>

                  <textarea
                    className="w-full rounded-lg px-3 py-2 font-body mb-3 focus:outline-none"
                    style={{
                      border: "1px solid var(--primary-30)",
                      fontSize: "13px",
                      background: "var(--primary-10)",
                      color: "var(--dark)",
                    }}
                    rows={2}
                    placeholder="Reviewer notes (optional)"
                    value={notes[p.item.id] ?? ""}
                    onChange={(e) => setNotes((prev) => ({ ...prev, [p.item.id]: e.target.value }))}
                  />

                  <div className="flex gap-2 flex-wrap">
                    <button disabled={submitting === p.item.id} onClick={() => review(p, "approved")} className="btn btn-success">
                      <CheckCircle size={12} /> Approve
                    </button>
                    <button disabled={submitting === p.item.id} onClick={() => review(p, "modified")} className="btn btn-primary">
                      <Pencil size={12} /> Modify & Accept
                    </button>
                    <button disabled={submitting === p.item.id} onClick={() => review(p, "rejected")} className="btn btn-danger">
                      <XCircle size={12} /> Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
