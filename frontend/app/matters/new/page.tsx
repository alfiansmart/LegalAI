"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function NewMatterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const res = await fetch("/api/matters", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, client, description }),
      });
      const m = await res.json();
      router.push(`/matters/${m.id}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4">
      <h1 className="text-2xl font-bold">Matter baru</h1>
      <p className="opacity-70 text-sm">
        Sebuah matter adalah unit kerja untuk satu perkara/engagement.
        Catatan, dokumen, dan chat di dalamnya akan dibaca oleh agent
        sebagai konteks.
      </p>

      <label className="block">
        <span className="text-sm opacity-80">Nama matter *</span>
        <input
          className="mt-1 w-full bg-white/5 rounded px-3 py-2"
          placeholder="PT Alpha vs PT Beta — Sengketa Vendor"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
      </label>
      <label className="block">
        <span className="text-sm opacity-80">Klien</span>
        <input
          className="mt-1 w-full bg-white/5 rounded px-3 py-2"
          placeholder="PT Alpha (in-house counsel)"
          value={client}
          onChange={(e) => setClient(e.target.value)}
        />
      </label>
      <label className="block">
        <span className="text-sm opacity-80">Ringkasan</span>
        <textarea
          className="mt-1 w-full bg-white/5 rounded px-3 py-2 resize-none"
          rows={3}
          placeholder="Singkat saja — agent akan membaca catatan lebih detail nanti."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      <button
        type="submit"
        disabled={busy || !name.trim()}
        className="px-4 py-2 rounded bg-accent disabled:opacity-50"
      >
        {busy ? "Membuat…" : "Buat matter"}
      </button>
    </form>
  );
}
