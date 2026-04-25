import { useEffect, useState, useCallback } from "react";
import { ExternalLink, Play } from "lucide-react";
import { api, type RegulatoryDocument, type RegulatoryChange } from "../api/client";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

const changeTypeStyle: Record<string, { bg: string; text: string }> = {
  limit_modification: { bg: "#FEF0E6", text: "#7A3800" },
  new_requirement:    { bg: "var(--primary-10)", text: "var(--primary)" },
  repeal:             { bg: "#FDEAEA", text: "#7A1020" },
  clarification:      { bg: "var(--light)", text: "var(--mid)" },
  deadline:           { bg: "#F0EBF9", text: "#3D1F70" },
  other:              { bg: "var(--light)", text: "var(--mid)" },
};

export function Documents() {
  const [docs, setDocs] = useState<RegulatoryDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<RegulatoryDocument | null>(null);
  const [changes, setChanges] = useState<RegulatoryChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setDocs(await api.documents.list()); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function selectDoc(doc: RegulatoryDocument) {
    setSelectedDoc(doc);
    setChanges(await api.documents.changes(doc.id));
  }

  async function triggerAnalysis() {
    if (!selectedDoc) return;
    setAnalyzing(true);
    try { await api.documents.analyze(selectedDoc.id); }
    finally { setAnalyzing(false); }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Hero */}
      <div className="hero-bg px-8 py-5 shrink-0">
        <h1 className="font-display text-white" style={{ fontSize: "32px", fontWeight: 400 }}>
          Regulatory{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Documents</em>
        </h1>
        <p className="mt-2 font-body text-white/50" style={{ fontSize: "14px" }}>
          {docs.length} ingested documents across all monitored sources.
        </p>
      </div>

      <div className="section-divider" />

      {/* Two-column layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Document list */}
        <div
          className="w-80 flex flex-col shrink-0"
          style={{ borderRight: "1px solid var(--primary-10)", background: "var(--white)" }}
        >
          <div className="px-4 py-3 shrink-0" style={{ borderBottom: "1px solid var(--primary-10)" }}>
            <p className="opb-label text-opb-mid">Documents</p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <p className="text-center py-8 font-body" style={{ color: "var(--mid)", fontSize: "13px" }}>
                Loading…
              </p>
            ) : docs.length === 0 ? (
              <p className="text-center py-8 font-body" style={{ color: "var(--mid)", fontSize: "13px" }}>
                No documents found.
              </p>
            ) : (
              docs.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => selectDoc(doc)}
                  className="w-full text-left px-4 py-3 transition-colors"
                  style={{
                    borderBottom: "1px solid var(--primary-10)",
                    background: selectedDoc?.id === doc.id ? "var(--primary-10)" : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (selectedDoc?.id !== doc.id)
                      (e.currentTarget as HTMLElement).style.background = "var(--light)";
                  }}
                  onMouseLeave={(e) => {
                    if (selectedDoc?.id !== doc.id)
                      (e.currentTarget as HTMLElement).style.background = "transparent";
                  }}
                >
                  <p
                    className="opb-label mb-0.5"
                    style={{ color: selectedDoc?.id === doc.id ? "var(--primary)" : "var(--mid)" }}
                  >
                    {doc.source}
                  </p>
                  <p className="font-body leading-snug line-clamp-2" style={{ fontSize: "13px", color: "var(--dark)" }}>
                    {doc.title}
                  </p>
                  <p className="mt-1 font-body" style={{ fontSize: "11px", color: "var(--mid)" }}>
                    {fmtDate(doc.publication_date)}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1 overflow-y-auto p-8">
          {!selectedDoc ? (
            <div
              className="flex h-full items-center justify-center font-body"
              style={{ color: "var(--mid)", fontSize: "14px" }}
            >
              Select a document to view its detected changes.
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {/* Header card */}
              <div
                className="rounded-xl bg-white shadow-sm overflow-hidden"
                style={{ border: "1px solid var(--primary-10)" }}
              >
                <div className="accent-bar" />
                <div className="px-6 py-5 flex items-start justify-between gap-4">
                  <div>
                    <p className="opb-label text-opb-mid mb-1">{selectedDoc.source}</p>
                    <h2
                      className="font-display"
                      style={{ fontSize: "20px", fontWeight: 400, color: "var(--dark)" }}
                    >
                      {selectedDoc.title}
                    </h2>
                    <p className="mt-1.5 font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                      Published {fmtDate(selectedDoc.publication_date)} · Fetched {fmtDate(selectedDoc.fetched_at)}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {selectedDoc.url && (
                      <a
                        href={selectedDoc.url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-outline"
                      >
                        <ExternalLink size={11} /> Source
                      </a>
                    )}
                    <button onClick={triggerAnalysis} disabled={analyzing} className="btn btn-primary">
                      <Play size={11} />
                      {analyzing ? "Queued…" : "Re-analyze"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Changes */}
              <div>
                <p className="eyebrow mb-1.5">
                  Detected changes
                  {changes.length > 0 && (
                    <span className="ml-2 font-body normal-case" style={{ fontSize: "11px", color: "var(--mid)", letterSpacing: 0 }}>
                      ({changes.length})
                    </span>
                  )}
                </p>
                <p className="font-body mb-4" style={{ fontSize: "13px", color: "var(--mid)" }}>
                  Regulatory provisions identified by the NLP engine in this document.
                </p>
                {changes.length === 0 ? (
                  <p className="font-body" style={{ fontSize: "14px", color: "var(--mid)" }}>
                    No changes detected yet. Run Re-analyze to process this document.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {changes.map((ch) => {
                      const cs = changeTypeStyle[ch.change_type] ?? changeTypeStyle.other;
                      return (
                        <div
                          key={ch.id}
                          className="rounded-xl bg-white px-5 py-4"
                          style={{ border: "1px solid var(--primary-10)" }}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span
                              className="opb-badge"
                              style={{ background: cs.bg, color: cs.text }}
                            >
                              {ch.change_type.replace(/_/g, " ")}
                            </span>
                            {ch.article_ref && (
                              <span className="font-body" style={{ fontSize: "12px", color: "var(--mid)" }}>
                                {ch.article_ref}
                              </span>
                            )}
                          </div>
                          <p className="font-body" style={{ fontSize: "14px", color: "var(--dark)" }}>
                            {ch.summary}
                          </p>
                          {ch.old_text && ch.new_text && (
                            <div className="mt-3 grid grid-cols-2 gap-2">
                              <div className="rounded-lg px-3 py-2" style={{ background: "#FDEAEA" }}>
                                <p className="opb-label mb-1" style={{ color: "#7A1020" }}>Before</p>
                                <p className="font-body" style={{ fontSize: "12px", color: "#7A1020" }}>
                                  {ch.old_text.slice(0, 120)}
                                </p>
                              </div>
                              <div className="rounded-lg px-3 py-2" style={{ background: "#E0F7EF" }}>
                                <p className="opb-label mb-1" style={{ color: "#0D5C3A" }}>After</p>
                                <p className="font-body" style={{ fontSize: "12px", color: "#0D5C3A" }}>
                                  {ch.new_text.slice(0, 120)}
                                </p>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
