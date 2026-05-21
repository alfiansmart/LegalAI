from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.config import get_settings

EMBED_DIM = get_settings().embedding_dim


class Base(DeclarativeBase):
    pass


def count(model):
    return select(func.count()).select_from(model)


# ---------- Legal corpus ----------


class JenisPeraturan(StrEnum):
    # Article 7 hierarchy
    UUD = "UUD"  # Constitution
    TAP_MPR = "TapMPR"  # Ketetapan MPR
    UU = "UU"
    PERPPU = "Perppu"
    PP = "PP"
    PERPRES = "Perpres"
    PERDA_PROV = "PerdaProv"
    PERDA_KAB = "PerdaKab"  # Kabupaten/Kota
    # Article 8 — body-issued regulations (binding by source authority)
    PERMEN = "Permen"  # Peraturan Menteri (use `kementerian` column for specifics)
    PERMA = "Perma"  # Peraturan MA
    SEMA = "SEMA"  # Surat Edaran MA
    PER_MK = "PerMK"  # Peraturan MK
    PER_KPU = "PerKPU"
    POJK = "POJK"  # Otoritas Jasa Keuangan
    PBI = "PBI"  # Peraturan Bank Indonesia
    PADG = "PADG"  # Peraturan Anggota Dewan Gubernur BI
    PERKA = "Perka"  # Peraturan Kepala (lembaga / badan)
    PUTUSAN_MK = "PutusanMK"
    PUTUSAN_MA = "PutusanMA"
    QANUN = "Qanun"  # Aceh
    # Legacy / aggregated kitab
    PERDA = "Perda"  # kept for backward compatibility; new rows should use PerdaProv / PerdaKab
    KUHP = "KUHP"
    KUHPERDATA = "KUHPerdata"
    KUHAP = "KUHAP"
    LAINNYA = "Lainnya"


class StatusPeraturan(StrEnum):
    BERLAKU = "berlaku"
    DICABUT = "dicabut"
    DIUBAH = "diubah"
    BELUM_BERLAKU = "belum_berlaku"


class Peraturan(Base):
    __tablename__ = "peraturan"

    id: Mapped[int] = mapped_column(primary_key=True)
    jenis: Mapped[JenisPeraturan] = mapped_column(Enum(JenisPeraturan, name="jenis_peraturan"))
    nomor: Mapped[str | None] = mapped_column(String(64))
    tahun: Mapped[int | None]
    judul: Mapped[str] = mapped_column(Text)
    tentang: Mapped[str | None] = mapped_column(Text)
    tanggal_ditetapkan: Mapped[date | None] = mapped_column(Date)
    tanggal_diundangkan: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusPeraturan] = mapped_column(
        Enum(StatusPeraturan, name="status_peraturan"), default=StatusPeraturan.BERLAKU
    )
    penerbit: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_pdf_url: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # ---- Hierarchy + promulgation metadata (Phase 8) -----------------------
    # `hierarchy_level` is the level computed from `jenis` per UU 12/2011.
    # Persisted (instead of always derived) so SQL queries can sort/filter
    # by authority without joining a constants table.
    hierarchy_level: Mapped[int | None]

    # Closing-clause metadata. These are the ground truth that downstream
    # questions about "is this still in force?" / "what amended it?" rely on.
    ditetapkan_di: Mapped[str | None] = mapped_column(String(128))  # e.g. "Jakarta"
    lembaran_negara: Mapped[str | None] = mapped_column(
        String(128)
    )  # "LN 2003 No. 39"
    tambahan_lembaran_negara: Mapped[str | None] = mapped_column(
        String(128)
    )  # "TLN No. 4279"
    berita_negara: Mapped[str | None] = mapped_column(
        String(128)
    )  # used for Permen and below

    # Source authority disambiguators.
    kementerian: Mapped[str | None] = mapped_column(
        String(255)
    )  # e.g. "Tenaga Kerja" for Permenaker
    daerah: Mapped[str | None] = mapped_column(
        String(255)
    )  # e.g. "Jawa Barat" / "DKI Jakarta / Bandung"

    pasal: Mapped[list[Pasal]] = relationship(back_populates="peraturan", cascade="all, delete-orphan")
    bab: Mapped[list[Bab]] = relationship(back_populates="peraturan", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("jenis", "nomor", "tahun", name="uq_peraturan_natural"),
        Index("ix_peraturan_tahun", "tahun"),
        Index("ix_peraturan_level", "hierarchy_level"),
    )


