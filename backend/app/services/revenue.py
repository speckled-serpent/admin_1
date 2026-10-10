"""Revenue for a single project. No cross-project rollup and no FX conversion."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.registry import build_revenue_adapter, resolve_fixture_path
from app.adapters.types import Charge
from app.config import Settings
from app.errors import MixedCurrencyError, ProjectNotFound, SourceNotConfigured
from app.models import PanelDataSource, Project
from app.panels import SALES_DATA
from app.services.connections import MODE_FAKE

KIND_REVENUE = "revenue"
FAKE_REVENUE_ADAPTER = "fixture.revenue"
FAKE_REVENUE_FIXTURE = "fixtures/acme_notes_charges.json"


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
    """Return fixture revenue when the Sales data panel is Fake.

    Push revenue stays in ``ingest_snapshots`` and is not rendered here.
    """
    project = db.scalar(select(Project).options(selectinload(Project.panels)).where(Project.slug == slug))
    if project is None:
        raise ProjectNotFound(slug)
    enabled = {panel.panel_key for panel in project.panels}
    source = db.scalar(
        select(PanelDataSource).where(
            PanelDataSource.project_id == project.id,
            PanelDataSource.panel_key == SALES_DATA,
        )
    )
    if SALES_DATA not in enabled or source is None or source.mode != MODE_FAKE:
        raise SourceNotConfigured(slug)
    path = resolve_fixture_path(settings, FAKE_REVENUE_FIXTURE)
    adapter = build_revenue_adapter(FAKE_REVENUE_ADAPTER, path)
    return project, summarize_charges(adapter.list_charges())

