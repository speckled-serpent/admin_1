"""Adapter registry. Keys map to local fixture readers, never remote clients."""

from __future__ import annotations

from pathlib import Path

from app.adapters.fixtures import FixtureCostAdapter, FixtureHealthAdapter, FixtureRevenueAdapter
from app.adapters.types import CostAdapter, HealthAdapter, RevenueAdapter
from app.config import Settings
from app.errors import FixtureError, UnknownAdapter

_REVENUE: dict[str, type[FixtureRevenueAdapter]] = {
    FixtureRevenueAdapter.key: FixtureRevenueAdapter,
}
_COSTS: dict[str, type[FixtureCostAdapter]] = {
    FixtureCostAdapter.key: FixtureCostAdapter,
}
_HEALTH: dict[str, type[FixtureHealthAdapter]] = {
    FixtureHealthAdapter.key: FixtureHealthAdapter,
}


def resolve_fixture_path(settings: Settings, relative: str) -> Path:
    """Resolve a project_sources.fixture_path and keep it inside fixtures/."""
    fixtures_root = settings.fixtures_dir.resolve()
    candidate = (settings.backend_root / relative).resolve()
    if not candidate.is_relative_to(fixtures_root):
        raise FixtureError("Fixture path must stay inside the fixtures directory")
    if not candidate.is_file():
        raise FixtureError(f"Fixture not found: {relative}")
    return candidate


def build_revenue_adapter(adapter_key: str, fixture_path: Path) -> RevenueAdapter:
    cls = _REVENUE.get(adapter_key)
    if cls is None:
        raise UnknownAdapter(adapter_key)
    return cls(fixture_path)


def build_cost_adapter(adapter_key: str, fixture_path: Path) -> CostAdapter:
    cls = _COSTS.get(adapter_key)
    if cls is None:
        raise UnknownAdapter(adapter_key)
    return cls(fixture_path)


def build_health_adapter(adapter_key: str, fixture_path: Path) -> HealthAdapter:
    cls = _HEALTH.get(adapter_key)
    if cls is None:
        raise UnknownAdapter(adapter_key)
    return cls(fixture_path)
