"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

type Props = {
  value: string;
  onChange: (next: string) => void;
};

export function DocumentEditor({ value, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: markdownToHtml(value),
    onUpdate({ editor }) {
      onChange(htmlToMarkdown(editor.getHTML()));
    },
    immediatelyRender: false,
  });

  useEffect(() => {
    if (editor && value !== htmlToMarkdown(editor.getHTML())) {
      editor.commands.setContent(markdownToHtml(value));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, value]);

  if (!editor) return <div className="opacity-60">Memuat editor…</div>;

  return (
    <div className="prose prose-invert max-w-none">
      <div className="mb-2 flex gap-2 text-xs">
        <button onClick={() => editor.chain().focus().toggleBold().run()}
                className="px-2 py-1 rounded bg-white/10">Bold</button>
        <button onClick={() => editor.chain().focus().toggleItalic().run()}
                className="px-2 py-1 rounded bg-white/10">Italic</button>
        <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                className="px-2 py-1 rounded bg-white/10">H2</button>
        <button onClick={() => editor.chain().focus().toggleBulletList().run()}
                className="px-2 py-1 rounded bg-white/10">List</button>
      </div>
      <div className="rounded border border-white/10 p-3 min-h-[60vh] bg-white/5">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

// Minimal markdown <-> HTML for in-editor display. Full fidelity comes
// from server-side rendering on export.
function markdownToHtml(md: string): string {
  const lines = md.split(/\r?\n/);
  const out: string[] = [];
  let inList = false;
  for (const raw of lines) {
    const line = raw;
    const liMatch = line.match(/^\s*[-*]\s+(.+)$/);
    if (liMatch) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${escapeHtml(liMatch[1])}</li>`);
      continue;
    }
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    const h = line.match(/^(#{1,4})\s+(.+)$/);
    if (h) {
      const level = h[1].length;
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      continue;
    }
    if (!line.trim()) {
      out.push("<p></p>");
      continue;
    }
    out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("");
}

function inline(s: string): string {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function htmlToMarkdown(html: string): string {
  // Reasonable round-trip for what the editor produces.
  return html
    .replace(/<h1[^>]*>(.*?)<\/h1>/g, "# $1\n")
    .replace(/<h2[^>]*>(.*?)<\/h2>/g, "## $1\n")
    .replace(/<h3[^>]*>(.*?)<\/h3>/g, "### $1\n")
    .replace(/<strong>(.*?)<\/strong>/g, "**$1**")
    .replace(/<em>(.*?)<\/em>/g, "*$1*")
    .replace(/<ul[^>]*>/g, "")
    .replace(/<\/ul>/g, "\n")
    .replace(/<li[^>]*>(.*?)<\/li>/g, "- $1\n")
    .replace(/<p[^>]*>(.*?)<\/p>/g, "$1\n")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .trim();
}
