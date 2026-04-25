import { useEffect, useState, useCallback } from "react";
import { AlertTriangle } from "lucide-react";
import { api, type DashboardStats, type ImpactAlert } from "../api/client";
import { StatsCard } from "../components/StatsCard";
import { AlertsTable } from "../components/AlertsTable";
import { AlertDrawer } from "../components/AlertDrawer";

const barGradients: Record<string, string> = {
  high:   "linear-gradient(90deg, #003366, #1A4D80)",
  medium: "linear-gradient(90deg, #1A4D80, #336699)",
  low:    "linear-gradient(90deg, #336699, #4A7FAA)",
};

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

  useEffect(() => { load(); }, [load]);

  function handleSelect(alert: ImpactAlert) {
    setSelected(alert);
    setAlerts((prev) => prev.map((a) => (a.id === alert.id ? { ...a, is_read: true } : a)));
  }

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-8 py-5">
        <h1
          className="font-display text-white"
          style={{ fontSize: "32px", fontWeight: 400 }}
        >
          Regulatory{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Intelligence</em>
        </h1>
        <p className="mt-2 font-body text-white/50" style={{ fontSize: "14px" }}>
          Live view of monitored sources, detected changes, and pending compliance actions.
        </p>
      </div>

      <div className="section-divider" />

      {loading ? (
        <div className="flex items-center justify-center py-24 font-body" style={{ color: "var(--mid)" }}>
          Loading…
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center gap-3 py-24">
          <AlertTriangle size={28} style={{ color: "#E03448" }} />
          <p className="font-body" style={{ fontSize: "14px", color: "var(--mid)" }}>{error}</p>
          <button onClick={load} className="btn btn-primary">Retry →</button>
        </div>
      ) : (
        <div className="flex flex-col gap-8 px-8 py-8">
          {/* KPI row */}
          <div>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="eyebrow mb-1.5">Key metrics</p>
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Live totals across all monitored regulatory sources and your document inventory.
                </p>
              </div>
              <button onClick={load} className="btn btn-ghost" style={{ fontSize: "12px" }}>
                Refresh →
              </button>
            </div>
            {stats && (
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatsCard
                  label="Total Documents"
                  value={stats.documents.total}
                  sub={Object.entries(stats.documents.by_source).map(([s, n]) => `${s}: ${n}`).join(" · ")}
                />
                <StatsCard
                  label="Regulatory Changes"
                  value={stats.changes.total}
                  sub={`${stats.changes.by_type["limit_modification"] ?? 0} limit modifications`}
                />
                <StatsCard
                  label="Unread Alerts"
                  value={stats.alerts.unread}
                  sub={`${stats.alerts.total} total alerts`}
                />
                <StatsCard
                  label="Pending Reviews"
                  value={stats.impact_items.pending_review}
                  sub={`${stats.impact_items.total} total items`}
                />
              </div>
            )}
          </div>

          <div className="section-divider" />

          {/* Severity breakdown */}
          {stats && stats.impact_items.total > 0 && (
            <>
              <div>
                <p className="eyebrow mb-1.5">Impact distribution</p>
                <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Proportion of active impact items grouped by severity rating.
                </p>
                <div className="rounded-xl bg-white p-6 shadow-sm" style={{ border: "1px solid var(--primary-10)" }}>
                  <div className="flex flex-col gap-3">
                    {(["high", "medium", "low"] as const).map((sev) => {
                      const count = stats.impact_items.by_severity[sev] ?? 0;
                      const total = stats.impact_items.total;
                      const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                      const color = barGradients[sev];
                      return (
                        <div key={sev} className="flex items-center gap-3">
                          <span
                            className="opb-label w-16 shrink-0"
                            style={{ color: "var(--mid)" }}
                          >
                            {sev.toUpperCase()}
                          </span>
                          <div
                            className="flex-1 rounded"
                            style={{ background: "var(--light)", height: "20px" }}
                          >
                            <div
                              className="h-full rounded flex items-center justify-end pr-2"
                              style={{ width: `${pct}%`, background: color, minWidth: count > 0 ? "2rem" : 0 }}
                            >
                              {pct > 0 && (
                                <span style={{ color: "#fff", fontSize: "10px", fontFamily: "var(--fb)" }}>
                                  {pct}%
                                </span>
                              )}
                            </div>
                          </div>
                          <span className="font-display w-8 text-right" style={{ fontSize: "18px", fontWeight: 300, color: "var(--dark)" }}>
                            {count}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              <div className="section-divider" />
            </>
          )}

          {/* Alerts feed */}
          <div>
            <p className="eyebrow mb-1.5">Recent alerts</p>
            <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
              The twenty most recent alerts generated from detected regulatory changes.
            </p>
            <AlertsTable alerts={alerts.slice(0, 20)} onSelect={handleSelect} />
          </div>
        </div>
      )}

      {selected && (
        <AlertDrawer
          alert={selected}
          onClose={() => setSelected(null)}
          onReviewed={() => { setSelected(null); load(); }}
        />
      )}
    </div>
  );
}
