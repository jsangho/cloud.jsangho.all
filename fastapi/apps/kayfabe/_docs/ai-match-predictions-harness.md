# HARNESS: PLE 승부예측 AI 멀티 에이전트 시스템

> **범위:** `fastapi/apps/kayfabe/` 중심. 수집·생성 능력은 `apps/ontology/`(허브)를 경유한다.
> 프론트 연동은 `www/components/ple-ai-scoreboard.tsx` · `www/components/ple/*`.
> **대상 저장소:** `cloud.jsangho.all`
> **작업 주체:** Claude Code
> **작성일:** 2026-08-04
> **상태:** 미착수 — 설계 계약만 확정. **§13-Q1(수집 대상의 적법성)이 정해지기 전에는 T3(수집 파이프라인)을 시작하지 않는다.**
> **상위 규칙:** [루트 CLAUDE.md](../../../../CLAUDE.md) · [fastapi/CLAUDE.md](../../../CLAUDE.md) · 참조 구현 [`kayfabe/adapter/outbound/repositories/wrestler_chat_repository.py`](../adapter/outbound/repositories/wrestler_chat_repository.py)

**한 줄 요약:** 지금 "AI 예측"은 **북메이커 배당이 낮은 쪽을 고르는 4줄짜리 규칙**이다(§1). 이것을 서사·오즈·루머를 각각 읽는 멀티 에이전트 합성으로 바꾸되, 이 저장소가 이미 갖춘 것(pgvector·bge-m3·Gemini 어댑터·크롤러)을 다시 만들지 않는다.

---

## 0. 이 문서를 읽는 방법

- **§2 델타**는 원본 지시서와 이 저장소의 실제 코드가 어긋나는 지점이다. **구현 전에 반드시 읽는다.** 지시서를 문자 그대로 실행하면 존재하지 않는 디렉터리 구조를 만들고, 이미 있는 벡터 DB 위에 새 벡터 DB를 얹고, 토폴로지 계약을 깨는 import를 쓰게 된다.
- **§3 결정사항**은 확정된 것이다. 재논의하지 말고 그대로 구현한다.
- **§4 금지사항**을 위반하는 코드는 작성 즉시 폐기 대상이다.
- **§10 작업 단위**는 순서대로 진행하며, 각 단위 종료 시 **§11 검증 기준**과 **§12 하네스 게이트**를 통과해야 다음으로 넘어간다.
- 판단이 필요한 지점이 생기면 **임의로 결정하지 말고 §13에 질문을 기록한 뒤 멈춘다.**

---

## 1. 현재 구현 실측 (2026-08-04, 코드 확인 결과)

> 추측이 아니라 아래 파일을 직접 읽고 정리한 것이다. 새 코드를 쓰기 전 이 표가 여전히 맞는지 확인한다.

