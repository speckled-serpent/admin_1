"""Local fake adapters. Each one reads a JSON fixture from disk."""

from __future__ import annotations

import json
from pathlib import Path

from app.adapters.types import Charge, CostItem, HealthPing
from app.errors import FixtureError

_CHARGE_STATUSES = {"succeeded", "pending", "failed"}
_HEALTH_STATUSES = {"up", "down", "degraded"}


def _load_json(path: Path) -> object:
    if not path.is_file():
        raise FixtureError(f"Fixture not found: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureError(f"Fixture is not valid JSON: {path.name}") from exc


def _require_mapping(payload: object, path: Path) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise FixtureError(f"Fixture root must be an object: {path.name}")
    return payload


def _as_int(value: object, field: str, record_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FixtureError(f"{record_id}: {field} must be an integer")
    return value


def _as_str(value: object, field: str, record_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FixtureError(f"{record_id}: {field} must be a non-empty string")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise FixtureError("optional text field must be a string or null")
    stripped = value.strip()
    return stripped or None


class FixtureRevenueAdapter:
    """Reads card-processor-shaped charges from a local JSON list."""

    key = "fixture.revenue"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def list_charges(self) -> list[Charge]:
        payload = _require_mapping(_load_json(self.fixture_path), self.fixture_path)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise FixtureError(f"{self.fixture_path.name}: data must be a list")
        return [_parse_charge(row) for row in rows]


class FixtureCostAdapter:
    """Reads cost line items from a local JSON list. Not wired to the API."""

    key = "fixture.costs"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def list_cost_items(self) -> list[CostItem]:
        payload = _require_mapping(_load_json(self.fixture_path), self.fixture_path)
        rows = payload.get("items")
        if not isinstance(rows, list):
            raise FixtureError(f"{self.fixture_path.name}: items must be a list")
        return [_parse_cost(row) for row in rows]


class FixtureHealthAdapter:
    """Reads health pings from a local JSON list. Not wired to the API."""

    key = "fixture.health"

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def list_pings(self) -> list[HealthPing]:
        payload = _require_mapping(_load_json(self.fixture_path), self.fixture_path)
        rows = payload.get("pings")
        if not isinstance(rows, list):
            raise FixtureError(f"{self.fixture_path.name}: pings must be a list")
        return [_parse_ping(row) for row in rows]


def _parse_charge(row: object) -> Charge:
    if not isinstance(row, dict):
        raise FixtureError("charge must be an object")
    record_id = row.get("id") if isinstance(row.get("id"), str) else "<unknown>"
    amount = _as_int(row.get("amount"), "amount", record_id)
    amount_refunded = _as_int(row.get("amount_refunded"), "amount_refunded", record_id)
    if amount < 0 or amount_refunded < 0 or amount_refunded > amount:
        raise FixtureError(f"{record_id}: refunded amount must be between 0 and amount")
    currency = _as_str(row.get("currency"), "currency", record_id).lower()
    if len(currency) != 3 or not currency.isalpha():
        raise FixtureError(f"{record_id}: currency must be a 3-letter code")
    status = _as_str(row.get("status"), "status", record_id)
    if status not in _CHARGE_STATUSES:
        raise FixtureError(f"{record_id}: status must be succeeded, pending, or failed")
    refunded = row.get("refunded")
    if not isinstance(refunded, bool):
        raise FixtureError(f"{record_id}: refunded must be a boolean")
    created = _as_int(row.get("created"), "created", record_id)
    if created < 0:
        raise FixtureError(f"{record_id}: created must be a unix timestamp")
    return Charge(
        id=_as_str(row.get("id"), "id", record_id),
        amount=amount,
        amount_refunded=amount_refunded,
        currency=currency,
        status=status,
        refunded=refunded,
        created=created,
        description=_optional_str(row.get("description")),
        customer=_optional_str(row.get("customer")),
    )


def _parse_cost(row: object) -> CostItem:
    if not isinstance(row, dict):
        raise FixtureError("cost item must be an object")
    record_id = row.get("id") if isinstance(row.get("id"), str) else "<unknown>"
    amount = _as_int(row.get("amount"), "amount", record_id)
    if amount < 0:
        raise FixtureError(f"{record_id}: amount must be >= 0")
    currency = _as_str(row.get("currency"), "currency", record_id).lower()
    incurred_on = _as_str(row.get("incurred_on"), "incurred_on", record_id)
    return CostItem(
        id=_as_str(row.get("id"), "id", record_id),
        vendor=_as_str(row.get("vendor"), "vendor", record_id),
        category=_as_str(row.get("category"), "category", record_id),
        description=_as_str(row.get("description"), "description", record_id),
        amount=amount,
        currency=currency,
        incurred_on=incurred_on,
    )


def _parse_ping(row: object) -> HealthPing:
    if not isinstance(row, dict):
        raise FixtureError("health ping must be an object")
    record_id = row.get("id") if isinstance(row.get("id"), str) else "<unknown>"
    status = _as_str(row.get("status"), "status", record_id)
    if status not in _HEALTH_STATUSES:
        raise FixtureError(f"{record_id}: status must be up, down, or degraded")
    latency = row.get("latency_ms")
    latency_ms: int | None
    if latency is None:
        latency_ms = None
    else:
        latency_ms = _as_int(latency, "latency_ms", record_id)
        if latency_ms < 0:
            raise FixtureError(f"{record_id}: latency_ms must be >= 0")
    return HealthPing(
        id=_as_str(row.get("id"), "id", record_id),
        checked_at=_as_str(row.get("checked_at"), "checked_at", record_id),
        status=status,
        latency_ms=latency_ms,
        region=_as_str(row.get("region"), "region", record_id),
    )
