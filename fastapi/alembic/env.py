from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_APPS_DIR = os.path.join(_BACKEND_DIR, "apps")
for path in (_BACKEND_DIR, _APPS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import heyman.adapter.outbound.orm.discord_orm  # noqa: E402, F401
import heyman.adapter.outbound.orm.email_orm  # noqa: E402, F401
import heyman.adapter.outbound.orm.juso_orm  # noqa: E402, F401
import heyman.adapter.outbound.orm.telegram_orm  # noqa: E402, F401
import soccer.adapter.outbound.orm.player_orm  # noqa: E402, F401
import soccer.adapter.outbound.orm.schedule_orm  # noqa: E402, F401
import soccer.adapter.outbound.orm.stadium_orm  # noqa: E402, F401
import soccer.adapter.outbound.orm.team_orm  # noqa: E402, F401
from core.matrix.grid_oracle_database_manager import DATABASE_URL, Base  # noqa: E402
from core.matrix.vault_keymaker_secret_manager import get_keymaker  # noqa: E402

import kayfabe.adapter.outbound.orm.championship_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.ple_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.title_history_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_andrews_architect_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_hartley_violin_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_james_director_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_lowe_boat_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_smith_captain_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.crew_walter_roaster_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.passenger_cal_tester_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.passenger_isidor_couple_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.passenger_jack_trainer_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.passenger_molly_scaler_orm  # noqa: E402, F401
import titanic.adapter.outbound.orm.passenger_ruth_validation_orm  # noqa: E402, F401

target_metadata = Base.metadata


def _sync_database_url() -> str:
    url = (DATABASE_URL or get_keymaker().get_secret("DATABASE_URL")).strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set in backend/.env")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
