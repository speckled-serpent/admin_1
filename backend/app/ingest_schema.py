"""Version 1 of the read-only push payload.

A project may send any non-empty subset of health, users, revenue, and costs.
A section that is present must be complete. Unknown keys are rejected.
"""

from __future__ import annotations

from datetime import datetime

from app.errors import InvalidPayload

SCHEMA_VERSION = 1
KINDS = ("health", "users", "revenue", "costs")
HEALTH_STATUSES = frozenset({"up", "down", "degraded"})
_TOP_LEVEL = frozenset({"schema_version", *KINDS})


def validate_ingest(body: object) -> dict[str, dict[str, object]]:
    if not isinstance(body, dict):
        raise InvalidPayload("Payload must be an object")
    unknown = set(body) - _TOP_LEVEL
    if unknown:
        name = sorted(unknown)[0]
        raise InvalidPayload(f"Unknown field: {name}")
    if body.get("schema_version") != SCHEMA_VERSION or type(body.get("schema_version")) is not int:
        raise InvalidPayload("schema_version must be 1")

    sections: dict[str, dict[str, object]] = {}
    for kind in KINDS:
        if kind not in body:
            continue
        sections[kind] = _section(kind, body[kind])
    if not sections:
        raise InvalidPayload("At least one of health, users, revenue, or costs is required")
    return sections


def _section(kind: str, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidPayload(f"{kind} must be an object")
    if kind == "health":
        return _health(value)
    if kind == "users":
        return _users(value)
    if kind == "revenue":
        return _revenue(value)
    return _costs(value)


def _health(value: dict[str, object]) -> dict[str, object]:
    _exact_keys(value, "health", {"status", "checked_at", "latency_ms"})
    status = value["status"]
    if status not in HEALTH_STATUSES:
        raise InvalidPayload("health.status must be up, down, or degraded")
    checked_at = _timestamp(value["checked_at"], "health.checked_at")
    latency = value["latency_ms"]
    if latency is not None and not _non_negative_int(latency):
        raise InvalidPayload("health.latency_ms must be a non-negative integer or null")
    return {"status": status, "checked_at": checked_at, "latency_ms": latency}


def _users(value: dict[str, object]) -> dict[str, object]:
    _exact_keys(value, "users", {"daily_active", "new", "monthly_returning", "as_of"})
    return {
        "daily_active": _count(value["daily_active"], "users.daily_active"),
        "new": _count(value["new"], "users.new"),
        "monthly_returning": _count(value["monthly_returning"], "users.monthly_returning"),
        "as_of": _timestamp(value["as_of"], "users.as_of"),
    }


def _revenue(value: dict[str, object]) -> dict[str, object]:
    _exact_keys(value, "revenue", {"currency", "gross_amount", "refunded_amount", "net_amount", "as_of"})
    currency = _currency(value["currency"], "revenue.currency")
    gross = _count(value["gross_amount"], "revenue.gross_amount")
    refunded = _count(value["refunded_amount"], "revenue.refunded_amount")
    net = _count(value["net_amount"], "revenue.net_amount")
    if refunded > gross:
        raise InvalidPayload("revenue.refunded_amount cannot exceed gross_amount")
    if net != gross - refunded:
        raise InvalidPayload("revenue.net_amount must equal gross_amount minus refunded_amount")
    return {
        "currency": currency,
        "gross_amount": gross,
        "refunded_amount": refunded,
        "net_amount": net,
        "as_of": _timestamp(value["as_of"], "revenue.as_of"),
    }


def _costs(value: dict[str, object]) -> dict[str, object]:
    _exact_keys(value, "costs", {"currency", "amount", "as_of"})
    return {
        "currency": _currency(value["currency"], "costs.currency"),
        "amount": _count(value["amount"], "costs.amount"),
        "as_of": _timestamp(value["as_of"], "costs.as_of"),
    }


def _exact_keys(value: dict[str, object], name: str, expected: set[str]) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing:
        raise InvalidPayload(f"{name}.{sorted(missing)[0]} is required")
    if extra:
        raise InvalidPayload(f"Unknown field: {name}.{sorted(extra)[0]}")


def _count(value: object, label: str) -> int:
    if not _non_negative_int(value):
        raise InvalidPayload(f"{label} must be a non-negative integer")
    return int(value)  # type: ignore[arg-type]


def _non_negative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _currency(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 3 or not value.isalpha():
        raise InvalidPayload(f"{label} must be a 3-letter code")
    return value.lower()


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidPayload(f"{label} must be an ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidPayload(f"{label} must be an ISO-8601 timestamp") from exc
    return value
