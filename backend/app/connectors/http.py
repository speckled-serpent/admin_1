"""Read-only HTTP transport. Callers inject this so tests never open a socket."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class HttpTransportError(Exception):
    """The remote check could not complete. The message is safe to show."""


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    elapsed_ms: int


class HttpClient(Protocol):
    def get(self, url: str, timeout: float, headers: dict[str, str] | None = None) -> HttpResponse:
        """Perform one GET. Implementations must not send another method."""


def get_http_client() -> HttpClient:
    from app.connectors.urllib_client import UrllibHttpClient

    return UrllibHttpClient()
