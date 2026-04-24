import { useEffect, useState, useCallback } from "react";
import { ExternalLink, Play } from "lucide-react";
import { api, type RegulatoryDocument, type RegulatoryChange } from "../api/client";

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const changeTypePill: Record<string, string> = {
  limit_modification: "bg-amber-100 text-amber-700",
  new_requirement: "bg-blue-100 text-blue-700",
  repeal: "bg-red-100 text-red-700",
  clarification: "bg-gray-100 text-gray-600",
  deadline: "bg-purple-100 text-purple-700",
  other: "bg-gray-100 text-gray-500",
};

export function Documents() {
  const [docs, setDocs] = useState<RegulatoryDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<RegulatoryDocument | null>(null);
  const [changes, setChanges] = useState<RegulatoryChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await api.documents.list());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function selectDoc(doc: RegulatoryDocument) {
    setSelectedDoc(doc);
    const c = await api.documents.changes(doc.id);
    setChanges(c);
  }

  async function triggerAnalysis() {
    if (!selectedDoc) return;
    setAnalyzing(true);
    try {
      await api.documents.analyze(selectedDoc.id);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="flex h-full">
      {/* Document list */}
      <div className="w-80 border-r border-gray-200 bg-white flex flex-col">
        <div className="border-b border-gray-100 px-4 py-3">
          <h1 className="text-sm font-semibold text-gray-900">Regulatory Documents</h1>
          <p className="text-xs text-gray-400 mt-0.5">{docs.length} documents</p>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
          {loading ? (
            <p className="text-center text-xs text-gray-400 py-8">Loading…</p>
          ) : docs.length === 0 ? (
            <p className="text-center text-xs text-gray-400 py-8">No documents found.</p>
          ) : (
            docs.map((doc) => (
              <button
                key={doc.id}
                onClick={() => selectDoc(doc)}
                className={`w-full text-left px-4 py-3 transition-colors hover:bg-gray-50 ${
                  selectedDoc?.id === doc.id ? "bg-blue-50" : ""
                }`}
              >
                <p className="text-xs font-semibold text-blue-600">{doc.source}</p>
                <p className="text-sm text-gray-800 mt-0.5 leading-snug line-clamp-2">
                  {doc.title}
                </p>
                <p className="text-xs text-gray-400 mt-1">{fmtDate(doc.publication_date)}</p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Document detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedDoc ? (
          <div className="flex h-full items-center justify-center text-gray-400 text-sm">
            Select a document to view its changes.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-xs font-semibold text-blue-600">{selectedDoc.source}</span>
                <h2 className="text-base font-bold text-gray-900 mt-0.5">{selectedDoc.title}</h2>
                <p className="text-xs text-gray-400 mt-1">
                  Published {fmtDate(selectedDoc.publication_date)} · Fetched {fmtDate(selectedDoc.fetched_at)}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                {selectedDoc.url && (
                  <a
                    href={selectedDoc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 rounded-md border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
                  >
                    <ExternalLink size={12} /> Source
                  </a>
                )}
                <button
                  onClick={triggerAnalysis}
                  disabled={analyzing}
                  className="flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Play size={12} />
                  {analyzing ? "Queued…" : "Re-analyze"}
                </button>
              </div>
            </div>

            {/* Changes */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                Detected Changes ({changes.length})
              </h3>
              {changes.length === 0 ? (
                <p className="text-sm text-gray-400">No changes detected yet.</p>
              ) : (
                <div className="space-y-2">
                  {changes.map((ch) => (
                    <div
                      key={ch.id}
                      className="rounded-lg border border-gray-200 bg-white px-4 py-3"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            changeTypePill[ch.change_type] ?? changeTypePill.other
                          }`}
                        >
                          {ch.change_type.replace(/_/g, " ")}
                        </span>
                        {ch.article_ref && (
                          <span className="text-xs text-gray-500">{ch.article_ref}</span>
                        )}
                      </div>
                      <p className="mt-2 text-sm text-gray-700">{ch.summary}</p>
                      {ch.old_text && ch.new_text && (
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <div className="rounded bg-red-50 px-2 py-1.5 text-xs text-red-700">
                            <span className="font-semibold">Before: </span>{ch.old_text.slice(0, 120)}
                          </div>
                          <div className="rounded bg-green-50 px-2 py-1.5 text-xs text-green-700">
                            <span className="font-semibold">After: </span>{ch.new_text.slice(0, 120)}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
