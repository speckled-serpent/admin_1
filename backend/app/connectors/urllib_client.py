"""The only module that opens an HTTP connection. Tests do not use it."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from app.connectors.http import HttpResponse, HttpTransportError


class UrllibHttpClient:
    def get(self, url: str, timeout: float, headers: dict[str, str] | None = None) -> HttpResponse:
        request = urllib.request.Request(url, headers=headers or {}, method="GET")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        started = time.perf_counter()
        try:
            with opener.open(request, timeout=timeout) as response:
                elapsed = int((time.perf_counter() - started) * 1000)
                return HttpResponse(status_code=response.status, elapsed_ms=elapsed)
        except urllib.error.HTTPError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            return HttpResponse(status_code=exc.code, elapsed_ms=elapsed)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HttpTransportError("Could not reach the health check URL") from exc
