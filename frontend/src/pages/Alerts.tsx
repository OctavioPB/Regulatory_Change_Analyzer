import { useEffect, useState, useCallback } from "react";
import { api, type ImpactAlert } from "../api/client";
import { AlertsTable } from "../components/AlertsTable";
import { AlertDrawer } from "../components/AlertDrawer";
import { Eyebrow } from "../components/Eyebrow";

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

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-6 py-4">
        <Eyebrow light>Impact Monitoring</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Impact{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Alerts</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Regulatory changes mapped to your contracts and processes.
        </p>
      </div>

      <div className="section-divider" />

      <div className="px-6 py-5 flex flex-col gap-5">
        {/* Controls */}
        <div className="flex items-start justify-between">
          <div>
            <p className="eyebrow mb-1.5">Alert registry</p>
            <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
              Every impact alert mapped to your contracts and processes, newest first.
            </p>
          </div>
          <label
            className="flex items-center gap-2 cursor-pointer font-body"
            style={{ fontSize: "13px", color: "var(--mid)" }}
          >
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
              className="rounded"
              style={{ accentColor: "var(--primary)" }}
            />
            Unread only
          </label>
        </div>

        {loading ? (
          <p className="text-center py-12 font-body" style={{ color: "var(--mid)", fontSize: "14px" }}>
            Loading…
          </p>
        ) : (
          <AlertsTable
            alerts={alerts}
            onSelect={(a) => {
              setSelected(a);
              setAlerts((prev) => prev.map((x) => (x.id === a.id ? { ...x, is_read: true } : x)));
            }}
          />
        )}
      </div>

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
