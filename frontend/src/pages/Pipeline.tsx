import { useState, useRef, useEffect } from "react";
import { CheckCircle, XCircle, Loader, Terminal } from "lucide-react";
import { api } from "../api/client";
import { Eyebrow } from "../components/Eyebrow";

type StepStatus = "idle" | "running" | "done" | "error";

interface StepState {
  status: StepStatus;
  message: string;
}

interface LogEntry {
  id: string;
  ts: string;
  step: string;
  status: "running" | "done" | "error";
  message: string;
}

const idle: StepState = { status: "idle", message: "" };

function fmtTime() {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

function StatusLine({ state }: { state: StepState }) {
  if (state.status === "idle") return null;
  if (state.status === "running") {
    return (
      <div className="flex items-center gap-2 mt-3" style={{ color: "var(--primary-60)" }}>
        <Loader size={13} className="animate-spin" />
        <span className="font-body" style={{ fontSize: "13px" }}>Running…</span>
      </div>
    );
  }
  if (state.status === "done") {
    return (
      <div className="flex items-center gap-2 mt-3" style={{ color: "#27B97C" }}>
        <CheckCircle size={13} />
        <span className="font-body" style={{ fontSize: "13px" }}>{state.message}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 mt-3" style={{ color: "#E03448" }}>
      <XCircle size={13} />
      <span className="font-body" style={{ fontSize: "13px" }}>{state.message}</span>
    </div>
  );
}

function RunButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button disabled={disabled} onClick={onClick} className="btn btn-primary">
      {label}
    </button>
  );
}

