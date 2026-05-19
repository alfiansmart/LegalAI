"use client";

import { useState } from "react";
import { Citation, PasalChip } from "@/components/citation/PasalChip";

type Message = { role: "user" | "assistant"; text: string; citations?: Citation[] };

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send() {
    if (!input.trim()) return;
    const userMsg: Message = { role: "user", text: input };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          agent: "asisten_hukum",
          message: userMsg.text,
        }),
      });
      const data = await res.json();
      setSessionId(data.session_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: data.reply, citations: data.citations },
      ]);
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
    <div className="max-w-3xl mx-auto flex flex-col h-[75vh]">
      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.length === 0 && (
          <div className="opacity-50 text-sm">
            Contoh: <em>“Apa syarat sah perjanjian menurut KUHPerdata?”</em>
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
        <input
          className="flex-1 bg-white/5 rounded px-3 py-2"
          placeholder="Tanyakan tentang peraturan…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          disabled={busy}
        />
        <button
          className="px-4 py-2 rounded bg-accent disabled:opacity-50"
          onClick={send}
          disabled={busy}
        >
          Kirim
        </button>
      </div>
    </div>
  );
}
