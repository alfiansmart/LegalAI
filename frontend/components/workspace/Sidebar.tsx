"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

type Matter = { id: number; slug: string; name: string; client: string | null; status: string };

export function Sidebar() {
  const pathname = usePathname();
  const [matters, setMatters] = useState<Matter[]>([]);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    fetch("/api/matters")
      .then((r) => r.json())
      .then(setMatters)
      .catch(() => setMatters([]));
  }, [pathname]);

  return (
    <aside
      className={`shrink-0 border-r border-white/10 transition-all ${
        open ? "w-64" : "w-12"
      } bg-black/20`}
    >
      <div className="flex items-center justify-between px-3 py-3">
        <Link href="/" className={`font-semibold ${open ? "" : "hidden"}`}>
          LegalAI
        </Link>
        <button
          className="text-xs opacity-60 hover:opacity-100"
          onClick={() => setOpen((x) => !x)}
          aria-label="toggle sidebar"
        >
          {open ? "«" : "»"}
        </button>
      </div>

      {open && (
        <nav className="px-2 py-1 space-y-4 text-sm">
          <section>
            <div className="flex items-center justify-between px-2 mb-1">
              <span className="text-xs uppercase opacity-50 tracking-wider">Matters</span>
              <Link href="/matters/new" className="text-xs opacity-70 hover:opacity-100">+ Baru</Link>
            </div>
            <ul className="space-y-0.5">
              {matters.map((m) => (
                <li key={m.id}>
                  <Link
                    href={`/matters/${m.id}`}
                    className={`block px-2 py-1.5 rounded hover:bg-white/5 truncate ${
                      pathname?.startsWith(`/matters/${m.id}`) ? "bg-accent/20" : ""
                    }`}
                    title={m.client ? `${m.name} — ${m.client}` : m.name}
                  >
                    📁 {m.name}
                  </Link>
                </li>
              ))}
              {matters.length === 0 && (
                <li className="px-2 py-1 opacity-50 text-xs">Belum ada matter.</li>
              )}
            </ul>
          </section>

          <section>
            <div className="px-2 mb-1">
              <span className="text-xs uppercase opacity-50 tracking-wider">Library</span>
            </div>
            <ul className="space-y-0.5">
              <SidebarLink href="/library/peraturan" label="📚 Peraturan" pathname={pathname} />
              <SidebarLink href="/documents" label="📋 Dokumen" pathname={pathname} />
              <SidebarLink href="/flows" label="🔖 Playbooks" pathname={pathname} />
            </ul>
          </section>

          <section>
            <div className="px-2 mb-1">
              <span className="text-xs uppercase opacity-50 tracking-wider">Workspace</span>
            </div>
            <ul className="space-y-0.5">
              <SidebarLink href="/chat" label="💬 Chat global" pathname={pathname} />
              <SidebarLink href="/admin" label="⚙️ Admin" pathname={pathname} />
            </ul>
          </section>
        </nav>
      )}
    </aside>
  );
}

function SidebarLink({
  href,
  label,
  pathname,
}: {
  href: string;
  label: string;
  pathname: string | null;
}) {
  const active = pathname === href;
  return (
    <li>
      <Link
        href={href}
        className={`block px-2 py-1.5 rounded hover:bg-white/5 ${
          active ? "bg-accent/20" : ""
        }`}
      >
        {label}
      </Link>
    </li>
  );
}
