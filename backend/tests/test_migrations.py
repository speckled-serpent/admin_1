from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import BACKEND_ROOT, get_settings
from app.database import Base


def test_upgrade_matches_models(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    expected = {name: {column.name for column in table.columns} for name, table in Base.metadata.tables.items()}
    actual = {name: {column["name"] for column in inspector.get_columns(name)} for name in expected}
    assert actual == expected
    engine.dispose()
