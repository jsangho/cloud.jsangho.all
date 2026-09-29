"""위키가 부르는 벨트 이름 ↔ 우리 보드가 부르는 벨트 이름.

## 왜 별칭표가 필요한가

2026-09-29 전수 대조에서 위키 20행 중 **넷이 이름만 다르고 같은 벨트**였다. 이름이
다른 채로 맞추면 그 넷은 "위키에 없는 벨트"로 빠지고, 보드는 낡은 값을 그대로 든다.

## 왜 우리 이름을 위키에 맞추지 않는가

`championship_succession.apply_results`가 **경기 제목과 벨트 이름의 정확 일치**로
타이틀 매치를 판정한다(부분 일치를 허용하면 도전자 결정전이 타이틀전으로 둔갑한다).
그 경기 제목은 PLE 카드가 적은 것이라 보드 이름을 위키 쪽으로 바꾸면 **PLE 결과가
어느 벨트에도 닿지 않게 된다.** 그래서 보드 이름을 그대로 두고 여기서 번역한다.

## 위키가 안 싣는 벨트는 보고만 한다

동기화는 위키 표에 없는 보드 행을 **지우지 않고** "위키에 없음"으로 보고한다 — 없는
것이 폐지인지 문서의 누락인지는 표가 말해 주지 않고, 지우는 판단은 사람 몫이다.

그 보고를 받고 사람이 정한 적이 실제로 있다: `WWE Speed Championship`·`WWE Women's
Speed Championship` 둘이 2026-09-29 동기화에서 걸렸고 **폐지로 확인돼 카탈로그에서
지웠다.** 지금은 보고에 걸리는 벨트가 없다.
"""

from __future__ import annotations

#: 현 챔피언 표가 실린 위키 문서와 절. 절 번호는 문서가 자라면 밀리므로 **제목으로
#: 찾는다** — `WikiArticlePort.sections`가 번호를 준다.
WIKI_CHAMPIONS_ARTICLE = "List of current champions in WWE"
WIKI_CHAMPIONS_SECTION = "Current champions"

#: 위키 이름 → 보드 이름. **여기 없는 이름은 그대로 대조한다** — 대부분은 같다.
WIKI_BELT_ALIASES: dict[str, str] = {
    "WWE Women's Intercontinental Championship": "Women's Intercontinental Championship",
    "WWE Women's United States Championship": "Women's United States Championship",
    "WWE Evolve Men's Championship": "WWE Evolve Championship",
    "WWE Women's ID Championship": "WWE ID Women's Championship",
}
