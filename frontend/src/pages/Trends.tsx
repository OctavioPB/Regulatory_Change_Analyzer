import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, TrendingUp } from "lucide-react";
import { api, type DomainForecast, type TrendSignal, type TrendStats } from "../api/client";
import { Eyebrow } from "../components/Eyebrow";

// ── Helpers ───────────────────────────────────────────────────────────────────

const DOC_TYPE_LABEL: Record<string, string> = {
  proposed_rule:    "Proposed Rule",
  no_action_letter: "No-Action Letter",
  interim_rule:     "Interim Rule",
  final_rule:       "Final Rule",
  guidance:         "Guidance",
  other:            "Other",
};

const DOC_TYPE_COLOR: Record<string, string> = {
  proposed_rule:    "#1A4D80",
  no_action_letter: "#C89B3C",
  interim_rule:     "#27B97C",
  guidance:         "#4A7FAA",
  final_rule:       "#6B7280",
  other:            "#9CA3AF",
};

function domainLabel(d: string) {
  return d.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function pct(v: number) {
  return `${Math.round(v * 100)}%`;
}

function horizonLabel(months: number) {
  if (months <= 3) return "< 3 months";
  if (months <= 6) return "3–6 months";
  if (months <= 12) return "6–12 months";
  return "> 12 months";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatPill({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div
      className="rounded-xl bg-white shadow-sm px-5 py-4 flex flex-col gap-0.5"
      style={{ border: "1px solid var(--primary-10)" }}
    >
      <p className="font-display leading-none" style={{ fontSize: "28px", fontWeight: 300, color: "var(--dark)" }}>
        {value}
      </p>
      <p className="opb-label" style={{ color: "var(--mid)" }}>{label}</p>
      {sub && <p style={{ fontSize: "11px", color: "var(--mid)" }}>{sub}</p>}
    </div>
  );
}

function DocTypeBadge({ type }: { type: string }) {
  return (
    <span
      className="inline-block rounded px-2 py-0.5"
      style={{
        background: DOC_TYPE_COLOR[type] ?? "#9CA3AF",
        color: "#fff",
        fontSize: "10px",
        fontFamily: "var(--fb)",
        letterSpacing: "0.4px",
        fontWeight: 500,
        whiteSpace: "nowrap",
      }}
    >
      {DOC_TYPE_LABEL[type] ?? type}
    </span>
  );
}

function ConfidenceDot({ score }: { score: number }) {
  const color = score >= 0.7 ? "#27B97C" : score >= 0.5 ? "var(--gold)" : "#9CA3AF";
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        marginRight: 5,
        flexShrink: 0,
      }}
    />
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Trends() {
  const [stats, setStats] = useState<TrendStats | null>(null);
  const [forecast, setForecast] = useState<DomainForecast[]>([]);
  const [signals, setSignals] = useState<TrendSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [filterType, setFilterType] = useState<string>("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, f, sig] = await Promise.all([
        api.trends.stats(),
        api.trends.forecast(),
        api.trends.list(),
      ]);
      setStats(s);
      setForecast(f);
      setSignals(sig);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleExtractAll() {
    setExtracting(true);
    try {
      await api.trends.extractAll();
      setTimeout(() => { load(); setExtracting(false); }, 2000);
    } catch {
      setExtracting(false);
    }
  }

  const filtered = filterType
    ? signals.filter((s) => s.doc_type === filterType)
    : signals;

  const maxForecastStrength = Math.max(...forecast.map((f) => f.avg_strength), 0.01);

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-6 py-4">
        <Eyebrow light>Predictive Analysis</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Trend{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Analysis</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Predictive signals from Proposed Rules and No-Action Letters — 6 to 12 months ahead.
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
        <div className="flex flex-col gap-6 px-6 py-5">

          {/* KPI row */}
          <div>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="eyebrow mb-1.5">Signal summary</p>
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Extracted signals from forward-looking regulatory documents.
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={load} className="btn btn-ghost" style={{ fontSize: "12px" }}>
                  Refresh →
                </button>
                <button
                  onClick={handleExtractAll}
                  disabled={extracting}
                  className="btn btn-primary"
                >
                  {extracting ? "Extracting…" : "Extract all →"}
                </button>
              </div>
            </div>

            {stats && (
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatPill
                  label="Total Signals"
                  value={stats.total_signals}
                  sub="across all doc types"
                />
                <StatPill
                  label="Proposed Rules"
                  value={stats.by_doc_type["proposed_rule"] ?? 0}
                  sub="highest regulatory impact"
                />
                <StatPill
                  label="No-Action Letters"
                  value={stats.by_doc_type["no_action_letter"] ?? 0}
                  sub="market practice signals"
                />
                <StatPill
                  label="Top Domain"
                  value={stats.top_domain ? domainLabel(stats.top_domain) : "—"}
                  sub="by avg signal strength"
                />
              </div>
            )}
          </div>

          <div className="section-divider" />

          {/* Domain forecast chart */}
          {forecast.length > 0 && (
            <div>
              <p className="eyebrow mb-1.5">Domain forecast</p>
              <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Average regulatory signal strength per domain, sorted by intensity.
              </p>
              <div
                className="rounded-xl p-6 shadow-sm" style={{ background: "var(--white)" }}
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <div className="flex flex-col gap-4">
                  {forecast.slice(0, 8).map((row) => {
                    const barPct = Math.round((row.avg_strength / maxForecastStrength) * 100);
                    return (
                      <div key={row.domain} className="flex items-center gap-3">
                        <span
                          className="font-body shrink-0 text-right"
                          style={{ width: "170px", fontSize: "12px", color: "var(--mid)" }}
                        >
                          {domainLabel(row.domain)}
                        </span>
                        <div
                          className="flex-1 rounded"
                          style={{ background: "var(--light)", height: "22px" }}
                        >
                          <div
                            className="h-full rounded flex items-center justify-end pr-2"
                            style={{
                              width: `${barPct}%`,
                              background: "linear-gradient(90deg, #003366, #1A4D80)",
                              minWidth: "2rem",
                            }}
                          >
                            <span style={{ color: "#fff", fontSize: "10px", fontFamily: "var(--fb)" }}>
                              {pct(row.avg_strength)}
                            </span>
                          </div>
                        </div>
                        <span
                          className="shrink-0 font-body"
                          style={{ width: "80px", fontSize: "11px", color: "var(--mid)" }}
                        >
                          ~{row.avg_horizon_months}m horizon
                        </span>
                        <span
                          className="shrink-0 font-body"
                          style={{ width: "50px", fontSize: "11px", color: "var(--mid)", textAlign: "right" }}
                        >
                          {row.signal_count} sig.
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          <div className="section-divider" />

          {/* Signal list */}
          <div>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="eyebrow mb-1.5">Signal feed</p>
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Individual regulatory signals with type, domain, and horizon estimate.
                </p>
              </div>
              {/* Doc-type filter */}
              <div className="flex gap-2 flex-wrap justify-end">
                {["", "proposed_rule", "no_action_letter", "interim_rule", "guidance"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setFilterType(t)}
                    className={filterType === t ? "btn btn-primary" : "btn btn-outline"}
                    style={{ fontSize: "11px", padding: "5px 12px" }}
                  >
                    {t ? DOC_TYPE_LABEL[t] : "All"}
                  </button>
                ))}
              </div>
            </div>

            {filtered.length === 0 ? (
              <div
                className="rounded-xl bg-white flex flex-col items-center justify-center gap-3 py-16"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <TrendingUp size={28} style={{ color: "var(--primary-10)" }} />
                <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  No signals yet. Run "Extract all" to analyse your documents.
                </p>
              </div>
            ) : (
              <div
                className="rounded-xl overflow-hidden"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                {/* Table header */}
                <div
                  className="grid px-5 py-2"
                  style={{
                    gridTemplateColumns: "170px 140px 1fr 90px 80px 80px",
                    background: "var(--primary)",
                    gap: "12px",
                  }}
                >
                  {["Type", "Domain", "Themes", "Horizon", "Strength", "Confidence"].map((h) => (
                    <span
                      key={h}
                      className="opb-label"
                      style={{ color: "rgba(255,255,255,.5)", marginBottom: 0 }}
                    >
                      {h}
                    </span>
                  ))}
                </div>

                {/* Rows */}
                {filtered.map((sig, i) => (
                  <div
                    key={sig.id}
                    className="grid px-5 py-3 items-center"
                    style={{
                      gridTemplateColumns: "170px 140px 1fr 90px 80px 80px",
                      gap: "12px",
                      background: i % 2 === 0 ? "#fff" : "var(--light)",
                      borderBottom: "1px solid var(--primary-10)",
                    }}
                  >
                    {/* Type */}
                    <DocTypeBadge type={sig.doc_type} />

                    {/* Domain */}
                    <span className="font-body" style={{ fontSize: "12px", color: "var(--dark)" }}>
                      {domainLabel(sig.domain)}
                    </span>

                    {/* Themes */}
                    <div className="flex flex-wrap gap-1">
                      {sig.key_themes.slice(0, 3).map((t) => (
                        <span
                          key={t}
                          className="rounded px-1.5 py-0.5"
                          style={{
                            background: "var(--primary-10)",
                            color: "var(--primary)",
                            fontSize: "10px",
                            fontFamily: "var(--fb)",
                          }}
                        >
                          {t.replace(/_/g, " ")}
                        </span>
                      ))}
                      {sig.key_themes.length === 0 && (
                        <span style={{ fontSize: "11px", color: "var(--mid)" }}>—</span>
                      )}
                    </div>

                    {/* Horizon */}
                    <span className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      {horizonLabel(sig.horizon_months)}
                    </span>

                    {/* Signal strength bar */}
                    <div className="flex items-center gap-1.5">
                      <div
                        className="rounded"
                        style={{ background: "var(--light)", height: "6px", flex: 1 }}
                      >
                        <div
                          className="h-full rounded"
                          style={{
                            width: pct(sig.signal_strength),
                            background: "linear-gradient(90deg, #003366, #336699)",
                          }}
                        />
                      </div>
                      <span style={{ fontSize: "10px", color: "var(--mid)", whiteSpace: "nowrap" }}>
                        {pct(sig.signal_strength)}
                      </span>
                    </div>

                    {/* Confidence */}
                    <div className="flex items-center">
                      <ConfidenceDot score={sig.confidence_score} />
                      <span className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                        {pct(sig.confidence_score)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}
