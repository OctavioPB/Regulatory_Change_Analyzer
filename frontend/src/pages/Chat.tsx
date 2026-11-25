import { useEffect, useRef, useState } from "react";
import {
  Send, Bot, User, ChevronDown, ChevronUp, BookOpen, FileText, Workflow, Loader2, Check, X,
} from "lucide-react";
import { api, type ChatCitation } from "../api/client";
import { readSSE } from "../api/sse";
import { Eyebrow } from "../components/Eyebrow";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentStep {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  status: "running" | "ok" | "error";
  summary?: string;
  /** Text the agent wrote just before this lookup ("Let me check the circular…") */
  note?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations: ChatCitation[];
  streaming: boolean;
  steps: AgentStep[];
}

const TOOL_LABELS: Record<string, string> = {
  search_regulations: "Searched regulations",
  get_regulatory_change: "Read regulatory change",
  find_cross_jurisdiction: "Checked other jurisdiction",
  search_contract_clauses: "Searched contract clauses",
  get_contract: "Opened contract",
  list_impact_alerts: "Listed impact alerts",
  get_impact_alert: "Opened impact alert",
};

function describeInput(input: Record<string, unknown>): string {
  const v = input.query ?? input.contract_name ?? input.change_id ?? input.alert_id ?? input.severity;
  if (typeof v !== "string") return "";
  return /^[0-9a-f-]{36}$/i.test(v) ? v.slice(0, 8) : `"${v}"`;
}

// ── Suggested questions ───────────────────────────────────────────────────────

const SUGGESTIONS = [
  "How does the latest CNBV circular affect our fintech onboarding process?",
  "Which contracts need updating due to recent leverage limit changes?",
  "What are the new AML/KYC obligations we need to implement?",
  "How does the new SEC rule affect our derivative trading agreements?",
  "Are there any pending regulatory deadlines we should be aware of?",
];

// ── Citation card ─────────────────────────────────────────────────────────────

