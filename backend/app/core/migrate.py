"""Bring the database schema up to date with Alembic (run at start-up for local SQLite).

Databases created before migrations were tracked (via create_all) are stamped at the baseline
first, so existing local data is upgraded in place rather than recreated.
"""
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import BACKEND_DIR
from app.core.database import engine


def upgrade_to_head() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and "users" in tables:
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")
