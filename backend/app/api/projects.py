"""Project list and the one wired revenue view."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import FixtureError, MixedCurrencyError, ProjectNotFound, SourceNotConfigured, UnknownAdapter
from app.models import User
from app.schemas import ChargeOut, ProjectOut, RevenueOut
from app.services.revenue import list_projects, project_revenue

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def projects_route(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[ProjectOut]:
    return [ProjectOut(slug=project.slug, name=project.name) for project in list_projects(db)]


@router.get("/{slug}/revenue", response_model=RevenueOut)
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
