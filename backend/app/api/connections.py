"""Operator routes for project connections and panel settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.http import HttpClient, get_http_client
from app.database import get_db
from app.deps import get_current_user
from app.errors import InvalidDataSource, ProjectNotFound
from app.models import User
from app.schemas import (
    ApiKeyOut,
    ConnectionIn,
    ConnectionOut,
    ConnectionTestOut,
    IssuedApiKeyOut,
    PanelSettingsOut,
    PanelSettingsUpdate,
)
from app.services.connections import (
    ConnectionView,
    PanelSettingsView,
    create_connection,
    issue_api_key,
    list_connections,
    panel_settings,
    project_or_404,
    revoke_api_key,
    test_connection,
    update_panel_settings,
)

router = APIRouter(tags=["connections"])


def _connection_out(row: ConnectionView) -> ConnectionOut:
    return ConnectionOut(
        id=row.id,
        name=row.name,
        kind=row.kind,
        url=row.url,
        expected_status=row.expected_status,
        timeout_seconds=row.timeout_seconds,
        has_secret=row.has_secret,
        api_key=None if row.api_key is None else ApiKeyOut(prefix=row.api_key.prefix, created_at=row.api_key.created_at),
        last_received_at=row.last_received_at,
        last_status=row.last_status,
    )


def _settings_out(row: PanelSettingsView) -> PanelSettingsOut:
    return PanelSettingsOut(
        panel_key=row.panel_key,
        mode=row.mode,
        connection_id=row.connection_id,
        allowed_modes=row.allowed_modes,
        last_received_at=row.last_received_at,
        last_status=row.last_status,
        connections=[_connection_out(item) for item in row.connections],
    )


def _project(db: Session, slug: str):
    try:
        return project_or_404(db, slug)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Project not found") from None


@router.get("/projects/{slug}/connections", response_model=list[ConnectionOut])
def list_connections_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[ConnectionOut]:
    project = _project(db, slug)
    return [_connection_out(row) for row in list_connections(db, project)]


@router.post("/projects/{slug}/connections", response_model=ConnectionOut, status_code=201)
def create_connection_route(
    slug: str,
    body: ConnectionIn,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ConnectionOut:
    project = _project(db, slug)
    try:
        created = create_connection(
            db,
            project,
            name=body.name,
            kind=body.kind,
            url=body.url,
            expected_status=body.expected_status,
            timeout_seconds=body.timeout_seconds,
            secret=body.secret,
        )
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    view = next(row for row in list_connections(db, project) if row.id == created.id)
    return _connection_out(view)


@router.get("/projects/{slug}/panels/{panel_key}/settings", response_model=PanelSettingsOut)
def panel_settings_route(
    slug: str,
    panel_key: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PanelSettingsOut:
    project = _project(db, slug)
    try:
        row = panel_settings(db, project, panel_key)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return _settings_out(row)


@router.put("/projects/{slug}/panels/{panel_key}/settings", response_model=PanelSettingsOut)
def update_panel_settings_route(
    slug: str,
    panel_key: str,
    body: PanelSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PanelSettingsOut:
    project = _project(db, slug)
    try:
        row = update_panel_settings(
            db,
            project,
            panel_key,
            body.mode,
            connection_id=body.connection_id,
            new_connection=None if body.new_connection is None else body.new_connection.model_dump(),
        )
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return _settings_out(row)


@router.post("/projects/{slug}/connections/{connection_id}/api-key", response_model=IssuedApiKeyOut, status_code=201)
def issue_api_key_route(
    slug: str,
    connection_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> IssuedApiKeyOut:
    return _issue(db, slug, connection_id, rotate=False)


@router.post(
    "/projects/{slug}/connections/{connection_id}/api-key/rotate",
    response_model=IssuedApiKeyOut,
    status_code=201,
)
def rotate_api_key_route(
    slug: str,
    connection_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> IssuedApiKeyOut:
    return _issue(db, slug, connection_id, rotate=True)


def _issue(db: Session, slug: str, connection_id: int, *, rotate: bool) -> IssuedApiKeyOut:
    project = _project(db, slug)
    try:
        issued = issue_api_key(db, project, connection_id, rotate=rotate)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return IssuedApiKeyOut(key=issued.key, prefix=issued.prefix, created_at=issued.created_at)


@router.delete("/projects/{slug}/connections/{connection_id}/api-key", status_code=204)
def revoke_api_key_route(
    slug: str,
    connection_id: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    project = _project(db, slug)
    try:
        revoke_api_key(db, project, connection_id)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None


@router.post("/projects/{slug}/panels/{panel_key}/test-connection", response_model=ConnectionTestOut)
def test_connection_route(
    slug: str,
    panel_key: str,
    db: Annotated[Session, Depends(get_db)],
    client: Annotated[HttpClient, Depends(get_http_client)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ConnectionTestOut:
    project = _project(db, slug)
    try:
        result = test_connection(db, project, panel_key, client)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return ConnectionTestOut(
        ok=result.ok,
        detail=result.detail,
        last_received_at=result.last_received_at,
        last_status=result.last_status,
    )