function CitationCard({ c }: { c: ChatCitation }) {
  const [open, setOpen] = useState(false);
  const isReg = c.type === "regulation";

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ border: "1px solid var(--primary-10)", fontSize: "12px" }}
    >
      <button
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
        style={{ background: isReg ? "rgba(0,51,102,.06)" : "rgba(200,155,60,.08)" }}
      >
        {isReg ? (
          <BookOpen size={11} style={{ color: "var(--primary)", flexShrink: 0 }} />
        ) : (
          <FileText size={11} style={{ color: "var(--gold)", flexShrink: 0 }} />
        )}
        <span
          className="font-body flex-1 truncate"
          style={{ color: "var(--dark)", fontWeight: 500 }}
        >
          [{isReg ? "REG" : "CON"}-{c.ref_id}] {c.title}
        </span>
        <span className="font-body shrink-0" style={{ color: "var(--mid)" }}>
          {c.article_ref}
        </span>
        {open ? (
          <ChevronUp size={11} style={{ color: "var(--mid)", flexShrink: 0 }} />
        ) : (
          <ChevronDown size={11} style={{ color: "var(--mid)", flexShrink: 0 }} />
        )}
      </button>

      {open && (
        <div className="px-3 py-2" style={{ background: "#fff", borderTop: "1px solid var(--primary-10)" }}>
          <div className="flex gap-3 mb-1.5">
            <span
              className="rounded px-1.5 py-0.5"
              style={{
                background: isReg ? "var(--primary)" : "var(--gold)",
                color: "#fff",
                fontSize: "10px",
                fontFamily: "var(--fb)",
                fontWeight: 600,
              }}
            >
              {isReg ? c.source : c.source}
            </span>
            {c.publication_date && (
              <span className="font-body" style={{ color: "var(--mid)", fontSize: "11px" }}>
                {c.publication_date}
              </span>
            )}
          </div>
          <p className="font-body" style={{ color: "var(--dark)", lineHeight: 1.6, fontSize: "12px" }}>
            {c.excerpt}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Agent steps ───────────────────────────────────────────────────────────────

function AgentSteps({ steps, running }: { steps: AgentStep[]; running: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div
      className="w-full rounded-lg px-3 py-2"
      style={{ border: "1px dashed var(--primary-30)", background: "rgba(0,51,102,.03)", fontSize: "12px" }}
    >
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 font-body"
        style={{ color: "var(--primary)", fontWeight: 600 }}
      >
        <Workflow size={12} />
        {running ? "Agent researching" : "Agent research"} · {steps.length} step{steps.length !== 1 ? "s" : ""}
        {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
      </button>
      {open && (
        <ol className="mt-1.5 flex flex-col gap-1">
          {steps.map((s) => (
            <li key={s.id} className="font-body flex flex-col" style={{ color: "var(--dark)" }}>
              {s.note && (
                <span style={{ color: "var(--mid)", fontStyle: "italic", whiteSpace: "pre-wrap" }}>{s.note}</span>
              )}
              <span className="flex items-center gap-1.5">
                {s.status === "running" ? (
                  <Loader2 size={11} className="animate-spin" style={{ color: "var(--primary)" }} />
                ) : s.status === "ok" ? (
                  <Check size={11} style={{ color: "var(--primary)" }} />
                ) : (
                  <X size={11} style={{ color: "#b41414" }} />
                )}
                {TOOL_LABELS[s.tool] ?? s.tool}
                <span style={{ color: "var(--mid)" }}>{describeInput(s.input)}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const [showCitations, setShowCitations] = useState(true);

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className="shrink-0 flex items-center justify-center rounded-full"
        style={{
          width: 32,
          height: 32,
          background: isUser ? "var(--gold)" : "var(--primary)",
          marginTop: "2px",
        }}
      >
        {isUser ? (
          <User size={14} style={{ color: "#fff" }} />
        ) : (
          <Bot size={14} style={{ color: "var(--gold-light)" }} />
        )}
      </div>

      {/* Content */}
      <div className={`flex flex-col gap-2 max-w-[78%] ${isUser ? "items-end" : "items-start"}`}>
        {!isUser && msg.steps.length > 0 && (
          <AgentSteps steps={msg.steps} running={msg.streaming} />
        )}

        {/* Bubble */}
        <div
          className="rounded-2xl px-4 py-3"
          style={{
            background: isUser ? "var(--primary)" : "#fff",
            color: isUser ? "#fff" : "var(--dark)",
            border: isUser ? "none" : "1px solid var(--primary-10)",
            fontSize: "13px",
            lineHeight: "1.65",
            fontFamily: "var(--fb)",
            whiteSpace: "pre-wrap",
            borderTopRightRadius: isUser ? 4 : undefined,
            borderTopLeftRadius: isUser ? undefined : 4,
            boxShadow: "0 1px 3px rgba(0,0,0,.06)",
          }}
        >
          {msg.text}
          {msg.streaming && (
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
        </div>

        {/* Citations */}
        {!isUser && msg.citations.length > 0 && (
          <div className="w-full flex flex-col gap-1">
            <button
              onClick={() => setShowCitations((p) => !p)}
              className="flex items-center gap-1.5 self-start"
              style={{ fontSize: "11px", color: "var(--mid)", fontFamily: "var(--fb)" }}
            >
              {showCitations ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              {msg.citations.length} source{msg.citations.length !== 1 ? "s" : ""} cited
            </button>
            {showCitations && (
              <div className="flex flex-col gap-1.5 w-full">
                {msg.citations.map((c, i) => (
                  <CitationCard key={`${c.ref_id}-${i}`} c={c} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function mkId() {
    return `${Date.now()}-${Math.random()}`;
  }

  async function send(queryText: string) {
    if (!queryText.trim() || busy) return;
    setBusy(true);
    setInput("");

    // Add user message
    const userMsg: Message = {
      id: mkId(),
      role: "user",
      text: queryText.trim(),
      citations: [],
      streaming: false,
      steps: [],
    };

    // Placeholder assistant message (streaming)
    const assistantId = mkId();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      text: "",
      citations: [],
      streaming: true,
      steps: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    const update = (fn: (m: Message) => Message) =>
      setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)));

    try {
      const q = queryText.trim();
      const res = await (agentMode ? api.agents.chat(q) : api.chat.stream(q));
      await readSSE(res, (evt) => {
        if (evt.type === "token") {
          update((m) => ({ ...m, text: m.text + evt.text }));
        } else if (evt.type === "step" && evt.status === "running") {
          // Text streamed before a lookup is the agent narrating: file it under the step
          update((m) => ({
            ...m,
            text: "",
            steps: [
              ...m.steps,
              { id: evt.id, tool: evt.tool, input: evt.input ?? {}, status: "running", note: m.text.trim() || undefined },
            ],
          }));
        } else if (evt.type === "step") {
          update((m) => ({
            ...m,
            steps: m.steps.map((st) => (st.id === evt.id ? { ...st, status: evt.status, summary: evt.summary } : st)),
          }));
        } else if (evt.type === "citations") {
          update((m) => ({ ...m, citations: evt.citations as ChatCitation[] }));
        } else if (evt.type === "done") {
          update((m) => ({ ...m, streaming: false }));
        } else if (evt.type === "error") {
          update((m) => ({ ...m, text: `Error: ${evt.message}`, streaming: false }));
        }
      });
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, text: `Connection error: ${(e as Error).message}`, streaming: false }
            : m
        )
      );
    } finally {
      // Stream may end without a "done" event (server crash, proxy cut)
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId && m.streaming ? { ...m, streaming: false } : m))
      );
      setBusy(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col" style={{ minHeight: "calc(100vh - 44px)" }}>
      {/* Hero */}
      <div className="hero-bg px-6 py-4 shrink-0">
        <Eyebrow light>RAG Assistant</Eyebrow>
        <h1 className="font-display text-white" style={{ fontSize: "26px", fontWeight: 300 }}>
          Chat with{" "}
          <em className="italic" style={{ color: "var(--gold-light)" }}>Policy</em>
        </h1>
        <p className="mt-1.5 font-body text-white/50" style={{ fontSize: "12px" }}>
          Ask compliance questions. Every answer is grounded in your regulatory documents and contracts.
        </p>
      </div>

      <div className="section-divider shrink-0" />

      {/* Chat body */}
      <div className="flex-1 px-6 py-5 flex flex-col gap-4">
        {/* Suggested questions — shown only when no messages */}
        {isEmpty && (
          <div className="flex flex-col items-center gap-6 py-8">
            <div
              className="flex items-center justify-center rounded-full"
              style={{ width: 56, height: 56, background: "rgba(0,51,102,.08)" }}
            >
              <Bot size={24} style={{ color: "var(--primary)" }} />
            </div>
            <div className="text-center">
              <p
                className="font-display"
                style={{ fontSize: "18px", fontWeight: 300, color: "var(--dark)" }}
              >
                Ask a compliance question
              </p>
              <p className="font-body mt-1" style={{ fontSize: "13px", color: "var(--mid)" }}>
                Answers are grounded in ingested regulations and your contracts.
              </p>
            </div>
            <div className="flex flex-col gap-2 w-full max-w-xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={busy}
                  className="text-left rounded-xl px-4 py-3 transition-all font-body"
                  style={{
                    background: "#fff",
                    border: "1px solid var(--primary-10)",
                    fontSize: "13px",
                    color: "var(--dark)",
                    boxShadow: "0 1px 2px rgba(0,0,0,.04)",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--primary-30)";
                    (e.currentTarget as HTMLButtonElement).style.background = "rgba(0,51,102,.03)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--primary-10)";
                    (e.currentTarget as HTMLButtonElement).style.background = "#fff";
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input area — sticky to viewport bottom while inside the scroll container */}
      <div
        className="px-8 py-4"
        style={{
          position: "sticky",
          bottom: 0,
          borderTop: "1px solid var(--primary-10)",
          background: "#fff",
          zIndex: 10,
        }}
      >
        <div
          className="flex items-end gap-3 rounded-xl px-4 py-3"
          style={{ border: "1px solid var(--primary-30)", background: "#fff", boxShadow: "0 2px 8px rgba(0,0,0,.06)" }}
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a regulation, contract impact, or compliance requirement…"
            disabled={busy}
            rows={1}
            className="flex-1 resize-none outline-none font-body bg-transparent"
            style={{
              fontSize: "13px",
              color: "var(--dark)",
              lineHeight: "1.5",
              maxHeight: "120px",
              overflowY: "auto",
            }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            className="shrink-0 flex items-center justify-center rounded-lg transition-all"
            style={{
              width: 36,
              height: 36,
              background: busy || !input.trim() ? "var(--primary-10)" : "var(--primary)",
              color: busy || !input.trim() ? "var(--mid)" : "#fff",
            }}
          >
            <Send size={15} />
          </button>
        </div>
        <div className="mt-2 flex items-center justify-center gap-4">
          <label
            className="flex items-center gap-1.5 font-body cursor-pointer select-none"
            style={{ fontSize: "11px", color: agentMode ? "var(--primary)" : "var(--mid)", fontWeight: agentMode ? 600 : 400 }}
            title="The agent decides what to look up and can chain several lookups (slower, uses more tokens, analyst role)"
          >
            <input type="checkbox" checked={agentMode} onChange={(e) => setAgentMode(e.target.checked)} disabled={busy} />
            <Workflow size={11} />
            Agent mode
          </label>
          <p className="font-body" style={{ fontSize: "11px", color: "var(--mid)" }}>
            Enter to send · Shift+Enter for new line · Answers cite sources from your regulatory database
          </p>
        </div>
      </div>

      {/* Blinking cursor animation */}
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
