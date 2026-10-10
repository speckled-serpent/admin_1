"""Project connections, panel assignments, and local ingest snapshots.

Push and pull both land in SQLite. Reading the dashboard does not call the network.
A connection is a named server. Several panels can share one. Push sections land
on the panels of the matching type that reference that connection.
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
from app.models import Connection, ConnectionApiKey, IngestSnapshot, PanelDataSource, Project, utcnow
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
CONNECTION_KINDS = {MODE_PUSH, MODE_HTTP_HEALTH}


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
class ConnectionView:
    id: int
    name: str
    kind: str
    url: str | None
    expected_status: int | None
    timeout_seconds: int | None
    has_secret: bool
    api_key: ApiKeyView | None
    last_received_at: datetime | None
    last_status: str | None


@dataclass(frozen=True)
class PanelSettingsView:
    panel_key: str
    mode: str
    connection_id: int | None
    allowed_modes: list[str]
    last_received_at: datetime | None
    last_status: str | None
    connections: list[ConnectionView]


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


def attach_initial_sources(
    db: Session,
    project: Project,
    panel_keys: list[str],
    connections: list[dict] | None,
    sources: list[dict] | None,
) -> None:
    """Create connection and panel rows for a new project. The caller commits."""
    if sources is None:
        for key in panel_keys:
            db.add(PanelDataSource(project_id=project.id, panel_key=key, mode=MODE_FAKE))
        return

    drafted = _draft_connections(db, project, connections or [])
    seen: set[str] = set()
    for source in sources:
        panel_key = str(source.get("panel") or "")
        if panel_key in seen:
            raise InvalidDataSource("Choose one data source for each panel")
        seen.add(panel_key)
        if panel_key not in panel_keys:
            raise InvalidDataSource("Choose a data source only for selected panels")
        mode = str(source.get("mode") or "")
        if mode not in allowed_modes(panel_key):
            raise InvalidDataSource("That data source is not available for this panel")
        ref = source.get("connection")
        connection_id = None
        if mode == MODE_FAKE:
            if ref:
                raise InvalidDataSource("Fake does not use a connection")
        else:
            if not isinstance(ref, str) or ref not in drafted:
                raise InvalidDataSource("Choose a connection for each panel")
            connection = drafted[ref]
            if connection.kind != mode:
                raise InvalidDataSource("That connection does not match this data source")
            connection_id = connection.id
        db.add(
            PanelDataSource(
                project_id=project.id,
                panel_key=panel_key,
                mode=mode,
                connection_id=connection_id,
            )
        )
    if seen != set(panel_keys):
        raise InvalidDataSource("Choose a data source for each panel")


def list_connections(db: Session, project: Project) -> list[ConnectionView]:
    rows = list(
        db.scalars(select(Connection).where(Connection.project_id == project.id).order_by(Connection.id))
    )
    return [_connection_view(db, row) for row in rows]


def panel_settings(db: Session, project: Project, panel_key: str) -> PanelSettingsView:
    row = _source_row(db, project, panel_key)
    return _settings_view(db, project, row)


def create_connection(
    db: Session,
    project: Project,
    *,
    name: str,
    kind: str,
    url: str | None = None,
    expected_status: int | None = None,
    timeout_seconds: int | None = None,
    secret: str | None = None,
    commit: bool = True,
) -> Connection:
    connection = Connection(
        project_id=project.id,
        name=_clean_name(name),
        kind=_clean_kind(kind),
        created_at=utcnow(),
    )
    _apply_http_fields(
        connection,
        url=url,
        expected_status=expected_status,
        timeout_seconds=timeout_seconds,
        secret=secret,
        secret_set=True,
    )
    db.add(connection)
    if commit:
        db.commit()
        db.refresh(connection)
    else:
        db.flush()
    return connection


def update_panel_settings(
    db: Session,
    project: Project,
    panel_key: str,
    mode: str,
    *,
    connection_id: int | None,
    new_connection: dict | None,
) -> PanelSettingsView:
    row = _source_row(db, project, panel_key)
    if mode not in allowed_modes(panel_key):
        raise InvalidDataSource("That data source is not available for this panel")
    if mode == MODE_FAKE:
        row.mode = MODE_FAKE
        row.connection_id = None
        db.commit()
        db.refresh(row)
        return _settings_view(db, project, row)
    if new_connection is not None and connection_id is not None:
        raise InvalidDataSource("Choose an existing connection or create a new one")
    if new_connection is not None:
        if str(new_connection.get("kind") or mode) != mode:
            raise InvalidDataSource("That connection does not match this data source")
        created = create_connection(
            db,
            project,
            name=str(new_connection.get("name") or ""),
            kind=mode,
            url=new_connection.get("url"),
            expected_status=new_connection.get("expected_status"),
            timeout_seconds=new_connection.get("timeout_seconds"),
            secret=new_connection.get("secret"),
            commit=False,
        )
        connection_id = created.id
    if connection_id is None:
        raise InvalidDataSource("Choose a connection")
    connection = _project_connection(db, project, connection_id)
    if connection.kind != mode:
        raise InvalidDataSource("That connection does not match this data source")
    row.mode = mode
    row.connection_id = connection.id
    db.commit()
    db.refresh(row)
    return _settings_view(db, project, row)


def issue_api_key(db: Session, project: Project, connection_id: int, *, rotate: bool) -> IssuedApiKey:
    connection = _project_connection(db, project, connection_id)
    if connection.kind != MODE_PUSH:
        raise InvalidDataSource("Only a push connection has an API key")
    current = _active_key_row(db, connection.id)
    if current is not None and not rotate:
        raise InvalidDataSource("An API key already exists. Rotate it to replace the key.")
    if current is not None:
        current.revoked_at = utcnow()
    plaintext = f"a1_{new_token()}"
    row = ConnectionApiKey(
        connection_id=connection.id,
        key_hash=hash_token(plaintext),
        prefix=plaintext[:12],
        created_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return IssuedApiKey(key=plaintext, prefix=row.prefix, created_at=row.created_at)


def revoke_api_key(db: Session, project: Project, connection_id: int) -> None:
    connection = _project_connection(db, project, connection_id)
    current = _active_key_row(db, connection.id)
    if current is None:
        raise InvalidDataSource("No active API key")
    current.revoked_at = utcnow()
    db.commit()


def connection_for_ingest_key(db: Session, slug: str, token: str) -> tuple[Project, Connection]:
    row = db.scalar(select(ConnectionApiKey).where(ConnectionApiKey.key_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        raise InvalidCredentials()
    connection = db.get(Connection, row.connection_id)
    if connection is None or connection.kind != MODE_PUSH:
        raise InvalidCredentials()
    project = db.get(Project, connection.project_id)
    if project is None or project.slug != slug:
        raise InvalidCredentials()
    return project, connection


def accept_ingest(db: Session, project: Project, connection: Connection, body: object) -> list[str]:
    try:
        sections = validate_ingest(body)
    except InvalidPayload:
        raise
    received_at = utcnow()
    for kind, section in sections.items():
        _upsert_snapshot(db, project.id, connection.id, kind, section, received_at)
        _stamp_push_panels(db, connection.id, kind, section, received_at)
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
    connection = None if row.connection_id is None else db.get(Connection, row.connection_id)
    if connection is None or connection.project_id != project.id:
        raise InvalidDataSource("Choose a connection")
    if row.mode == MODE_PUSH:
        if _active_key_row(db, connection.id) is None:
            raise InvalidDataSource("Generate an API key first")
        return ConnectionTest(
            ok=True,
            detail="Push is ready. This panel reads the local snapshot after data arrives.",
            last_received_at=row.last_received_at,
            last_status=row.last_status,
        )
    checked_at = utcnow()
    ping = _run_http_health(connection, client, checked_at)
    _stamp_connection_panels(db, connection, ping.status, checked_at)
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
    """Check HTTP health connections whose last receipt is older than the poll interval.

    Nothing in this process starts a timer. A later scheduler calls this.
    """
    rows = list(db.scalars(select(Connection).where(Connection.kind == MODE_HTTP_HEALTH)))
    checked: list[int] = []
    for connection in rows:
        last = _aware(connection.last_received_at)
        if last is not None and (now - last).total_seconds() < HTTP_HEALTH_POLL_SECONDS:
            continue
        ping = _run_http_health(connection, client, now)
        _stamp_connection_panels(db, connection, ping.status, now)
        checked.append(connection.id)
    if checked:
        db.commit()
    return checked


def project_or_404(db: Session, slug: str) -> Project:
    project = db.scalar(select(Project).options(selectinload(Project.panels)).where(Project.slug == slug))
    if project is None:
        raise ProjectNotFound()
    return project


def _draft_connections(db: Session, project: Project, connections: list[dict]) -> dict[str, Connection]:
    drafted: dict[str, Connection] = {}
    for item in connections:
        ref = item.get("key")
        if not isinstance(ref, str) or not ref.strip():
            raise InvalidDataSource("Name the connection")
        if ref in drafted:
            raise InvalidDataSource("Connection key is duplicated")
        drafted[ref] = create_connection(
            db,
            project,
            name=str(item.get("name") or ""),
            kind=str(item.get("kind") or ""),
            url=item.get("url"),
            expected_status=item.get("expected_status"),
            timeout_seconds=item.get("timeout_seconds"),
            secret=item.get("secret"),
            commit=False,
        )
    return drafted


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidDataSource("Name is required")
    if len(cleaned) > 120:
        raise InvalidDataSource("Name is too long")
    return cleaned


def _clean_kind(kind: str) -> str:
    if kind not in CONNECTION_KINDS:
        raise InvalidDataSource("Connection kind must be push or http-health")
    return kind


def _apply_http_fields(
    connection: Connection,
    *,
    url: str | None,
    expected_status: int | None,
    timeout_seconds: int | None,
    secret: str | None,
    secret_set: bool,
) -> None:
    if connection.kind != MODE_HTTP_HEALTH:
        return
    if url is None or expected_status is None or timeout_seconds is None:
        raise InvalidDataSource("HTTP health needs a URL, expected status, and timeout")
    validate_health_target(url, expected_status, timeout_seconds)
    connection.url = url
    connection.expected_status = expected_status
    connection.timeout_seconds = timeout_seconds
    if secret_set:
        connection.secret_ciphertext = encrypt_secret(secret) if secret else None


def _run_http_health(connection: Connection, client: HttpClient, checked_at: datetime):
    if connection.url is None or connection.expected_status is None or connection.timeout_seconds is None:
        raise InvalidDataSource("HTTP health needs a URL, expected status, and timeout")
    validate_health_target(connection.url, connection.expected_status, connection.timeout_seconds)
    secret = None
    if connection.secret_ciphertext:
        try:
            secret = decrypt_secret(connection.secret_ciphertext)
        except SecretError as exc:
            raise InvalidDataSource("Stored connector secret could not be decrypted") from exc
    adapter = HttpHealthAdapter(
        client,
        connection.url,
        connection.expected_status,
        float(connection.timeout_seconds),
        secret,
        checked_at=checked_at,
    )
    ping = adapter.list_pings()[0]
    connection.last_status = ping.status
    connection.last_received_at = checked_at
    return ping


def _stamp_connection_panels(db: Session, connection: Connection, status: str, checked_at: datetime) -> None:
    rows = list(db.scalars(select(PanelDataSource).where(PanelDataSource.connection_id == connection.id)))
    for row in rows:
        row.last_status = status
        row.last_received_at = checked_at


def _upsert_snapshot(
    db: Session,
    project_id: int,
    connection_id: int,
    kind: str,
    section: dict[str, object],
    received_at: datetime,
) -> None:
    row = db.scalar(
        select(IngestSnapshot).where(IngestSnapshot.connection_id == connection_id, IngestSnapshot.kind == kind)
    )
    encoded = json.dumps(section, separators=(",", ":"), sort_keys=True)
    if row is None:
        db.add(
            IngestSnapshot(
                project_id=project_id,
                connection_id=connection_id,
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
    connection_id: int,
    kind: str,
    section: dict[str, object],
    received_at: datetime,
) -> None:
    rows = list(
        db.scalars(
            select(PanelDataSource).where(
                PanelDataSource.connection_id == connection_id,
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


def _project_connection(db: Session, project: Project, connection_id: int) -> Connection:
    connection = db.get(Connection, connection_id)
    if connection is None or connection.project_id != project.id:
        raise InvalidDataSource("Connection not found")
    return connection


def _active_key_row(db: Session, connection_id: int) -> ConnectionApiKey | None:
    return db.scalar(
        select(ConnectionApiKey)
        .where(ConnectionApiKey.connection_id == connection_id, ConnectionApiKey.revoked_at.is_(None))
        .order_by(ConnectionApiKey.id.desc())
    )


def _connection_view(db: Session, row: Connection) -> ConnectionView:
    key = _active_key_row(db, row.id)
    return ConnectionView(
        id=row.id,
        name=row.name,
        kind=row.kind,
        url=row.url,
        expected_status=row.expected_status,
        timeout_seconds=row.timeout_seconds,
        has_secret=row.secret_ciphertext is not None,
        api_key=None if key is None else ApiKeyView(prefix=key.prefix, created_at=key.created_at),
        last_received_at=row.last_received_at,
        last_status=row.last_status,
    )


def _settings_view(db: Session, project: Project, row: PanelDataSource) -> PanelSettingsView:
    return PanelSettingsView(
        panel_key=row.panel_key,
        mode=row.mode,
        connection_id=row.connection_id,
        allowed_modes=allowed_modes(row.panel_key),
        last_received_at=row.last_received_at,
        last_status=row.last_status,
        connections=list_connections(db, project),
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
