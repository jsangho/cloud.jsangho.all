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

#: **응답 헤더(`ETag` + `Last-Modified`)를 계보로 인정하는 도메인** (2026-09-28).
#:
#: 계보가 없으면 그 글을 인용한 예측은 `unverifiable_corpus`(hold)로 걸려 `eligible`이
#: 되지 못한다. wwe.com은 위키와 달리 개정본 API가 없어, 계보를 얻을 자리가 우리가 본문을
#: 받아 온 그 응답의 헤더뿐이다.
#:
#: **위키는 여기 들어가지 않는다.** 그쪽 `Last-Modified`는 `page_touched`라 개정본
#: 시각이 아니고, 실측에서 21일 벌어져 있었다(`wikipedia_revision_metadata` 독스트링).
#: API가 답하지 못한 날 헤더로 물러서면 계보가 조용히 나빠진다.
#:
#: **무엇을 주장하고 무엇을 주장하지 않는가.** `Last-Modified`는 CDN 재생성 시각일 수
#: 있으므로(실측: wwe.com이 조회 19분 전 값을 줬다) "이 판본이 언제 쓰였는가"를 말하지
#: 못한다. 말할 수 있는 것은 **"늦어도 그때 존재했다"** 이고, 자격 판정이 묻는 것이
#: 정확히 그것이다 — 경기보다 앞서는가 · 예측보다 앞서는가. 발행 시각(`published_at`)은
#: 여전히 메타태그에서만 온다.
HEADER_LINEAGE_DOMAINS: frozenset[str] = WWE_OFFICIAL_DOMAINS
