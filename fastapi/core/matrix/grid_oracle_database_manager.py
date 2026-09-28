"""Neon(Postgres) 비동기 연결 · FastAPI Depends(get_db)."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from fastapi import HTTPException

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
    return get_keymaker().get_secret("NEON_SQL_LOG").lower() in (
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


_raw_url = get_keymaker().get_secret("DATABASE_URL")
DATABASE_URL = (
    _strip_unsupported_asyncpg_query_params(_async_database_url(_raw_url))
    if _raw_url
    else ""
)


def _force_round_trip_float_text(async_engine) -> None:
    """새 연결마다 `extra_float_digits`를 올린다 — **읽어 온 float이 저장값과 달라진다.**

    운영 연결의 기본값이 `0`이었다(2026-09-28 실측). 그 값에서 PostgreSQL은
    `double precision`을 **유효숫자 15자리 문자열**로 내보내고, psycopg가 그것을 다시
    파싱하면 원래와 **다른 double**이 된다. 저장은 정확한데 읽기에서 깨지는 것이다:

        confidence = (1.0/3.0)::float8   -> true    (저장값은 정확하다)
        confidence::text                 -> '0.333333333333333'
        파싱 결과                         != 1/3

    `1` 이상이면 왕복 무손실(최단 정확 표현)로 바뀐다. `3`을 쓰지 않는 이유는 그것이
    PostgreSQL 12 이전의 "최대 자리수" 관용값이고 지금은 1 이상이면 전부 같기 때문이다.

    **startup 파라미터(`options=-c extra_float_digits=1`)로는 안 된다.** Supabase 풀러가
    그것을 **조용히 버린다** — 연결은 성공하고 에러도 없는데 값이 `0`에 머문다(실측).
    고친 줄 알고 아무것도 안 바뀌는 쪽이 더 위험해서 `SET`으로 간다. 세션 모드
    풀러(5432)라 `SET`이 연결 수명 동안 유지된다.

    처음 드러난 자리는 KAYFABE 재현(Phase 5)이다 — 저장된 `confidence`와 다시 계산한
    값을 **오차 없이** 견주므로, 1/3·2/3처럼 15자리로 안 떨어지는 값이면 멀쩡한 예측이
    `diverged`로 떴다. 다만 이 칸은 kayfabe 전용이 아니라 float을 읽는 모든 곳에 걸린다.
    """

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_extra_float_digits(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET extra_float_digits = 1")
        finally:
            cursor.close()
        # **커밋을 빼면 아무 효과가 없다.** psycopg는 이 `SET`으로 트랜잭션을 열고
        # (`[INTRANS]`), 세션이 반납될 때 도는 rollback이 `SET`을 함께 되돌린다.
        # `SET LOCAL`이 아니어도 트랜잭션 안에서 실행하면 롤백 대상이다.
        #
        # 놓치기 쉬운 이유: `SET` 직후 같은 트랜잭션에서 읽으면 `1`로 보인다.
        # 요청 하나가 끝나고 나서야 `0`으로 돌아가므로, 스크립트로 확인하면 고쳐진
        # 것처럼 보이고 앱에서만 안 고쳐진다. **요청 경로로 확인해야 한다.**
        dbapi_connection.commit()


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
if engine is not None:
    _force_round_trip_float_text(engine)
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
