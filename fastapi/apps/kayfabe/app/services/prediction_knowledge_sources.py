"""수집 허용 도메인 목록 — 하네스 §3-D10 (Q1 결정).

**금지 목록이 아니라 허용 목록이다.** 여기에 없는 주소로는 요청 자체를 보내지 않는다.
새 도메인을 넣을 때는 robots.txt와 이용약관을 먼저 확인하고, 왜 넣는지 주석으로 남긴다.

**2026-09-30에 레슬링 전문 매체를 넣었다.** 그전까지는 wwe.com과 위키뿐이었는데, 둘 다
백과·로스터 문서라 부상·복귀·계약 만료가 실릴 자리가 아니다. 루머 에이전트가 거의 항상
"의견 없음"을 낸 것은 고장이 아니라 그 구성의 결과였다. 아래 도메인은 전부
**robots.txt를 실제로 받아 확인**했고, 확인한 내용을 각 항목에 적었다.

여기에 **없는 것**도 그대로 결정이다 — 아래 `_EXCLUDED` 참조.
"""

from __future__ import annotations

#: WWE 공식. 카드·결과·부상 발표의 1차 출처다.
WWE_OFFICIAL_DOMAINS = frozenset({"www.wwe.com", "wwe.com"})

#: 위키피디아. 선수 이력·과거 대회 결과의 공개 백과 출처.
WIKIPEDIA_DOMAINS = frozenset({"en.wikipedia.org", "ko.wikipedia.org"})

#: **자체 취재를 하는 매체** (2026-09-30). 남의 기사를 옮기는 것이 아니라 직접 묻고
#: 쓰는 곳이고, 루머 축이 찾는 사실(부상·복귀·계약·결장)이 최초로 실리는 자리다.
#:
#: robots.txt 실측 (2026-09-30):
#: * `pwinsider.com` — `User-agent: * / Allow: /`. 막는 경로 없음.
#: * `www.fightful.com` — `User-agent: * / Disallow:` (빈 값 = 전체 허용).
#: * `www.pwtorch.com` — robots.txt가 404다. 규격상 **전면 허용**이고, `pwtorch.com`은
#:   www로 301한다. 목록에는 리다이렉트 **목적지만** 넣는다 — 출발지를 넣어도
#:   본문 fetch가 따라가므로 실익이 없고, 계보 대조는 목적지 기준으로 돈다.
#: * `www.postwrestling.com` — 기사 경로 허용(`/search/`·쿼리 문자열만 차단).
REPORTING_DOMAINS = frozenset(
    {
        "pwinsider.com",
        "www.fightful.com",
        "www.pwtorch.com",
        "www.postwrestling.com",
    }
)

#: **보도를 종합하는 매체** (2026-09-30). 위 매체의 특종을 받아 정리하는 쪽이라 사실의
#: 출처는 아니지만, 한 건의 소식이 여러 곳에 실리면 루머 축이 그 사실을 놓칠 확률이
#: 줄어든다. 자체 취재 매체와 **등급을 나눠 둔 이유**는 나중에 무게를 달리 주거나
#: 한쪽만 끄기 위해서다 — 지금은 둘 다 같은 자격으로 수집된다.
#:
#: robots.txt 실측 (2026-09-30):
#: * `www.wrestlinginc.com` — 기사 경로 허용(`/wp-admin/`·`/search/` 등만 차단).
#: * `wrestletalk.com` — `User-agent: * / Disallow:` (전체 허용).
AGGREGATOR_DOMAINS = frozenset(
    {
        "www.wrestlinginc.com",
        "wrestletalk.com",
    }
)

ALLOWED_DOMAINS: frozenset[str] = (
    WWE_OFFICIAL_DOMAINS | WIKIPEDIA_DOMAINS | REPORTING_DOMAINS | AGGREGATOR_DOMAINS
)