class Bab(Base):
    __tablename__ = "bab"
    id: Mapped[int] = mapped_column(primary_key=True)
    peraturan_id: Mapped[int] = mapped_column(ForeignKey("peraturan.id", ondelete="CASCADE"))
    nomor: Mapped[str] = mapped_column(String(32))
    judul: Mapped[str | None] = mapped_column(Text)
    peraturan: Mapped[Peraturan] = relationship(back_populates="bab")


class Bagian(Base):
    __tablename__ = "bagian"
    id: Mapped[int] = mapped_column(primary_key=True)
    bab_id: Mapped[int] = mapped_column(ForeignKey("bab.id", ondelete="CASCADE"))
    nomor: Mapped[str] = mapped_column(String(32))
    judul: Mapped[str | None] = mapped_column(Text)


class Paragraf(Base):
    __tablename__ = "paragraf"
    id: Mapped[int] = mapped_column(primary_key=True)
    bagian_id: Mapped[int] = mapped_column(ForeignKey("bagian.id", ondelete="CASCADE"))
    nomor: Mapped[str] = mapped_column(String(32))
    judul: Mapped[str | None] = mapped_column(Text)


class Pasal(Base):
    __tablename__ = "pasal"
    id: Mapped[int] = mapped_column(primary_key=True)
    peraturan_id: Mapped[int] = mapped_column(ForeignKey("peraturan.id", ondelete="CASCADE"))
    bab_id: Mapped[int | None] = mapped_column(ForeignKey("bab.id", ondelete="SET NULL"))
    nomor: Mapped[str] = mapped_column(String(32))
    teks: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))

    peraturan: Mapped[Peraturan] = relationship(back_populates="pasal")
    ayat: Mapped[list[Ayat]] = relationship(back_populates="pasal", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("peraturan_id", "nomor", "effective_from", name="uq_pasal_natural"),
        Index("ix_pasal_peraturan", "peraturan_id"),
        Index(
            "ix_pasal_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Ayat(Base):
    __tablename__ = "ayat"
    id: Mapped[int] = mapped_column(primary_key=True)
    pasal_id: Mapped[int] = mapped_column(ForeignKey("pasal.id", ondelete="CASCADE"))
    nomor: Mapped[str] = mapped_column(String(16))
    teks: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))

    pasal: Mapped[Pasal] = relationship(back_populates="ayat")
    huruf: Mapped[list[Huruf]] = relationship(back_populates="ayat", cascade="all, delete-orphan")


class Huruf(Base):
    __tablename__ = "huruf"
    id: Mapped[int] = mapped_column(primary_key=True)
    ayat_id: Mapped[int] = mapped_column(ForeignKey("ayat.id", ondelete="CASCADE"))
    huruf: Mapped[str] = mapped_column(String(8))
    teks: Mapped[str] = mapped_column(Text)
    ayat: Mapped[Ayat] = relationship(back_populates="huruf")


# ---------- Graphs ----------


class CitationKind(StrEnum):
    REFERS = "refers"
    AMENDS = "amends"
    REPEALS = "repeals"
    IMPLEMENTS = "implements"
    DASAR_HUKUM = "dasar_hukum"
    TURUNAN = "turunan"


