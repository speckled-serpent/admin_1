"""Core tables: local users, sessions, projects, and source bindings."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    sources: Mapped[list[ProjectSource]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    panels: Mapped[list[ProjectPanel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list[ProjectApiKey]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list[IngestSnapshot]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list[PanelDataSource]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectSource(Base):
    """Binds one project to one local adapter for a single source kind.

    Kinds in use: ``revenue``, ``costs``, ``health``. A project has at most one
    row per kind. The adapter reads ``fixture_path``; it does not call the network.
    """

    __tablename__ = "project_sources"
    __table_args__ = (UniqueConstraint("project_id", "kind", name="uq_project_source_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    fixture_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="sources")


class ProjectPanel(Base):
    """A panel the operator turned on for a project. No live data is attached."""

    __tablename__ = "project_panels"
    __table_args__ = (UniqueConstraint("project_id", "panel_key", name="uq_project_panel_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    panel_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="panels")


class ProjectApiKey(Base):
    """Per-project ingest credential. Only the SHA-256 of the key is stored."""

    __tablename__ = "project_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="api_keys")


class IngestSnapshot(Base):
    """Latest accepted push payload for one kind. The dashboard reads this table, not the network."""

    __tablename__ = "ingest_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "kind", name="uq_ingest_snapshot_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    project: Mapped[Project] = relationship(back_populates="snapshots")


class PanelDataSource(Base):
    """How one panel is fed: local fixtures, push ingest, or a pull connector."""

    __tablename__ = "panel_data_sources"
    __table_args__ = (UniqueConstraint("project_id", "panel_key", name="uq_panel_data_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    panel_key: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="fake")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_status: Mapped[int | None] = mapped_column(nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(nullable=True)
    secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="data_sources")
