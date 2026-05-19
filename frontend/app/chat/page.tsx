"use client";

import { useEffect, useRef, useState } from "react";
import { Citation, PasalChip } from "@/components/citation/PasalChip";
import { CommandDef, SlashPalette } from "@/components/chat/SlashPalette";
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

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [persona, setPersona] = useState("asisten_hukum");
  const [planMode, setPlanMode] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const slashOpen = input.startsWith("/") && !input.includes("\n");

  async function send(messageOverride?: string) {
    const text = (messageOverride ?? input).trim();
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
      // Reset session-resetting commands.
      if (text === "/clear") {
        setMessages([{ role: "assistant", text: data.reply }]);
        setPlanMode(false);
        return;
      }
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.reply,
          citations: data.citations,
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

  function onPickCommand(c: CommandDef) {
    setInput(c.trigger + " ");
    inputRef.current?.focus();
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
          onClick={() => send("/clear")}
          className="ml-auto px-2 py-1 rounded text-xs bg-white/10"
          disabled={busy}
        >
          /clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 mb-3">
        {messages.length === 0 && (
          <div className="opacity-50 text-sm space-y-1">
            <div>Mulai dengan slash command — ketik <code>/</code> untuk lihat daftar.</div>
            <div className="opacity-70">
              Contoh: <code>/find syarat sah perjanjian</code> ·
              <code> /draft nda</code> · <code>/cite Pasal 1320 KUHPerdata</code>
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

      <div className="relative">
        <SlashPalette
          query={input}
          visible={slashOpen}
          onPick={onPickCommand}
        />
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            className="flex-1 bg-white/5 rounded px-3 py-2 resize-none"
            placeholder='Ketik pesan atau "/" untuk slash command…'
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
    </div>
  );
}
