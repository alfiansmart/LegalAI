"use client";

/**
 * TaskRunner — unified modal that hosts the input form for any task and
 * renders its structured result (text + artifacts) once the API returns.
 *
 * Each task has a tiny per-task form (sometimes none) and shares the
 * same result rendering: status text, summary fields, plus artifacts
 * via ArtifactRenderer.
 */
import { useEffect, useState } from "react";
import { ArtifactRenderer, type Artifact } from "@/components/artifacts/ArtifactRenderer";

export type TaskKind =
  | "upload"
  | "draft"
  | "review"
  | "compare"
  | "research"
  | "summarize"
  | "extract";

type TaskResult = {
  status: string;
  artifacts?: Artifact[];
  [k: string]: unknown;
};

type Props = {
  task: TaskKind;
  matterId: number;
  documentIds?: number[];
  onClose: () => void;
};

const TITLES: Record<TaskKind, string> = {
  upload: "📤 Upload dokumen",
  draft: "✍️ Draft perjanjian",
  review: "🔍 Review kontrak",
  compare: "⚖️ Compare dengan baseline",
  research: "📚 Research hukum",
  summarize: "📝 Ringkas dokumen",
  extract: "🧾 Ekstrak fakta",
};

export function TaskRunner({ task, matterId, documentIds = [], onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-neutral-900 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between p-4 border-b border-white/10">
          <h2 className="text-lg font-semibold">{TITLES[task]}</h2>
          <button onClick={onClose} className="text-xl opacity-60 hover:opacity-100">
            ×
          </button>
        </header>
        <div className="p-4">
          {task === "upload" && <UploadForm matterId={matterId} onClose={onClose} />}
          {task === "draft" && <DraftForm matterId={matterId} />}
          {task === "review" && (
            <DocumentScopedTask
              endpoint="/api/tasks/review"
              documentIds={documentIds}
              extraFields={<></>}
            />
          )}
          {task === "compare" && <CompareForm documentIds={documentIds} />}
          {task === "research" && <ResearchForm matterId={matterId} />}
          {task === "summarize" && (
            <DocumentScopedTask
              endpoint="/api/tasks/summarize"
              documentIds={documentIds}
            />
          )}
          {task === "extract" && (
            <DocumentScopedTask
              endpoint="/api/tasks/extract-facts"
              documentIds={documentIds}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- Upload ----------

function UploadForm({ matterId, onClose }: { matterId: number; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("matter_id", String(matterId));
      fd.append("title", file.name);
      const res = await fetch("/api/tasks/upload-and-index", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult({ status: "ok", ...data });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-3">
        <div className="text-sm">
          ✅ Diproses. {String(result["chunks_inserted"])} chunk,{" "}
          {String(result["outline_nodes"])} node outline,{" "}
          {String(result["terms_extracted"])} defined terms,{" "}
          {String(result["citations_inferred"])} rujukan peraturan.
        </div>
        <button onClick={onClose} className="px-3 py-1 rounded bg-accent text-sm">
          Tutup
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <input
        type="file"
        accept=".pdf,.docx,.md,.txt"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="block text-sm"
      />
      {file && <div className="text-xs opacity-70">{file.name} — {file.size} bytes</div>}
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <button
        onClick={submit}
        disabled={!file || busy}
        className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
      >
        {busy ? "Memproses…" : "Upload"}
      </button>
    </div>
  );
}

// ---------- Draft ----------

function DraftForm({ matterId }: { matterId: number }) {
  // Two drafting modes:
  //   "template"    — classic flow: pick template, fill params (rigid)
  //   "describe"    — AI-assisted: describe the doc in plain Bahasa,
  //                   AI generates a full structure (no template needed)
  const [mode, setMode] = useState<"template" | "describe">("describe");
  const [templates, setTemplates] = useState<{ id: string; title: string }[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [partiesRaw, setPartiesRaw] = useState("PT Alpha\nPT Beta");
  const [paramsRaw, setParamsRaw] = useState("{}");
  const [includeClauses, setIncludeClauses] = useState("force_majeure,arbitrase_bani");
  const [description, setDescription] = useState(
    "NDA dua arah antara PT Alpha (vendor IT) dan PT Beta (klien), jangka waktu 24 bulan, mencakup force majeure dan arbitrase BANI."
  );
  const [docKind, setDocKind] = useState("perjanjian");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/documents/templates")
      .then((r) => r.json())
      .then((rows) => {
        setTemplates(rows);
        if (rows[0]) setTemplateId(rows[0].id);
      })
      .catch(() => {});
  }, []);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      let res: Response;
      if (mode === "describe") {
        res = await fetch("/api/tasks/draft-from-description", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            description,
            doc_kind: docKind,
            matter_id: matterId,
          }),
        });
      } else {
        const body = {
          template_id: templateId,
          parties: partiesRaw.split("\n").map((p) => p.trim()).filter(Boolean),
          params: JSON.parse(paramsRaw || "{}"),
          include_clauses: includeClauses.split(",").map((s) => s.trim()).filter(Boolean),
          matter_id: matterId,
        };
        res = await fetch("/api/tasks/draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return <TaskResultView result={result} extraLink={result.document_id ? `/documents/${result.document_id}` : null} />;
  }

  return (
    <div className="space-y-3 text-sm">
      <div className="flex gap-1 text-xs">
        {(["describe", "template"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-2 py-1 rounded ${
              mode === m ? "bg-accent" : "bg-white/5 hover:bg-white/10"
            }`}
          >
            {m === "describe" ? "🪄 Deskripsikan saja" : "📋 Pilih template"}
          </button>
        ))}
      </div>

      {mode === "describe" && (
        <>
          <label className="block">
            <span className="text-xs opacity-60">
              Deskripsi dokumen (Bahasa Indonesia bebas — para pihak, tujuan,
              jangka waktu, klausa penting, dst.)
            </span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-white/5 rounded px-2 py-1 text-xs"
              rows={6}
              placeholder="Contoh: Perjanjian sewa-menyewa ruko di Jakarta antara PT Alpha (penyewa) dan Pak Budi (pemilik), 3 tahun, harga sewa Rp 200 juta per tahun, deposit 3 bulan, opsi perpanjangan otomatis…"
            />
          </label>
          <label className="block">
            <span className="text-xs opacity-60">Jenis dokumen</span>
            <select
              value={docKind}
              onChange={(e) => setDocKind(e.target.value)}
              className="w-full bg-white/5 rounded px-2 py-1"
            >
              {[
                "perjanjian",
                "memo",
                "opini",
                "somasi",
                "gugatan",
                "surat_kuasa",
                "lainnya",
              ].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </label>
          {err && <div className="text-xs text-rose-300">{err}</div>}
          <button
            onClick={submit}
            disabled={busy || !description.trim()}
            className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
          >
            {busy ? "Menyusun…" : "Buat draft (AI)"}
          </button>
          <div className="text-xs opacity-60 pt-2 border-t border-white/10">
            Setelah draft selesai, Anda dapat menyempurnakan lewat tombol{" "}
            <em>Revise dengan AI</em> di halaman dokumen — pilih teks,
            beri instruksi, dan AI mengusulkan revisi yang bisa Anda
            terima atau tolak per perubahan.
          </div>
        </>
      )}

      {mode === "template" && (
        <>
          <label className="block">
            <span className="text-xs opacity-60">Template</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="w-full bg-white/5 rounded px-2 py-1"
            >
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.title}</option>
              ))}
            </select>
          </label>
      <label className="block">
        <span className="text-xs opacity-60">Para Pihak (satu baris satu pihak)</span>
        <textarea
          value={partiesRaw}
          onChange={(e) => setPartiesRaw(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1 font-mono text-xs"
          rows={3}
        />
      </label>
      <label className="block">
        <span className="text-xs opacity-60">Params (JSON)</span>
        <textarea
          value={paramsRaw}
          onChange={(e) => setParamsRaw(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1 font-mono text-xs"
          rows={3}
        />
      </label>
          <label className="block">
            <span className="text-xs opacity-60">Klausa standar (CSV)</span>
            <input
              value={includeClauses}
              onChange={(e) => setIncludeClauses(e.target.value)}
              className="w-full bg-white/5 rounded px-2 py-1"
            />
          </label>
          {err && <div className="text-xs text-rose-300">{err}</div>}
          <button
            onClick={submit}
            disabled={busy || !templateId}
            className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
          >
            {busy ? "Menyusun…" : "Buat draft"}
          </button>
        </>
      )}
    </div>
  );
}

// ---------- Compare ----------

function CompareForm({ documentIds }: { documentIds: number[] }) {
  const [head, setHead] = useState<string>(documentIds[0]?.toString() ?? "");
  const [baseTemplate, setBaseTemplate] = useState("nda");
  const [baseDoc, setBaseDoc] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = { head_document_id: parseInt(head, 10) };
      if (baseDoc) body.base_document_id = parseInt(baseDoc, 10);
      else body.base_template_id = baseTemplate;
      const res = await fetch("/api/tasks/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (result) return <TaskResultView result={result} />;

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="text-xs opacity-60">Head document_id</span>
        <input
          value={head}
          onChange={(e) => setHead(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1"
        />
      </label>
      <label className="block">
        <span className="text-xs opacity-60">Baseline template (mis. nda)</span>
        <input
          value={baseTemplate}
          onChange={(e) => setBaseTemplate(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1"
        />
      </label>
      <label className="block">
        <span className="text-xs opacity-60">…atau document_id baseline</span>
        <input
          value={baseDoc}
          onChange={(e) => setBaseDoc(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1"
          placeholder="kosongkan kalau pakai template"
        />
      </label>
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <button
        onClick={submit}
        disabled={busy || !head}
        className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
      >
        {busy ? "Membandingkan…" : "Compare"}
      </button>
    </div>
  );
}

// ---------- Research ----------

function ResearchForm({ matterId }: { matterId: number }) {
  const [issue, setIssue] = useState("");
  const [asOf, setAsOf] = useState("");
  const [saveMemo, setSaveMemo] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/tasks/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issue,
          as_of: asOf || null,
          save_as_memo: saveMemo,
          matter_id: matterId,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (result)
    return (
      <TaskResultView
        result={result}
        extraLink={
          result.memo_document_id
            ? `/documents/${result.memo_document_id}`
            : null
        }
      />
    );

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="text-xs opacity-60">Isu hukum</span>
        <textarea
          value={issue}
          onChange={(e) => setIssue(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1"
          rows={3}
          placeholder="Force majeure dalam kontrak B2B"
        />
      </label>
      <label className="block">
        <span className="text-xs opacity-60">As-of (opsional)</span>
        <input
          value={asOf}
          type="date"
          onChange={(e) => setAsOf(e.target.value)}
          className="bg-white/5 rounded px-2 py-1"
        />
      </label>
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={saveMemo}
          onChange={(e) => setSaveMemo(e.target.checked)}
        />
        Simpan sebagai memo
      </label>
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <button
        onClick={submit}
        disabled={busy || !issue.trim()}
        className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
      >
        {busy ? "Meneliti…" : "Research"}
      </button>
    </div>
  );
}

// ---------- Generic document-scoped task (Review / Summarize / Extract) ----------

function DocumentScopedTask({
  endpoint,
  documentIds,
  extraFields,
}: {
  endpoint: string;
  documentIds: number[];
  extraFields?: React.ReactNode;
}) {
  const [docId, setDocId] = useState<string>(documentIds[0]?.toString() ?? "");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TaskResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: parseInt(docId, 10) }),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (result) return <TaskResultView result={result} />;

  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="text-xs opacity-60">Document ID</span>
        <input
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className="w-full bg-white/5 rounded px-2 py-1"
          placeholder="123"
        />
      </label>
      {extraFields}
      {err && <div className="text-xs text-rose-300">{err}</div>}
      <button
        onClick={submit}
        disabled={busy || !docId}
        className="px-3 py-1 rounded bg-accent text-sm disabled:opacity-40"
      >
        {busy ? "Memproses…" : "Jalankan"}
      </button>
    </div>
  );
}

// ---------- Shared result view ----------

function TaskResultView({
  result,
  extraLink,
}: {
  result: TaskResult;
  extraLink?: string | null;
}) {
  const summary =
    typeof result.summary === "string"
      ? (result.summary as string)
      : typeof result.exec_summary === "string"
        ? (result.exec_summary as string)
        : typeof result.memo_preview === "string"
          ? (result.memo_preview as string).slice(0, 400)
          : "";

  return (
    <div className="space-y-4">
      <div className="text-xs opacity-60">Status: {result.status}</div>
      {summary && <div className="text-sm whitespace-pre-wrap">{summary}</div>}
      {extraLink && (
        <a
          href={extraLink}
          className="inline-block text-xs px-2 py-1 rounded bg-accent"
        >
          Buka dokumen →
        </a>
      )}
      {result.artifacts && result.artifacts.length > 0 && (
        <div className="space-y-3">
          {result.artifacts.map((a) => (
            <ArtifactRenderer key={a.id} artifact={a} />
          ))}
        </div>
      )}
    </div>
  );
}
