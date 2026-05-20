"use client";

import { useState } from "react";
import { Citation, PasalChip } from "@/components/citation/PasalChip";
import { TraceEvent, TraceList } from "@/components/chat/TraceChip";

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  trace?: TraceEvent[];
};

const PERSONAS = [
  { id: "asisten_hukum", label: "Asisten" },
  { id: "drafter", label: "Drafter" },
  { id: "reviewer", label: "Reviewer" },
  { id: "researcher", label: "Researcher" },
];

export function MatterChat({
  matterId,
  matterName,
}: {
  matterId: number;
  matterName?: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [persona, setPersona] = useState("asisten_hukum");
  const [busy, setBusy] = useState(false);

  async function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          agent: persona,
          message: msg,
          matter_id: matterId,
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
          trace: data.trace,
        },
      ]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${String(err)}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-sm">
        <span className="opacity-60">Bicara dengan:</span>
        <select
          className="bg-white/5 rounded px-2 py-1"
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
        >
          {PERSONAS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <span className="ml-auto text-xs opacity-50">
          Konteks: {matterName ?? `matter #${matterId}`}
        </span>
      </div>

      <div className="space-y-2 min-h-[40vh] max-h-[60vh] overflow-y-auto p-2 rounded bg-black/20">
        {messages.length === 0 && (
          <div className="opacity-50 text-sm p-3">
            Agent sudah membaca catatan matter ini. Ajukan pertanyaan,
            atau gunakan tombol aksi di tab Overview untuk operasi cepat.
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
        {busy && <div className="opacity-60 text-sm px-3">Asisten sedang berpikir…</div>}
      </div>

      <div className="flex gap-2">
        <textarea
          className="flex-1 bg-white/5 rounded px-3 py-2 resize-none"
          rows={2}
          placeholder="Tulis pertanyaan…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={busy}
        />
        <button
          onClick={() => send()}
          disabled={busy}
          className="px-4 py-2 rounded bg-accent disabled:opacity-50"
        >
          Kirim
        </button>
      </div>
    </div>
  );
}
