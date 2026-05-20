"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { MatterChat } from "@/components/workspace/MatterChat";

type Matter = {
  id: number;
  slug: string;
  name: string;
  client: string | null;
  description: string | null;
  notes_md: string | null;
  status: string;
};

type Doc = { id: number; title: string; kind: string; source_filename: string | null };
type Activity = {
  kind: "turn" | "document";
  role?: string;
  text?: string;
  title?: string;
  doc_kind?: string;
  at: string | null;
  document_id?: number;
};

type Tab = "overview" | "documents" | "chat" | "activity";

export default function MatterDetail() {
  const params = useParams<{ id: string }>();
  const id = params?.id ? parseInt(params.id, 10) : null;
  const [tab, setTab] = useState<Tab>("overview");
  const [matter, setMatter] = useState<Matter | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/matters/${id}`).then((r) => r.json()).then(setMatter).catch(() => {});
    fetch(`/api/matters/${id}/documents`).then((r) => r.json()).then(setDocs).catch(() => {});
    fetch(`/api/matters/${id}/activity`).then((r) => r.json()).then(setActivity).catch(() => {});
  }, [id, tab]);

  if (!matter) return <div className="opacity-60">Memuat…</div>;

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <div className="text-xs opacity-60">
          <Link href="/" className="hover:underline">Matters</Link> /{" "}
          <span>{matter.name}</span>
        </div>
        <h1 className="text-2xl font-bold">{matter.name}</h1>
        <div className="flex gap-4 text-xs opacity-70">
          {matter.client && <span>Klien: {matter.client}</span>}
          <span>Status: {matter.status}</span>
        </div>
      </header>

      <nav className="flex gap-1 border-b border-white/10">
        {(["overview", "documents", "chat", "activity"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm capitalize ${
              tab === t
                ? "border-b-2 border-accent text-accent"
                : "opacity-70 hover:opacity-100"
            }`}
          >
            {t === "overview"
              ? "Overview"
              : t === "documents"
              ? `Dokumen (${docs.length})`
              : t === "chat"
              ? "Chat"
              : "Aktivitas"}
          </button>
        ))}
      </nav>

      <section className="pt-2">
        {tab === "overview" && <OverviewTab matter={matter} onChange={setMatter} />}
        {tab === "documents" && <DocumentsTab docs={docs} />}
        {tab === "chat" && <MatterChat matterId={matter.id} matterName={matter.name} />}
        {tab === "activity" && <ActivityTab events={activity} />}
      </section>
    </div>
  );
}

function OverviewTab({ matter, onChange }: { matter: Matter; onChange: (m: Matter) => void }) {
  const [notes, setNotes] = useState(matter.notes_md || "");
  const [saving, setSaving] = useState(false);
  const dirty = notes !== (matter.notes_md || "");

  async function save() {
    setSaving(true);
    try {
      const res = await fetch(`/api/matters/${matter.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes_md: notes }),
      });
      const next = await res.json();
      onChange(next);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="md:col-span-2 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm uppercase opacity-60 tracking-wider">
            MATTER.md — catatan yang dibaca agent setiap turn
          </h2>
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="text-xs px-2 py-1 rounded bg-accent disabled:opacity-40"
          >
            {saving ? "Menyimpan…" : dirty ? "Simpan" : "Tersimpan"}
          </button>
        </div>
        <textarea
          className="w-full bg-white/5 rounded p-3 font-mono text-sm min-h-[50vh]"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      <aside className="space-y-3">
        <h2 className="text-sm uppercase opacity-60 tracking-wider">Info</h2>
        <div className="p-3 rounded bg-white/5 text-sm space-y-1">
          <div><span className="opacity-60">Slug:</span> <code>{matter.slug}</code></div>
          {matter.description && <div className="opacity-80">{matter.description}</div>}
        </div>
        <p className="text-xs opacity-60">
          Tulis fakta-fakta kunci di sini. Agent akan menggunakannya sebagai
          konteks tanpa Anda perlu mengulanginya di setiap pesan.
        </p>
      </aside>
    </div>
  );
}

function DocumentsTab({ docs }: { docs: Doc[] }) {
  if (docs.length === 0) {
    return (
      <div className="p-6 rounded-lg border border-dashed border-white/15 opacity-70">
        Belum ada dokumen di matter ini. Buat draft via tab <em>Chat</em>{" "}
        (mis. <code>/draft nda</code>), atau upload kontrak di phase berikutnya.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {docs.map((d) => (
        <li key={d.id} className="p-3 rounded border border-white/10 flex items-center gap-3">
          <span className="text-xs opacity-60 uppercase">{d.kind}</span>
          <Link href={`/documents/${d.id}`} className="font-semibold hover:text-accent">
            {d.title}
          </Link>
          {d.source_filename && (
            <span className="text-xs opacity-50">({d.source_filename})</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function ActivityTab({ events }: { events: Activity[] }) {
  if (events.length === 0) {
    return <div className="opacity-60">Belum ada aktivitas di matter ini.</div>;
  }
  return (
    <ul className="space-y-2">
      {events.map((e, i) => (
        <li key={i} className="p-3 rounded border border-white/10 text-sm">
          <div className="flex items-center gap-2 text-xs opacity-60 mb-1">
            <span>{e.kind === "turn" ? "💬 chat" : "📄 dokumen"}</span>
            {e.at && <span>· {new Date(e.at).toLocaleString("id-ID")}</span>}
          </div>
          {e.kind === "turn" ? (
            <div className="whitespace-pre-wrap line-clamp-3">
              <span className="opacity-60">{e.role}:</span> {e.text}
            </div>
          ) : (
            <Link href={`/documents/${e.document_id}`} className="hover:text-accent">
              {e.title}{" "}
              <span className="opacity-60 text-xs">({e.doc_kind})</span>
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}
