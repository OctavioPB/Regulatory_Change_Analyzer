import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { FileSignature, Download, Loader2, AlertCircle, ChevronDown } from "lucide-react";
import { api, type ImpactAlert } from "../api/client";
import { Eyebrow } from "../components/Eyebrow";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StreamMeta {
  contract_name: string;
  doc_title: string;
}

// ── Section renderer ──────────────────────────────────────────────────────────

function DraftPreview({ text }: { text: string }) {
  if (!text) return null;
  const sections = text.split(/^----+$/m).map((s) => s.trim()).filter(Boolean);

  return (
    <div className="flex flex-col gap-4">
      {sections.map((section, i) => {
        const lines = section.split("\n");
        const first = lines[0].trim();
        const isHeading =
          /^[A-Z\s\d.]+$/.test(first) ||
          /^(ARTICLE|WHEREAS|RECITAL|SCHEDULE|EXHIBIT|ANNEX|ADDENDUM)/i.test(first);

        return (
          <div
            key={i}
            className="rounded-xl px-5 py-4"
            style={{
              background: i === 0 ? "rgba(0,51,102,.04)" : "#fff",
              border: "1px solid var(--primary-10)",
            }}
          >
            {isHeading && (
              <p
                className="font-body mb-2"
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                  color: "var(--primary)",
                }}
              >
                {first}
              </p>
            )}
            <p
              className="font-body"
              style={{
                fontSize: "13px",
                lineHeight: "1.75",
                color: "var(--dark)",
                whiteSpace: "pre-wrap",
              }}
            >
              {isHeading ? lines.slice(1).join("\n").trim() : section}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Addendum() {
  const location = useLocation();
  const preselectedId = (location.state as { alertId?: string } | null)?.alertId ?? null;

  const [alerts, setAlerts] = useState<ImpactAlert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<ImpactAlert | null>(null);
  const [loadingAlerts, setLoadingAlerts] = useState(true);

  const [drafting, setDrafting] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [meta, setMeta] = useState<StreamMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.alerts.list(false).then((a) => {
      setAlerts(a);
      if (preselectedId) {
        const found = a.find((x) => x.id === preselectedId) ?? null;
        setSelectedAlert(found);
      }
      setLoadingAlerts(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [draftText]);

  async function generateDraft() {
    if (!selectedAlert || drafting) return;
    setDrafting(true);
    setDraftText("");
    setMeta(null);
    setError(null);

    try {
      const res = await api.addendum.stream(selectedAlert.id);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === "meta") {
              setMeta({ contract_name: evt.contract_name, doc_title: evt.doc_title });
            } else if (evt.type === "token") {
              setDraftText((prev) => prev + evt.text);
            } else if (evt.type === "error") {
              setError(evt.message);
            }
          } catch {
            // ignore malformed SSE
          }
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDrafting(false);
    }
  }

  async function downloadAs(format: "pdf" | "docx") {
    if (!draftText || !selectedAlert) return;
    setExporting(format);
    try {
      const title = meta?.contract_name ?? selectedAlert.title;
      const res = await api.addendum.exportDoc(draftText, title, format);
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `addendum.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(null);
    }
  }

  const hasDraft = draftText.length > 0;

  return (
    <div className="flex flex-col" style={{ minHeight: "calc(100vh - 44px)" }}>
      {/* Hero */}
      <div className="hero-bg px-6 py-4 shrink-0">
        <Eyebrow light>Contract Management</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Addendum{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Drafting</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Select an impact alert and generate a complete contract addendum draft — ready for legal review.
        </p>
      </div>

      <div className="section-divider shrink-0" />

      <div className="flex-1 px-6 py-5 flex flex-col gap-5">
        {/* Alert selector */}
        <div
          className="rounded-xl px-6 py-5"
          style={{ background: "#fff", border: "1px solid var(--primary-10)", boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}
        >
          <p className="eyebrow mb-3">1 · Select alert</p>

          {loadingAlerts ? (
            <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>Loading alerts…</p>
          ) : (
            <div className="relative" style={{ maxWidth: 520 }}>
              <select
                value={selectedAlert?.id ?? ""}
                onChange={(e) => {
                  const found = alerts.find((a) => a.id === e.target.value) ?? null;
                  setSelectedAlert(found);
                  setDraftText("");
                  setMeta(null);
                  setError(null);
                }}
                className="w-full font-body rounded-lg px-4 py-2.5 appearance-none focus:outline-none"
                style={{
                  border: "1px solid var(--primary-30)",
                  fontSize: "13px",
                  color: selectedAlert ? "var(--dark)" : "var(--mid)",
                  background: "#fff",
                  paddingRight: "36px",
                }}
              >
                <option value="">— Choose an impact alert —</option>
                {alerts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title} · {a.items.length} item{a.items.length !== 1 ? "s" : ""}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", color: "var(--mid)", pointerEvents: "none" }}
              />
            </div>
          )}

          {selectedAlert && (
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedAlert.items.map((item) => (
                <span
                  key={item.id}
                  className="font-body rounded-full px-3 py-0.5"
                  style={{
                    fontSize: "11px",
                    background: "rgba(0,51,102,.06)",
                    color: "var(--primary)",
                    border: "1px solid rgba(0,51,102,.12)",
                  }}
                >
                  {item.affected_name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Generate button */}
        <div
          className="rounded-xl px-6 py-5"
          style={{ background: "#fff", border: "1px solid var(--primary-10)", boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}
        >
          <p className="eyebrow mb-3">2 · Generate draft</p>
          <div className="flex items-center gap-4">
            <button
              onClick={generateDraft}
              disabled={!selectedAlert || drafting}
              className="btn btn-primary flex items-center gap-2"
              style={{ fontSize: "13px", paddingLeft: "20px", paddingRight: "20px", height: "40px" }}
            >
              {drafting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FileSignature size={14} />
              )}
              {drafting ? "Generating…" : "Generate addendum"}
            </button>
            {hasDraft && !drafting && (
              <p className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                Draft ready — review below before downloading.
              </p>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            className="flex items-start gap-3 rounded-xl px-5 py-4"
            style={{ background: "rgba(180,20,20,.06)", border: "1px solid rgba(180,20,20,.15)" }}
          >
            <AlertCircle size={16} style={{ color: "#b41414", flexShrink: 0, marginTop: 2 }} />
            <p className="font-body" style={{ fontSize: "13px", color: "#b41414" }}>
              {error}
            </p>
          </div>
        )}

        {/* Meta banner */}
        {meta && (
          <div
            className="rounded-xl px-5 py-3 flex items-center gap-4"
            style={{ background: "rgba(0,51,102,.06)", border: "1px solid rgba(0,51,102,.12)" }}
          >
            <FileSignature size={16} style={{ color: "var(--primary)", flexShrink: 0 }} />
            <div>
              <p className="font-body font-semibold" style={{ fontSize: "13px", color: "var(--dark)" }}>
                {meta.contract_name}
              </p>
              <p className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                Triggered by: {meta.doc_title}
              </p>
            </div>
          </div>
        )}

        {/* Draft preview */}
        {(hasDraft || drafting) && (
          <div
            className="rounded-xl overflow-hidden"
            style={{ border: "1px solid var(--primary-10)", boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}
          >
            <div
              className="px-6 py-3 flex items-center justify-between"
              style={{ background: "rgba(0,51,102,.04)", borderBottom: "1px solid var(--primary-10)" }}
            >
              <p className="eyebrow">3 · Review draft</p>
              {hasDraft && !drafting && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => downloadAs("pdf")}
                    disabled={!!exporting}
                    className="btn btn-ghost flex items-center gap-1.5"
                    style={{ fontSize: "12px" }}
                  >
                    {exporting === "pdf" ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                    PDF
                  </button>
                  <button
                    onClick={() => downloadAs("docx")}
                    disabled={!!exporting}
                    className="btn btn-ghost flex items-center gap-1.5"
                    style={{ fontSize: "12px" }}
                  >
                    {exporting === "docx" ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                    DOCX
                  </button>
                </div>
              )}
            </div>

            <div className="px-6 py-5">
              {draftText ? (
                <DraftPreview text={draftText} />
              ) : (
                <div className="flex items-center gap-3 py-6">
                  <Loader2 size={18} className="animate-spin" style={{ color: "var(--primary)" }} />
                  <p className="font-body" style={{ fontSize: "13px", color: "var(--mid)" }}>
                    Claude is drafting the addendum…
                  </p>
                </div>
              )}
              {drafting && draftText && (
                <span
                  style={{
                    display: "inline-block",
                    width: 8,
                    height: 14,
                    background: "var(--gold)",
                    marginLeft: 3,
                    borderRadius: 1,
                    animation: "blink 1s step-end infinite",
                  }}
                />
              )}
              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* Disclaimer */}
        {hasDraft && !drafting && (
          <p
            className="font-body text-center"
            style={{ fontSize: "11px", color: "var(--mid)", maxWidth: 640, margin: "0 auto" }}
          >
            This draft is AI-generated and requires review by a qualified attorney or compliance officer
            before execution. Placeholders marked [DATE], [PARTY A], [PARTY B] must be completed.
          </p>
        )}
      </div>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
