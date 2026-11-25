import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  FileSignature, Download, Loader2, AlertCircle, ChevronDown, Users, CheckCircle2, AlertTriangle,
} from "lucide-react";
import { api, type ImpactAlert } from "../api/client";
import { readSSE } from "../api/sse";
import { Eyebrow } from "../components/Eyebrow";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StreamMeta {
  contract_name: string;
  doc_title: string;
}

interface ReviewIssue {
  severity: "blocker" | "major" | "minor";
  section: string;
  problem: string;
  fix: string;
}

interface TeamContract {
  contract_name: string;
  doc_title: string;
  modifications: number;
  activity: string;
  reviews: { round: number; approved: boolean; summary: string; issues: ReviewIssue[] }[];
  result?: { approved: boolean | null; rounds: number; open_issues: ReviewIssue[] };
  failed?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  get_regulatory_change: "reading the regulation",
  get_contract: "reading the contract",
  search_regulations: "searching related regulations",
};

const SEVERITY_COLOR: Record<string, string> = { blocker: "#b41414", major: "#b45f06", minor: "var(--mid)" };

// ── Team progress ─────────────────────────────────────────────────────────────

function TeamProgress({ contracts, summary }: { contracts: TeamContract[]; summary: string | null }) {
  return (
    <div
      className="rounded-xl px-6 py-5"
      style={{ background: "#fff", border: "1px solid var(--primary-10)", boxShadow: "0 1px 3px rgba(0,0,0,.04)" }}
    >
      <p className="eyebrow mb-3 flex items-center gap-2">
        <Users size={12} /> Drafting team · {contracts.length} drafting agent{contracts.length !== 1 ? "s" : ""} + reviewer
      </p>
      <div className="flex flex-col gap-3">
        {contracts.map((c) => {
          const issues = c.result?.open_issues ?? c.reviews[c.reviews.length - 1]?.issues ?? [];
          return (
            <div key={c.contract_name} className="rounded-lg px-4 py-3" style={{ border: "1px solid var(--primary-10)" }}>
              <div className="flex items-center gap-2">
                {c.failed ? (
                  <AlertCircle size={14} style={{ color: "#b41414" }} />
                ) : !c.result ? (
                  <Loader2 size={14} className="animate-spin" style={{ color: "var(--primary)" }} />
                ) : c.result.approved ? (
                  <CheckCircle2 size={14} style={{ color: "var(--primary)" }} />
                ) : (
                  <AlertTriangle size={14} style={{ color: "#b45f06" }} />
                )}
                <p className="font-body font-semibold flex-1" style={{ fontSize: "13px", color: "var(--dark)" }}>
                  {c.contract_name}
                </p>
                <span className="font-body" style={{ fontSize: "11px", color: "var(--mid)" }}>
                  {c.modifications} modification{c.modifications !== 1 ? "s" : ""}
                </span>
              </div>
              <p className="font-body mt-1" style={{ fontSize: "12px", color: "var(--mid)" }}>
                {c.result
                  ? c.result.approved === null
                    ? `Drafted in ${c.result.rounds || 1} round(s): review unavailable`
                    : c.result.approved
                      ? `Passed review after ${c.result.rounds} round(s)`
                      : `Open issues after ${c.result.rounds} round(s): needs legal attention`
                  : c.activity}
              </p>
              {c.reviews.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {c.reviews.map((r) => (
                    <span
                      key={r.round}
                      title={r.summary}
                      className="font-body rounded-full px-2 py-0.5"
                      style={{
                        fontSize: "10px",
                        background: r.approved ? "rgba(0,51,102,.08)" : "rgba(180,95,6,.10)",
                        color: r.approved ? "var(--primary)" : "#b45f06",
                      }}
                    >
                      Review {r.round}: {r.approved ? "approved" : `${r.issues.length} issue${r.issues.length !== 1 ? "s" : ""}`}
                    </span>
                  ))}
                </div>
              )}
              {c.result && issues.length > 0 && (
                <ul className="mt-2 flex flex-col gap-1">
                  {issues.map((i, k) => (
                    <li key={k} className="font-body" style={{ fontSize: "12px", color: "var(--dark)" }}>
                      <span style={{ color: SEVERITY_COLOR[i.severity], fontWeight: 600, textTransform: "uppercase", fontSize: "10px" }}>
                        {i.severity}
                      </span>{" "}
                      {i.section}: {i.problem} <span style={{ color: "var(--mid)" }}>· Fix: {i.fix}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      {summary && (
        <p className="font-body mt-3" style={{ fontSize: "11px", color: "var(--mid)" }}>
          {summary}
        </p>
      )}
    </div>
  );
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
  const [teamMode, setTeamMode] = useState(false);
  const [team, setTeam] = useState<TeamContract[]>([]);
  const [teamSummary, setTeamSummary] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.alerts
      .list(false)
      .then((a) => {
        setAlerts(a);
        if (preselectedId) {
          setSelectedAlert(a.find((x) => x.id === preselectedId) ?? null);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoadingAlerts(false));
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
    setTeam([]);
    setTeamSummary(null);

    try {
      if (teamMode) {
        await runTeam(selectedAlert.id);
      } else {
        const res = await api.addendum.stream(selectedAlert.id);
        await readSSE(res, (evt) => {
          if (evt.type === "meta") {
            setMeta({ contract_name: evt.contract_name, doc_title: evt.doc_title });
          } else if (evt.type === "token") {
            setDraftText((prev) => prev + evt.text);
          } else if (evt.type === "error") {
            setError(evt.message);
          }
        });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDrafting(false);
    }
  }

  async function runTeam(alertId: string) {
    const drafts: string[] = [];
    const patch = (name: string, fn: (c: TeamContract) => TeamContract) =>
      setTeam((prev) => prev.map((c) => (c.contract_name === name ? fn(c) : c)));

    const res = await api.agents.addendum(alertId);
    await readSSE(res, (evt) => {
      if (evt.type === "plan") {
        setTeam(
          (evt.contracts as { contract_name: string; doc_title: string; modifications: number }[]).map((c) => ({
            ...c,
            activity: "Queued",
            reviews: [],
          })),
        );
        if (evt.skipped?.length) setError(`Not drafted (limit per alert): ${evt.skipped.join(", ")}`);
      } else if (evt.type === "agent") {
        const who = evt.role === "drafter" ? "Drafter" : "Reviewer";
        const activity =
          evt.status === "tool"
            ? `${who}: ${TOOL_LABELS[evt.tool] ?? evt.tool}`
            : evt.status === "started"
              ? evt.role === "drafter"
                ? evt.round === 1 ? "Drafter: writing the addendum" : `Drafter: revising (round ${evt.round})`
                : `Reviewer: checking draft ${evt.round}`
              : evt.status === "finished"
                ? evt.role === "drafter" ? "Draft ready: waiting for review" : "Review complete"
                : `${who} failed (${evt.detail ?? "error"})`;
        patch(evt.contract_name, (c) => ({ ...c, activity, failed: c.failed || (evt.status === "failed" && evt.round === 0) }));
      } else if (evt.type === "review") {
        patch(evt.contract_name, (c) => ({
          ...c,
          reviews: [...c.reviews, { round: evt.round, approved: evt.approved, summary: evt.summary, issues: evt.issues }],
        }));
      } else if (evt.type === "draft") {
        drafts.push(evt.text);
        setDraftText(drafts.join("\n----\n\n"));
        setMeta((m) => m ?? { contract_name: evt.contract_name, doc_title: evt.doc_title });
        patch(evt.contract_name, (c) => ({
          ...c,
          result: { approved: evt.approved, rounds: evt.rounds, open_issues: evt.open_issues ?? [] },
        }));
      } else if (evt.type === "done") {
        const u = evt.usage ?? {};
        setTeamSummary(
          `${evt.approved}/${evt.total} draft(s) passed review · ` +
            `${(u.input_tokens ?? 0).toLocaleString()} input / ${(u.output_tokens ?? 0).toLocaleString()} output tokens`,
        );
      } else if (evt.type === "error") {
        setError(evt.message);
      }
    });
    // Contracts whose subagent never produced a draft
    setTeam((prev) => prev.map((c) => (c.result ? c : { ...c, failed: true })));
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
                  setTeam([]);
                  setTeamSummary(null);
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
              {drafting ? "Generating…" : teamMode ? "Run drafting team" : "Generate addendum"}
            </button>
            <label
              className="flex items-center gap-1.5 font-body cursor-pointer select-none"
              style={{ fontSize: "12px", color: teamMode ? "var(--primary)" : "var(--mid)", fontWeight: teamMode ? 600 : 400 }}
              title="One drafting agent per contract reads the full sources; a reviewer agent checks each draft and sends it back for revision (slower, more tokens)"
            >
              <input type="checkbox" checked={teamMode} onChange={(e) => setTeamMode(e.target.checked)} disabled={drafting} />
              <Users size={12} />
              Multi-agent (draft + review)
            </label>
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

        {/* Team progress */}
        {team.length > 0 && <TeamProgress contracts={team} summary={teamSummary} />}

        {/* Meta banner */}
        {meta && !teamMode && (
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
                    {teamMode ? "The drafting team is working: drafts appear here once reviewed…" : "Claude is drafting the addendum…"}
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