class CitationEdge(Base):
    __tablename__ = "citation_edge"
    id: Mapped[int] = mapped_column(primary_key=True)
    src_pasal_id: Mapped[int] = mapped_column(ForeignKey("pasal.id", ondelete="CASCADE"))
    dst_pasal_id: Mapped[int] = mapped_column(ForeignKey("pasal.id", ondelete="CASCADE"))
    kind: Mapped[CitationKind] = mapped_column(Enum(CitationKind, name="citation_kind"))
    __table_args__ = (
        UniqueConstraint("src_pasal_id", "dst_pasal_id", "kind", name="uq_citation"),
        Index("ix_citation_src", "src_pasal_id"),
        Index("ix_citation_dst", "dst_pasal_id"),
    )


class ConceptNode(Base):
    __tablename__ = "concept_node"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[str] = mapped_column(String(64))  # concept|party|institution|term
    summary: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))


class ConceptEdge(Base):
    __tablename__ = "concept_edge"
    id: Mapped[int] = mapped_column(primary_key=True)
    src_id: Mapped[int] = mapped_column(ForeignKey("concept_node.id", ondelete="CASCADE"))
    dst_id: Mapped[int] = mapped_column(ForeignKey("concept_node.id", ondelete="CASCADE"))
    relation: Mapped[str] = mapped_column(String(64))  # defines|regulates|exempts|requires
    evidence_pasal_id: Mapped[int | None] = mapped_column(ForeignKey("pasal.id", ondelete="SET NULL"))


class RaptorNode(Base):
    """Hierarchical summary node (Pasal -> Bagian -> Bab -> Peraturan -> Topic)."""

    __tablename__ = "raptor_node"
    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[int]
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("raptor_node.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    payload: Mapped[dict | None] = mapped_column(JSON)  # e.g. {pasal_ids: [...]}


# ---------- Memory ----------


class UserMemory(Base):
    __tablename__ = "user_memory"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))  # fact|preference|persona
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    Index("ix_user_memory_user", "user_id")


# ---------- Users + collaboration (Phase 7) ----------
#
# Until now `user_id` has been a free-form string carried through API
# endpoints — fine for single-user dev. Phase 7 introduces a real User
# row plus matter-level membership / roles so a firm can have several
# lawyers and paralegals sharing a workspace, and an immutable
# AuditLog so every consequential action is traceable.


class UserRole(StrEnum):
    OWNER = "owner"  # firm admin
    LAWYER = "lawyer"
    PARALEGAL = "paralegal"
    CLIENT = "client"  # read-only on specific matters


class User(Base):
    __tablename__ = "user_account"  # 'user' is a Postgres reserved word
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.LAWYER
    )
    api_token_hash: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class MatterMemberRole(StrEnum):
    OWNER = "owner"  # can delete the matter
    EDITOR = "editor"  # can edit documents, run AI tasks
    REVIEWER = "reviewer"  # can comment + run AI tasks; can't edit
    VIEWER = "viewer"  # read-only


