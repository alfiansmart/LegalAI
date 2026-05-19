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
    UUD = "UUD"
    UU = "UU"
    PERPPU = "Perppu"
    PP = "PP"
    PERPRES = "Perpres"
    PERMEN = "Permen"
    PERDA = "Perda"
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

    pasal: Mapped[list[Pasal]] = relationship(back_populates="peraturan", cascade="all, delete-orphan")
    bab: Mapped[list[Bab]] = relationship(back_populates="peraturan", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("jenis", "nomor", "tahun", name="uq_peraturan_natural"),
        Index("ix_peraturan_tahun", "tahun"),
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


# ---------- Documents (perjanjian / memo / opini) ----------


class DocumentKind(StrEnum):
    PERJANJIAN = "perjanjian"
    MEMO = "memo"
    OPINI = "opini"
    SOMASI = "somasi"
    GUGATAN = "gugatan"
    SURAT_KUASA = "surat_kuasa"
    LAINNYA = "lainnya"


class Document(Base):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind, name="document_kind"))
    template_id: Mapped[str | None] = mapped_column(String(128))
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


# ---------- Chat sessions ----------


class Session(Base):
    __tablename__ = "session"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64))
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
