"""플레이어가 속한 팀 (하네스 §3-D30).

`team_engine`이 아니라 값 객체로 둔다 — `CareerRun`이 이 값을 들고 있어야 하는데,
엔티티가 서비스를 import하면 의존이 거꾸로 흐른다(§2 레이어 규칙).

**이름이 없을 수 있다.** 태그팀의 35%는 이름을 짓지 않고 "A & B"로 불린다
(2026-08-10 사용자 지시 7-2번).
"""

from __future__ import annotations

from dataclasses import dataclass

from wwe_game.domain.constants.teams import TeamKind, kind_for


@dataclass(frozen=True)
class Team:
    name: str
    """빈 문자열이면 이름이 없는 팀이다. `label`이 구성원을 이어 부른다."""
    members: tuple[str, ...]
    """플레이어를 **포함한** 전원. 화면이 "누구와 함께인지"를 보여줘야 한다."""
    formed_week: int = 0

    @property
    def kind(self) -> TeamKind:
        return kind_for(len(self.members))

    @property
    def label(self) -> str:
        """화면에 그대로 나가는 이름."""
        return self.name or " & ".join(self.members)

    def without(self, member: str) -> Team | None:
        """한 명이 빠진 팀. **둘이 남지 않으면 팀이 아니다** — 해체다."""
        rest = tuple(m for m in self.members if m != member)
        return Team(self.name, rest, self.formed_week) if len(rest) >= 2 else None