class MatterMember(Base):
    """Who has access to which matter, and at what role."""

    __tablename__ = "matter_member"
    id: Mapped[int] = mapped_column(primary_key=True)
    matter_id: Mapped[int] = mapped_column(
        ForeignKey("matter.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MatterMemberRole] = mapped_column(
        Enum(MatterMemberRole, name="matter_member_role"),
        default=MatterMemberRole.EDITOR,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("matter_id", "user_id", name="uq_matter_member"),
    )


class Comment(Base):
    """A human comment on a specific document range.

    Range coordinates are character offsets into the latest version's
    content. `range_start` / `range_end` may be NULL for document-level
    comments. `parent_id` allows threaded replies.
    """

    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comment.id", ondelete="CASCADE")
    )
    range_start: Mapped[int | None]
    range_end: Mapped[int | None]
    body: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Suggestion(Base):
    """A proposed text replacement (track-changes-style).

    Source is either an AI skill (e.g. contract_review's recommendation)
    or a human reviewer. On accept, a new DocumentVersion is created
    with the replacement applied.
    """

    __tablename__ = "suggestion"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(32))  # ai|human
    range_start: Mapped[int]
    range_end: Mapped[int]
    base_text: Mapped[str] = mapped_column(Text)
    proposed_text: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus, name="suggestion_status"),
        default=SuggestionStatus.PENDING,
    )
    resolved_by: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Append-only event log: who did what when, on which object.

    Backs compliance ("who saw the merger memo last Tuesday?") and
    debugging ("why did the obligations table get rewritten?"). Every
    consequential write operation in routes/* writes one of these.
    """

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))  # matter.create|document.upload|task.run|comment.add|...
    object_kind: Mapped[str | None] = mapped_column(String(32))  # matter|document|comment|...
    object_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_object", "object_kind", "object_id"),
        Index("ix_audit_log_user", "user_id"),
    )


# ---------- Documents (perjanjian / memo / opini) ----------


class DocumentKind(StrEnum):
    PERJANJIAN = "perjanjian"
    MEMO = "memo"
    OPINI = "opini"
    SOMASI = "somasi"
    GUGATAN = "gugatan"
    SURAT_KUASA = "surat_kuasa"
    KONTRAK_UPLOAD = "kontrak_upload"
    LAINNYA = "lainnya"


class Document(Base):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    matter_id: Mapped[int | None] = mapped_column(ForeignKey("matter.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind, name="document_kind"))
    template_id: Mapped[str | None] = mapped_column(String(128))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version"
    )


class DocumentVersion(Base):
    __tablename__ = "document_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    version: Mapped[int]
    content: Mapped[str] = mapped_column(Text)  # TipTap JSON or markdown
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    document: Mapped[Document] = relationship(back_populates="versions")
    __table_args__ = (UniqueConstraint("document_id", "version", name="uq_doc_version"),)


# ---------- Long-document RAG over uploaded contracts ----------
#
# When a user uploads a contract we don't just store the file: we parse
# its structural tree, extract defined terms, chunk along structural
# boundaries (never mid-pasal), augment each chunk with a context blurb
# (Anthropic-style contextual retrieval), and embed the augmented text.
# This is what makes the workspace useful for 200-page contracts where
# naive 800-token windows would lose definitions and cross-references.


class DocumentOutline(Base):
    """The structural tree of an uploaded document.

    Levels mirror what the doc actually contains: for peraturan-style
    text it's Bab > Bagian > Pasal > Ayat > Huruf; for contracts it's
    Section > Clause > Sub-clause. Used to (a) compute breadcrumbs for
    chunks, (b) render the 'tree' visual artifact, (c) support
    recursive retrieval (drill into a section).
    """

    __tablename__ = "document_outline"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("document_outline.id", ondelete="CASCADE"))
    level: Mapped[int]  # 0 = root, 1 = top-level section, etc.
    ordinal: Mapped[int]  # position among siblings
    kind: Mapped[str] = mapped_column(String(32))  # bab|bagian|pasal|ayat|huruf|section|clause|schedule|definitions
    title: Mapped[str | None] = mapped_column(Text)
    span_start: Mapped[int | None]  # char offset in extracted text
    span_end: Mapped[int | None]


class DocumentChunk(Base):
    """A retrievable unit of an uploaded document.

    `text` is the raw extracted text of the chunk. `contextual_text` is
    the Anthropic-style context-augmented version we actually embed
    (chunk text with a 1-2 sentence context blurb prepended). The
    embedding lives on `contextual_text`, not `text`.

    `breadcrumb` carries the structural path ("Section 4 / Clause 4.2")
    so the LLM can cite the chunk precisely. `parent_summary` is a
    short summary of the enclosing section — gives the model context
    even when retrieval pulls only this leaf.
    """

    __tablename__ = "document_chunk"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    matter_id: Mapped[int | None] = mapped_column(ForeignKey("matter.id", ondelete="SET NULL"), index=True)
    outline_id: Mapped[int | None] = mapped_column(ForeignKey("document_outline.id", ondelete="SET NULL"))
    ordinal: Mapped[int]  # position in the document
    text: Mapped[str] = mapped_column(Text)
    contextual_text: Mapped[str | None] = mapped_column(Text)
    breadcrumb: Mapped[str | None] = mapped_column(Text)
    parent_summary: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM))

    __table_args__ = (
        Index("ix_document_chunk_document", "document_id", "ordinal"),
        Index(
            "ix_document_chunk_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DocumentEntity(Base):
    """Extracted entities: parties, dates, monetary amounts, jurisdictions.

    Populated at upload by `document_extract` skill or rule-based
    extractors, used to render the Extract task's `table` artifacts
    and to feed downstream skills (e.g. Review wants the parties).
    """

    __tablename__ = "document_entity"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # party|date|money|obligation|jurisdiction|law|term_ref
    value: Mapped[str] = mapped_column(Text)
    span_start: Mapped[int | None]
    span_end: Mapped[int | None]
    payload: Mapped[dict | None] = mapped_column(JSON)


class DocumentCitation(Base):
    """Resolved peraturan reference from an uploaded document into the corpus.

    Example: a contract that says "tunduk pada Pasal 1320 KUHPerdata"
    gets a DocumentCitation(document_id=..., pasal_id=<Pasal 1320 row
    in pasal table>, kind=REFERS) so retrieval can expand from the
    uploaded doc into the corpus and vice versa.
    """

    __tablename__ = "document_citation"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    pasal_id: Mapped[int] = mapped_column(ForeignKey("pasal.id", ondelete="CASCADE"), index=True)
    kind: Mapped[CitationKind] = mapped_column(
        Enum(CitationKind, name="citation_kind", create_type=False)
    )
    raw_text: Mapped[str | None] = mapped_column(Text)  # the source phrase we matched
    __table_args__ = (
        UniqueConstraint("document_id", "pasal_id", "kind", name="uq_document_citation"),
    )


class DocumentTerm(Base):
    """A defined term parsed from a contract's Definitions / Ketentuan Umum section.

    "Pihak Penjual" -> "PT Alpha Mandiri, sebuah perseroan terbatas..."
    These are auto-injected into the retrieval context whenever a
    chunk uses one of them, so the model never sees an opaque defined
    term without its definition.
    """

    __tablename__ = "document_term"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"), index=True)
    term: Mapped[str] = mapped_column(String(255))
    definition: Mapped[str] = mapped_column(Text)
    span_start: Mapped[int | None]
    span_end: Mapped[int | None]
    __table_args__ = (
        UniqueConstraint("document_id", "term", name="uq_document_term"),
        Index("ix_document_term_term", "term"),
    )


# ---------- Flows ----------


class Flow(Base):
    __tablename__ = "flow"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict] = mapped_column(JSON)  # {nodes:[], edges:[]}
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FlowRun(Base):
    __tablename__ = "flow_run"
    id: Mapped[int] = mapped_column(primary_key=True)
    flow_id: Mapped[int] = mapped_column(ForeignKey("flow.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32))  # pending|running|success|error|paused
    inputs: Mapped[dict | None] = mapped_column(JSON)
    outputs: Mapped[dict | None] = mapped_column(JSON)
    trace: Mapped[list | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


# ---------- Matter (the workspace organizing unit) ----------


class MatterStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class Matter(Base):
    __tablename__ = "matter"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    client: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    notes_md: Mapped[str | None] = mapped_column(Text)  # MATTER.md content
    status: Mapped[MatterStatus] = mapped_column(
        Enum(MatterStatus, name="matter_status"), default=MatterStatus.ACTIVE
    )
    user_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------- Chat sessions ----------


class Session(Base):
    __tablename__ = "session"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64))
    matter_id: Mapped[int | None] = mapped_column(ForeignKey("matter.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Turn(Base):
    __tablename__ = "turn"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))  # user|assistant|tool
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_args: Mapped[dict | None] = mapped_column(JSON)
    tool_result: Mapped[dict | None] = mapped_column(JSON)
    citations: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
