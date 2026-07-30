from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from core.matrix.vault_keymaker_secret_manager import get_keymaker
from soccer.adapter.outbound.orm.player_orm import PlayerOrm
from soccer.adapter.outbound.orm.schedule_orm import ScheduleOrm
from soccer.adapter.outbound.orm.stadium_orm import StadiumOrm
from soccer.adapter.outbound.orm.team_orm import TeamOrm
from soccer.app.dtos.soccer_chat_dto import SoccerChatCommand, SoccerChatTurnDto
from soccer.app.ports.output.soccer_chat_port import SoccerChatPort
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.app.dtos.gemini_generation_dto import GeminiGenerationCommand
from ontology.app.ports.input.gemini_generation_use_case import (
    GeminiGenerationUseCase,
)

logger = logging.getLogger("uvicorn.error")

MONEYBALL_PERSONA = (
    "당신은 축구 데이터 분석에 진심인 스카우트 '머니볼'입니다. "
    "경기장, 구단, 경기 일정, 선수 정보를 모두 꿰고 있습니다. "
    "아래 [축구 데이터]에 있는 사실만 근거로, 한국어로 3~5문장 안에 간결하고 확신 있게 답하세요. "
    "[축구 데이터]에 없는 내용은 추측하지 말고 모른다고 답하세요. "
    "각 섹션 머리에 붙은 표시를 반드시 따르세요 — "
    "'(완전 목록)'이면 그것이 전체이므로 총 개수를 말해도 됩니다. "
    "'(유사도 상위 일부)'이면 전체가 아니므로 '총 N명', '전부', '모두' 같은 "
    "전체 개수나 완전성을 절대 단언하지 말고, 더 있을 수 있다고 덧붙이세요."
)
TOP_K_PER_TABLE = 3
# 선수는 "○○ 소속 수비수 알려줘" 같은 목록형 질문이 많아 3건으로는 부족하다.
TOP_K_PLAYER = 8
# 팀·포지션 선필터가 걸렸을 때는 그 집합이 곧 답이므로 넉넉히 가져온다.
FILTERED_PLAYER_LIMIT = 40
MAX_PROMPT_MESSAGES = 8

# 질문에서 포지션을 집어내기 위한 표기 → 컬럼 값 매핑 (LLM 없이 결정적으로 판정).
POSITION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "GK": ("골키퍼", "키퍼", "GK"),
    "DF": ("수비수", "수비", "DF"),
    "MF": ("미드필더", "미들", "MF"),
    "FW": ("공격수", "공격", "FW", "포워드"),
}


