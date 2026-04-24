import { useState } from "react";
import { CheckCircle, XCircle, Loader } from "lucide-react";
import { api } from "../api/client";

type StepStatus = "idle" | "running" | "done" | "error";

interface StepState {
  status: StepStatus;
  message: string;
}

const idle: StepState = { status: "idle", message: "" };

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

function RunButton({
  label,
  disabled,
  onClick,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-lg px-4 py-2 font-body font-medium disabled:opacity-40 transition-opacity"
      style={{ background: "var(--primary)", color: "#fff", fontSize: "13px" }}
    >
      {label}
    </button>
  );
}

async function run(
  fn: () => Promise<{ detail: string }>,
  set: (s: StepState) => void,
  successMsg: (detail: string) => string,
) {
  set({ status: "running", message: "" });
  try {
    const res = await fn();
    set({ status: "done", message: successMsg(res.detail) });
  } catch (e) {
    set({ status: "error", message: (e as Error).message });
  }
}

export function Pipeline() {
  const [ingest, setIngest] = useState<StepState>(idle);
  const [analyze, setAnalyze] = useState<StepState>(idle);
  const [mapStep, setMapStep] = useState<StepState>(idle);

  const busy = (s: StepState) => s.status === "running";

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="hero-bg px-8 py-5">
        <h1 className="font-display text-white" style={{ fontSize: "32px", fontWeight: 400 }}>
          Data{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Pipeline</em>
        </h1>
        <p className="mt-2 font-body text-white/50" style={{ fontSize: "14px" }}>
          Run each stage of the regulatory analysis pipeline from the browser.
        </p>
      </div>

      <div className="section-divider" />

      <div className="px-8 py-8 flex flex-col gap-6 max-w-2xl">

        {/* Step 1 */}
        <div
          className="rounded-xl bg-white shadow-sm overflow-hidden"
          style={{ border: "1px solid var(--primary-10)" }}
        >
          <div className="accent-bar" />
          <div className="px-6 py-5">
            <p className="eyebrow mb-1.5">Step 01 · Fetch</p>
            <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
              Pull the latest documents from each monitored regulatory source.
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              <RunButton
                label="SEC"
                disabled={busy(ingest)}
                onClick={() =>
                  run(() => api.pipeline.ingest("sec"), setIngest, () => "SEC ingestion queued")
                }
              />
              <RunButton
                label="CNBV"
                disabled={busy(ingest)}
                onClick={() =>
                  run(() => api.pipeline.ingest("cnbv"), setIngest, () => "CNBV ingestion queued")
                }
              />
              <button
                disabled={busy(ingest)}
                onClick={() =>
                  run(() => api.pipeline.ingest(), setIngest, () => "All sources queued")
                }
                className="flex items-center gap-1.5 rounded-lg px-4 py-2 font-body font-medium disabled:opacity-40 transition-opacity"
                style={{ border: "1px solid var(--primary-30)", color: "var(--primary)", fontSize: "13px" }}
              >
                All sources →
              </button>
            </div>
            <StatusLine state={ingest} />
          </div>
        </div>

        {/* Step 2 */}
        <div
          className="rounded-xl bg-white shadow-sm overflow-hidden"
          style={{ border: "1px solid var(--primary-10)" }}
        >
          <div className="accent-bar" />
          <div className="px-6 py-5">
            <p className="eyebrow mb-1.5">Step 02 · Analyze</p>
            <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
              Run NLP on all ingested documents that have not yet been analyzed.
            </p>
            <div className="mt-4">
              <RunButton
                label="Analyze all pending →"
                disabled={busy(analyze)}
                onClick={() =>
                  run(api.pipeline.analyze, setAnalyze, () => "Analysis queued — check Documents for results")
                }
              />
            </div>
            <StatusLine state={analyze} />
          </div>
        </div>

        {/* Step 3 */}
        <div
          className="rounded-xl bg-white shadow-sm overflow-hidden"
          style={{ border: "1px solid var(--primary-10)" }}
        >
          <div className="accent-bar" />
          <div className="px-6 py-5">
            <p className="eyebrow mb-1.5">Step 03 · Map impacts</p>
            <p className="font-body mb-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
              Map detected regulatory changes to contracts and generate impact alerts.
            </p>
            <div className="mt-4">
              <RunButton
                label="Map impacts →"
                disabled={busy(mapStep)}
                onClick={() =>
                  run(api.pipeline.mapImpacts, setMapStep, () => "Impact mapping queued — check Alerts for results")
                }
              />
            </div>
            <StatusLine state={mapStep} />
          </div>
        </div>

      </div>
    </div>
  );
}
