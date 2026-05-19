"""Slash-command parser. Translates `/cmd args` into a structured
intent the harness can execute without changing the chat contract.

Lifecycle:
  user types "/draft nda PT Alpha; PT Beta; diskusi JV; 24"
      ↓
  parse(...) → SlashIntent(command="draft", ...)
      ↓
  to_user_message(...) returns the canonical natural-language request
  the agent runs with (so the same tool loop handles everything).
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field


@dataclass(slots=True)
class SlashIntent:
    command: str
    agent: str | None = None  # override persona
    plan_mode: bool = False
    args: list[str] = field(default_factory=list)
    raw: str = ""
    help_text: str | None = None


COMMANDS: dict[str, dict] = {
    "help": {
        "desc": "Daftar slash command.",
        "usage": "/help",
    },
    "clear": {
        "desc": "Mulai sesi baru (history dilupakan).",
        "usage": "/clear",
    },
    "find": {
        "desc": "Cari pasal yang relevan dengan kueri (peraturan_search).",
        "usage": "/find <kueri>",
        "agent": "asisten_hukum",
    },
    "cite": {
        "desc": "Ambil teks eksak suatu pasal.",
        "usage": "/cite <ref>  — contoh: /cite Pasal 1320 KUHPerdata",
        "agent": "asisten_hukum",
    },
    "explain": {
        "desc": "Jelaskan suatu pasal dalam bahasa awam.",
        "usage": "/explain <ref>",
        "agent": "asisten_hukum",
    },
    "draft": {
        "desc": "Mulai draft perjanjian dari template.",
        "usage": "/draft <template> [parameter-bebas]",
        "agent": "drafter",
    },
    "review": {
        "desc": "Review klausa kontrak (paste teksnya setelah perintah).",
        "usage": "/review\n<teks kontrak>",
        "agent": "reviewer",
    },
    "memo": {
        "desc": "Susun memo hukum dari isu yang diberikan.",
        "usage": "/memo <isu hukum>",
        "agent": "researcher",
    },
    "plan": {
        "desc": "Aktifkan plan-mode untuk pesan berikutnya.",
        "usage": "/plan <permintaan>",
    },
    "agent": {
        "desc": "Ganti persona untuk pesan ini saja.",
        "usage": "/agent <asisten_hukum|drafter|reviewer|researcher>",
    },
}


def is_slash(message: str) -> bool:
    return message.lstrip().startswith("/")


def parse(message: str) -> SlashIntent | None:
    msg = message.lstrip()
    if not msg.startswith("/"):
        return None
    # Split first line from body.
    first, _, rest = msg.partition("\n")
    parts = first[1:].split(maxsplit=1)
    if not parts:
        return None
    cmd = parts[0].lower()
    body = parts[1] if len(parts) > 1 else ""
    # For commands whose body is multi-line free text (review, memo, …),
    # also fold in the rest of the original message.
    if rest:
        body = (body + "\n" + rest).strip() if body else rest
    args = _safe_split(body) if cmd in {"agent", "draft"} else [body] if body else []

    spec = COMMANDS.get(cmd)
    if not spec:
        return SlashIntent(
            command=cmd,
            raw=message,
            help_text=f"Perintah tidak dikenal: /{cmd}. Ketik `/help`.",
        )

    intent = SlashIntent(
        command=cmd,
        agent=spec.get("agent"),
        args=args,
        raw=message,
    )

    if cmd == "agent":
        # /agent <persona> rewrites the persona; remaining body goes back
        # as the user's actual message.
        if not args:
            intent.help_text = "Usage: " + spec["usage"]
        else:
            intent.agent = args[0]
            intent.args = args[1:]
    elif cmd == "plan":
        intent.plan_mode = True
    elif cmd == "help":
        intent.help_text = _help_text()
    elif cmd == "clear":
        pass  # route handles this (resets session_id)

    return intent


def to_user_message(intent: SlashIntent) -> str:
    """Render a slash intent as a canonical natural-language request the
    agent can run with its standard tool loop."""
    body = " ".join(intent.args).strip()
    match intent.command:
        case "find":
            return (
                f"Cari pasal yang relevan dengan: {body!r}. "
                f"Gunakan tool peraturan_search dan kembalikan top 8 hasil "
                f"dengan kutipan singkat."
            )
        case "cite":
            return (
                f"Ambil teks eksak dari referensi berikut menggunakan "
                f"tool pasal_lookup: {body}. Tampilkan teks pasal beserta "
                f"semua ayatnya."
            )
        case "explain":
            return (
                f"Jelaskan pasal berikut dalam bahasa awam (maksimal 2 "
                f"paragraf), pakai pasal_lookup dulu untuk dapat teks eksak: "
                f"{body}."
            )
        case "draft":
            return (
                f"Buat draft dokumen menggunakan tool contract_draft. "
                f"Parameter pengguna: {body}. Tanyakan informasi yang masih "
                f"kurang sebelum memanggil tool."
            )
        case "review":
            return (
                f"Lakukan review kontrak berikut menggunakan tool "
                f"contract_review. Kembalikan ringkasan eksekutif + findings."
                f"\n\nKontrak:\n{body}"
            )
        case "memo":
            return (
                f"Susun memo hukum terstruktur untuk isu: {body}. "
                f"Pertama jalankan peraturan_search untuk mengumpulkan "
                f"bukti, lalu legal_memo_compose."
            )
        case "plan" | "agent":
            return body or intent.raw
        case _:
            return intent.raw


def _safe_split(s: str) -> list[str]:
    try:
        return shlex.split(s)
    except ValueError:
        return s.split()


def _help_text() -> str:
    lines = ["**Slash command yang tersedia:**", ""]
    for name, spec in COMMANDS.items():
        lines.append(f"- `/{name}` — {spec['desc']}")
        lines.append(f"    usage: `{spec['usage']}`")
    return "\n".join(lines)
