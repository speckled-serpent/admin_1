"""Generic HTTP health check. One GET, compared to an expected status. Nothing else is sent."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from app.adapters.types import HealthPing
from app.connectors.http import HttpClient, HttpTransportError
from app.errors import InvalidDataSource

CONNECTOR_KEY = "http.health"


class HttpHealthAdapter:
    key = CONNECTOR_KEY

    def __init__(
        self,
        client: HttpClient,
        url: str,
        expected_status: int,
        timeout_seconds: float,
        secret: str | None = None,
        *,
        checked_at: datetime | None = None,
    ) -> None:
        self._client = client
        self._url = url
        self._expected_status = expected_status
        self._timeout_seconds = timeout_seconds
        self._secret = secret
        self._checked_at = checked_at or datetime.now(timezone.utc)

    def list_pings(self) -> list[HealthPing]:
        headers = {"Authorization": f"Bearer {self._secret}"} if self._secret else None
        try:
            response = self._client.get(self._url, timeout=self._timeout_seconds, headers=headers)
        except HttpTransportError:
            return [self._ping(status="down", latency_ms=None)]
        status = "up" if response.status_code == self._expected_status else "down"
        return [self._ping(status=status, latency_ms=response.elapsed_ms)]

    def _ping(self, *, status: str, latency_ms: int | None) -> HealthPing:
        return HealthPing(
            id=f"http-{self._checked_at.strftime('%Y%m%dT%H%M%SZ')}",
            checked_at=self._checked_at.isoformat(),
            status=status,
            latency_ms=latency_ms,
            region="remote",
        )


def validate_health_target(url: str, expected_status: int, timeout_seconds: int) -> None:
    if not isinstance(url, str) or len(url) > 500:
        raise InvalidDataSource("URL is required")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidDataSource("URL must be an http or https address")
    if parsed.username or parsed.password:
        raise InvalidDataSource("Put credentials in the secret field, not the URL")
    if type(expected_status) is not int or not 100 <= expected_status <= 599:
        raise InvalidDataSource("Expected status must be an integer from 100 to 599")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
        raise InvalidDataSource("Timeout must be an integer from 1 to 30 seconds")
