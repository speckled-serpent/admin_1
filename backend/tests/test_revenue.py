from pathlib import Path

import pytest

from app.adapters.fixtures import FixtureCostAdapter, FixtureHealthAdapter, FixtureRevenueAdapter
from app.adapters.registry import build_revenue_adapter, resolve_fixture_path
from app.adapters.types import Charge
from app.config import get_settings
from app.errors import FixtureError, MixedCurrencyError, UnknownAdapter
from app.services.revenue import summarize_charges

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_acme_notes_revenue_fixture_totals() -> None:
    charges = FixtureRevenueAdapter(FIXTURES / "acme_notes_charges.json").list_charges()
    summary = summarize_charges(charges)

    assert summary.currency == "usd"
    assert summary.gross_amount == 15900
    assert summary.refunded_amount == 1700
    assert summary.net_amount == 14200
    assert summary.succeeded_count == 6
    assert summary.refunded_count == 2
    assert summary.charge_count == 8
    assert summary.charges[0].id == "ch_acme_1008"
    assert summary.charges[0].status == "pending"
    assert any(charge.id == "ch_acme_1006" and charge.refunded for charge in summary.charges)
    assert any(charge.id == "ch_acme_1005" and charge.amount_refunded == 200 for charge in summary.charges)


def test_failed_and_pending_do_not_change_net() -> None:
    summary = summarize_charges(
        [
            Charge(
                id="ch_ok",
                amount=1000,
                amount_refunded=0,
                currency="usd",
                status="succeeded",
                refunded=False,
                created=1,
            ),
            Charge(
                id="ch_no",
                amount=5000,
                amount_refunded=0,
                currency="usd",
                status="failed",
                refunded=False,
                created=2,
            ),
        ]
    )
    assert summary.gross_amount == 1000
    assert summary.net_amount == 1000
    assert summary.charge_count == 2


def test_mixed_currency_is_rejected() -> None:
    charges = [
        Charge(
            id="ch_usd",
            amount=100,
            amount_refunded=0,
            currency="usd",
            status="succeeded",
            refunded=False,
            created=1,
        ),
        Charge(
            id="ch_eur",
            amount=100,
            amount_refunded=0,
            currency="eur",
            status="succeeded",
            refunded=False,
            created=2,
        ),
    ]
    with pytest.raises(MixedCurrencyError):
        summarize_charges(charges)


def test_cost_and_health_fakes_read_local_fixtures() -> None:
    costs = FixtureCostAdapter(FIXTURES / "acme_notes_costs.json").list_cost_items()
    pings = FixtureHealthAdapter(FIXTURES / "acme_notes_health.json").list_pings()

    assert [item.id for item in costs] == ["cost_acme_001", "cost_acme_002", "cost_acme_003"]
    assert sum(item.amount for item in costs) == 3450
    assert [ping.status for ping in pings] == ["up", "degraded", "down", "up"]
    assert pings[2].latency_ms is None


def test_fixture_path_must_stay_inside_fixtures() -> None:
    with pytest.raises(FixtureError):
        resolve_fixture_path(get_settings(), "../LICENSE")


def test_unknown_revenue_adapter() -> None:
    with pytest.raises(UnknownAdapter):
        build_revenue_adapter("fixture.other", FIXTURES / "acme_notes_charges.json")
