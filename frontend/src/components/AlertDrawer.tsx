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
        alert.id,
        item.id,
        status,
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
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />

      {/* Drawer panel */}
      <div className="relative z-10 flex w-full max-w-2xl flex-col bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-200 px-6 py-4">
          <div className="flex-1 pr-4">
            <h2 className="text-base font-semibold text-gray-900 leading-snug">
              {alert.title}
            </h2>
            <p className="mt-1 text-xs text-gray-400">
              {new Date(alert.created_at).toLocaleString()} · {alert.items.length} impact item
              {alert.items.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <a
              href={api.export.alertXlsx(alert.id)}
              download
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-green-600"
              title="Download Excel"
            >
              <Download size={16} />
            </a>
            <a
              href={api.export.alertPdf(alert.id)}
              download
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-red-600"
              title="Download PDF"
            >
              <Download size={16} />
            </a>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Items list */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {alert.items.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-10">
              No impact items for this alert.
            </p>
          )}

          {alert.items.map((item) => (
            <div
              key={item.id}
              className="rounded-lg border border-gray-200 bg-gray-50"
            >
              {/* Item header */}
              <button
                className="flex w-full items-center justify-between px-4 py-3 text-left"
                onClick={() => setExpanded(expanded === item.id ? null : item.id)}
              >
                <div className="flex items-center gap-3">
                  <SeverityBadge severity={item.severity} />
                  <StatusBadge status={item.approval_status} />
                  <span className="text-sm font-medium text-gray-800">
                    {item.affected_name}
                  </span>
                  {item.affected_ref && (
                    <span className="text-xs text-gray-400">· {item.affected_ref}</span>
                  )}
                </div>
                {expanded === item.id ? (
                  <ChevronUp size={14} className="text-gray-400 shrink-0" />
                ) : (
                  <ChevronDown size={14} className="text-gray-400 shrink-0" />
                )}
              </button>

              {/* Expanded suggestion + actions */}
              {expanded === item.id && (
                <div className="border-t border-gray-200 px-4 pb-4 pt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
                    Suggestion
                  </p>
                  <p className="text-sm text-gray-700 leading-relaxed">{item.suggestion}</p>

                  {item.reviewer_notes && (
                    <div className="mt-3 rounded-md bg-blue-50 px-3 py-2 text-xs text-blue-700">
                      <span className="font-semibold">Notes: </span>
                      {item.reviewer_notes}
                    </div>
                  )}

                  {/* Notes input when modifying */}
                  {reviewing?.itemId === item.id && (
                    <textarea
                      className="mt-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={2}
                      placeholder="Reviewer notes (optional)"
                      value={reviewing.notes}
                      onChange={(e) => setReviewing({ itemId: item.id, notes: e.target.value })}
                    />
                  )}

                  {/* Action buttons */}
                  {item.approval_status === "pending" && (
                    <div className="mt-3 flex gap-2">
                      <button
                        disabled={loading}
                        onClick={() => submitReview(item, "approved")}
                        className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        <CheckCircle size={13} />
                        Approve
                      </button>
                      <button
                        disabled={loading}
                        onClick={() =>
                          reviewing?.itemId === item.id
                            ? submitReview(item, "modified")
                            : setReviewing({ itemId: item.id, notes: "" })
                        }
                        className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        <Pencil size={13} />
                        {reviewing?.itemId === item.id ? "Save" : "Modify"}
                      </button>
                      <button
                        disabled={loading}
                        onClick={() => submitReview(item, "rejected")}
                        className="flex items-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        <XCircle size={13} />
                        Reject
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
