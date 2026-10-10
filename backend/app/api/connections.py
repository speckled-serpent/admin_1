"""Operator routes for panel data sources and project API keys."""

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
    ConnectionTestOut,
    DataSourceUpdate,
    DataSourcesOut,
    IssuedApiKeyOut,
    PanelSourceOut,
)
from app.services.connections import (
    PanelSourceView,
    active_api_key,
    issue_api_key,
    list_panel_sources,
    project_or_404,
    revoke_api_key,
    set_panel_source,
    test_connection,
)

router = APIRouter(tags=["connections"])


def _panel_out(row: PanelSourceView) -> PanelSourceOut:
    return PanelSourceOut(
        panel_key=row.panel_key,
        mode=row.mode,
        allowed_modes=row.allowed_modes,
        url=row.url,
        expected_status=row.expected_status,
        timeout_seconds=row.timeout_seconds,
        has_secret=row.has_secret,
        last_received_at=row.last_received_at,
        last_status=row.last_status,
    )


def _project(db: Session, slug: str):
    try:
        return project_or_404(db, slug)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Project not found") from None


@router.get("/projects/{slug}/data-sources", response_model=DataSourcesOut)
def data_sources_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> DataSourcesOut:
    project = _project(db, slug)
    key = active_api_key(db, project)
    return DataSourcesOut(
        api_key=None if key is None else ApiKeyOut(prefix=key.prefix, created_at=key.created_at),
        panels=[_panel_out(row) for row in list_panel_sources(db, project)],
    )


@router.put("/projects/{slug}/panels/{panel_key}/data-source", response_model=PanelSourceOut)
def update_data_source_route(
    slug: str,
    panel_key: str,
    body: DataSourceUpdate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> PanelSourceOut:
    project = _project(db, slug)
    try:
        row = set_panel_source(
            db,
            project,
            panel_key,
            body.mode,
            url=body.url,
            expected_status=body.expected_status,
            timeout_seconds=body.timeout_seconds,
            secret=body.secret,
            secret_set="secret" in body.model_fields_set,
        )
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return _panel_out(row)


@router.post("/projects/{slug}/api-key", response_model=IssuedApiKeyOut, status_code=201)
def issue_api_key_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> IssuedApiKeyOut:
    project = _project(db, slug)
    try:
        issued = issue_api_key(db, project, rotate=False)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return IssuedApiKeyOut(key=issued.key, prefix=issued.prefix, created_at=issued.created_at)


@router.post("/projects/{slug}/api-key/rotate", response_model=IssuedApiKeyOut, status_code=201)
def rotate_api_key_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> IssuedApiKeyOut:
    project = _project(db, slug)
    try:
        issued = issue_api_key(db, project, rotate=True)
    except InvalidDataSource as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return IssuedApiKeyOut(key=issued.key, prefix=issued.prefix, created_at=issued.created_at)


@router.delete("/projects/{slug}/api-key", status_code=204)
def revoke_api_key_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    project = _project(db, slug)
    try:
        revoke_api_key(db, project)
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
