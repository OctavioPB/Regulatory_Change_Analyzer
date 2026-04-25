import { useState } from "react";
import { X, CheckCircle, XCircle, Pencil, ChevronDown, ChevronUp, Download } from "lucide-react";
import type { ApprovalStatus, ImpactAlert, ImpactItem } from "../api/client";
import { api } from "../api/client";
import { SeverityBadge } from "./SeverityBadge";
import { StatusBadge } from "./StatusBadge";

interface Props {
  alert: ImpactAlert;
  onClose: () => void;
  onReviewed: () => void;
}

interface ReviewState {
  itemId: string;
  notes: string;
}

export function AlertDrawer({ alert, onClose, onReviewed }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<ReviewState | null>(null);
  const [loading, setLoading] = useState(false);

  async function submitReview(item: ImpactItem, status: ApprovalStatus) {
    setLoading(true);
    try {
      await api.alerts.review(
        alert.id, item.id, status,
        reviewing?.itemId === item.id ? reviewing.notes : undefined
      );
      onReviewed();
    } finally {
      setLoading(false);
      setReviewing(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      <div className="relative z-10 flex w-full max-w-2xl flex-col bg-white shadow-2xl">
        {/* Top accent bar */}
        <div className="accent-bar" />

        {/* Header */}
        <div
          className="px-6 py-4 flex items-start justify-between"
          style={{ borderBottom: "1px solid var(--primary-10)" }}
        >
          <div className="flex-1 pr-4">
            <p className="eyebrow mb-1">Impact Detail</p>
            <h2
              className="font-display leading-snug"
              style={{ fontSize: "18px", fontWeight: 400, color: "var(--dark)" }}
            >
              {alert.title}
            </h2>
            <p className="mt-1 font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
              {new Date(alert.created_at).toLocaleString()} · {alert.items.length} impact item
              {alert.items.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <a href={api.export.alertXlsx(alert.id)} download className="btn btn-ghost" title="Download Excel">
              <Download size={14} /> XLS
            </a>
            <a href={api.export.alertPdf(alert.id)} download className="btn btn-ghost" title="Download PDF">
              <Download size={14} /> PDF
            </a>
            <button onClick={onClose} className="btn btn-ghost ml-1" style={{ padding: "7px 10px" }}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {alert.items.length === 0 && (
            <p className="text-center py-10 font-body" style={{ color: "var(--mid)", fontSize: "14px" }}>
              No impact items for this alert.
            </p>
          )}

          {alert.items.map((item) => (
            <div
              key={item.id}
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid var(--primary-10)" }}
            >
              <button
                className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-opb-light"
                onClick={() => setExpanded(expanded === item.id ? null : item.id)}
              >
                <div className="flex items-center gap-2 flex-wrap">
                  <SeverityBadge severity={item.severity} />
                  <StatusBadge status={item.approval_status} />
                  <span className="font-body font-medium" style={{ fontSize: "14px", color: "var(--dark)" }}>
                    {item.affected_name}
                  </span>
                  {item.affected_ref && (
                    <span className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      · {item.affected_ref}
                    </span>
                  )}
                </div>
                {expanded === item.id
                  ? <ChevronUp size={13} style={{ color: "var(--mid)" }} className="shrink-0" />
                  : <ChevronDown size={13} style={{ color: "var(--mid)" }} className="shrink-0" />}
              </button>

              {expanded === item.id && (
                <div
                  className="px-4 pb-4 pt-3"
                  style={{ borderTop: "1px solid var(--primary-10)", background: "var(--primary-10)" }}
                >
                  <p className="opb-label text-opb-mid mb-1.5">Suggested action</p>
                  <p className="font-body" style={{ fontSize: "14px", color: "var(--dark)", lineHeight: "1.7" }}>
                    {item.suggestion}
                  </p>

                  {item.reviewer_notes && (
                    <div
                      className="mt-3 rounded-lg px-3 py-2 font-body"
                      style={{ background: "var(--primary-10)", fontSize: "13px", color: "var(--primary-80)" }}
                    >
                      <span className="font-semibold">Notes: </span>
                      {item.reviewer_notes}
                    </div>
                  )}

                  {reviewing?.itemId === item.id && (
                    <textarea
                      className="mt-3 w-full rounded-lg px-3 py-2 font-body focus:outline-none"
                      style={{
                        border: "1px solid var(--primary-30)",
                        fontSize: "13px",
                        background: "var(--white)",
                        color: "var(--dark)",
                      }}
                      rows={2}
                      placeholder="Reviewer notes (optional)"
                      value={reviewing.notes}
                      onChange={(e) => setReviewing({ itemId: item.id, notes: e.target.value })}
                    />
                  )}

                  {item.approval_status === "pending" && (
                    <div className="mt-3 flex gap-2 flex-wrap">
                      <button disabled={loading} onClick={() => submitReview(item, "approved")} className="btn btn-success">
                        <CheckCircle size={12} /> Approve
                      </button>
                      <button
                        disabled={loading}
                        onClick={() =>
                          reviewing?.itemId === item.id
                            ? submitReview(item, "modified")
                            : setReviewing({ itemId: item.id, notes: "" })
                        }
                        className="btn btn-primary"
                      >
                        <Pencil size={12} />
                        {reviewing?.itemId === item.id ? "Save" : "Modify"}
                      </button>
                      <button disabled={loading} onClick={() => submitReview(item, "rejected")} className="btn btn-danger">
                        <XCircle size={12} /> Reject
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