| 구성요소 | 실제 위치 | 현재 동작 |
|---|---|---|
| **현재의 "AI 예측"** | `kayfabe/app/services/ple_ai.py` | `derive_ai_pick_from_card()` — **북메이커 소수 배당이 낮은 쪽**을 고른다. 단일전은 `left`/`right`, 다인전은 최저 배당의 인덱스 문자열. LLM도 외부 데이터도 쓰지 않는다 |
| 예측이 만들어지는 시점 | `kayfabe/adapter/outbound/pg/ple_events_pg_repository.py:282` | **카드 동기화 경로**에서 파생된다. 프론트가 정적 카드와 DB 지문이 다를 때 재동기화하면서 `ai_pick`·`ai_pick_name`을 채운다 |
| 채점 | 같은 파일 `:338` | `grade_ai_correct(ai_pick, winner_pick)` — 경기 결과 확정 시 `ai_correct` 갱신 |
| 저장 컬럼 | `kayfabe/adapter/outbound/orm/ple_orm.py` `ple_matches` | `ai_pick`(20자) · `ai_pick_name`(200자) · `ai_correct`(bool) **3개뿐이다. 근거·승률·리포트를 담을 자리가 없다** |
| 적중률 집계 | `ple_events_pg_repository.py:159` `get_ai_stats()` | `ai_correct IS NOT NULL` 행을 세어 `accuracy_percent`(소수 1자리)와 최근 기록 목록을 만든다. **이미 DB 집계다 — 화면의 적중률은 하드코딩이 아니다** |
| 프론트 위젯 | `www/components/ple-ai-scoreboard.tsx` | 이미 존재한다. `:171`에 `"북메이커 배당 favorite 기준 · 경기 결과 확정 시 자동 채점"` 문구 |
| **kayfabe의 RAG 선례** | `kayfabe/adapter/outbound/repositories/wrestler_chat_repository.py` | **이 작업의 참조 구현이다.** 검색(pgvector `<=>`)과 프롬프트 구성은 kayfabe가 소유하고, 텍스트 생성은 `ontology`의 `GeminiGenerationUseCase`에 위임한다. `TOP_K = 5` |
| 임베딩 | `core/matrix/vault_keymaker_secret_manager.py:114` `embed_text()` | **bge-m3**, `normalize_embeddings=True`, 인프로세스(Ollama 비의존). CPU 바운드라 호출 측에서 `asyncio.to_thread`로 넘긴다 |
| 벡터 저장 | `kayfabe/adapter/outbound/orm/wrestler_orm.py` | `pgvector.sqlalchemy.Vector(EMBEDDING_DIM)` 컬럼. **벡터 DB가 이미 있다** |
| 생성 어댑터 | `ontology/adapter/outbound/gemini_generator.py` | `google-genai`, 모델 `gemini-3.5-flash`, 스트리밍. 출력 포트 뒤에 은닉 |
| 크롤링·스크래핑 | `ontology/app/use_cases/crawler_interactor.py` · `scraper_interactor.py` | 허브에 이미 있다. `CrawlerUseCase.crawl(website, keyword)` → `CrawlResult`, `ScraperUseCase.scrape(CrawlResult)` → `ScrapeResult`(BeautifulSoup) |
| **`rag_interactor.py`** | `ontology/app/use_cases/rag_interactor.py` | **빈 파일(0줄)이다.** 이름만 있고 구현이 없다 — 여기에 무언가 있으리라 가정하지 않는다 |
| 토폴로지 계약 | `fastapi/.importlinter` | 계약 4개. **스포크 → 허브(ontology) import는 허용, 스포크 ↔ 스포크는 금지.** `wrestler_chat_repository.py`가 그 허용 방향을 실제로 쓴다 |
| 의존성 | 루트 `pyproject.toml` | `google-genai` · `beautifulsoup4` · `pgvector` · `sentence-transformers` **이미 있음**. Pinecone·Chroma·LangChain 에이전트 프레임워크는 **없다** |

---

## 2. 원본 지시서와 이 저장소의 델타 (구현 전 필독)

### D-1. 지시서의 디렉터리 구조는 이 저장소에 존재하지 않는다

지시서: `src/domain` · `src/use_cases` · `src/interface_adapters` · `src/frameworks_drivers`

이 저장소의 클린 아키텍처 층 이름은 다르다(루트 `CLAUDE.md` §0-3, `fastapi/CLAUDE.md` §2).

| 지시서 | 이 저장소 |
|---|---|
| `domain/` | `apps/kayfabe/domain/` (동일 개념) |
| `use_cases/` | `apps/kayfabe/app/use_cases/` + 포트는 `app/ports/` |
| `interface_adapters/controllers/` | `apps/kayfabe/adapter/inbound/api/v1/` |
| `interface_adapters/gateways/` | `apps/kayfabe/adapter/outbound/` |
| `frameworks_drivers/ai_agents/` | `apps/kayfabe/adapter/outbound/agents/` (어댑터다. 별도 최상위 층을 만들지 않는다) |
| `frameworks_drivers/database/` | `apps/kayfabe/adapter/outbound/pg/` · `orm/` |
| `frameworks_drivers/web/` | `www/` (별도 저장소 경로, Next.js) |

→ **`src/` 디렉터리를 새로 만들지 않는다.** import 경로는 앱명부터(`kayfabe.domain....`), core는 `jsangho.core.`로 시작한다.

### D-2. "스타 토폴로지"라는 말이 이 저장소에서는 다른 것을 가리킨다 — 가장 중요한 델타

