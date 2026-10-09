"""Idempotent local seed: one dev user and one project with a revenue fixture.

Cost and health fixtures exist on disk for their adapters, but they are not
bound here. See docs/roadmap.md.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_session_factory
from app.models import Project, ProjectSource, User
from app.security import hash_password
from app.services.revenue import KIND_REVENUE

ACME_SLUG = "acme-notes"
ACME_NAME = "Acme Notes"
ACME_REVENUE_FIXTURE = "fixtures/acme_notes_charges.json"
ACME_REVENUE_ADAPTER = "fixture.revenue"


def seed(db: Session, settings: Settings) -> list[str]:
    notes: list[str] = []
    user = db.scalar(select(User).where(User.username == settings.dev_username))
    if user is None:
        db.add(User(username=settings.dev_username, password_hash=hash_password(settings.dev_password)))
        notes.append(f"seeded user {settings.dev_username!r}")
    else:
        notes.append(f"user {settings.dev_username!r} already present")

    project = db.scalar(select(Project).where(Project.slug == ACME_SLUG))
    if project is None:
        project = Project(slug=ACME_SLUG, name=ACME_NAME)
        db.add(project)
        db.flush()
        notes.append(f"seeded project {ACME_SLUG!r}")
    else:
        notes.append(f"project {ACME_SLUG!r} already present")

    source = db.scalar(
        select(ProjectSource).where(
            ProjectSource.project_id == project.id,
            ProjectSource.kind == KIND_REVENUE,
        )
    )
    if source is None:
        db.add(
            ProjectSource(
                project_id=project.id,
                kind=KIND_REVENUE,
                adapter_key=ACME_REVENUE_ADAPTER,
                fixture_path=ACME_REVENUE_FIXTURE,
            )
        )
        notes.append(f"bound {ACME_REVENUE_ADAPTER} to {ACME_SLUG!r}")
    else:
        notes.append(f"revenue source for {ACME_SLUG!r} already present")

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
