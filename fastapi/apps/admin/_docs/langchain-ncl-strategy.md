# LANGCHAIN-NCL-STRATEGY.md

NCL(Norwegian Cruise Line) 사례([langchain-harness](./langchain-harness.md) 참고)를 이 리포에 적용하기 위한 전략 문서. 코드는 아직 없다 — 구현은 별도 요청 시 진행한다.

---

## 0. 사례 요약

NCL은 LangChain을 이용해 고객이 이상적인 크루즈 여행을 계획하도록 돕는 AI 어시스턴트를 개발했다. 고객의 선호도와 탐색 기록을 기반으로 맞춤형 추천을 제공하며, LangChain의 사용자 맞춤형 프롬프팅·파인튜닝 기능을 통해 실시간으로 변화하는 고객 요구에 대응한다.

---

## 1. 이 리포에 적용할 구조

Morningstar 사례와 달리, 이 리포에는 재사용할 기존 파이프라인(PDF/Neo4j 같은)이 없다. 고객 선호도·탐색 기록이라는 **상태가 대화 중 계속 갱신**된다는 점이 핵심이라, 단발성 체인보다 LangGraph의 상태 그래프가 더 맞는 형태다.

```
고객 선호도 프로필 (미정: 저장 위치)     탐색 기록 / 대화 이력 (미정: 세션 저장소)
         │                                        │
         ▼                                        ▼
              LangGraph 상태(State) — 선호도 + 대화 컨텍스트
                          │
                          ▼
        크루즈 일정 조회 Tool (미정: 내부 카탈로그 or 외부 API)
                          │
                          ▼
        선호도 재랭킹 노드 (탐색 기록 반영 → 추천 재정렬)
                          │
                          ▼
     ChatGoogleGenerativeAI (langchain-google-genai) + 프롬프트 템플릿
                          │
                          ▼
              맞춤형 크루즈 여행 추천 응답
```

### 1-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| 상태·흐름 관리 | **LangGraph** — 선호도/탐색 기록이 대화 중 갱신되므로 단일 체인이 아니라 상태 그래프(node: 조회 → 재랭킹 → 응답 생성)로 구성 |
| LLM 연동 | **langchain-google-genai + Keymaker** — `vault_keymaker_secret_manager.get_keymaker()`로 키 조회, 호출은 `ChatGoogleGenerativeAI`로 감싸 LangGraph 노드에서 사용 |

### 1-2. 미정 사항 (구현 전 재확인 필요)

- **소속 앱** — 이 리포에는 크루즈/여행/고객 선호도 도메인 앱이 아직 없다(`fastapi/apps/`: admin·auth·heyman·kayfabe·lion_king·ontology·sample·soccer·superstar·titanic). 신규 앱을 만들지, 기존 앱에 얹을지부터 결정 필요 — §0-3 경로 규칙상 앱명이 정해져야 패키지 경로를 확정할 수 있다.
- **선호도 프로필 저장소** — 회원 도메인(현재 auth 앱은 인증만 담당)에 선호도 필드가 없다. 신규 테이블/앱 필요 여부 결정.
- **탐색 기록(세션) 저장 방식** — Redis(이미 의존성 있음)로 최근 세션만 유지할지, PG에 영구 저장할지 미정.
- **크루즈 일정 데이터 소스** — 내부 카탈로그가 없으므로, 실제 연동 전에는 Tool을 플레이스홀더(mock)로 구현하거나 이 부분은 스코프에서 제외.
- LangGraph 체크포인터(대화 재개용) 사용 여부 — `langgraph-checkpoint`는 이미 설치돼 있으나 저장소(in-memory vs PG)는 미정.

---

## 2. 레이어 배치 (fastapi/CLAUDE.md 규칙 적용)

앱명이 미정이므로 아래는 `<app>`으로 표기한다 — 구현 전 실제 앱명으로 치환.

| 레이어 | 파일(예정) | 역할 |
|--------|-----------|------|
| `app/ports/input` | `cruise_recommendation_use_case.py` | 맞춤형 추천 조회 UseCase(Protocol) |
| `app/use_cases` | `cruise_recommendation_interactor.py` | LangGraph 실행 오케스트레이션(선호도 조회 → 그래프 invoke → 응답 반환) |
| `app/ports/output` | `cruise_catalog_port.py`, `preference_profile_port.py` | 일정 조회·선호도 조회 포트(Protocol) |
| `adapter/outbound/graphs` | `cruise_recommendation_graph.py` | LangGraph `StateGraph` 정의(조회/재랭킹/응답 노드) |
| `adapter/outbound/repositories` | `cruise_catalog_repository.py`, `preference_profile_repository.py` | 실제 데이터 소스 구현체 |
| `adapter/inbound/api` | `cruise_recommendation_router.py` / `_schema.py` | 추천 요청 API 엔드포인트 |
| `dependencies` | `cruise_recommendation_provider.py` | DI 팩토리 |

`domain/`은 프레임워크 비의존 유지 원칙(`fastapi/CLAUDE.md` §2)을 따라, LangChain·LangGraph 관련 타입은 `adapter`/`app` 레이어에만 두고 `domain/`에는 노출하지 않는다.

---

## 3. 의존성 현황

```
langchain-core          # 이미 pyproject.toml에 반영됨
langchain-google-genai  # 이미 pyproject.toml에 반영됨
langgraph               # 이미 pyproject.toml에 반영됨
```

- 위 세 패키지는 이미 루트 `pyproject.toml`에 추가돼 있다(실사용 코드는 아직 없음).
- 크루즈 일정 외부 API 연동이 확정되면, 해당 API 전용 클라이언트(예: `langchain-community`의 범용 Tool 래퍼 또는 직접 `httpx` 클라이언트)를 그때 추가한다 — 지금은 추가하지 않는다.

---

## 4. 관련 문서

| 문서 | 역할 |
|------|------|
| `apps/admin/_docs/langchain-harness.md` | LangChain 개념·현재 상태·도입 판단 체크리스트 |
| `apps/admin/_docs/langchain-morningstar-strategy.md` | 기존 파이프라인(PDF/Neo4j) 재사용형 사례 — 이 문서와 대비되는 "그린필드"형 사례 |