지시서에서 스타 토폴로지는 **멀티 에이전트의 Hub-Spoke**를 뜻한다.
이 저장소에서 스타 토폴로지는 **앱 간 의존 관계**이고, `import-linter`가 CI에서 강제한다(`fastapi/CLAUDE.md` §6-2).

```
           [ontology] ← HUB (앱 레벨 허브)
          /     |     \
   [kayfabe] [titanic] [soccer] ...  ← SPOKE (앱 레벨 스포크)
```

두 개념이 겹치지 않게 아래를 확정한다.

- **에이전트 허브(코디네이터)는 `kayfabe` 안의 유스케이스다.** 앱이 아니다. `AiPredictionInteractor`가 그 자리다.
- **에이전트가 필요로 하는 외부 능력(LLM 생성·크롤링)은 `ontology` 허브를 경유한다.** kayfabe가 `ontology.app.ports.input.*`을 import하는 것은 계약상 허용된다(스포크 → 허브).
- **`ontology`가 `kayfabe`를 import하면 계약 위반이다.** 수집 파이프라인을 허브에 두더라도, "이번 PLE 대진표를 안다"는 지식은 허브로 올리지 않는다.

참조 구현이 이미 이 구조를 쓴다 — `wrestler_chat_repository.py`의 주석이 그 이유를 적어 두었다: *"검색과 프롬프트 구성은 kayfabe가 직접 소유하고, 실제 텍스트 생성은 ontology(허브)에 위임한다."*

### D-3. 벡터 DB를 새로 도입하지 않는다

지시서: "벡터 DB(Pinecone/Chroma 등)에 임베딩"

이 저장소에는 **pgvector + bge-m3가 이미 돌고 있다**(§1). `wrestlers.embedding`은 `Vector(EMBEDDING_DIM)` 컬럼이고 코사인(`<=>`) 검색이 실제로 쓰인다.

→ 새 벡터 스토어를 붙이는 것은 요청받지 않은 의존성 추가다(루트 `CLAUDE.md` §2). **pgvector를 쓴다.** 새 지식(뉴스·서사 요약)은 새 테이블에 같은 차원의 `embedding` 컬럼으로 넣는다.

### D-4. 프론트 위젯은 이미 있고, 적중률도 이미 실시간이다

지시서: "적중률(68.5%)을 API를 통해 실시간 연동되도록 **설계**합니다"

실측(§1): `ple-ai-scoreboard.tsx`가 이미 있고, 적중률은 `get_ai_stats()`가 DB에서 집계해 내려준다. **68.5%는 하드코딩된 값이 아니라 그 시점의 집계 결과다.**

→ 이 단계에서 실제로 할 일은 **문구 교체 한 줄과, 근거 리포트를 여는 새 UI**뿐이다. 통계 연동을 처음부터 만들지 않는다.

### D-5. 예측 결과를 담을 자리가 지금 없다

`ple_matches`에는 `ai_pick` · `ai_pick_name` · `ai_correct` 세 컬럼뿐이다. 승률(%)·근거·에이전트별 리포트·출처를 넣을 자리가 없다.

→ **새 테이블이 필요하다**(§5). 기존 3컬럼은 지우지 않는다 — 적중률 집계(`get_ai_stats`)와 화면이 그 컬럼을 읽고 있고, 폴백 경로로도 쓴다(§3-D5).

### D-6. 수집 대상의 적법성은 코드보다 먼저 결정할 문제다

지시서: "PWInsider, Wrestling Observer, 소셜 미디어(X/Twitter 저널리스트) … 수집"

- **PWInsider·Wrestling Observer(F4W)의 핵심 콘텐츠는 유료 구독**이다. 구독 콘텐츠를 긁어 서버에 저장·재가공하면 이용약관 위반이고 저작권 문제도 생긴다.
- **X/Twitter는 무단 스크래핑을 약관으로 금지**하고 공식 API는 유료 등급이다.
- 이 저장소의 크롤러(`ontology/crawler_interactor.py`)에는 robots.txt 확인 로직이 없다.

