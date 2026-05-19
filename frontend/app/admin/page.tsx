"use client";

import { useEffect, useState } from "react";

export default function AdminPage() {
  const [skills, setSkills] = useState<any[]>([]);
  const [agents, setAgents] = useState<any[]>([]);
  const [stats, setStats] = useState<any | null>(null);

  useEffect(() => {
    fetch("/api/skills").then((r) => r.json()).then(setSkills).catch(() => {});
    fetch("/api/agents").then((r) => r.json()).then(setAgents).catch(() => {});
    fetch("/api/corpus/stats").then((r) => r.json()).then(setStats).catch(() => {});
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">Admin</h1>

      <section>
        <h2 className="text-xl mb-2">Korpus</h2>
        {stats ? (
          <div className="flex gap-4 text-sm">
            <span>Peraturan: {stats.peraturan ?? 0}</span>
            <span>Pasal: {stats.pasal ?? 0}</span>
            <span>Ayat: {stats.ayat ?? 0}</span>
          </div>
        ) : (
          <div className="opacity-60">Memuat statistik…</div>
        )}
      </section>

      <section>
        <h2 className="text-xl mb-2">Agents</h2>
        <ul className="space-y-2">
          {agents.map((a) => (
            <li key={a.id} className="p-3 rounded border border-white/10">
              <div className="font-semibold">{a.name}</div>
              <div className="text-sm opacity-70">{a.description}</div>
              <div className="text-xs opacity-50 mt-1">skills: {(a.skills || []).join(", ")}</div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-xl mb-2">Skills</h2>
        <ul className="space-y-2">
          {skills.map((s) => (
            <li key={s.id} className="p-3 rounded border border-white/10">
              <div className="font-semibold">{s.name}</div>
              <div className="text-sm opacity-70">{s.description}</div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