export function Pipeline() {
  const [seed, setSeed] = useState<StepState>(idle);
  const [ingest, setIngest] = useState<StepState>(idle);
  const [analyze, setAnalyze] = useState<StepState>(idle);
  const [mapStep, setMapStep] = useState<StepState>(idle);
  const [trendStep, setTrendStep] = useState<StepState>(idle);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const busy = (s: StepState) => s.status === "running";

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  function appendLog(step: string, status: LogEntry["status"], message: string) {
    setLogs((prev) => [
      ...prev,
      { id: `${Date.now()}-${Math.random()}`, ts: fmtTime(), step, status, message },
    ]);
  }

  async function run(
    fn: () => Promise<{ detail: string }>,
    set: (s: StepState) => void,
    step: string,
    successMsg: (detail: string) => string,
  ) {
    set({ status: "running", message: "" });
    appendLog(step, "running", "Started…");
    try {
      const res = await fn();
      const msg = successMsg(res.detail);
      set({ status: "done", message: msg });
      appendLog(step, "done", msg);
    } catch (e) {
      const msg = (e as Error).message;
      set({ status: "error", message: msg });
      appendLog(step, "error", msg);
    }
  }

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-6 py-4">
        <Eyebrow light>Data Ingestion</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Data{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Pipeline</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Run each stage of the regulatory analysis pipeline from the browser.
        </p>
      </div>

      <div className="section-divider" />

      {/* Two-column body */}
      <div className="px-6 py-5 grid gap-5" style={{ gridTemplateColumns: "420px 1fr" }}>

        {/* Left: step cards */}
        <div className="flex flex-col gap-5">

          {/* Step 0 */}
          <div className="rounded-xl bg-white shadow-sm overflow-hidden" style={{ border: "1px solid var(--primary-10)" }}>
            <div className="accent-bar" />
            <div className="px-6 py-5">
              <p className="eyebrow mb-1.5">Step 00 · Setup</p>
              <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Seed the database with sample contracts so the impact mapper has targets to match against.
              </p>
              <div className="mt-4">
                <RunButton
                  label="Seed demo contracts →"
                  disabled={busy(seed)}
                  onClick={() => run(api.pipeline.seedContracts, setSeed, "SETUP", (d) => d)}
                />
              </div>
              <StatusLine state={seed} />
            </div>
          </div>

          {/* Step 1 */}
          <div className="rounded-xl bg-white shadow-sm overflow-hidden" style={{ border: "1px solid var(--primary-10)" }}>
            <div className="accent-bar" />
            <div className="px-6 py-5">
              <p className="eyebrow mb-1.5">Step 01 · Fetch</p>
              <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Pull the latest documents from each monitored regulatory source.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <RunButton label="SEC" disabled={busy(ingest)}
                  onClick={() => run(() => api.pipeline.ingest("sec"), setIngest, "FETCH", () => "SEC ingestion queued")} />
                <RunButton label="CNBV" disabled={busy(ingest)}
                  onClick={() => run(() => api.pipeline.ingest("cnbv"), setIngest, "FETCH", () => "CNBV ingestion queued")} />
                <button disabled={busy(ingest)}
                  onClick={() => run(() => api.pipeline.ingest(), setIngest, "FETCH", () => "All sources queued")}
                  className="btn btn-outline">
                  All sources →
                </button>
              </div>
              <StatusLine state={ingest} />
            </div>
          </div>

          {/* Step 2 */}
          <div className="rounded-xl bg-white shadow-sm overflow-hidden" style={{ border: "1px solid var(--primary-10)" }}>
            <div className="accent-bar" />
            <div className="px-6 py-5">
              <p className="eyebrow mb-1.5">Step 02 · Analyze</p>
              <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Run NLP on all ingested documents that have not yet been analyzed.
              </p>
              <div className="mt-4">
                <RunButton label="Analyze all pending →" disabled={busy(analyze)}
                  onClick={() => run(api.pipeline.analyze, setAnalyze, "ANALYZE", () => "Analysis queued — check Documents for results")} />
              </div>
              <StatusLine state={analyze} />
            </div>
          </div>

          {/* Step 3 */}
          <div className="rounded-xl bg-white shadow-sm overflow-hidden" style={{ border: "1px solid var(--primary-10)" }}>
            <div className="accent-bar" />
            <div className="px-6 py-5">
              <p className="eyebrow mb-1.5">Step 03 · Map impacts</p>
              <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Map detected regulatory changes to contracts and generate impact alerts.
              </p>
              <div className="mt-4">
                <RunButton label="Map impacts →" disabled={busy(mapStep)}
                  onClick={() => run(api.pipeline.mapImpacts, setMapStep, "MAP", () => "Impact mapping queued — check Alerts for results")} />
              </div>
              <StatusLine state={mapStep} />
            </div>
          </div>

          {/* Step 4 */}
          <div className="rounded-xl bg-white shadow-sm overflow-hidden" style={{ border: "1px solid var(--primary-10)" }}>
            <div className="accent-bar" />
            <div className="px-6 py-5">
              <p className="eyebrow mb-1.5">Step 04 · Trend signals</p>
              <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Extract predictive signals from Proposed Rules and No-Action Letters.
              </p>
              <div className="mt-4">
                <RunButton label="Extract trends →" disabled={busy(trendStep)}
                  onClick={() => run(api.trends.extractAll, setTrendStep, "TREND", () => "Trend extraction queued — check Trends for results")} />
              </div>
              <StatusLine state={trendStep} />
            </div>
          </div>

        </div>

        {/* Right: activity log */}
        <div className="rounded-xl overflow-hidden flex flex-col" style={{ border: "1px solid var(--primary-10)", minHeight: "420px" }}>
          {/* Log header */}
          <div
            className="px-5 py-3 flex items-center gap-2 shrink-0"
            style={{ background: "var(--primary)", borderBottom: "1px solid rgba(255,255,255,.08)" }}
          >
            <Terminal size={13} style={{ color: "var(--gold)" }} />
            <p className="eyebrow" style={{ color: "var(--gold)", marginBottom: 0 }}>Activity log</p>
            {logs.length > 0 && (
              <span
                className="ml-auto font-body"
                style={{ fontSize: "11px", color: "rgba(255,255,255,.35)", cursor: "pointer" }}
                onClick={() => setLogs([])}
              >
                Clear
              </span>
            )}
          </div>

          {/* Log body */}
          <div
            className="flex-1 overflow-y-auto p-4"
            style={{ background: "#0D1B2A", fontFamily: "'Courier New', monospace" }}
          >
            {logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-2" style={{ minHeight: "340px" }}>
                <Terminal size={22} style={{ color: "rgba(255,255,255,.12)" }} />
                <p style={{ fontSize: "12px", color: "rgba(255,255,255,.2)", letterSpacing: "0.5px" }}>
                  No activity yet. Run a step to see logs.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {logs.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3" style={{ fontSize: "12px", lineHeight: "1.6" }}>
                    <span style={{ color: "rgba(255,255,255,.3)", whiteSpace: "nowrap", flexShrink: 0 }}>
                      {entry.ts}
                    </span>
                    <span
                      style={{
                        color: "var(--gold-light)",
                        whiteSpace: "nowrap",
                        flexShrink: 0,
                        minWidth: "60px",
                      }}
                    >
                      {entry.step}
                    </span>
                    <span
                      style={{
                        color:
                          entry.status === "done"  ? "#27B97C" :
                          entry.status === "error" ? "#E03448" :
                          "#4A90D9",
                      }}
                    >
                      {entry.status === "running" && "⟳ "}
                      {entry.status === "done"    && "✓ "}
                      {entry.status === "error"   && "✗ "}
                      {entry.message}
                    </span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
