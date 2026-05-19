import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "LegalAI",
  description: "Indonesian Legal Agent Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="bg-background text-foreground min-h-screen">
        <header className="border-b border-white/10 p-4 flex gap-6">
          <Link href="/" className="font-semibold">LegalAI</Link>
          <nav className="flex gap-4 text-sm opacity-80">
            <Link href="/chat">Chat</Link>
            <Link href="/flows">Flows</Link>
            <Link href="/documents">Documents</Link>
            <Link href="/admin">Admin</Link>
          </nav>
        </header>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
