"""Project list and the one wired revenue view."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import (
    FixtureError,
    InvalidProject,
    MixedCurrencyError,
    ProjectNotFound,
    SourceNotConfigured,
    UnknownAdapter,
)
from app.models import Project, User
from app.panels import PANELS
from app.schemas import ChargeOut, PanelOut, ProjectCreate, ProjectDetail, ProjectOut, RevenueOut
from app.services.projects import create_project, list_projects, panel_keys_for
from app.services.revenue import project_revenue

router = APIRouter(tags=["projects"])


def _detail(project: Project) -> ProjectDetail:
    return ProjectDetail(slug=project.slug, name=project.name, panels=panel_keys_for(project))


@router.get("/panel-catalog", response_model=list[PanelOut])
def panel_catalog_route(_user: Annotated[User, Depends(get_current_user)]) -> list[PanelOut]:
    return [PanelOut(key=panel.key, label=panel.label, group=panel.group, description=panel.description) for panel in PANELS]


@router.get("/projects", response_model=list[ProjectDetail])
def projects_route(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[ProjectDetail]:
    return [_detail(project) for project in list_projects(db)]


@router.post("/projects", response_model=ProjectDetail, status_code=201)
def create_project_route(
    body: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ProjectDetail:
    try:
        project = create_project(db, body.name, body.panels)
    except InvalidProject as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return _detail(project)


@router.get("/projects/{slug}/revenue", response_model=RevenueOut)
def revenue_route(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(get_current_user)],
) -> RevenueOut:
    try:
        project, summary = project_revenue(db, settings, slug)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Project not found") from None
    except SourceNotConfigured:
        raise HTTPException(status_code=404, detail="No revenue source is configured for this project") from None
    except MixedCurrencyError:
        raise HTTPException(
            status_code=422,
            detail="This project mixes currencies. Conversion is not available.",
        ) from None
    except (FixtureError, UnknownAdapter):
        raise HTTPException(status_code=500, detail="Revenue data is unavailable") from None
    return RevenueOut(
        project=ProjectOut(slug=project.slug, name=project.name),
        currency=summary.currency,
        gross_amount=summary.gross_amount,
        refunded_amount=summary.refunded_amount,
        net_amount=summary.net_amount,
        charge_count=summary.charge_count,
        succeeded_count=summary.succeeded_count,
        refunded_count=summary.refunded_count,
        charges=[
            ChargeOut(
                id=charge.id,
                amount=charge.amount,
                amount_refunded=charge.amount_refunded,
                currency=charge.currency,
                status=charge.status,
                refunded=charge.refunded,
                created=charge.created,
                description=charge.description,
                customer=charge.customer,
            )
            for charge in summary.charges
        ],
    )
