import { useEffect, useState, useCallback } from "react";
import { api, type AuditEntry } from "../api/client";
import { Eyebrow } from "../components/Eyebrow";

const actionStyle: Record<string, { bg: string; text: string }> = {
  document_ingested:    { bg: "var(--primary-10)", text: "var(--primary)" },
  document_analyzed:    { bg: "#F0EBF9",           text: "#3D1F70" },
  document_seeded:      { bg: "var(--primary-10)", text: "var(--primary)" },
  impact_alert_created: { bg: "#FEF0E6",           text: "#7A3800" },
  item_approved:        { bg: "#E0F7EF",           text: "#0D5C3A" },
  item_modified:        { bg: "#F0EBF9",           text: "#3D1F70" },
  item_rejected:        { bg: "#FDEAEA",           text: "#7A1020" },
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
    try { setEntries(await api.audit.list(entityType || undefined)); }
    finally { setLoading(false); }
  }, [entityType]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-6 py-4">
        <Eyebrow light>Activity Log</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Audit{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Trail</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Every system action and reviewer decision, logged chronologically.
        </p>
      </div>

      <div className="section-divider" />

      <div className="px-6 py-5 flex flex-col gap-5">
        {/* Controls */}
        <div className="flex items-start justify-between">
          <div>
            <p className="eyebrow mb-1.5">Event log</p>
            <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
              Immutable record of every system action and reviewer decision, ordered chronologically.
            </p>
          </div>
          <select
            className="rounded-lg px-3 py-1.5 font-body focus:outline-none"
            style={{
              border: "1px solid var(--primary-30)",
              fontSize: "13px",
              color: "var(--dark)",
              background: "var(--white)",
            }}
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
          >
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>{t || "All entities"}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <p className="text-center py-12 font-body" style={{ color: "var(--mid)", fontSize: "14px" }}>
            Loading…
          </p>
        ) : entries.length === 0 ? (
          <div
            className="rounded-xl py-16 text-center font-body"
            style={{ border: "1px dashed var(--primary-30)", color: "var(--mid)", fontSize: "14px" }}
          >
            No audit entries found.
          </div>
        ) : (
          <div
            className="overflow-hidden rounded-xl bg-white shadow-sm"
            style={{ border: "1px solid var(--primary-10)" }}
          >
            <table className="w-full" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "var(--primary)" }}>
                  {["Time", "Actor", "Action", "Entity", "Detail"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-white"
                      style={{ fontSize: "10px", letterSpacing: "2px", textTransform: "uppercase", fontFamily: "var(--fb)", fontWeight: 500 }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {entries.map((e, idx) => (
                  <tr
                    key={e.id}
                    style={{
                      background: idx % 2 === 0 ? "var(--white)" : "var(--primary-10)",
                      borderBottom: "1px solid var(--primary-10)",
                    }}
                  >
                    <td className="px-4 py-2.5 whitespace-nowrap font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      {fmtDate(e.created_at)}
                    </td>
                    <td className="px-4 py-2.5 font-body font-medium" style={{ fontSize: "13px", color: "var(--dark)" }}>
                      {e.actor}
                    </td>
                    <td className="px-4 py-2.5">
                      {(() => {
                        const s = actionStyle[e.action] ?? { bg: "var(--light)", text: "var(--mid)" };
                        return (
                          <span
                            className="opb-badge"
                            style={{ background: s.bg, color: s.text }}
                          >
                            {e.action.replace(/_/g, " ")}
                          </span>
                        );
                      })()}
                    </td>
                    <td className="px-4 py-2.5 font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      {e.entity_type && (
                        <span>
                          {e.entity_type}
                          {e.entity_id && (
                            <span className="ml-1" style={{ fontFamily: "Courier New", fontSize: "11px", color: "var(--primary-30)" }}>
                              {e.entity_id.slice(0, 8)}…
                            </span>
                          )}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-body max-w-xs truncate" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      {e.detail}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
