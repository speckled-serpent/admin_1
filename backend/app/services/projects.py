"""Create and list projects and the panels chosen for each one."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.errors import InvalidProject
from app.models import Project, ProjectPanel
from app.panels import PANELS_BY_KEY, ordered_panel_keys

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:80]


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).options(selectinload(Project.panels)).order_by(Project.name)))


def panel_keys_for(project: Project) -> list[str]:
    selected = {row.panel_key for row in project.panels}
    return ordered_panel_keys(selected)


def create_project(db: Session, name: str, panel_keys: list[str]) -> Project:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidProject("Name is required")
    if len(cleaned) > 120:
        raise InvalidProject("Name is too long")

    unknown = [key for key in panel_keys if key not in PANELS_BY_KEY]
    if unknown:
        raise InvalidProject(f"Unknown panel: {unknown[0]}")
    selected = ordered_panel_keys(set(panel_keys))
    if not selected:
        raise InvalidProject("Select at least one panel")

    base = slugify(cleaned)
    if not base:
        raise InvalidProject("Name is required")

    project = Project(slug=_unique_slug(db, base), name=cleaned)
    db.add(project)
    db.flush()
    for key in selected:
        db.add(ProjectPanel(project_id=project.id, panel_key=key))
    project_id = project.id
    db.commit()
    stored = db.scalar(select(Project).options(selectinload(Project.panels)).where(Project.id == project_id))
    assert stored is not None
    return stored


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    number = 2
    while db.scalar(select(Project.id).where(Project.slug == slug)) is not None:
        suffix = f"-{number}"
        slug = f"{base[: 80 - len(suffix)]}{suffix}"
        number += 1
    return slug
