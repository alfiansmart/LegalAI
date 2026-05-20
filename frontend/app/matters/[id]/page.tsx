"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { MatterChat } from "@/components/workspace/MatterChat";
import { TaskCards } from "@/components/workspace/TaskCards";

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

      <section className="pt-2 space-y-4">
        {(tab === "overview" || tab === "documents") && (
          <TaskCards
            matterId={matter.id}
            documentIds={docs.map((d) => d.id)}
            onComplete={() => {
              // Refresh docs list after a task completes (upload, draft, research-memo).
              fetch(`/api/matters/${matter.id}/documents`)
                .then((r) => r.json())
                .then(setDocs)
                .catch(() => {});
            }}
          />
        )}
        {tab === "overview" && <OverviewTab matter={matter} onChange={setMatter} />}
        {tab === "documents" && <DocumentsTab docs={docs} matterId={matter.id} />}
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

function DocumentsTab({ docs, matterId }: { docs: Doc[]; matterId: number }) {
  if (docs.length === 0) {
    return (
      <div className="p-6 rounded-lg border border-dashed border-white/15 opacity-70">
        Belum ada dokumen di matter ini. Klik <strong>📤 Upload</strong> atau{" "}
        <strong>✍️ Draft</strong> di atas untuk memulai.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {docs.map((d) => (
        <DocRow key={d.id} doc={d} matterId={matterId} />
      ))}
    </ul>
  );
}

function DocRow({ doc, matterId }: { doc: Doc; matterId: number }) {
  return (
    <li className="p-3 rounded border border-white/10 flex items-center gap-3 flex-wrap">
      <span className="text-xs opacity-60 uppercase">{doc.kind}</span>
      <Link href={`/documents/${doc.id}`} className="font-semibold hover:text-accent">
        {doc.title}
      </Link>
      {doc.source_filename && (
        <span className="text-xs opacity-50">({doc.source_filename})</span>
      )}
      <div className="ml-auto">
        <PerDocButtons docId={doc.id} matterId={matterId} />
      </div>
    </li>
  );
}

function PerDocButtons({ docId, matterId }: { docId: number; matterId: number }) {
  void matterId;
  const [open, setOpen] = useState<null | "review" | "summarize" | "extract">(null);
  return (
    <>
      <div className="flex gap-1">
        {(["review", "summarize", "extract"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setOpen(t)}
            className="text-xs px-2 py-1 rounded bg-white/5 hover:bg-accent/20"
          >
            {t === "review" ? "🔍 Review" : t === "summarize" ? "📝 Ringkas" : "🧾 Ekstrak"}
          </button>
        ))}
      </div>
      {open && <InlineRunner task={open} docId={docId} onClose={() => setOpen(null)} />}
    </>
  );
}

function InlineRunner({
  task,
  docId,
  onClose,
}: {
  task: "review" | "summarize" | "extract";
  docId: number;
  onClose: () => void;
}) {
  // Reuse TaskRunner via dynamic-ish wrapper: feed only one document_id.
  const [Renderer, setRenderer] = useState<React.ComponentType<{
    task: "review" | "summarize" | "extract";
    matterId: number;
    documentIds: number[];
    onClose: () => void;
  }> | null>(null);
  useEffect(() => {
    import("@/components/workspace/TaskRunner").then((mod) => {
      // TaskRunner accepts wider TaskKind; we cast accordingly.
      setRenderer(() => mod.TaskRunner as unknown as typeof Renderer);
    });
  }, []);
  if (!Renderer) return null;
  return <Renderer task={task} matterId={0} documentIds={[docId]} onClose={onClose} />;
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
