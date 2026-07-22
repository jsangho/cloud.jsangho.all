"""Neon(Postgres) 비동기 연결 · FastAPI Depends(get_db)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from fastapi import HTTPException

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

APP_LOG = logging.getLogger("uvicorn.error")
LAYER_LOG = APP_LOG


def james_director_upload_info(src: str, msg: str, *args: object) -> None:
    """James Director 업로드 계층 로그 (현재 시각 + 파일명)."""
    from datetime import datetime

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LAYER_LOG.info("[JamesDirectorUpload][%s][%s] " + msg, ts, src, *args)


class Base(DeclarativeBase):
    pass


def _neon_sql_log_enabled() -> bool:
    return os.getenv("NEON_SQL_LOG", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


class _SuppressPoolTerminateOnCancel(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if not msg.startswith("Exception terminating connection"):
            return True
        exc = record.exc_info[1] if record.exc_info else None
        return not isinstance(exc, asyncio.CancelledError)


def configure_db_logging() -> None:
    APP_LOG.setLevel(logging.INFO)
    pool_log = logging.getLogger("sqlalchemy.pool")
    pool_log.addFilter(_SuppressPoolTerminateOnCancel())
    for name in (
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
        "neon.db",
        "secom.layer",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return url  # psycopg3은 async 기본 지원 — 드라이버 변환 불필요
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def _strip_unsupported_asyncpg_query_params(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in {"sslmode", "channel_binding"}
    ]
    new_query = urlencode(kept)
    return urlunparse(parsed._replace(query=new_query))


_raw_url = os.getenv("DATABASE_URL", "").strip()
DATABASE_URL = (
    _strip_unsupported_asyncpg_query_params(_async_database_url(_raw_url))
    if _raw_url
    else ""
)

engine = (
    create_async_engine(
        DATABASE_URL,
        echo=_neon_sql_log_enabled(),
        pool_pre_ping=False,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_timeout=30,
    )
    if DATABASE_URL
    else None
)
AsyncSessionLocal = (
    async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    if engine is not None
    else None
)


def attach_neon_sql_logging(async_engine) -> None:
    if not _neon_sql_log_enabled():
        return
    sync_engine = async_engine.sync_engine
    if getattr(sync_engine, "_neon_sql_logging", False):
        return
    sync_engine._neon_sql_logging = True
    log = APP_LOG

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(
            asyncio.get_event_loop().time()
        )
        log.info("[Neon SQL] %s", statement)

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).pop()


async def rollback_readonly(session: AsyncSession) -> None:
    if session.in_transaction():
        await session.rollback()


async def warmup_db_pool() -> None:
    if engine is None:
        return
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def init_db() -> None:
    if engine is None:
        return

    import titanic.adapter.outbound.orm.passenger_jack_trainer_orm  # noqa: F401
    import titanic.adapter.outbound.orm.passenger_rose_model_strategies  # noqa: F401

    try:
        import manager.adapter.outbound.orm.juso_orm  # noqa: F401
    except ImportError:
        pass

    try:
        import secom.app.models.user_model  # noqa: F401
    except ImportError:
        pass

    try:
        import kayfabe.adapter.outbound.orm.ple_orm  # noqa: F401
        import kayfabe.adapter.outbound.orm.title_history_orm  # noqa: F401
    except ImportError:
        pass

    import core.entities.user_model  # noqa: F401

    await warmup_db_pool()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    if engine is not None:
        await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession]:
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # `flush()` 이후에는 session.new/dirty/deleted가 비어 보일 수 있어
            # 변경 사항이 있는데도 rollback 되는 케이스가 생깁니다.
            # 트랜잭션이 열려 있으면 commit 하고, 아니면 아무 것도 하지 않습니다.
            if session.in_transaction():
                await session.commit()
        except asyncio.CancelledError:
            if session.in_transaction():
                await session.rollback()
            raise
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