→ **§13-Q1이 결정되기 전에는 T3을 시작하지 않는다.** 기본 입장은 이렇게 잡는다: **공개 RSS·공식 API·robots.txt가 허용하는 공개 페이지만** 수집하고, 유료 구독 콘텐츠는 **본문을 저장하지 않는다**(제목·링크·공개 요약까지). 배당은 공개 배당 페이지 또는 제휴 API를 쓴다.

### D-7. 에이전트를 카드 동기화 경로에 넣으면 비용이 트래픽에 비례한다

현재 `ai_pick`은 **프론트가 페이지에 들어와 카드 지문이 어긋날 때마다** 파생된다(§1). 여기에 LLM 3~4회 호출을 얹으면, 사용자가 PLE 페이지를 열 때마다 경기 수 × 에이전트 수만큼 호출이 발생한다.

→ **예측 생성과 조회를 분리한다**(§3-D1). 페이지 진입은 **저장된 예측을 읽기만** 한다.

### D-8. 커스텀 예외 계층을 만들지 않는다 · 포트는 `ABC`다

이 저장소에는 전용 `AppError` 계층이 없다(루트 `CLAUDE.md`). 도메인·포트는 평범한 `Exception` 서브클래스를 던지고, **라우터에서만 `HTTPException`으로 변환**한다.
포트는 `Protocol`이 아니라 **`ABC` + `@abstractmethod`** 다 — `lion_king`·`ontology`의 기존 포트가 전부 그렇다.

---

## 3. 확정된 결정사항 (변경 금지)

### D-1. 생성은 명시적 트리거, 조회는 저장된 값
예측 생성은 **관리자 엔드포인트 또는 배치**로만 돈다. 사용자 페이지 진입은 LLM을 부르지 않는다(§2-D7).

### D-2. 에이전트는 출력 포트 뒤에 숨는다
`AiPredictionInteractor`(허브)는 Gemini도 크롤러도 모른다. 포트가 돌려주는 것은 **엔진 중립 DTO**(`AgentReport`)다. 에이전트를 늘리거나 모델을 바꿔도 유스케이스는 그대로다.

### D-3. 합성 규칙은 `domain`의 순수 로직이다
에이전트 리포트 3건 → 최종 pick·승률 변환은 프레임워크·LLM·HTTP를 모르는 순수 함수다. **고정 리포트 픽스처만으로 테스트가 돌아야 한다**(LLM 호출 없이).

### D-4. 승률은 `0.0 ~ 1.0` float으로 저장하고 표시할 때만 %로 바꾼다
DB에 `68.5`를 넣지 않는다. 반올림은 화면에서 한 번만 한다.

### D-5. 에이전트가 실패하면 기존 북메이커 파생으로 강등한다
LLM·수집이 죽어도 화면은 예측을 보여줘야 한다. 폴백을 쓴 예측은 **그 사실을 응답에 담아**(`source: "bookmaker_fallback"`) 화면이 구분해 표시한다. 조용히 같은 얼굴로 내보내지 않는다.

### D-6. 근거 없는 예측은 만들지 않는다
합성 결과에는 **에이전트별 리포트와 출처 URL**이 함께 저장된다. 리포트가 하나도 없으면 예측을 저장하지 않고 실패로 남긴다 — "AI가 골랐다"는 말만 있고 근거가 없는 상태를 만들지 않는다.

### D-7. 검색은 kayfabe가 소유하고 생성은 ontology에 위임한다
`wrestler_chat_repository.py`와 같은 구조를 따른다(§2-D2). 새 패턴을 발명하지 않는다.

### D-8. 기존 `ai_pick` 컬럼과 적중률 집계는 유지한다
`get_ai_stats()`의 정의를 바꾸면 지금까지 쌓인 적중 기록의 의미가 소급 변경된다. 새 예측도 **같은 컬럼에 함께 반영**해 지표 연속성을 지킨다(§13-Q4에서 재확인).

### D-9. 임베딩은 `embed_text()`를 쓰고 `asyncio.to_thread`로 넘긴다
bge-m3는 CPU 바운드다. `async def` 안에서 그냥 부르면 이벤트 루프가 멈춘다(`fastapi/CLAUDE.md` §9).

---

## 4. 금지사항

위반하는 코드는 작성 즉시 폐기 대상이다.

