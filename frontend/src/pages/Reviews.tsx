import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, Pencil, ClipboardCheck } from "lucide-react";
import { api, type ApprovalStatus, type ImpactAlert, type ImpactItem } from "../api/client";
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
          if (item.approval_status === "pending") {
            items.push({ alert, item });
          }
        }
      }
      setPending(items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        <ClipboardCheck size={20} className="text-blue-600" />
        <h1 className="text-xl font-bold text-gray-900">Pending Reviews</h1>
        <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
          {pending.length}
        </span>
      </div>

      {loading ? (
        <p className="text-center text-sm text-gray-400 py-12">Loading…</p>
      ) : pending.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 py-16 text-center text-gray-400">
          <CheckCircle size={32} className="mx-auto mb-2 text-green-400" />
          All impact items have been reviewed.
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((p) => (
            <div
              key={p.item.id}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              {/* Context header */}
              <p className="text-xs text-gray-400 mb-2 truncate">{p.alert.title}</p>

              {/* Item info */}
              <div className="flex items-center gap-2 mb-2">
                <SeverityBadge severity={p.item.severity} />
                <StatusBadge status={p.item.approval_status} />
                <span className="text-sm font-medium text-gray-800">{p.item.affected_name}</span>
                {p.item.affected_ref && (
                  <span className="text-xs text-gray-400">· {p.item.affected_ref}</span>
                )}
              </div>

              <p className="text-sm text-gray-700 leading-relaxed mb-3">{p.item.suggestion}</p>

              {/* Notes */}
              <textarea
                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
                rows={2}
                placeholder="Reviewer notes (optional)"
                value={notes[p.item.id] ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [p.item.id]: e.target.value }))}
              />

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  disabled={submitting === p.item.id}
                  onClick={() => review(p, "approved")}
                  className="flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle size={13} /> Approve
                </button>
                <button
                  disabled={submitting === p.item.id}
                  onClick={() => review(p, "modified")}
                  className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Pencil size={13} /> Modify & Accept
                </button>
                <button
                  disabled={submitting === p.item.id}
                  onClick={() => review(p, "rejected")}
                  className="flex items-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  <XCircle size={13} /> Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
