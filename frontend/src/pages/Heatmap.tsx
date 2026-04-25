import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  api,
  type DepartmentSummary,
  type MatrixCell,
  type MonthlyPoint,
} from "../api/client";

// ── Constants ─────────────────────────────────────────────────────────────────

const CHANGE_TYPE_LABELS: Record<string, string> = {
  new_requirement:   "New Req.",
  limit_modification:"Limit Mod.",
  repeal:            "Repeal",
  clarification:     "Clarification",
  deadline:          "Deadline",
  other:             "Other",
};

const CHANGE_TYPES = Object.keys(CHANGE_TYPE_LABELS);

// Departments shown in canonical order (zero-padded if no data)
const DEPT_ORDER = ["AML", "Risk", "Compliance", "Legal", "Treasury", "IT"];

// ── Heat color scale (0 → 1 → churn_score or count/maxCount) ─────────────────
function heatColor(intensity: number): string {
  if (intensity <= 0) return "rgba(0,51,102,0.04)";
  if (intensity < 0.15) return "rgba(0,51,102,0.12)";
  if (intensity < 0.30) return "rgba(0,51,102,0.25)";
  if (intensity < 0.50) return "rgba(0,51,102,0.42)";
  if (intensity < 0.70) return "rgba(0,51,102,0.62)";
  if (intensity < 0.85) return "rgba(0,51,102,0.78)";
  return "rgba(0,51,102,0.92)";
}