1. `src/` 등 지시서의 가상 디렉터리 생성 (§2-D1)
2. `ontology`가 `kayfabe`를 import — 토폴로지 계약 위반 (§2-D2)
3. 스포크 ↔ 스포크 직접 import (`kayfabe` ↔ `soccer` 등)
4. Pinecone·Chroma·새 에이전트 프레임워크 도입 (§2-D3)
5. `domain/`에서 `google.genai`·`sqlalchemy`·`fastapi`·`httpx` import
6. 도메인·포트에서 `HTTPException` 발생
7. 사용자 페이지 진입 경로(카드 동기화)에서 LLM 호출 (§2-D7)
8. 유료 구독 기사 본문 저장·재배포 (§2-D6)
9. robots.txt·ToS 확인 없는 신규 도메인 수집
10. LLM 원본 응답(JSON 전문)을 그대로 API로 흘려보내기
11. 실패를 조용히 삼키고 임의 승률 반환 — 판독 실패와 "우열을 못 가림"은 다른 상태다
12. 승률·적중률을 소수점 이하까지 화면 문구에 하드코딩

---

## 5. 도메인 모델 (핵심 산출물)

```
AgentPrediction                   # 애그리거트 루트
├── event_slug    : str
├── match_key     : str           # ple_matches.match_key와 같은 값
├── pick          : str           # "left" | "right" | 다인전 인덱스 문자열
├── pick_name     : str
├── win_probability : float       # 0.0 ~ 1.0
├── confidence    : float         # 0.0 ~ 1.0 (합의 정도)
├── rationale     : str           # 한국어 합성 근거 3~5문장
├── source        : PredictionSource   # agents | bookmaker_fallback
├── reports       : list[AgentReport]
└── generated_at  : datetime

AgentReport
├── agent      : AgentKind        # storyline | odds | rumor
├── pick       : str | None       # 의견 없음이면 None
├── weight     : float            # 0.0 ~ 1.0, 이 에이전트의 확신
├── summary    : str              # 근거 요약 (한국어)
└── sources    : list[str]        # 참조 URL. 빈 목록이면 "출처 없음"으로 표시
```

### 에이전트별 역할 (§2-D2의 Spoke)

| 에이전트 | 입력 | 판단 근거 | 산출 |
|---|---|---|---|
| **Storyline Analyst** | 대진 + RAG 검색 결과(최근 서사 요약) | 대립 각본의 진행 방향, 복수극·타이틀 명분, 푸시 흐름 | pick + 근거 요약 |
| **Odds Scout** | 카드의 `bookmakerDecimal` + 공개 배당 변동 | 배당의 절대 수준과 **변동 방향** | pick + 확신도 |
| **Rumor Scout** | 공개 소스의 부상·복귀·계약 만료 소식 | 출전 가능 여부, 이적·복귀 타이밍 | pick(또는 의견 없음) + 출처 |

### 합성 규칙 (순수 함수, §3-D3)

- 각 리포트의 `weight`를 정규화해 pick별 가중 득표를 만든다.
- 최다 득표 pick을 고르고, 그 득표 비중을 `win_probability`로 쓴다.
- `confidence`는 **합의 정도**다 — 세 에이전트가 같은 쪽이면 높고, 갈리면 낮다. 승률과 다른 축이다.
  구현(T1)에서 `합의도 × 응답률`로 확정했다. 응답률을 곱하는 이유는 **셋 중 하나만 답했을 때
  합의도가 1.0이 되어 "확신 100%"로 보이는 문제** 때문이다. 그래서 `synthesize()`는 리포트
  목록 길이가 아니라 **물어본 에이전트 수(`agent_count`)** 를 따로 받는다 — 실패한 에이전트는
  목록에서 아예 빠지기 때문이다.
- 리포트가 0건이면 `ReportsUnavailableError`를 던진다(§3-D6). 임의 0.5를 채우지 않는다.

---

## 6. 레이어 배치 (`fastapi/CLAUDE.md` §4 네이밍 적용)

