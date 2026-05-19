"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Doc = { id: number; title: string; kind: string; template_id: string | null };
type Tmpl = { id: string; title: string };

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [templates, setTemplates] = useState<Tmpl[]>([]);

  useEffect(() => {
    fetch("/api/documents").then((r) => r.json()).then(setDocs).catch(() => setDocs([]));
    fetch("/api/documents/templates")
      .then((r) => r.json())
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">Dokumen</h1>

      <section>
        <h2 className="text-xl mb-2">Template tersedia</h2>
        <div className="grid grid-cols-2 gap-3">
          {templates.map((t) => (
            <div key={t.id} className="p-3 rounded border border-white/10">
              <div className="font-semibold">{t.title}</div>
              <div className="text-xs opacity-50">{t.id}</div>
            </div>
          ))}
          {templates.length === 0 && (
            <div className="opacity-60">Tidak ada template terdeteksi.</div>
          )}
        </div>
        <p className="text-xs opacity-60 mt-2">
          Buat draft via chat: <em>“Tolong buatkan NDA antara PT A dan PT B…”</em>
        </p>
      </section>

      <section>
        <h2 className="text-xl mb-2">Draft yang sudah dibuat</h2>
        <ul className="space-y-2">
          {docs.map((d) => (
            <li key={d.id} className="p-3 rounded border border-white/10">
              <Link href={`/documents/${d.id}`} className="font-semibold hover:text-accent">
                {d.title}
              </Link>
              <div className="text-xs opacity-50">
                {d.kind}
                {d.template_id ? ` · ${d.template_id}` : ""}
              </div>
            </li>
          ))}
          {docs.length === 0 && (
            <div className="opacity-60">Belum ada draft. Mulai dari Chat.</div>
          )}
        </ul>
      </section>
    </div>
  );
}
