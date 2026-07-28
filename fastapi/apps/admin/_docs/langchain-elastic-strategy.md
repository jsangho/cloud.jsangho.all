# LANGCHAIN-ELASTIC-STRATEGY.md

Elastic 사례([langchain-harness](./langchain-harness.md) 참고)를 이 리포에 적용하기 위한 전략 문서. 코드는 아직 없다 — 구현은 별도 요청 시 진행한다.

---

## 0. 사례 요약

보안 소프트웨어 기업 Elastic은 LangChain을 활용해 보안 분석가를 지원하는 AI 어시스턴트를 개발했다. 이 어시스턴트는 (1) 보안 경고 요약, (2) 대응 워크플로우 제안, (3) 쿼리 생성·변환의 세 가지 기능을 수행한다. 실시간으로 대량의 보안 데이터를 처리·분석해야 하므로, LangChain의 다양한 데이터 소스 통합 기능이 핵심 역할을 한다.

---

## 1. 이 리포에 적용할 구조

NCL 사례([langchain-ncl-strategy](./langchain-ncl-strategy.md))처럼 이 리포에는 재사용할 기존 보안/로그 파이프라인이 없다 — Elasticsearch 자체도, 보안 경고 데이터 모델도 없는 그린필드다. Morningstar 사례와의 차이는 상태가 대화 중 갱신되는 게 아니라 **요약 / 워크플로우 제안 / 쿼리 생성**이라는 서로 독립적인 세 기능을 하나의 어시스턴트가 상황에 맞게 골라 쓴다는 점이다 — 이는 LangGraph의 순차 상태 그래프보다 **Tool을 여러 개 바인딩한 단일 에이전트** 형태가 더 맞는다.

```
보안 경고 데이터 소스 (미정: Elasticsearch or 내부 로그)
              │
              ▼
   LangChain Retriever/Tool (경고 조회 — langchain-elasticsearch)
              │
              ▼
┌─────────────────────────────────────────────┐
│      ChatGoogleGenerativeAI 기반 에이전트       │
│  Tool 1: 경고 요약                              │
│  Tool 2: 대응 워크플로우 제안                     │
│  Tool 3: 자연어 → 쿼리(ES|QL/DSL) 생성·변환       │
└─────────────────────────────────────────────┘
              │
              ▼
        분석가에게 반환되는 응답(요약/제안/쿼리)
```

### 1-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| 오케스트레이션 형태 | **Tool 바인딩 에이전트** — 세 기능이 서로 독립적이라 LangGraph 상태 그래프 대신 `langchain-core`의 tool-calling 에이전트로 구성하고, 에이전트가 요청 내용에 따라 요약/워크플로우/쿼리생성 Tool 중 필요한 것을 호출 |
| LLM 연동 | **langchain-google-genai + Keymaker** — `vault_keymaker_secret_manager.get_keymaker()`로 키 조회, 호출은 `ChatGoogleGenerativeAI`로 감싸 에이전트에 바인딩 |

### 1-2. 미정 사항 (구현 전 재확인 필요)

- **소속 앱** — 이 리포에는 보안/SIEM 도메인 앱이 없다(`fastapi/apps/`: admin·auth·heyman·kayfabe·lion_king·ontology·sample·soccer·superstar·titanic). "운영 효율성" 성격상 `admin` 앱에 얹는 게 자연스러워 보이지만, 실제 보안 경고 소스가 무엇인지에 따라 별도 앱이 필요할 수도 있다.
- **보안 경고 데이터 소스** — 진짜 Elasticsearch 클러스터를 붙일지, 이 리포가 이미 갖고 있는 로그(있다면)를 재사용할지 결정 필요. 현재 리포에는 Elasticsearch 관련 의존성·인프라(docker-compose 서비스 포함)가 전혀 없다.
- **쿼리 생성·변환의 대상 언어** — Elasticsearch DSL(JSON)인지 ES|QL인지, 혹은 완전히 다른 내부 쿼리 포맷인지 미정.
- **워크플로우 제안의 실행 여부** — 제안만 하는지, 승인 후 실제 액션(티켓 생성 등)까지 트리거하는지 — 후자라면 별도 아웃바운드 어댑터(외부 티켓팅 시스템 연동)가 필요.
- 실시간 대량 데이터 처리 요구 수준 — 스트리밍/배치 여부에 따라 Elasticsearch 클라이언트 호출 전략(bulk vs 단건)이 달라짐.

---

## 2. 레이어 배치 (fastapi/CLAUDE.md 규칙 적용)

앱명이 미정이므로 아래는 `<app>`으로 표기한다 — 구현 전 실제 앱명으로 치환.

| 레이어 | 파일(예정) | 역할 |
|--------|-----------|------|
| `app/ports/input` | `security_assistant_use_case.py` | 요약/워크플로우 제안/쿼리 생성 요청 UseCase(Protocol) |
| `app/use_cases` | `security_assistant_interactor.py` | 에이전트 실행 오케스트레이션(요청 → 에이전트 invoke → 응답 반환) |
| `app/ports/output` | `security_alert_port.py` | 보안 경고 조회 포트(Protocol) |
| `adapter/outbound/agents` | `security_assistant_agent.py` | Tool 바인딩 에이전트 정의(요약/워크플로우/쿼리생성 Tool 등록) |
| `adapter/outbound/repositories` | `security_alert_repository.py` | 실제 경고 데이터 소스(Elasticsearch 등) 구현체 |
| `adapter/inbound/api` | `security_assistant_router.py` / `_schema.py` | 어시스턴트 질의 API 엔드포인트 |
| `dependencies` | `security_assistant_provider.py` | DI 팩토리 |

`domain/`은 프레임워크 비의존 유지 원칙(`fastapi/CLAUDE.md` §2)을 따라, LangChain 관련 타입(Tool, Agent 등)은 `adapter`/`app` 레이어에만 두고 `domain/`에는 노출하지 않는다.

---

## 3. 의존성 현황

```
langchain-core          # 이미 pyproject.toml에 반영됨
langchain-google-genai  # 이미 pyproject.toml에 반영됨
langchain-elasticsearch  # 미반영 — Elasticsearch 연동 확정 시에만 추가
elasticsearch            # 미반영 — 위와 동일
```

- `langchain-core`/`langchain-google-genai`는 이미 루트 `pyproject.toml`에 있다(실사용 코드는 아직 없음).
- Elasticsearch 실제 연동이 확정되기 전에는 `langchain-elasticsearch`/`elasticsearch` 클라이언트를 추가하지 않는다 — §1-2의 데이터 소스 결정이 선행 조건.

---

## 4. 관련 문서

| 문서 | 역할 |
|------|------|
| `apps/admin/_docs/langchain-harness.md` | LangChain 개념·현재 상태·도입 판단 체크리스트 |
| `apps/admin/_docs/langchain-morningstar-strategy.md` | 기존 파이프라인 재사용형 사례 |
| `apps/admin/_docs/langchain-ncl-strategy.md` | 그린필드 + 상태 그래프형 사례 — 이 문서(그린필드 + Tool 에이전트형)와 대비 |