```
apps/kayfabe/
├── domain/
│   ├── entities/agent_prediction.py        # AgentPrediction · AgentReport · AgentKind
│   └── services/prediction_synthesis.py    # 리포트 → 최종 pick·승률 (순수 함수)
├── app/
│   ├── dtos/agent_prediction_dto.py        # GeneratePredictionCommand · AgentPredictionDto
│   ├── ports/input/ai_prediction_use_case.py       # AiPredictionUseCase (ABC)
│   ├── ports/output/
│   │   ├── storyline_analyst_port.py       # StorylineAnalystPort (ABC)
│   │   ├── odds_scout_port.py              # OddsScoutPort (ABC)
│   │   ├── rumor_scout_port.py             # RumorScoutPort (ABC)
│   │   ├── prediction_knowledge_port.py    # RAG 검색 (pgvector)
│   │   └── agent_prediction_repository.py  # 저장·조회
│   └── use_cases/ai_prediction_interactor.py       # ★ 코디네이터(Hub)
├── adapter/
│   ├── inbound/api/v1/ai_prediction_router.py
│   ├── inbound/api/schemas/ai_prediction_schema.py
│   └── outbound/
│       ├── agents/
│       │   ├── storyline_gemini_agent.py   # ontology GeminiGenerationUseCase 경유
│       │   ├── odds_scout_agent.py
│       │   └── rumor_scout_agent.py
│       ├── repositories/prediction_knowledge_repository.py   # pgvector <=> 검색
│       ├── orm/agent_prediction_orm.py     # 새 테이블 2개 (§5)
│       └── pg/agent_prediction_pg_repository.py
├── dependencies/ai_prediction_provider.py
└── tests/test_prediction_synthesis.py · test_ai_prediction_interactor.py · test_ai_prediction_router.py
```

**수집(ingestion)은 `ontology` 쪽에 둔다** — 크롤러·스크래퍼가 이미 거기 있고, 특정 앱의 지식이 아니기 때문이다. kayfabe는 **검색만** 한다(§2-D2).

### DB 엔티티 (`_claude/ENTITY_RULE.md` 준수)

| 테이블 | 용도 | 비고 |
|---|---|---|
| `ple_agent_predictions` | 경기별 최종 예측 | PK `id: int` auto-increment. `(event_id, match_key)` 유니크 |
| `ple_agent_reports` | 에이전트별 리포트 | FK `prediction_id` |
| `ple_knowledge_chunks` | RAG 지식 청크 | `embedding Vector(EMBEDDING_DIM)` · `source_url` · `published_at` |

Alembic 마이그레이션은 자동 생성 후 손대지 않는다(루트 `CLAUDE.md` 주의사항).

---

## 7. API 계약

### 7.1 `GET /api/ple_events/{slug}/ai-predictions` — 조회 (인증 불필요)

**저장된 예측만 읽는다. LLM을 부르지 않는다**(§3-D1).

```json
{
  "items": [
    {
      "matchKey": "ss26-n2-whc",
      "pick": "left",
      "pickName": "Roman Reigns",
      "winProbability": 0.78,
      "confidence": 0.67,
      "rationale": "세 분석 중 둘이 로만 레인즈를 골랐습니다. …",
      "source": "agents",
      "generatedAt": "2026-08-01T09:00:00",
      "reports": [
        {
          "agent": "storyline",
          "pick": "left",
          "weight": 0.8,
          "summary": "타이틀 명분이 …",
          "sources": ["https://www.wwe.com/..."]
        }
      ]
    }
  ]
}
```

### 7.2 `POST /api/ple_events/{slug}/ai-predictions` — 생성 (관리자 전용)

`Depends(RoleChecker(UserRole.ADMIN))`. 비용이 드는 경로라 권한을 건다.

```json
{ "matchKeys": ["ss26-n2-whc"], "force": false }
```

- `matchKeys` 생략 시 그 이벤트의 **미생성 경기 전부**. `force: true`면 기존 예측을 다시 만든다.
- 응답은 생성 건수와 실패 건수의 요약이다. 개별 실패는 전체를 실패시키지 않는다.

### 7.3 기존 엔드포인트

`GET /api/ple_events/ai-stats`(적중률)는 **그대로 둔다**(§3-D8).

---

## 8. 예외 → HTTP 상태 코드 매핑

