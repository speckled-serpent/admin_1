"""Idempotent local seed: one dev user and no projects.

Revenue, cost, and health fixtures stay on disk for adapters and tests.
A fresh database has nothing to show until someone creates a project.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_session_factory
from app.models import User
from app.security import hash_password


def seed(db: Session, settings: Settings) -> list[str]:
    notes: list[str] = []
    user = db.scalar(select(User).where(User.username == settings.dev_username))
    if user is None:
        db.add(User(username=settings.dev_username, password_hash=hash_password(settings.dev_password)))
        notes.append(f"seeded user {settings.dev_username!r}")
    else:
        notes.append(f"user {settings.dev_username!r} already present")

    db.commit()
    return notes


def main() -> None:
    settings = get_settings()
    try:
        factory = get_session_factory()
        with factory() as db:
            for line in seed(db, settings):
                print(line)
    except OperationalError as exc:
        print(
            "Seed failed because the database schema is missing. "
            "Apply migrations first: cd backend && .venv/bin/alembic upgrade head",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
