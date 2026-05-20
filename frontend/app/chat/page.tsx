"use client";

import { useRef, useState } from "react";
import { Citation, PasalChip } from "@/components/citation/PasalChip";
import { TraceEvent, TraceList } from "@/components/chat/TraceChip";
import { ArtifactRenderer, type Artifact } from "@/components/artifacts/ArtifactRenderer";

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  artifacts?: Artifact[];
  trace?: TraceEvent[];
};

const PERSONAS = [
  { id: "asisten_hukum", label: "Asisten" },
  { id: "drafter", label: "Drafter" },
  { id: "reviewer", label: "Reviewer" },
  { id: "researcher", label: "Researcher" },
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [persona, setPersona] = useState("asisten_hukum");
  const [planMode, setPlanMode] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function send() {
    const text = input.trim();
    if (!text) return;
    const userMsg: Message = { role: "user", text };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          agent: persona,
          message: text,
          plan_mode: planMode,
        }),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.reply,
          citations: data.citations,
          artifacts: data.artifacts,
          trace: data.trace,
        },
      ]);
      if (planMode) setPlanMode(false); // one-shot
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `Error: ${String(err)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[80vh]">
      <div className="flex items-center gap-3 mb-2 text-sm">
        <span className="opacity-60">Persona:</span>
        <select
          className="bg-white/5 rounded px-2 py-1"
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
          disabled={busy}
        >
          {PERSONAS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <button
          onClick={() => setPlanMode((x) => !x)}
          className={`px-2 py-1 rounded text-xs ${
            planMode ? "bg-accent" : "bg-white/10"
          }`}
          title="Plan mode: rencana dulu, baru jalankan"
        >
          {planMode ? "Plan-mode: ON" : "Plan-mode: off"}
        </button>
        <button
          onClick={() => {
            setMessages([]);
            setSessionId(null);
          }}
          className="ml-auto px-2 py-1 rounded text-xs bg-white/10"
          disabled={busy}
        >
          Sesi baru
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 mb-3">
        {messages.length === 0 && (
          <div className="opacity-50 text-sm space-y-1">
            <div>Tanyakan apa saja tentang hukum Indonesia.</div>
            <div className="opacity-70">
              Contoh: <em>“Bagaimana syarat sah perjanjian menurut KUHPerdata?”</em>
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-3 rounded-lg ${
              m.role === "user" ? "bg-white/5" : "bg-accent/10"
            }`}
          >
            <div className="text-xs opacity-60 mb-1">
              {m.role === "user" ? "Anda" : "Asisten"}
            </div>
            <div className="whitespace-pre-wrap">{m.text}</div>
            {m.artifacts && m.artifacts.length > 0 && (
              <div className="mt-3 space-y-3">
                {m.artifacts.map((a) => (
                  <ArtifactRenderer key={a.id} artifact={a} />
                ))}
              </div>
            )}
            {m.trace && <TraceList trace={m.trace} />}
            {m.citations && m.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {m.citations.map((c, j) => (
                  <PasalChip key={j} c={c} />
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="opacity-60 text-sm">Asisten sedang berpikir…</div>}
      </div>

      <div className="flex gap-2">
        <textarea
          ref={inputRef}
          className="flex-1 bg-white/5 rounded px-3 py-2 resize-none"
          placeholder="Ketik pesan…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          disabled={busy}
        />
        <button
          className="px-4 py-2 rounded bg-accent disabled:opacity-50"
          onClick={() => send()}
          disabled={busy}
        >
          Kirim
        </button>
      </div>
    </div>
  );
}
