"use client";

import { useEffect, useState } from "react";

type Playbook = { slug: string; name: string; description: string };

export default function PlaybooksPage() {
  const [items, setItems] = useState<Playbook[]>([]);
  useEffect(() => {
    fetch("/api/flows").then((r) => r.json()).then(setItems).catch(() => setItems([]));
  }, []);
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold">Playbooks</h1>
      <p className="opacity-70">
        Playbook adalah resep tetap untuk SOP hukum yang sering diulang (mis.
        Draft NDA, Tinjau Kontrak Vendor). Daripada drag-and-drop DAG, di
        LegalAI Anda menjalankannya lewat <em>chat</em> — agent yang memilih
        playbook tepat untuk permintaan Anda. Daftar di bawah ini bisa juga
        Anda panggil eksplisit, contoh: <code>/find ...</code>, <code>/draft
        ...</code>, <code>/review</code>, <code>/memo ...</code>.
      </p>
      <div className="grid grid-cols-1 gap-3">
        {items.map((p) => (
          <div key={p.slug} className="p-3 rounded border border-white/10">
            <div className="font-semibold">{p.name}</div>
            <div className="text-sm opacity-70">{p.description}</div>
            <div className="text-xs opacity-50 mt-1 font-mono">{p.slug}</div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="opacity-60">Belum ada playbook tersedia.</div>
        )}
      </div>
    </div>
  );
}
