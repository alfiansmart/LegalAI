"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Matter = {
  id: number;
  slug: string;
  name: string;
  client: string | null;
  description: string | null;
  status: string;
  updated_at: string | null;
};

export default function HomePage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  useEffect(() => {
    fetch("/api/matters").then((r) => r.json()).then(setMatters).catch(() => {});
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold">Workspace</h1>
        <p className="opacity-70 mt-1">
          Setiap perkara hidup di dalam <em>Matter</em>: catatan, dokumen, riset,
          dan chat — semuanya terhubung. Buka matter untuk mulai bekerja.
        </p>
      </header>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl">Matters aktif</h2>
          <Link
            href="/matters/new"
            className="px-3 py-1.5 rounded bg-accent text-sm hover:bg-accent/80"
          >
            + Matter baru
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {matters
            .filter((m) => m.status === "active")
            .map((m) => (
              <Link
                key={m.id}
                href={`/matters/${m.id}`}
                className="block p-4 rounded-lg border border-white/10 hover:border-accent/60 transition"
              >
                <div className="font-semibold">{m.name}</div>
                {m.client && (
                  <div className="text-xs opacity-60 mt-0.5">Klien: {m.client}</div>
                )}
                {m.description && (
                  <div className="text-sm opacity-70 mt-2 line-clamp-2">{m.description}</div>
                )}
              </Link>
            ))}
          {matters.length === 0 && (
            <div className="col-span-2 p-6 text-center rounded-lg border border-dashed border-white/15 opacity-70">
              Belum ada matter.{" "}
              <Link href="/matters/new" className="underline">Buat matter pertama</Link>{" "}
              untuk mulai bekerja.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
