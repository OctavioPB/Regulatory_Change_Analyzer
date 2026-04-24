import { useEffect, useState, useCallback } from "react";
import { api, type ImpactAlert } from "../api/client";
import { AlertsTable } from "../components/AlertsTable";
import { AlertDrawer } from "../components/AlertDrawer";

export function Alerts() {
  const [alerts, setAlerts] = useState<ImpactAlert[]>([]);
  const [selected, setSelected] = useState<ImpactAlert | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setAlerts(await api.alerts.list(unreadOnly));
    } finally {
      setLoading(false);
    }
  }, [unreadOnly]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Alerts</h1>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Unread only
        </label>
      </div>

      {loading ? (
        <p className="text-center text-sm text-gray-400 py-12">Loading…</p>
      ) : (
        <AlertsTable
          alerts={alerts}
          onSelect={(a) => {
            setSelected(a);
            setAlerts((prev) =>
              prev.map((x) => (x.id === a.id ? { ...x, is_read: true } : x))
            );
          }}
        />
      )}

      {selected && (
        <AlertDrawer
          alert={selected}
          onClose={() => setSelected(null)}
          onReviewed={() => {
            setSelected(null);
            load();
          }}
        />
      )}
    </div>
  );
}
