"use client";

import { useState } from "react";

export type Citation = {
  label: string;
  peraturan: string;
  pasal: string;
  ayat?: string | null;
  huruf?: string | null;
  pasal_id?: number | null;
  verified: boolean;
};

type PasalDetail = {
  id: number;
  nomor: string;
  teks: string;
  ayat: { id: number; nomor: string; teks: string; huruf: { huruf: string; teks: string }[] }[];
  peraturan: { label: string; judul: string };
};

export function PasalChip({ c }: { c: Citation }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<PasalDetail | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (detail || !c.pasal_id) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/corpus/pasal/${c.pasal_id}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <span className="relative inline-block">
      <button
        className={`text-xs px-2 py-1 rounded ${
          c.verified ? "bg-accent/30 hover:bg-accent/50" : "bg-red-500/30"
        }`}
        title={c.verified ? "Klik untuk lihat teks pasal" : "Citation tidak terverifikasi"}
        onMouseEnter={load}
        onClick={() => {
          load();
          setOpen((x) => !x);
        }}
      >
        {c.label}
        {!c.verified && " ⚠"}
      </button>
      {open && (
        <div className="absolute z-10 left-0 mt-1 w-96 max-h-80 overflow-y-auto p-3 rounded-lg border border-white/20 bg-background shadow-lg text-sm">
          {loading && <div className="opacity-60">Memuat…</div>}
          {detail && (
            <div className="space-y-2">
              <div className="font-semibold text-xs opacity-70">
                {detail.peraturan.label} — {detail.peraturan.judul}
              </div>
              <div className="font-semibold">Pasal {detail.nomor}</div>
              {detail.teks && <div className="whitespace-pre-wrap">{detail.teks}</div>}
              {detail.ayat?.map((a) => (
                <div key={a.id} className="pl-3">
                  <span className="opacity-60">({a.nomor})</span> {a.teks}
                  {a.huruf?.map((h) => (
                    <div key={h.huruf} className="pl-4">
                      <span className="opacity-60">{h.huruf}.</span> {h.teks}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
          {!loading && !detail && (
            <div className="opacity-60">Tidak ada teks tersedia.</div>
          )}
        </div>
      )}
    </span>
  );
}
