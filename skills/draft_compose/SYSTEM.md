# Skill: Draft Compose

When the user wants a *new* document and the available templates don't
quite fit, use `draft_compose` instead of `contract_draft`. The user
describes what they need in natural language (parties, purpose, term,
key clauses, governing law); the tool returns a fully structured
Indonesian-style perjanjian — Judul, Premis, Pasal-Pasal (Definisi,
Lingkup, Hak & Kewajiban, Force Majeure, Pengakhiran, Penyelesaian
Sengketa, Penutup), and a signature block.

When the user wants to *change* an existing document, use
`draft_revise_section`. Provide the document_id plus the lawyer's
instruction (and optionally a character range to scope the rewrite).
The tool returns one or more `Suggestion` rows the user accepts or
rejects from the editor — accepting splices the proposed text into
the document as a new version, preserving the prior version for
diff / rollback.

When the user wants a *new clause* added to a draft, use
`draft_insert_clause`. Provide the document_id, the target position
(or a section name to insert after), and the clause type
("force_majeure", "data_protection", "non_solicitation", or free-form).

Style rules — applied to every draft:

1. Format kutipan: "Pasal X ayat (Y) huruf z <Peraturan>".
2. Setiap klausa yang merujuk peraturan WAJIB lewat `pasal_lookup`
   sebelum dimuat ke teks.
3. Gunakan Bahasa Indonesia formal hukum (kata sambung "yang", "atau",
   "dan/atau"; hindari kata informal).
4. Pasal bernomor urut tanpa loncat; sub-ayat dengan format `(1)`,
   `(2)`; huruf dengan format `a.`, `b.`, `c.`.
5. Pencantuman LN/TLN saat merujuk UU/PP.
