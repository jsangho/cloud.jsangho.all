"""커리어 샌드박스 조립.

**규칙을 여기 쓰지 않는다.** 하는 일은 셋뿐이다 — 세이브를 읽고, 도메인 함수를
부르고, 다시 쓴다. 수치가 이 파일에 나타나면 규칙이 두 곳에 있다는 뜻이다.

## 쓰기 경로는 모두 같은 모양이다

    1. `load_for_update` 로 **행을 잠그고** 읽는다
    2. 그 커리어의 **요청 영수증**을 찾는다 — 있으면 저장된 응답을 그대로 준다
    3. 도메인 함수를 부른다 (순수 함수 — 실패하면 아무것도 안 바뀐다)
    4. `save` 로 세이브와 영수증을 **한 커밋**에 쓴다

**세 장치가 서로 다른 것을 막고, 셋 다 필요하다.**

    잠금(1)        서로 다른 두 연산이 같은 세이브를 동시에 고치는 것 (잃어버린 갱신)
    영수증(2·4)    같은 **요청**의 재전송 — 중복 클릭·응답 유실 후 재시도
    도메인 키      같은 **연산**의 재적용 — 같은 주차를 두 번 처리, 결산 두 번

2026-10-21 에 실제 스택(격리 PostgreSQL + httpx)으로 재서, 1과 도메인 키만으로는
중복 요청이 **전부 통과**하는 것을 확인했다 — 잠금은 두 요청이 같은 요청인지
모르고, 행동 키의 순번은 **남은 포인트**에서 나와 재시도가 다음 순번을 쓴다. 그
빈칸을 메우는 것이 2번이다.

**영수증 열쇠는 클라이언트가 만든다.** 서버가 만들면 모든 요청이 새 요청이라
재시도를 식별할 수 없다 — 이 유스케이스가 `request_id` 를 필수로 받는 이유다.

## AI 를 부르지 않는다

사용자 요구 §2.3 — 경기 결과·상태는 규칙이 정한다. AI 가 들어갈 자리는 확정된
상태를 읽어 문장을 만드는 쪽이고, 이 유스케이스 바깥이다. 그래서 AI 가 죽어도
주차 진행이 저장된다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from kayfabe.app.dtos.career_sandbox_dto import (
    AbilityDto,
    CardDto,
    CareerOutcome,
    CareerSummaryDto,
    CareerViewDto,
    ChoiceDto,
    EventDto,
    InjuryDto,
    IntentDto,
    LogDto,
    RelationshipDto,
    RetirementDto,
    RiskDto,
    SeasonSummaryDto,
    TitleDto,
    WeekReportDto,
    WrestlerDto,
)
from kayfabe.app.ports.input.career_sandbox_use_case import (
    CareerSandboxUseCase,
    RequestKeyConflictError,
)
from kayfabe.app.ports.output.sandbox_career_repository import (
    DuplicateRequestError,
    RequestReceipt,
    SandboxCareerRepository,
)
from kayfabe.domain.services import career_actions as actions
from kayfabe.domain.services import career_aging as aging
from kayfabe.domain.services import career_engine as engine
from kayfabe.domain.services import career_events as events
from kayfabe.domain.services import career_relations as relations
from kayfabe.domain.services import career_retirement as retire
from kayfabe.domain.services import career_season as season_rules
from kayfabe.domain.services.career_engine import WeekReport
from kayfabe.domain.services.career_world import (
    Ability,
    Balance,
    Title,
    WorldState,
    Wrestler,
)

logger = logging.getLogger("uvicorn.error")

#: 대시보드가 들고 가는 최근 기록 줄 수. 전체 기록은 `/log` 로 따로 읽는다 —
#: 사용자 요구 §5 가 "긴 기록 목록이 화면의 중심을 차지하지 않도록" 이라고 적었다.
RECENT_LOG = 12


class CareerSandboxInteractor(CareerSandboxUseCase):
    def __init__(
        self,
        *,
        repository: SandboxCareerRepository,
        balance: Balance | None = None,
    ) -> None:
        self._repo = repository
        #: 밸런스를 주입받는 것은 테스트 때문만이 아니다 — 시즌 길이가 설정이라
        #: 서버 설정으로 바꿀 수 있어야 한다(사용자 요구 §1 마지막 줄).
        self._balance = balance or Balance()

    # ── 생성·조회 ─────────────────────────────────────────────

    async def create(
        self, *, user_id: int, name: str, style: str, age: int, seed: int | None = None
    ) -> CareerViewDto:
        # 시드를 안 주면 만든다. **저장해 두므로 재접속해도 같은 세계다.**
        chosen = seed if seed is not None else secrets.randbelow(2**31)
        world = engine.create_world(
            player=name, style=style, seed=chosen, age=age, balance=self._balance
        )
        career_id = await self._repo.create(
            user_id=user_id, player_name=world.player, seed=chosen, state=world
        )
        logger.info(
            "[CareerSandbox] created id=%d user=%d player=%s seed=%d",
            career_id,
            user_id,
            world.player,
            chosen,
        )
        return self._view(career_id, world)

    async def list_careers(self, user_id: int) -> list[CareerSummaryDto]:
        rows = await self._repo.list_for_user(user_id)
        return [
            CareerSummaryDto(
                id=r.id,
                player_name=r.player_name,
                season=r.season,
                week=r.week,
                season_weeks=self._balance.season_weeks,
                phase=r.phase,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def view(self, *, user_id: int, career_id: int) -> CareerViewDto | None:
        world = await self._repo.load(user_id=user_id, career_id=career_id)
        if world is None:
            return None
        return self._view(career_id, world)

    async def log(
        self,
        *,
        user_id: int,
        career_id: int,
        season: int | None,
        limit: int,
        offset: int,
    ) -> list[LogDto]:
        world = await self._repo.load(user_id=user_id, career_id=career_id)
        if world is None:
            raise LookupError("커리어를 찾을 수 없습니다")
        entries = [e for e in world.log if season is None or e.season == season]
        # 최근 것부터.
        entries.reverse()
        return [_log_dto(e) for e in entries[offset : offset + limit]]

    # ── 쓰기 ──────────────────────────────────────────────────

    async def _mutate(
        self,
        *,
        user_id: int,
        career_id: int,
        request_id: str,
        operation: str,
        payload: dict[str, Any],
        change: Callable[[WorldState], WorldState],
        view_of: Callable[[WorldState], CareerViewDto] | None = None,
    ) -> CareerOutcome:
        """잠그고, 영수증을 보고, 바꾸고, 쓴다. **쓰기 경로가 전부 이 문을 지난다.**

        순서가 규칙이다. 영수증 조회가 **잠금 뒤**에 있어야 동시 요청 둘 중 둘째가
        첫째의 커밋을 보고 멈춘다 — 잠금 앞에서 읽으면 둘 다 `None` 을 보고 둘 다
        적용한다(READ COMMITTED 에서 각 문장이 새 스냅샷을 받으므로, 잠금이 풀린
        뒤의 조회는 첫째의 커밋을 본다).

        **실패는 영수증을 남기지 않는다.** 도메인이 거부하면(`ValueError`) 세이브도
        영수증도 쓰이지 않으므로 같은 키로 다시 보내도 된다 — 바뀐 것이 없으니
        재시도가 안전하고, 입력을 고쳐 보내면 지문이 달라 충돌로 잡힌다. 실패
        응답을 성공으로 재사용하지 않기 위해 **성공한 요청만** 적는다.
        """
        if not request_id.strip():
            raise ValueError("요청 키가 비어 있습니다")

        fingerprint = _fingerprint(operation, payload)
        world = await self._repo.load_for_update(user_id=user_id, career_id=career_id)
        if world is None:
            raise LookupError("커리어를 찾을 수 없습니다")

        stored = await self._repo.find_receipt(
            user_id=user_id, career_id=career_id, request_id=request_id
        )
        if stored is not None:
            return self._replay(stored, fingerprint=fingerprint, request_id=request_id)

        updated = change(world)
        view = self._view(career_id, updated) if view_of is None else view_of(updated)
        try:
            await self._repo.save(
                user_id=user_id,
                career_id=career_id,
                state=updated,
                receipt=RequestReceipt(
                    request_id=request_id,
                    fingerprint=fingerprint,
                    response=asdict(view),
                ),
            )
        except DuplicateRequestError:
            # 고유 제약이 잡았다 — 잠금이 막지 못한 경로로 동시에 들어왔다는 뜻이다.
            # 세이브 변경까지 되돌려졌으므로 저장된 응답을 읽어 돌려준다.
            raced = await self._repo.find_receipt(
                user_id=user_id, career_id=career_id, request_id=request_id
            )
            if raced is None:  # pragma: no cover - 제약이 잡았는데 행이 없을 수 없다
                raise
            logger.warning(
                "[CareerSandbox] duplicate request caught by constraint id=%d req=%s",
                career_id,
                request_id,
            )
            return self._replay(raced, fingerprint=fingerprint, request_id=request_id)
        return CareerOutcome(view=view)

    def _replay(
        self, receipt: RequestReceipt, *, fingerprint: str, request_id: str
    ) -> CareerOutcome:
        """저장된 응답을 그대로 돌려준다. **지문이 다르면 거부한다.**"""
        if receipt.fingerprint != fingerprint:
            raise RequestKeyConflictError(
                f"요청 키를 다른 요청에 다시 썼습니다: {request_id}"
            )
        logger.info("[CareerSandbox] replayed request req=%s", request_id)
        return CareerOutcome(replayed=receipt.response)

    async def act(
        self,
        *,
        user_id: int,
        career_id: int,
        action: str,
        target: str | None,
        request_id: str,
    ) -> CareerOutcome:
        return await self._mutate(
            user_id=user_id,
            career_id=career_id,
            request_id=request_id,
            operation="act",
            payload={"action": action, "target": target},
            change=lambda w: actions.perform(
                w, action=action, balance=self._balance, target=target
            ),
        )

    async def advance(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        report: list[WeekReport] = []

        def step(w: WorldState) -> WorldState:
            result = engine.advance_week(w, balance=self._balance)
            report.append(result.report)
            return result.state

        return await self._mutate(
            user_id=user_id,
            career_id=career_id,
            request_id=request_id,
            operation="advance",
            payload={},
            change=step,
            # 주차 보고는 세이브에 없다 — 진행의 결과물이라 여기서만 나온다. 그래서
            # 영수증에 담기는 응답에도 함께 들어가야 재시도가 **같은 답**을 받는다.
            view_of=lambda w: self._view(
                career_id, w, report=report[0] if report else None
            ),
        )

    async def resolve(
        self,
        *,
        user_id: int,
        career_id: int,
        event_id: str,
        choice: str,
        request_id: str,
    ) -> CareerOutcome:
        return await self._mutate(
            user_id=user_id,
            career_id=career_id,
            request_id=request_id,
            operation="resolve",
            payload={"event_id": event_id, "choice": choice},
            change=lambda w: events.resolve(
                w, event_id_=event_id, choice_code=choice, balance=self._balance
            ),
        )

    async def settle(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        return await self._mutate(
            user_id=user_id,
            career_id=career_id,
            request_id=request_id,
            operation="settle",
            payload={},
            change=lambda w: season_rules.settle(w, balance=self._balance),
        )

    async def next_season(
        self, *, user_id: int, career_id: int, request_id: str
    ) -> CareerOutcome:
        return await self._mutate(
            user_id=user_id,
            career_id=career_id,
            request_id=request_id,
            operation="next_season",
            payload={},
            change=lambda w: season_rules.start_next_season(w, balance=self._balance),
        )

    # ── DTO 변환 ──────────────────────────────────────────────

    def _view(
        self, career_id: int, world: WorldState, *, report: WeekReport | None = None
    ) -> CareerViewDto:
        hero = world.hero
        card = engine.book(world, balance=self._balance)
        return CareerViewDto(
            id=career_id,
            season=world.season,
            week=world.week,
            season_weeks=self._balance.season_weeks,
            phase=str(world.phase),
            action_points=world.action_points,
            max_action_points=self._balance.action_points,
            player=self._wrestler_dto(hero, world, with_risk=True),
            next_card=CardDto(
                kind=card.kind,
                opponent=card.opponent,
                title=card.title,
                partner=card.partner,
                opponents=card.opponents,
                note=card.note,
            ),
            pending=tuple(
                EventDto(
                    id=e.id,
                    kind=e.kind,
                    season=e.season,
                    week=e.week,
                    subject=e.subject,
                    other=e.other,
                    headline=e.headline,
                    detail=e.detail,
                    choices=tuple(
                        ChoiceDto(
                            code=c.code, label=c.label, enabled=c.enabled, note=c.note
                        )
                        for c in e.choices
                    ),
                )
                for e in world.pending
            ),
            titles=tuple(self._title_dto(t, world) for t in world.titles),
            relationships=tuple(
                RelationshipDto(
                    a=r.a,
                    b=r.b,
                    kind=str(r.kind),
                    heat=r.heat,
                    started_week=r.started_week,
                    last_week=r.last_week,
                    history=r.history,
                    feud=relations.is_feud(r),
                )
                for r in world.relationships
            ),
            roster=tuple(
                self._wrestler_dto(w, world, with_risk=False) for w in world.roster
            ),
            seasons=tuple(_season_dto(s) for s in world.seasons),
            recent_log=tuple(_log_dto(e) for e in reversed(world.log[-RECENT_LOG:])),
            last_report=_report_dto(report) if report is not None else None,
        )

    def _wrestler_dto(
        self, w: Wrestler, world: WorldState, *, with_risk: bool
    ) -> WrestlerDto:
        trend = aging.recent_trend(w)
        risk = None
        if with_risk and not w.retired:
            assessed = retire.assess(w, self._balance)
            # **점수를 담지 않는다.** 밴드와 근거만 내보낸다(§6).
            risk = RiskDto(band=assessed.band, reasons=assessed.explained[:5])
        return WrestlerDto(
            name=w.name,
            style=w.style,
            brand=w.brand,
            age=w.age,
            debut_age=w.debut_age,
            alignment=str(w.alignment),
            popularity=w.popularity,
            ability=_ability_dto(w.ability),
            condition=w.condition,
            status=str(w.status),
            wins=w.wins,
            losses=w.losses,
            reigns=w.reigns,
            held=w.held,
            out_weeks=w.out_weeks,
            is_player=w.is_player,
            injuries=tuple(
                InjuryDto(
                    kind=i.kind,
                    severity=str(i.severity),
                    season=i.season,
                    week=i.week,
                    weeks_out=i.weeks_out,
                    recovered=i.recovered,
                    recurrence=i.recurrence,
                    permanent=i.permanent,
                )
                for i in w.injuries
            ),
            trend=_ability_dto(trend) if trend is not None else None,
            intent=(
                None
                if w.intent is None
                else IntentDto(
                    origin=w.intent.origin,
                    cause=str(w.intent.cause),
                    season=w.intent.season,
                    week=w.intent.week,
                    final_season=w.intent.final_season,
                )
            ),
            retirement=(
                None
                if w.retirement is None
                else RetirementDto(
                    cause=str(w.retirement.cause),
                    season=w.retirement.season,
                    week=w.retirement.week,
                    age=w.retirement.age,
                    wins=w.retirement.wins,
                    losses=w.retirement.losses,
                    held=w.retirement.held,
                    reigns=w.retirement.reigns,
                    titles=w.retirement.titles,
                    note=w.retirement.note,
                )
            ),
            risk=risk,
        )

    def _title_dto(self, t: Title, world: WorldState) -> TitleDto:
        """재위 주차를 계산해 넣는다. **절대 주차 차이**다 — 시즌을 넘겨도 맞다."""
        reign = None
        if t.holder is not None and t.won_week is not None:
            absolute = (world.season - 1) * self._balance.season_weeks + world.week
            reign = max(0, absolute - t.won_week)
        return TitleDto(
            name=t.name,
            brand=t.brand,
            required_popularity=t.required_popularity,
            holder=t.holder,
            defenses=t.defenses,
            reign_weeks=reign,
        )


def _fingerprint(operation: str, payload: dict[str, Any]) -> str:
    """연산 이름 + payload 의 sha256.

    **연산 이름이 지문에 들어간다.** 빼면 payload 가 빈 쓰기들(`advance` ·
    `settle` · `next_season`)이 같은 지문을 갖고, 같은 키로 `/advance` 를 보낸 뒤
    `/settle` 을 보내면 충돌 대신 **주차 진행 응답**이 돌아간다.

    `sort_keys` 로 칸 순서를 지우고 `separators` 로 공백을 지운다 — 같은 뜻의
    payload 가 다른 지문을 갖는 길을 막는다. `ensure_ascii=False` 는 한글 행동
    이름(`훈련`)을 그대로 두는 것이고, 해시 입력이 안정적이기만 하면 된다.
    """
    canonical = json.dumps(
        [operation, payload],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _ability_dto(a: Ability) -> AbilityDto:
    return AbilityDto(
        in_ring=a.in_ring, mic=a.mic, stamina=a.stamina, resilience=a.resilience
    )


def _log_dto(e) -> LogDto:
    return LogDto(
        season=e.season,
        week=e.week,
        kind=e.kind,
        subject=e.subject,
        summary=e.summary,
        other=e.other,
        result=e.result,
        title=e.title,
    )


def _season_dto(s) -> SeasonSummaryDto:
    return SeasonSummaryDto(
        season=s.season,
        wins=s.wins,
        losses=s.losses,
        age=s.age,
        ability=_ability_dto(s.ability),
        ability_delta=_ability_dto(s.ability_delta),
        titles_won=s.titles_won,
        defenses=s.defenses,
        injuries=s.injuries,
        retired=s.retired,
        highlights=s.highlights,
        risk_band=s.risk_band,
    )


def _report_dto(r: WeekReport) -> WeekReportDto:
    return WeekReportDto(
        season=r.season,
        week=r.week,
        kind=r.kind,
        opponent=r.opponent,
        won=r.won,
        title=r.title,
        title_changed=r.title_changed,
        finish=r.finish,
        rating=r.rating,
        popularity_delta=r.popularity_delta,
        injured=r.injured,
        injured_weeks=r.injured_weeks,
        promoted_to=r.promoted_to,
        opened_events=r.opened_events,
        retired=r.retired,
        risk_band=r.risk_band,
        probability=r.probability,
    )
