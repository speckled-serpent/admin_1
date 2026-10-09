"""Revenue for a single project. No cross-project rollup and no FX conversion."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.registry import build_revenue_adapter, resolve_fixture_path
from app.adapters.types import Charge
from app.config import Settings
from app.errors import MixedCurrencyError, ProjectNotFound, SourceNotConfigured
from app.models import Project, ProjectSource

KIND_REVENUE = "revenue"


@dataclass(frozen=True)
class RevenueSummary:
    currency: str | None
    gross_amount: int
    refunded_amount: int
    net_amount: int
    charge_count: int
    succeeded_count: int
    refunded_count: int
    charges: list[Charge]


def summarize_charges(charges: list[Charge]) -> RevenueSummary:
    """Sum succeeded charges.

    Gross is the sum of ``amount`` on ``succeeded`` charges. Refunded is the
    sum of ``amount_refunded`` on those same charges (partial and full).
    Pending and failed charges stay in ``charges`` and do not affect totals.
    Net is gross minus refunded. Mixed currencies are rejected.
    """
    included = [charge for charge in charges if charge.status == "succeeded"]
    currencies = {charge.currency for charge in included if charge.amount or charge.amount_refunded}
    if len(currencies) > 1:
        raise MixedCurrencyError("succeeded charges use more than one currency")
    currency = next(iter(currencies)) if currencies else None
    gross = sum(charge.amount for charge in included)
    refunded = sum(charge.amount_refunded for charge in included)
    refunded_count = sum(1 for charge in included if charge.amount_refunded > 0)
    ordered = sorted(charges, key=lambda charge: charge.created, reverse=True)
    return RevenueSummary(
        currency=currency,
        gross_amount=gross,
        refunded_amount=refunded,
        net_amount=gross - refunded,
        charge_count=len(charges),
        succeeded_count=len(included),
        refunded_count=refunded_count,
        charges=ordered,
    )


def project_revenue(db: Session, settings: Settings, slug: str) -> tuple[Project, RevenueSummary]:
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is None:
        raise ProjectNotFound(slug)
    source = db.scalar(
        select(ProjectSource).where(
            ProjectSource.project_id == project.id,
            ProjectSource.kind == KIND_REVENUE,
        )
    )
    if source is None:
        raise SourceNotConfigured(slug)
    path = resolve_fixture_path(settings, source.fixture_path)
    adapter = build_revenue_adapter(source.adapter_key, path)
    return project, summarize_charges(adapter.list_charges())


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.name)))