| 상황 | 발생 지점 | 예외 | 상태 | 사용자 문구 |
|---|---|---|---|---|
| 없는 이벤트·경기 | 리포지토리 | `MatchNotFoundError` | 404 | 경기를 찾을 수 없습니다. |
| 리포트 0건 | 합성 함수 | `ReportsUnavailableError` | 503 | 분석 근거를 모으지 못했습니다. |
| LLM 오류·한도 초과 | 에이전트 어댑터 | `AgentUnavailableError` | 503 | AI 분석을 잠시 사용할 수 없습니다. |
| 수집 대상 응답 실패 | 수집 어댑터 | `KnowledgeSourceUnavailableError` | 503 | (생성 경로에서만. 조회는 저장분을 그대로 준다) |
| 권한 없음 | `RoleChecker` | `HTTPException` | 403 | (기존 문구) |

**원칙:** 모델 이름·프롬프트·수집 대상 URL의 내부 사정은 `detail`에 노출하지 않고 로그에만 남긴다.

---

## 9. 환경 변수

기존 키로 충분하다. **새로 추가할 키가 없다.**

```bash
GEMINI_API_KEY=        # 이미 있음 — 생성은 ontology 허브가 담당
DATABASE_URL=          # 이미 있음 — pgvector 포함
```

수집 대상이 공식 API를 요구하는 것으로 결정되면(§13-Q1) 그때 키를 추가하고 `.env.example`에도 반영한다.

---

## 10. 작업 단위

각 단위가 끝날 때마다 §12 하네스 게이트를 통과시킨다.

| # | 작업 | 산출물 | 완료 판정 |
|---|---|---|---|
| **T0** | §13-Q1·Q2 결정 | 이 문서 §13 갱신 | 수집 대상과 합성 가중치가 확정됐다. **미결이면 T3에서 멈춘다** |
| ~~**T1**~~ | ~~도메인 — 엔티티 + 합성 함수~~ | `agent_prediction.py` · `prediction_synthesis.py` | **완료 (2026-08-04)** — 픽스처 테스트 23건 통과, LLM 호출 0회 |
| **T2** | 포트 정의 | `ports/input/*` · `ports/output/*` | 전부 `ABC`. 구현체 없이 import 된다 |
| **T3** | 지식 적재 (RAG) | `ontology` 수집 + `ple_knowledge_chunks` | 공개 소스만. `embed_text` + pgvector 저장. **Q1 결정 후 착수** |
| **T4** | 검색 리포지토리 | `prediction_knowledge_repository.py` | `<=>` 코사인 top-k. `wrestler_chat_repository` 패턴 |
| **T5** | 에이전트 3종 | `adapter/outbound/agents/*` | 벤더 타입이 포트 시그니처에 새지 않음. 생성은 ontology 경유 |
| **T6** | 코디네이터 유스케이스 | `ai_prediction_interactor.py` | 포트 페이크로 테스트. **한 에이전트가 실패해도 나머지로 합성**됨을 검증 |
| **T7** | 영속화 + 라우터 | ORM·마이그레이션·라우터·프로바이더 | `/docs` 노출. 관리자 권한 가드 동작 |
| **T8** | 프론트 연동 | `ple-ai-scoreboard.tsx` 문구 · 리포트 모달 | §2-D4 참조 — **문구 교체와 모달만**. 통계 연동은 이미 있다 |

---

## 11. 검증 기준 (Definition of Done)

1. PLE 페이지 진입 시 **LLM 호출 0회** (네트워크·로그로 확인). 저장된 예측만 표시된다
2. 비관리자가 `POST .../ai-predictions` 호출 → `403`
3. 에이전트 하나를 강제로 실패시켜도 나머지 둘로 예측이 만들어지고, 리포트에 실패가 드러난다
4. 세 에이전트 전부 실패 → 북메이커 폴백으로 예측이 나오고 `source: "bookmaker_fallback"`이 응답에 있다
5. 리포트 0건 상황에서 임의 승률 0.5가 저장되지 않는다 (503)
6. 응답 어디에도 모델 이름·프롬프트 원문·내부 URL이 없다
7. 화면 문구에 `"북메이커 배당 favorite 기준"`이 남아 있지 않다
8. 적중률 집계(`get_ai_stats`)가 기존과 같은 정의로 계속 동작한다
9. `lint-imports` 계약 4건 KEPT — 특히 `ontology → kayfabe` import가 없다
10. §12 게이트 전부 통과

