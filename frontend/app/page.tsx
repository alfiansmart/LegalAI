import Link from "next/link";

export default function HomePage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">LegalAI</h1>
      <p className="opacity-80">
        Platform agentic AI khusus hukum Indonesia — riset peraturan, draft
        perjanjian, review kontrak, dan susun flow hukum secara visual.
      </p>
      <div className="grid grid-cols-2 gap-4">
        {[
          { href: "/chat", title: "Chat", desc: "Tanya jawab peraturan dengan kutipan pasal terverifikasi." },
          { href: "/flows", title: "Flow Builder", desc: "Susun SOP hukum sebagai DAG visual." },
          { href: "/documents", title: "Dokumen", desc: "Draft & review perjanjian dengan redlining." },
          { href: "/admin", title: "Admin", desc: "Kelola agent, skill, dan corpus." },
        ].map((c) => (
          <Link key={c.href} href={c.href}
                className="block p-4 rounded-lg border border-white/10 hover:border-accent/60 transition">
            <div className="font-semibold">{c.title}</div>
            <div className="text-sm opacity-70">{c.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
