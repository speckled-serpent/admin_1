"""Panel data sources, project API keys, and local ingest snapshots.

Push and pull both land in SQLite. Reading the dashboard does not call the network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.connectors.http import HttpClient
from app.connectors.http_health import HttpHealthAdapter, validate_health_target
from app.crypto import SecretError, decrypt_secret, encrypt_secret
from app.errors import InvalidCredentials, InvalidDataSource, InvalidPayload, ProjectNotFound
from app.ingest_schema import SCHEMA_VERSION, validate_ingest
from app.models import IngestSnapshot, PanelDataSource, Project, ProjectApiKey, utcnow
from app.security import hash_token, new_token

MODE_FAKE = "fake"
MODE_PUSH = "push"
MODE_HTTP_HEALTH = "http-health"
SYSTEM_HEALTH = "system-health"
HTTP_HEALTH_POLL_SECONDS = 300
PANEL_KIND = {
    "system-health": "health",
    "user-data": "users",
    "sales-data": "revenue",
    "consolidated-costs": "costs",
}


@dataclass(frozen=True)
class PanelSourceView:
    panel_key: str
    mode: str
    allowed_modes: list[str]
    url: str | None
    expected_status: int | None
    timeout_seconds: int | None
    has_secret: bool
    last_received_at: datetime | None
    last_status: str | None


@dataclass(frozen=True)
class ApiKeyView:
    prefix: str
    created_at: datetime


@dataclass(frozen=True)
class IssuedApiKey:
    key: str
    prefix: str
    created_at: datetime


@dataclass(frozen=True)
class ConnectionTest:
    ok: bool
    detail: str
    last_received_at: datetime | None
    last_status: str | None


def allowed_modes(panel_key: str) -> list[str]:
    if panel_key == SYSTEM_HEALTH:
        return [MODE_FAKE, MODE_PUSH, MODE_HTTP_HEALTH]
    return [MODE_FAKE, MODE_PUSH]


def ensure_panel_sources(db: Session, project: Project) -> None:
    existing = {
        row.panel_key
        for row in db.scalars(select(PanelDataSource).where(PanelDataSource.project_id == project.id))
    }
    added = False
    for panel in project.panels:
        if panel.panel_key in existing:
            continue
        db.add(PanelDataSource(project_id=project.id, panel_key=panel.panel_key, mode=MODE_FAKE))
        added = True
    if added:
        db.commit()


def list_panel_sources(db: Session, project: Project) -> list[PanelSourceView]:
    ensure_panel_sources(db, project)
    rows = list(
        db.scalars(
            select(PanelDataSource)
            .where(PanelDataSource.project_id == project.id)
            .order_by(PanelDataSource.panel_key)
        )
    )
    order = {panel.panel_key: index for index, panel in enumerate(project.panels)}
    rows.sort(key=lambda row: order.get(row.panel_key, 100))
    return [_view(row) for row in rows if row.panel_key in order]


def active_api_key(db: Session, project: Project) -> ApiKeyView | None:
    row = _active_key_row(db, project.id)
    if row is None:
        return None
    return ApiKeyView(prefix=row.prefix, created_at=row.created_at)


def set_panel_source(
    db: Session,
    project: Project,
    panel_key: str,
    mode: str,
    *,
    url: str | None,
    expected_status: int | None,
    timeout_seconds: int | None,
    secret: str | None,
    secret_set: bool,
) -> PanelSourceView:
    row = _source_row(db, project, panel_key)
    if mode not in allowed_modes(panel_key):
        raise InvalidDataSource("That data source is not available for this panel")
    if mode == MODE_HTTP_HEALTH:
        if url is None or expected_status is None or timeout_seconds is None:
            raise InvalidDataSource("HTTP health needs a URL, expected status, and timeout")
        validate_health_target(url, expected_status, timeout_seconds)
        row.url = url
        row.expected_status = expected_status
        row.timeout_seconds = timeout_seconds
        if secret_set:
            row.secret_ciphertext = encrypt_secret(secret) if secret else None
    row.mode = mode
    db.commit()
    db.refresh(row)
    return _view(row)


def issue_api_key(db: Session, project: Project, *, rotate: bool) -> IssuedApiKey:
    current = _active_key_row(db, project.id)
    if current is not None and not rotate:
        raise InvalidDataSource("An API key already exists. Rotate it to replace the key.")
    if current is not None:
        current.revoked_at = utcnow()
    plaintext = f"a1_{new_token()}"
    row = ProjectApiKey(
        project_id=project.id,
        key_hash=hash_token(plaintext),
        prefix=plaintext[:12],
        created_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return IssuedApiKey(key=plaintext, prefix=row.prefix, created_at=row.created_at)


def revoke_api_key(db: Session, project: Project) -> None:
    current = _active_key_row(db, project.id)
    if current is None:
        raise InvalidDataSource("No active API key")
    current.revoked_at = utcnow()
    db.commit()


def project_for_ingest_key(db: Session, slug: str, token: str) -> Project:
    row = db.scalar(select(ProjectApiKey).where(ProjectApiKey.key_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        raise InvalidCredentials()
    project = db.get(Project, row.project_id)
    if project is None or project.slug != slug:
        raise InvalidCredentials()
    return project


def accept_ingest(db: Session, project: Project, body: object) -> list[str]:
    try:
        sections = validate_ingest(body)
    except InvalidPayload:
        raise
    received_at = utcnow()
    for kind, section in sections.items():
        _upsert_snapshot(db, project.id, kind, section, received_at)
        _stamp_push_panels(db, project.id, kind, section, received_at)
    db.commit()
    return list(sections)


def test_connection(db: Session, project: Project, panel_key: str, client: HttpClient) -> ConnectionTest:
    row = _source_row(db, project, panel_key)
    if row.mode == MODE_FAKE:
        return ConnectionTest(
            ok=True,
            detail="Local fixtures do not call the network.",
            last_received_at=row.last_received_at,
            last_status=row.last_status,
        )
    if row.mode == MODE_PUSH:
        if _active_key_row(db, project.id) is None:
            raise InvalidDataSource("Generate an API key first")
        return ConnectionTest(
            ok=True,
            detail="Push is ready. This panel reads the local snapshot after data arrives.",
            last_received_at=row.last_received_at,
            last_status=row.last_status,
        )
    checked_at = utcnow()
    ping = _run_http_health(row, client, checked_at)
    db.commit()
    db.refresh(row)
    ok = ping.status == "up"
    detail = "Health check matched the expected status." if ok else "Health check did not match the expected status."
    return ConnectionTest(
        ok=ok,
        detail=detail,
        last_received_at=row.last_received_at,
        last_status=row.last_status,
    )


def poll_due_http_health(db: Session, client: HttpClient, now: datetime) -> list[int]:
    """Check HTTP health rows whose last receipt is older than the poll interval.

    Nothing in this process starts a timer. A later scheduler calls this.
    """
    rows = list(db.scalars(select(PanelDataSource).where(PanelDataSource.mode == MODE_HTTP_HEALTH)))
    checked: list[int] = []
    for row in rows:
        last = _aware(row.last_received_at)
        if last is not None and (now - last).total_seconds() < HTTP_HEALTH_POLL_SECONDS:
            continue
        _run_http_health(row, client, now)
        checked.append(row.id)
    if checked:
        db.commit()
    return checked


def project_or_404(db: Session, slug: str) -> Project:
    project = db.scalar(select(Project).options(selectinload(Project.panels)).where(Project.slug == slug))
    if project is None:
        raise ProjectNotFound()
    return project


def _run_http_health(row: PanelDataSource, client: HttpClient, checked_at: datetime):
    if row.url is None or row.expected_status is None or row.timeout_seconds is None:
        raise InvalidDataSource("HTTP health needs a URL, expected status, and timeout")
    validate_health_target(row.url, row.expected_status, row.timeout_seconds)
    secret = None
    if row.secret_ciphertext:
        try:
            secret = decrypt_secret(row.secret_ciphertext)
        except SecretError as exc:
            raise InvalidDataSource("Stored connector secret could not be decrypted") from exc
    adapter = HttpHealthAdapter(
        client,
        row.url,
        row.expected_status,
        float(row.timeout_seconds),
        secret,
        checked_at=checked_at,
    )
    ping = adapter.list_pings()[0]
    row.last_status = ping.status
    row.last_received_at = checked_at
    return ping


def _upsert_snapshot(
    db: Session,
    project_id: int,
    kind: str,
    section: dict[str, object],
    received_at: datetime,
) -> None:
    row = db.scalar(
        select(IngestSnapshot).where(IngestSnapshot.project_id == project_id, IngestSnapshot.kind == kind)
    )
    encoded = json.dumps(section, separators=(",", ":"), sort_keys=True)
    if row is None:
        db.add(
            IngestSnapshot(
                project_id=project_id,
                kind=kind,
                schema_version=SCHEMA_VERSION,
                body=encoded,
                received_at=received_at,
            )
        )
        return
    row.schema_version = SCHEMA_VERSION
    row.body = encoded
    row.received_at = received_at


def _stamp_push_panels(
    db: Session,
    project_id: int,
    kind: str,
    section: dict[str, object],
    received_at: datetime,
) -> None:
    rows = list(
        db.scalars(
            select(PanelDataSource).where(
                PanelDataSource.project_id == project_id,
                PanelDataSource.mode == MODE_PUSH,
            )
        )
    )
    for row in rows:
        if PANEL_KIND.get(row.panel_key) != kind:
            continue
        row.last_received_at = received_at
        if kind == "health" and isinstance(section.get("status"), str):
            row.last_status = str(section["status"])


def _source_row(db: Session, project: Project, panel_key: str) -> PanelDataSource:
    ensure_panel_sources(db, project)
    enabled = {panel.panel_key for panel in project.panels}
    if panel_key not in enabled:
        raise InvalidDataSource("Panel is not enabled on this project")
    row = db.scalar(
        select(PanelDataSource).where(
            PanelDataSource.project_id == project.id,
            PanelDataSource.panel_key == panel_key,
        )
    )
    if row is None:
        raise InvalidDataSource("Panel is not enabled on this project")
    return row


def _active_key_row(db: Session, project_id: int) -> ProjectApiKey | None:
    return db.scalar(
        select(ProjectApiKey)
        .where(ProjectApiKey.project_id == project_id, ProjectApiKey.revoked_at.is_(None))
        .order_by(ProjectApiKey.id.desc())
    )


def _view(row: PanelDataSource) -> PanelSourceView:
    return PanelSourceView(
        panel_key=row.panel_key,
        mode=row.mode,
        allowed_modes=allowed_modes(row.panel_key),
        url=row.url,
        expected_status=row.expected_status,
        timeout_seconds=row.timeout_seconds,
        has_secret=row.secret_ciphertext is not None,
        last_received_at=row.last_received_at,
        last_status=row.last_status,
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