#: **넣지 않기로 한 곳과 그 이유** (2026-09-30). 목록이 아니라 기록이다 — 코드가 읽지
#: 않으므로 값이 아니라 주석에 가깝지만, 다음 사람이 "왜 f4w가 없지"를 다시 조사하는
#: 일을 막으려면 답이 코드 옆에 있어야 한다.
#:
#: * `www.f4wonline.com` (Wrestling Observer) — robots.txt는 `Allow: /`지만
#:   **`Content-Signal: search=yes, ai-train=no, use=reference`** 를 함께 선언한다.
#:   `use=reference`는 "참조로만 쓰라"는 뜻이고, 우리가 하는 일은 본문을 잘라 저장했다가
#:   프롬프트에 넣는 것이라 그 선언과 맞지 않는다. 레슬링 저널리즘에서 가장 인용이
#:   많은 곳이지만 **그래서 더 선언을 지킨다.** 제목·링크만 다루는 경로가 생기면
#:   그때 다시 본다.
#: * `www.sescoops.com` — robots.txt는 허용이나 실제 요청이 **403**이다(Cloudflare가
#:   우리 UA를 막는다). 우회는 하지 않는다.
#: * `www.411mania.com` — Cloudflare 챌린지 페이지만 돌아온다. 위와 같은 이유로 제외.
#: * `www.cagematch.net` — `Crawl-delay: 527`(9분)에 `/database/`·`/db/`가 차단이다.
#:   뉴스가 아니라 경기 데이터베이스라 루머 축이 찾는 것도 여기 없다.
#: * `ringsidenews.com` — robots.txt는 허용이지만 자체 취재 비중이 낮고 제목 과장이
#:   잦다. **공신력을 기준으로 뺐다** — 기술적으로 가능한 것과 실어도 되는 것은 다르다.
#: * X(트위터) — 스크래핑 금지(§4-8·§4-9). 선수 본인 발표가 가장 먼저 올라오는 곳이라
#:   아깝지만 이 결정은 그대로다.
_EXCLUDED = (
    "www.f4wonline.com",
    "www.sescoops.com",
    "www.411mania.com",
    "www.cagematch.net",
    "ringsidenews.com",
)

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
#: **레슬링 매체도 여기 들어가지 않는다** (2026-09-30). 넣어도 계보가 서지 않기
#: 때문이다 — 실측에서 **둘 중 하나씩만** 준다:
#:
#:     www.wrestlinginc.com   Last-Modified 있음, ETag 없음
#:     wrestletalk.com        ETag 있음, Last-Modified 없음
#:     www.fightful.com       Last-Modified 있음, ETag 없음
#:     pwinsider.com          둘 다 없음
#:
#: `_revision_from_response`는 둘을 **모두** 요구하므로 어느 쪽도 통과하지 못한다.
#: 그래서 이 매체들의 계보는 아래 `COLLECTION_LINEAGE_DOMAINS`가 맡는다.
HEADER_LINEAGE_DOMAINS: frozenset[str] = WWE_OFFICIAL_DOMAINS

#: **수집 시각을 계보로 인정하는 도메인** (2026-09-30 · 하네스 §13-Q8 결정).
#:
#: 위 매체들은 판본을 스스로 밝히지 않는다. 남은 후보는 둘이었다.
#:
#: * `article:published_time` — 이들은 위키가 끝내 못 주던 발행 시각을 정확히 준다
#:   (실측: wrestlinginc `2026-09-15T17:37:42`, wrestletalk `2026-09-26T00:12:35`).
#:   **그런데도 계보로 쓰지 않는다.** 같은 URL이 경기 뒤에 결과로 갱신돼도 이 값은
#:   그대로여서, 경기 후 본문이 경기 전 증거로 통과한다 — 게이트가 막으려던 그 일이다.
#: * **수집 시각** — "이 본문을 우리가 그때 쥐고 있었다." 본문 해시가 함께 남아
#:   자기 증명이 되고, 발행 뒤의 조용한 수정에 흔들리지 않는다.
#:
#: 둘째를 골랐다. 틀리는 방향이 안전하기 때문이다 — 수집이 늦으면 멀쩡한 기사도
#: 걸리지만, 통과시키면 안 될 것을 통과시키지는 않는다.
#:
#: **운영 규칙이 하나 생긴다: 대회 전에 수집해야 그 기사가 증거로 쓰인다.**
#: 대회가 끝난 뒤 수집한 기사는 `unverifiable_corpus`로 걸리고, 그것이 맞다.
#:
#: 위키와 wwe.com은 여기 들어가지 않는다 — 각각 개정본 API와 응답 헤더라는 **더 강한
#: 주장**을 이미 갖고 있고, 약한 쪽으로 물러설 이유가 없다.
COLLECTION_LINEAGE_DOMAINS: frozenset[str] = REPORTING_DOMAINS | AGGREGATOR_DOMAINS
