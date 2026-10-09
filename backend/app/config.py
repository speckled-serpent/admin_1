"""Runtime settings. Defaults boot a local SQLite database with no .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader. Variables already in the environment win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_ttl_hours: int
    dev_username: str
    dev_password: str
    cors_origins: tuple[str, ...]
    backend_root: Path

    @property
    def fixtures_dir(self) -> Path:
        return self.backend_root / "fixtures"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(BACKEND_ROOT / ".env")
    origins = tuple(
        part.strip()
        for part in os.environ.get(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if part.strip()
    )
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/admin.db"),
        session_ttl_hours=int(os.environ.get("SESSION_TTL_HOURS", "168")),
        dev_username=os.environ.get("DEV_USERNAME", "dev"),
        dev_password=os.environ.get("DEV_PASSWORD", "devpass"),
        cors_origins=origins,
        backend_root=BACKEND_ROOT,
    )
