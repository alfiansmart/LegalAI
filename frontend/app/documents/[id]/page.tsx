"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { DocumentEditor } from "@/components/document-editor/Editor";

type Version = { version: number; content: string; note: string | null; created_at: string | null };
type Doc = { id: number; title: string; kind: string; template_id: string | null; versions: Version[] };

export default function DocumentDetail() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [doc, setDoc] = useState<Doc | null>(null);
  const [content, setContent] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/documents/${id}`)
      .then((r) => r.json())
      .then((d: Doc) => {
        setDoc(d);
        const last = d.versions[d.versions.length - 1];
        setContent(last?.content ?? "");
        setDirty(false);
      })
      .catch(() => setDoc(null));
  }, [id]);

  async function save() {
    if (!id) return;
    setSaving(true);
    try {
      await fetch(`/api/documents/${id}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, note: "manual edit" }),
      });
      setDirty(false);
      // refresh
      const next = await fetch(`/api/documents/${id}`).then((r) => r.json());
      setDoc(next);
    } finally {
      setSaving(false);
    }
  }

  function exportAs(fmt: "docx" | "md") {
    if (!id) return;
    window.open(`/api/documents/${id}/export?format=${fmt}`, "_blank");
  }

  if (!doc) return <div className="opacity-60">Memuat…</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{doc.title}</h1>
          <div className="text-xs opacity-60">
            {doc.kind} · {doc.template_id ?? "tanpa template"} · v{doc.versions.length}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => exportAs("md")} className="px-3 py-1 rounded bg-white/10 text-sm">
            Export .md
          </button>
          <button onClick={() => exportAs("docx")} className="px-3 py-1 rounded bg-white/10 text-sm">
            Export .docx
          </button>
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-50"
          >
            {saving ? "Menyimpan…" : "Simpan versi"}
          </button>
        </div>
      </div>
      <DocumentEditor
        value={content}
        onChange={(next) => {
          setContent(next);
          setDirty(true);
        }}
      />
    </div>
  );
}
