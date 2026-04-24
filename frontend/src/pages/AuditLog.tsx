import { useEffect, useState, useCallback } from "react";
import { ShieldCheck } from "lucide-react";
import { api, type AuditEntry } from "../api/client";

const actionColour: Record<string, string> = {
  document_ingested: "bg-blue-100 text-blue-700",
  document_analyzed: "bg-purple-100 text-purple-700",
  impact_alert_created: "bg-amber-100 text-amber-700",
  item_approved: "bg-green-100 text-green-700",
  item_modified: "bg-sky-100 text-sky-700",
  item_rejected: "bg-red-100 text-red-700",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const ENTITY_TYPES = ["", "RegulatoryDocument", "ImpactAlert", "ImpactItem"];

export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [entityType, setEntityType] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEntries(await api.audit.list(entityType || undefined));
    } finally {
      setLoading(false);
    }
  }, [entityType]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck size={20} className="text-blue-600" />
          <h1 className="text-xl font-bold text-gray-900">Audit Trail</h1>
        </div>
        <select
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t || "All entities"}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-center text-sm text-gray-400 py-12">Loading…</p>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-300 py-16 text-center text-gray-400">
          No audit entries found.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {entries.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap text-xs">
                    {fmtDate(e.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 font-medium">{e.actor}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        actionColour[e.action] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {e.action.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-500">
                    {e.entity_type && (
                      <span>
                        {e.entity_type}
                        {e.entity_id && (
                          <span className="ml-1 font-mono text-gray-400">
                            {e.entity_id.slice(0, 8)}…
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-400 max-w-xs truncate">
                    {e.detail}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
