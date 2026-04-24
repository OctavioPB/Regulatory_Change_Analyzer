import { useEffect, useState, useCallback } from "react";
import { Bell, FileText, AlertTriangle, ClipboardCheck } from "lucide-react";
import { api, type DashboardStats, type ImpactAlert } from "../api/client";
import { StatsCard } from "../components/StatsCard";
import { AlertsTable } from "../components/AlertsTable";
import { AlertDrawer } from "../components/AlertDrawer";

export function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [alerts, setAlerts] = useState<ImpactAlert[]>([]);
  const [selected, setSelected] = useState<ImpactAlert | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, a] = await Promise.all([api.stats(), api.alerts.list()]);
      setStats(s);
      setAlerts(a);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleSelect(alert: ImpactAlert) {
    setSelected(alert);
    // Optimistically mark as read in the list
    setAlerts((prev) =>
      prev.map((a) => (a.id === alert.id ? { ...a, is_read: true } : a))
    );
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400">
        Loading…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
        <AlertTriangle size={32} className="text-red-400" />
        <p className="text-sm">{error}</p>
        <button
          onClick={load}
          className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">Dashboard</h1>
        <button
          onClick={load}
          className="rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatsCard
            label="Total Documents"
            value={stats.documents.total}
            sub={Object.entries(stats.documents.by_source)
              .map(([s, n]) => `${s}: ${n}`)
              .join(" · ")}
            icon={FileText}
            accent="blue"
          />
          <StatsCard
            label="Regulatory Changes"
            value={stats.changes.total}
            sub={`${stats.changes.by_type["limit_modification"] ?? 0} limit modifications`}
            icon={AlertTriangle}
            accent="amber"
          />
          <StatsCard
            label="Unread Alerts"
            value={stats.alerts.unread}
            sub={`${stats.alerts.total} total alerts`}
            icon={Bell}
            accent="red"
          />
          <StatsCard
            label="Pending Reviews"
            value={stats.impact_items.pending_review}
            sub={`${stats.impact_items.total} total items`}
            icon={ClipboardCheck}
            accent="green"
          />
        </div>
      )}

      {/* Severity breakdown */}
      {stats && stats.impact_items.total > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-semibold text-gray-700 mb-3">Impact items by severity</p>
          <div className="flex gap-4">
            {(["high", "medium", "low"] as const).map((sev) => {
              const count = stats.impact_items.by_severity[sev] ?? 0;
              const total = stats.impact_items.total;
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;
              const colors = {
                high: "bg-red-500",
                medium: "bg-amber-400",
                low: "bg-green-400",
              };
              return (
                <div key={sev} className="flex items-center gap-2 text-sm">
                  <div className={`h-3 w-3 rounded-full ${colors[sev]}`} />
                  <span className="text-gray-600 capitalize">{sev}</span>
                  <span className="font-semibold text-gray-900">{count}</span>
                  <span className="text-gray-400">({pct}%)</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Alerts feed */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Recent Alerts</h2>
        <AlertsTable alerts={alerts.slice(0, 20)} onSelect={handleSelect} />
      </div>

      {/* Detail drawer */}
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