class SoccerChatRepository(SoccerChatPort):
    """soccer(스포크)의 RAG 리포지토리.

    검색(임베딩 유사도)과 프롬프트 구성은 soccer가 직접 소유하고, 실제 텍스트
    생성은 ontology(허브)의 GeminiGenerationUseCase에 위임한다 — 스포크 ↔ 스포크
    직접 의존을 만들지 않기 위해 생성 능력은 허브를 경유한다.
    """

    def __init__(
        self, session: AsyncSession, generation_use_case: GeminiGenerationUseCase
    ) -> None:
        self.session = session
        self._generation_use_case = generation_use_case

    async def stream_chat(self, command: SoccerChatCommand) -> AsyncIterator[str]:
        user_messages = [m for m in command.messages if m.role == "user"]
        if not user_messages:
            yield "궁금한 선수, 구단, 경기 정보를 물어봐 주세요."
            return

        question = user_messages[-1].text
        logger.info("[soccer.soccer_chat] 질문 수신 | question=%r", question)

        context = await self._retrieve_context(question)
        prompt = self._build_prompt(command.messages, context)

        logger.info(
            "[soccer.soccer_chat] ontology 허브로 위임 | prompt_len=%d", len(prompt)
        )
        chunk_count = 0
        async for chunk in self._generation_use_case.stream_generate(
            GeminiGenerationCommand(prompt=prompt)
        ):
            chunk_count += 1
            yield chunk
        logger.info("[soccer.soccer_chat] 답변 스트리밍 완료 | chunks=%d", chunk_count)

    async def _retrieve_context(self, question: str) -> str:
        query_embedding = await asyncio.to_thread(get_keymaker().embed_text, question)

        stadiums = await self._search(StadiumOrm, query_embedding)
        teams = await self._search(TeamOrm, query_embedding)
        schedules = await self._search(ScheduleOrm, query_embedding)
        players, players_exhaustive = await self._search_players(
            question, query_embedding
        )

        team_names = await self._team_name_lookup()
        stadium_names = await self._stadium_name_lookup()

        partial = "유사도 상위 일부"
        sections = [
            (
                "경기장",
                partial,
                [self._describe_stadium(r, team_names) for r in stadiums],
            ),
            (
                "구단",
                partial,
                [self._describe_team(r, stadium_names) for r in teams],
            ),
            (
                "경기 일정",
                partial,
                [self._describe_schedule(r, team_names) for r in schedules],
            ),
            (
                "선수",
                "완전 목록" if players_exhaustive else partial,
                [self._describe_player(r, team_names) for r in players],
            ),
        ]
        blocks = [
            f"[{label}] ({note})\n" + "\n".join(lines)
            for label, note, lines in sections
            if lines
        ]
        if not blocks:
            return "(일치하는 축구 데이터 없음)"
        return "\n\n".join(blocks)

    async def _search_players(self, question: str, query_embedding: list[float]):
        """팀·포지션이 질문에 있으면 SQL로 먼저 좁힌 뒤 그 안에서 벡터 랭킹한다.

        순수 벡터 검색만 쓰면 "아이파크 소속 수비수"처럼 조건이 명확한 목록형
        질문에서 전체 선수 중 상위 k명만 뽑혀 대상 다수가 누락된다.
        반환값 두 번째는 "이 결과가 조건에 맞는 전부인가" 여부다.
        """
        team_id, position = await self._detect_player_filters(question)
        if team_id is None and position is None:
            rows = await self._search(PlayerOrm, query_embedding, top_k=TOP_K_PLAYER)
            return rows, False

        conditions = [PlayerOrm.embedding.is_not(None)]
        if team_id is not None:
            conditions.append(PlayerOrm.team_id == team_id)
        if position is not None:
            conditions.append(PlayerOrm.position == position)

        total = await self.session.scalar(
            select(func.count()).select_from(PlayerOrm).where(*conditions)
        )
        rows = (
            await self.session.scalars(
                select(PlayerOrm)
                .where(*conditions)
                .order_by(PlayerOrm.embedding.op("<=>")(query_embedding))
                .limit(FILTERED_PLAYER_LIMIT)
            )
        ).all()
        logger.info(
            "[soccer.soccer_chat] 선필터 검색 | team_id=%s | position=%s | %d/%d건",
            team_id,
            position,
            len(rows),
            total or 0,
        )
        return rows, len(rows) == (total or 0)

    async def _detect_player_filters(
        self, question: str
    ) -> tuple[str | None, str | None]:
        """질문에서 팀·포지션을 집어낸다 — 구단이 15개뿐이라 문자열 매칭으로 충분."""
        rows = (
            await self.session.execute(
                select(TeamOrm.team_id, TeamOrm.team_name, TeamOrm.region_name)
            )
        ).all()
        team_id = None
        for tid, team_name, region_name in rows:
            for candidate in (team_name, region_name):
                if candidate and candidate.strip() and candidate.strip() in question:
                    team_id = tid
                    break
            if team_id is not None:
                break

        position = None
        for pos, keywords in POSITION_KEYWORDS.items():
            if any(kw in question for kw in keywords):
                position = pos
                break
        return team_id, position

    async def _search(
        self, orm_cls, query_embedding: list[float], top_k: int = TOP_K_PER_TABLE
    ):
        stmt = (
            select(orm_cls)
            .where(orm_cls.embedding.is_not(None))
            .order_by(orm_cls.embedding.op("<=>")(query_embedding))
            .limit(top_k)
        )
        rows = (await self.session.scalars(stmt)).all()
        logger.info(
            "[soccer.soccer_chat] RAG 검색 완료 | table=%s | top_k=%d | 결과 수=%d",
            orm_cls.__tablename__,
            top_k,
            len(rows),
        )
        return rows

    async def _team_name_lookup(self) -> dict[str, str]:
        rows = (
            await self.session.execute(select(TeamOrm.team_id, TeamOrm.team_name))
        ).all()
        return {team_id: team_name for team_id, team_name in rows if team_name}

    async def _stadium_name_lookup(self) -> dict[str, str]:
        rows = (
            await self.session.execute(
                select(StadiumOrm.stadium_id, StadiumOrm.statdium_name)
            )
        ).all()
        return {
            stadium_id: statdium_name
            for stadium_id, statdium_name in rows
            if statdium_name
        }

    def _describe_stadium(self, r: StadiumOrm, team_names: dict[str, str]) -> str:
        fields = [
            ("경기장명", r.statdium_name),
            ("홈팀", team_names.get(r.hometeam_id, r.hometeam_id)),
            ("좌석수", r.seat_count),
            ("주소", r.address),
        ]
        return "- " + " / ".join(f"{k}: {v}" for k, v in fields if v)

    def _describe_team(self, r: TeamOrm, stadium_names: dict[str, str]) -> str:
        fields = [
            ("구단명", r.team_name),
            ("영문명", r.e_team_name),
            ("연고지", r.region_name),
            ("창단연도", r.orig_yyyy),
            ("홈구장", stadium_names.get(r.stadium_id, r.stadium_id)),
        ]
        return "- " + " / ".join(f"{k}: {v}" for k, v in fields if v)

    def _describe_schedule(self, r: ScheduleOrm, team_names: dict[str, str]) -> str:
        home = team_names.get(r.hometeam_id, r.hometeam_id)
        away = team_names.get(r.awayteam_id, r.awayteam_id)
        fields = [
            ("일자", r.sche_date),
            ("구분", r.gubun),
            ("대진", f"{home} vs {away}" if home or away else None),
            (
                "스코어",
                f"{r.home_score}:{r.away_score}" if r.home_score is not None else None,
            ),
        ]
        return "- " + " / ".join(f"{k}: {v}" for k, v in fields if v)

    def _describe_player(self, r: PlayerOrm, team_names: dict[str, str]) -> str:
        fields = [
            ("이름", r.player_name),
            ("영문명", r.e_player_name),
            ("별명", r.nickname),
            ("포지션", r.position),
            ("국적", r.nation),
            ("소속팀", team_names.get(r.team_id, r.team_id)),
            ("등번호", r.back_no),
            ("생년월일", r.birth_date),
            # 임베딩에는 들어가 있으나 표시에서 빠져 LLM이 못 보던 필드.
            ("신장", f"{r.height}cm" if r.height else None),
            ("체중", f"{r.weight}kg" if r.weight else None),
        ]
        return "- " + " / ".join(f"{k}: {v}" for k, v in fields if v)

    def _build_prompt(
        self, messages: tuple[SoccerChatTurnDto, ...], context: str
    ) -> str:
        recent = messages[-MAX_PROMPT_MESSAGES:]
        lines = [
            f"{'질문자' if turn.role == 'user' else '머니볼'}: {turn.text.strip()}"
            for turn in recent
        ]
        return (
            f"{MONEYBALL_PERSONA}\n\n"
            f"[축구 데이터]\n{context}\n\n" + "\n".join(lines) + "\n머니볼:"
        )
