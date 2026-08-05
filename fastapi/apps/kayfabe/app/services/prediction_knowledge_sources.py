"""수집 허용 도메인 목록 — 하네스 §3-D10 (Q1 결정).

**금지 목록이 아니라 허용 목록이다.** 여기에 없는 주소로는 요청 자체를 보내지 않는다.
새 도메인을 넣을 때는 robots.txt와 이용약관을 먼저 확인하고, 왜 넣는지 주석으로 남긴다.

여기에 **없는 것**이 이 결정의 핵심이다.
- 유료 구독 매체(PWInsider·Wrestling Observer 등): 본문을 저장하지 않기로 했으므로
  수집 대상이 아니다. 제목·링크가 필요해지면 그때 본문 저장 없이 다루는 경로를 따로 만든다.
- X(트위터): 스크래핑 금지(§4-8·§4-9).

대가는 알고 받는다 — 백스테이지 루머의 깊이를 포기했다. 루머 에이전트가 "의견 없음"을
자주 내는 것이 고장이 아니라 이 결정의 결과다(§13-Q1).
"""

from __future__ import annotations

#: WWE 공식. 카드·결과·부상 발표의 1차 출처다.
WWE_OFFICIAL_DOMAINS = frozenset({"www.wwe.com", "wwe.com"})

#: 위키피디아. 선수 이력·과거 대회 결과의 공개 백과 출처.
WIKIPEDIA_DOMAINS = frozenset({"en.wikipedia.org", "ko.wikipedia.org"})

ALLOWED_DOMAINS: frozenset[str] = WWE_OFFICIAL_DOMAINS | WIKIPEDIA_DOMAINS
