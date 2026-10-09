"""ASGI app. Create with create_app() so tests can mount a fresh instance."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    # Telemetry stays off. This process does not export traces, metrics, or logs.
    app = FastAPI(
        title="admin_1",
        version="0.1.0",
        telemetry={
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
            "auto_configure": False,
        },
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    app.include_router(auth_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