---

## 12. 하네스 게이트 (코드 작성 후 필수)

```bash
uv run ruff check fastapi/ --config pyproject.toml --fix
uv run ruff format fastapi/ --config pyproject.toml
cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports
cd fastapi && PYTHONPATH=apps uv run pytest apps/kayfabe/tests -q
```

프론트를 건드렸다면:

```bash
cd www && pnpm lint && pnpm type-check && pnpm format
```

> `uv run` 없이 실행하면 PATH상 다른 Python이 잡혀 잘못된 버전이 돌거나 앱 패키지를 못 찾는다.

---

## 13. 미해결 질문 (구현 중 발견 시 여기에 기록하고 중단)

- [ ] **Q1. 수집 대상의 적법 범위** — PWInsider·Wrestling Observer는 유료 구독, X는 약관·유료 API다(§2-D6). 어디까지 수집할지 확정해야 T3을 시작할 수 있다. 제안: **공개 RSS·공식 API·robots.txt 허용 페이지만, 유료 콘텐츠는 본문 미저장.**
- [ ] **Q2. 합성 가중치** — 서사·오즈·루머의 기본 가중치를 같게 둘지, 오즈에 더 줄지. 적중률로 사후 조정할지. **근거 없는 숫자를 코드에 박기 전에 정한다.**
- [ ] **Q3. 생성 트리거** — 관리자 수동 호출만으로 갈지, PLE 개최 D-7/D-1 배치를 걸지. 배치라면 스케줄러가 지금 없다(별도 작업).
- [ ] **Q4. 기존 지표와의 연속성** — 새 예측도 `ple_matches.ai_pick`에 함께 반영하면 적중률이 이어지지만, **규칙 기반 시절 기록과 멀티 에이전트 기록이 한 숫자로 섞인다.** 분리해서 보여줄지.
- [ ] **Q5. 비용 상한** — 경기당 3회 호출 × 이벤트당 12경기 = 이벤트 1회 36회. 월 상한과 초과 시 동작(중단/폴백)을 정한다.
- [ ] **Q6. 지식 신선도** — `ple_knowledge_chunks`를 언제 지울지. 6개월 보관이면 그 이후 청크의 처리(삭제/아카이브)를 정한다.
- [ ] **Q7. 문서 위치** — 이 문서는 사용자 지정 경로(`apps/kayfabe/_docs/`)에 있다. 루트 `CLAUDE.md` §0-4는 백엔드 문서를 `fastapi/_docs/`로 안내하지만, `apps/kayfabe/_docs/CLAUDE.md` 선례가 이미 있어 앱 전용 문서는 앱 아래 두는 것으로 보인다. 규칙을 §0-4에 명시할지.

---

## 14. 작업 로그

| 날짜 | 단위 | 내용 | 검증 |
|---|---|---|---|
| 2026-08-04 | T1 | 도메인 엔티티(`AgentPrediction`·`AgentReport`·`AgentKind`·`PredictionSource`)와 합성 순수 함수(`synthesize`) 구현. **에이전트별 기본 가중치는 넣지 않았다** — §13-Q2 미결이라 근거 없는 숫자를 코드에 남기지 않는다. `confidence`는 합의도 × 응답률로 정의했다(§5 보강: 셋 중 하나만 답했을 때 확신 100%가 되는 문제) | `pytest apps/kayfabe/tests/domain` 23 passed · ruff·lint-imports 통과 · LLM/DB 호출 0회 |
| 2026-08-04 | — | 원본 지시서를 이 저장소 맥락으로 옮겨 하네스 계약 작성. `ple_ai.py`·`ple_events_pg_repository.py`·`wrestler_chat_repository.py`·`ple_orm.py`·`ple-ai-scoreboard.tsx`·`.importlinter`·`ontology` 유스케이스 목록을 실측해 델타 8건(§2)·미해결 질문 7건(§13) 도출 | 문서만 작성, 코드 변경 없음 |
