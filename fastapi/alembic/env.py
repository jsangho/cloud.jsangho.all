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

import core.entities.user_model  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.championship_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.agent_prediction_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.knowledge_chunk_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.ple_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.shop_orm  # noqa: E402, F401
import kayfabe.adapter.outbound.orm.title_history_orm  # noqa: E402, F401

# **고아 테이블 주의 (2026-09-28).** `wwe_game`·`titanic` 앱을 지웠지만 그 테이블은
# 운영 DB에 그대로 남겨 뒀다(career_* 에 저장된 플레이 기록이 있다). 위 메타데이터에
# 더 이상 그 모델이 없으므로 **`--autogenerate`가 DROP TABLE을 제안한다.**
# 생성된 마이그레이션에 career_*·passengers·crew_* drop이 보이면 지우고 넘어간다.
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
