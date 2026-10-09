"""Records returned by source adapters.

Money is always an integer count of minor units (cents for usd). Currency codes
are lowercase ISO-4217. This package does not convert currencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Charge:
    """One card-processor charge, including refunds.

    ``amount`` and ``amount_refunded`` are minor units. ``status`` is
    ``succeeded``, ``pending``, or ``failed``. ``refunded`` is true only when
    the charge was fully refunded. Partial refunds keep ``refunded`` false and
    set ``amount_refunded`` above zero.
    """

    id: str
    amount: int
    amount_refunded: int
    currency: str
    status: str
    refunded: bool
    created: int
    description: str | None = None
    customer: str | None = None


@dataclass(frozen=True)
class CostItem:
    """One local cost line. ``amount`` is minor units."""

    id: str
    vendor: str
    category: str
    description: str
    amount: int
    currency: str
    incurred_on: str


@dataclass(frozen=True)
class HealthPing:
    """One local health observation. ``status`` is up, down, or degraded."""

    id: str
    checked_at: str
    status: str
    latency_ms: int | None
    region: str


class RevenueAdapter(Protocol):
    key: str

    def list_charges(self) -> list[Charge]:
        """Return charges for the bound project source. File order."""


class CostAdapter(Protocol):
    key: str

    def list_cost_items(self) -> list[CostItem]:
        """Return cost lines for the bound project source. File order."""


class HealthAdapter(Protocol):
    key: str

    def list_pings(self) -> list[HealthPing]:
        """Return health pings for the bound project source. File order."""
