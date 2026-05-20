import "./globals.css";
import { Sidebar } from "@/components/workspace/Sidebar";

export const metadata = {
  title: "LegalAI",
  description: "Indonesian Legal Workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="bg-background text-foreground min-h-screen flex">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="px-8 py-6 max-w-6xl mx-auto">{children}</div>
        </main>
      </body>
    </html>
  );
}