function textOnHeat(intensity: number): string {
  return intensity >= 0.50 ? "#fff" : "var(--dark)";
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function severityBar(d: DepartmentSummary) {
  const total = d.total || 1;
  return (
    <div className="flex h-1.5 w-full rounded overflow-hidden gap-px">
      <div style={{ width: `${(d.high / total) * 100}%`, background: "#003366" }} />
      <div style={{ width: `${(d.medium / total) * 100}%`, background: "#336699" }} />
      <div style={{ width: `${(d.low / total) * 100}%`, background: "#91B5D1" }} />
    </div>
  );
}

function pct(v: number) {
  return `${Math.round(v * 100)}%`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DeptCard({ d, max }: { d: DepartmentSummary; max: number }) {
  const intensity = max > 0 ? d.churn_score : 0;
  const bg = heatColor(intensity);
  const fg = textOnHeat(intensity);
  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-3 transition-all"
      style={{ background: bg, border: `1px solid rgba(0,51,102,${Math.max(0.08, intensity * 0.3)})` }}
    >
      <div className="flex items-start justify-between">
        <p
          className="font-display"
          style={{ fontSize: "15px", fontWeight: 500, color: fg, letterSpacing: "0.3px" }}
        >
          {d.department}
        </p>
        <span
          className="rounded px-2 py-0.5"
          style={{
            fontSize: "10px",
            fontFamily: "var(--fb)",
            fontWeight: 600,
            background: intensity >= 0.5 ? "rgba(255,255,255,.18)" : "rgba(0,51,102,.08)",
            color: fg,
            letterSpacing: "0.5px",
          }}
        >
          {d.total} impacts
        </span>
      </div>

      {/* Churn score */}
      <div>
        <p style={{ fontSize: "28px", fontWeight: 300, fontFamily: "var(--fd)", color: fg, lineHeight: 1 }}>
          {pct(d.churn_score)}
        </p>
        <p style={{ fontSize: "10px", color: fg, opacity: 0.65, fontFamily: "var(--fb)", letterSpacing: "0.5px", marginTop: "2px" }}>
          CHURN SCORE
        </p>
      </div>

      {/* Severity bar */}
      {severityBar(d)}

      {/* Pill row */}
      <div className="flex gap-2 flex-wrap">
        {[
          { label: `${d.high} high`, visible: d.high > 0, strong: true },
          { label: `${d.medium} med`, visible: d.medium > 0, strong: false },
          { label: `${d.recent_30d} recent`, visible: d.recent_30d > 0, strong: false },
        ].map(({ label, visible, strong }) =>
          visible ? (
            <span
              key={label}
              style={{
                fontSize: "10px",
                fontFamily: "var(--fb)",
                background: strong
                  ? (intensity >= 0.5 ? "rgba(255,255,255,.25)" : "rgba(0,51,102,.15)")
                  : (intensity >= 0.5 ? "rgba(255,255,255,.12)" : "rgba(0,51,102,.06)"),
                color: fg,
                borderRadius: "4px",
                padding: "2px 7px",
              }}
            >
              {label}
            </span>
          ) : null
        )}
      </div>
    </div>
  );
}

// ── Matrix component ──────────────────────────────────────────────────────────

function HeatMatrix({
  departments,
  matrix,
}: {
  departments: DepartmentSummary[];
  matrix: MatrixCell[];
}) {
  // Build lookup: dept+change_type → {count, severity_score}
  const lookup: Record<string, MatrixCell> = {};
  for (const cell of matrix) {
    lookup[`${cell.department}|${cell.change_type}`] = cell;
  }

  const maxCount = Math.max(1, ...matrix.map((c) => c.count));
  const depts = DEPT_ORDER.filter((d) =>
    departments.some((x) => x.department === d) || matrix.some((c) => c.department === d)
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "560px" }}>
        <thead>
          <tr>
            <th
              style={{
                padding: "8px 16px",
                textAlign: "left",
                fontSize: "10px",
                letterSpacing: "1.5px",
                fontFamily: "var(--fb)",
                fontWeight: 500,
                background: "var(--primary)",
                color: "rgba(255,255,255,.45)",
              }}
            >
              DEPT
            </th>
            {CHANGE_TYPES.map((ct) => (
              <th
                key={ct}
                style={{
                  padding: "8px 10px",
                  textAlign: "center",
                  fontSize: "10px",
                  letterSpacing: "0.8px",
                  fontFamily: "var(--fb)",
                  fontWeight: 500,
                  background: "var(--primary)",
                  color: "rgba(255,255,255,.45)",
                  minWidth: "80px",
                }}
              >
                {CHANGE_TYPE_LABELS[ct]}
              </th>
            ))}
            <th
              style={{
                padding: "8px 14px",
                textAlign: "center",
                fontSize: "10px",
                letterSpacing: "0.8px",
                fontFamily: "var(--fb)",
                fontWeight: 500,
                background: "var(--primary)",
                color: "rgba(255,255,255,.45)",
              }}
            >
              TOTAL
            </th>
          </tr>
        </thead>
        <tbody>
          {depts.map((dept, ri) => {
            const summary = departments.find((d) => d.department === dept);
            const rowTotal = summary?.total ?? 0;
            return (
              <tr
                key={dept}
                style={{ background: ri % 2 === 0 ? "#fff" : "var(--light)" }}
              >
                <td
                  style={{
                    padding: "10px 16px",
                    fontSize: "12px",
                    fontFamily: "var(--fb)",
                    fontWeight: 600,
                    color: "var(--dark)",
                    whiteSpace: "nowrap",
                    borderRight: "1px solid var(--primary-10)",
                  }}
                >
                  {dept}
                </td>
                {CHANGE_TYPES.map((ct) => {
                  const cell = lookup[`${dept}|${ct}`];
                  const count = cell?.count ?? 0;
                  const intensity = count / maxCount;
                  return (
                    <td
                      key={ct}
                      title={count > 0 ? `${count} impact${count !== 1 ? "s" : ""} — severity score ${cell?.severity_score.toFixed(1)}` : "No impacts"}
                      style={{
                        padding: "10px",
                        textAlign: "center",
                        background: heatColor(intensity),
                        color: textOnHeat(intensity),
                        fontSize: "12px",
                        fontFamily: "var(--fb)",
                        fontWeight: count > 0 ? 600 : 400,
                        borderLeft: "1px solid rgba(0,0,0,.04)",
                        transition: "background 0.2s",
                      }}
                    >
                      {count > 0 ? count : "—"}
                    </td>
                  );
                })}
                <td
                  style={{
                    padding: "10px 14px",
                    textAlign: "center",
                    fontSize: "12px",
                    fontFamily: "var(--fb)",
                    fontWeight: 700,
                    color: "var(--primary)",
                    borderLeft: "1px solid var(--primary-10)",
                  }}
                >
                  {rowTotal > 0 ? rowTotal : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Monthly sparkline bars ────────────────────────────────────────────────────

function MonthlyTrend({ data }: { data: MonthlyPoint[] }) {
  // Get unique sorted months
  const allMonths = [...new Set(data.map((d) => d.month))].sort();
  // Get unique departments that have any data
  const depts = DEPT_ORDER.filter((d) => data.some((r) => r.department === d));
  if (!allMonths.length || !depts.length) {
    return (
      <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
        No monthly data available yet.
      </p>
    );
  }

  const maxCount = Math.max(1, ...data.map((d) => d.count));

  const lookup: Record<string, number> = {};
  for (const row of data) {
    lookup[`${row.department}|${row.month}`] = row.count;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "460px" }}>
        <thead>
          <tr>
            <th
              style={{
                padding: "8px 16px",
                textAlign: "left",
                fontSize: "10px",
                letterSpacing: "1.5px",
                fontFamily: "var(--fb)",
                fontWeight: 500,
                background: "var(--primary)",
                color: "rgba(255,255,255,.45)",
              }}
            >
              DEPT
            </th>
            {allMonths.map((m) => (
              <th
                key={m}
                style={{
                  padding: "8px 10px",
                  textAlign: "center",
                  fontSize: "10px",
                  fontFamily: "var(--fb)",
                  fontWeight: 500,
                  background: "var(--primary)",
                  color: "rgba(255,255,255,.45)",
                  minWidth: "70px",
                }}
              >
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {depts.map((dept, ri) => (
            <tr key={dept} style={{ background: ri % 2 === 0 ? "#fff" : "var(--light)" }}>
              <td
                style={{
                  padding: "10px 16px",
                  fontSize: "12px",
                  fontFamily: "var(--fb)",
                  fontWeight: 600,
                  color: "var(--dark)",
                  whiteSpace: "nowrap",
                  borderRight: "1px solid var(--primary-10)",
                }}
              >
                {dept}
              </td>
              {allMonths.map((m) => {
                const count = lookup[`${dept}|${m}`] ?? 0;
                const intensity = count / maxCount;
                const barH = Math.round(intensity * 28) + 4;
                return (
                  <td
                    key={m}
                    style={{
                      padding: "6px 10px",
                      textAlign: "center",
                      verticalAlign: "bottom",
                      borderLeft: "1px solid rgba(0,0,0,.04)",
                    }}
                  >
                    {count > 0 ? (
                      <div className="flex flex-col items-center gap-0.5">
                        <span style={{ fontSize: "10px", color: "var(--mid)", fontFamily: "var(--fb)" }}>
                          {count}
                        </span>
                        <div
                          style={{
                            width: "28px",
                            height: `${barH}px`,
                            background: heatColor(intensity),
                            borderRadius: "3px 3px 0 0",
                          }}
                        />
                      </div>
                    ) : (
                      <span style={{ fontSize: "10px", color: "rgba(0,0,0,.15)", fontFamily: "var(--fb)" }}>—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Heatmap() {
  const [departments, setDepartments] = useState<DepartmentSummary[]>([]);
  const [matrix, setMatrix] = useState<MatrixCell[]>([]);
  const [monthly, setMonthly] = useState<MonthlyPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [d, m, t] = await Promise.all([
        api.heatmap.departments(),
        api.heatmap.matrix(),
        api.heatmap.trend(6),
      ]);
      setDepartments(d);
      setMatrix(m);
      setMonthly(t);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const maxChurn = Math.max(...departments.map((d) => d.churn_score), 0.01);
  const totalImpacts = departments.reduce((s, d) => s + d.total, 0);
  const hottestDept = departments[0]?.department ?? "—";

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-8 py-5">
        <h1 className="font-display text-white" style={{ fontSize: "32px", fontWeight: 400 }}>
          Risk{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Heatmap</em>
        </h1>
        <p className="mt-2 font-body text-white/50" style={{ fontSize: "14px" }}>
          Which business departments are most exposed to regulatory churn.
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

          {/* Summary row */}
          <div>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="eyebrow mb-1.5">Exposure summary</p>
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Regulatory impact distributed across your business departments.
                </p>
              </div>
              <button onClick={load} className="btn btn-ghost" style={{ fontSize: "12px" }}>
                Refresh →
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div
                className="rounded-xl bg-white shadow-sm px-5 py-4 flex flex-col gap-0.5"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <p className="font-display leading-none" style={{ fontSize: "28px", fontWeight: 300, color: "var(--dark)" }}>
                  {totalImpacts}
                </p>
                <p className="opb-label" style={{ color: "var(--mid)" }}>Total Impacts</p>
              </div>
              <div
                className="rounded-xl bg-white shadow-sm px-5 py-4 flex flex-col gap-0.5"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <p className="font-display leading-none" style={{ fontSize: "28px", fontWeight: 300, color: "var(--dark)" }}>
                  {hottestDept}
                </p>
                <p className="opb-label" style={{ color: "var(--mid)" }}>Highest Churn Dept.</p>
              </div>
              <div
                className="rounded-xl bg-white shadow-sm px-5 py-4 flex flex-col gap-0.5"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <p className="font-display leading-none" style={{ fontSize: "28px", fontWeight: 300, color: "var(--dark)" }}>
                  {departments.reduce((s, d) => s + d.recent_30d, 0)}
                </p>
                <p className="opb-label" style={{ color: "var(--mid)" }}>New (last 30 days)</p>
              </div>
            </div>

            {/* Department heat cards */}
            {departments.length === 0 ? (
              <div
                className="rounded-xl bg-white flex flex-col items-center justify-center gap-3 py-16"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  No impact data yet. Run the pipeline (Steps 01–03) to generate alerts.
                </p>
              </div>
            ) : (
              <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
                {departments.map((d) => (
                  <DeptCard key={d.department} d={d} max={maxChurn} />
                ))}
              </div>
            )}
          </div>

          {departments.length > 0 && (
            <>
              <div className="section-divider" />

              {/* Impact matrix */}
              <div>
                <p className="eyebrow mb-1.5">Department × Change type matrix</p>
                <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Each cell shows the number of impact items at the intersection of department and change type. Darker = more exposure.
                </p>
                <div
                  className="rounded-xl overflow-hidden shadow-sm"
                  style={{ border: "1px solid var(--primary-10)" }}
                >
                  <HeatMatrix departments={departments} matrix={matrix} />
                </div>

                {/* Legend */}
                <div className="flex items-center gap-3 mt-3">
                  <span className="font-body" style={{ fontSize: "11px", color: "var(--mid)" }}>Intensity:</span>
                  {[0, 0.15, 0.35, 0.55, 0.75, 0.92].map((v) => (
                    <div
                      key={v}
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: 3,
                        background: heatColor(v),
                        border: "1px solid rgba(0,0,102,.08)",
                      }}
                    />
                  ))}
                  <span className="font-body" style={{ fontSize: "11px", color: "var(--mid)" }}>Low → High</span>
                </div>
              </div>

              <div className="section-divider" />

              {/* Monthly trend */}
              <div>
                <p className="eyebrow mb-1.5">Monthly churn trend</p>
                <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Impact count per department over the last 6 months. Taller bars mean higher regulatory activity.
                </p>
                <div
                  className="rounded-xl overflow-hidden shadow-sm"
                  style={{ border: "1px solid var(--primary-10)" }}
                >
                  <MonthlyTrend data={monthly} />
                </div>
              </div>
            </>
          )}

        </div>
      )}
    </div>
  );
}
