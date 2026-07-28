# LANGGRAPH-HARNESS.md

시멘틱 라우터(`ontology` 허브)가 질문을 `reasoning`으로 분류했을 때, `admin`의 LangChain 단발성 체인 대신 LangGraph 상태 그래프로 처리를 위임하기 위한 하네스 문서. 코드는 아직 없다 — 구현은 별도 요청 시 진행한다.

---

## 0. 현재 상태 (실제 확인한 내용)

- `langgraph>=1.2.9`(lock: `1.2.9`)는 이미 루트 `pyproject.toml`에 등록돼 있지만, `fastapi/` 전체에서 `import langgraph`는 0건이다. `admin/app/use_cases/langgraph_interactor.py`도 0바이트 플레이스홀더다 — 이번 작업을 위해 미리 예약만 돼 있던 자리다.
- 현재 챗 흐름(`admin/adapter/outbound/repositories/langchain_chat_repository.py`, `LangchainChatRepository.generate`)은 **완전한 선형 단일 호출**이다: 마지막 사용자 메시지로 `ontology`의 `SemanticRoutingUseCase.route()`를 호출해 `entities`만 시스템 메시지 힌트로 붙이고, `ChatGoogleGenerativeAI("gemini-3.5-flash").ainvoke()` 한 번으로 끝난다. **`decision.destination` 값 자체는 분기에 전혀 쓰이지 않는다** — 이게 이번 작업의 실질적 갭이다.
- 시멘틱 라우터는 `ontology/app/dtos/semantic_routing_dto.py`에 `RoutingDestination = Literal["crud", "exaone_rag", "gemini"]`로 정의돼 있고, `SemanticRoutingInteractor.route()`(`ontology/app/use_cases/semantic_routing_interactor.py`)가 정규식 산술 단축 → 프로바이더(`SEMANTIC_ROUTING_PROVIDER`: `ollama`/`gemini`/`embedding`) 분류 → JSON 파싱 순으로 처리하고, 파싱 실패 시 `exaone_rag`로 폴백한다. **`reasoning`이라는 목적지는 아직 존재하지 않는다** — 이 문서가 추가를 제안하는 신규 카테고리다.
- Neo4j는 이미 연결돼 있다(`core/matrix/grid_architect_graph_manager.py`의 `AsyncGraphDatabase` 드라이버 + `get_neo4j_session()`). 다만 실제로 쓰는 곳은 `admin/app/use_cases/pdf_loader_interactor.py` → `pdf_document_repository.py`뿐이고, `MERGE (:Document {id, ...})`로 **평평한(flat) 문서 노드**만 저장한다. 엔티티·관계 추출(GraphRAG용 지식 그래프)은 아직 없다.
- `langchain-neo4j`(`Neo4jGraph`/`GraphCypherQAChain`/`Neo4jVector`)와 `langgraph-checkpoint`는 **미설치**다. `langchain-ncl-strategy.md`가 "`langgraph-checkpoint`는 이미 설치돼 있다"고 적어둔 건 확인 결과 사실이 아니므로(§7 리서치 결과) 그 문서 기술은 신뢰하지 않는다.

---

## 1. LangChain 선형 체인 → LangGraph로 확장하는 이유

### 1-1. 선형 구조의 한계

기존 `LangchainChatRepository.generate()`는 A(라우팅) → B(프롬프트 조립) → C(LLM 호출) 한 방향으로만 흐르는 강물과 같다. "검색 결과가 부실하면 다시 조회 단계로 돌아가기" 같은 루프나, 목적지별로 다른 경로를 타는 조건 분기가 구조적으로 불가능하다. 실제로 지금은 `destination`이 `crud`든 `gemini`든 `exaone_rag`든 상관없이 똑같은 한 줄짜리 `ainvoke()`로 끝난다.

### 1-2. 정교한 상태 관리 (State Management)

대화 기록뿐 아니라 라우터가 내린 중간 판단(`destination`, `entities`), 그래프에서 조회한 문서/관계, 남은 재시도 횟수 같은 것들을 하나의 `State` 객체에 담아 그래프 전체가 공유·갱신할 수 있다. 지금 리포는 클라이언트가 보낸 `messages` 배열 외에는 서버 쪽에 아무 상태도 남지 않는다 — LangGraph의 `StateGraph` + (선택적) 체크포인터가 이 자리를 메운다.

### 1-3. 복잡한 에이전트 제어 및 루프

`reasoning` 질문은 한 번의 검색·한 번의 생성으로 충분하지 않은 경우가 많다(다단계 추론, 근거 부족 시 재검색). 오류·근거 부족을 스스로 감지해 검색 단계로 되돌아가는 self-correction 루프나, 조건 분기(근거 충분 → 답변 생성, 부족 → 재검색)를 안정적으로 표현하려면 조건부 엣지(conditional edge)가 필요하다 — 이건 LangChain 체인만으로는 만들 수 없다.

### 1-4. 멀티 에이전트 협업

지금은 리서치·검증·답변 작성 역할이 분리돼 있지 않다. LangGraph는 이런 역할별 노드(조회 노드, 재랭킹/검증 노드, 답변 생성 노드)가 상호작용하는 구조를 그래프로 명시적으로 표현할 수 있다 — `langchain-ncl-strategy.md`의 "조회 → 재랭킹 → 응답 생성" 구조가 이미 같은 패턴을 쓰고 있다.

---

## 2. GraphRAG를 위한 Neo4j 활용법

`reasoning` 노드가 참고할 지식 소스로 Neo4j를 GraphRAG 인프라로 확장하는 경우의 개념 정리. **아래 네 단계 모두 이 리포에는 아직 구현돼 있지 않다** — §0에서 확인했듯 지금은 `(:Document)` 평면 노드 쓰기까지만 돼 있다.

### 2-1. 지식 그래프 구축 (Ingestion)

`langchain-neo4j`(또는 `neo4j-graphrag`, 이미 설치돼 있음)의 `LLMGraphTransformer` 같은 도구로 문서 텍스트에서 핵심 개념(노드)과 관계(엣지)를 추출해 `Neo4jGraph`에 저장한다. 지금의 `PdfLoaderInteractor`가 텍스트를 뽑아 `(:Document)`로만 저장하는 것과 달리, 엔티티·관계까지 추출하는 단계가 추가된다.

### 2-2. Text-to-Cypher 검색

사용자 질문을 LLM이 `GraphCypherQAChain`(`langchain-neo4j`) 등으로 Cypher 쿼리로 변환해 그래프를 조회한다.

### 2-3. 그래프 탐색 및 하이브리드 검색

변환된 Cypher로 다중 홉(multi-hop) 이웃 노드를 가져오거나, Neo4j 5의 벡터 인덱스와 결합해 (관계 기반 + 의미론적) 하이브리드 검색을 수행한다. 리포에 이미 있는 `pgvector`는 Postgres 쪽 벡터고 Neo4j 벡터 인덱스와는 별개이므로 혼동하지 않는다.

### 2-4. 정교한 답변 생성

그래프에서 나온 명시적 관계·맥락을 LLM 프롬프트에 주입해, 근거 없는 추측(hallucination)을 줄인 답변을 생성한다.

---

## 3. 이 리포에 적용할 구조 — `reasoning` 라우팅 신설

```
사용자 질문
     │
     ▼
SemanticRoutingUseCase.route()  (ontology 허브, 기존)
     │
     ├─ "crud" / "gemini" / "exaone_rag"  →  기존 LangchainChatRepository 단일 호출 (변경 없음)
     │
     └─ "reasoning" (신규)
              │
              ▼
     admin의 LangGraph StateGraph 실행
     State = { messages, entities, retrieved_context, retry_count }
              │
              ▼
     ┌──────────────┐   근거 부족 & 재시도 남음
     │ retrieve 노드 │◄────────────────────────┐
     │ (Neo4j Cypher/│                          │
     │  벡터 하이브리드)│                         │
     └──────┬───────┘                          │
            ▼                                  │
     ┌──────────────┐                          │
     │ answer 노드   │  근거 충분? ─── No ───────┘
     │ (Gemini)     │
     └──────┬───────┘
            │ Yes / 재시도 소진
            ▼
        최종 응답
```

### 3-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| `reasoning` 분류 위치 | **`ontology` 허브** — `semantic_routing_dto.py`의 `RoutingDestination` Literal에 `"reasoning"` 추가, `ROUTING_SYSTEM_PROMPT`에 판단 기준 반영 (기존 `crud`/`exaone_rag`/`gemini` 판단 로직과 동일한 자리) |
| 그래프 실행 위치 | **`admin` 스포크** — 기존에 `LangchainChatRepository`가 `LangchainChatPort`를 구현하며 `ontology`의 라우팅 결과를 소비하는 것과 같은 방향(spoke → hub 조회는 허용, 역방향 없음) |
| 상태·흐름 관리 | **LangGraph `StateGraph`** — retrieve → answer 노드, 조건부 엣지로 재검색 루프 |
| destination 분기 도입 | `LangchainChatRepository.generate()`가 지금 무시하고 있는 `decision.destination`을 실제로 분기해야 함 — `reasoning`이면 LangGraph 그래프를, 나머지는 기존 단일 호출을 타도록 수정 필요 |

### 3-2. 미정 사항 (구현 전 재확인 필요)

- `reasoning`으로 분류할 질문의 구체적 기준(예시 문장, 프롬프트 문구) — 사용자 확인 필요. 임베딩 라우터(`embedding_router_generator.py`)는 카테고리별 예시 문장 센트로이드 방식이라, `reasoning` 추가 시 예시 문장 세트도 같이 정의해야 한다.
- retrieve 노드가 조회할 그래프 스키마 — 지금은 `(:Document)` 평면 노드뿐이라 §2-1의 엔티티/관계 추출(`LLMGraphTransformer` 도입 여부)부터 결정해야 실질적인 그래프 탐색이 가능하다. 도입하지 않는다면 retrieve 노드는 당분간 벡터 검색만으로 축소해야 한다.
- self-correction 루프의 최대 재시도 횟수(무한 루프 방지 상한).
- 체크포인터(대화 재개) 사용 여부와 저장소 — `langgraph-checkpoint`는 미설치이며, 쓴다면 in-memory/Redis(이미 의존성 있음)/PG 중 선택 필요.
- `reasoning` 전용 LLM을 챗 모델(`gemini-3.5-flash`)과 분리할지 — Google Search grounding을 껐다 되돌린 이력(커밋 `8d8c69b`/`7e385a7`, 쿼터 초과)이 있으므로, 다단계 호출이 늘어나는 `reasoning` 경로는 쿼터 소비량을 먼저 가늠해야 한다.

---

## 4. 레이어 배치 (fastapi/CLAUDE.md §2 규칙 적용)

| 레이어 | 파일(예정) | 역할 |
|--------|-----------|------|
| `ontology/app/dtos` | `semantic_routing_dto.py` (수정) | `RoutingDestination`에 `"reasoning"` 추가 |
| `ontology/app/use_cases` | `semantic_routing_interactor.py` (수정) | 신규 목적지에 대한 폴백/파싱 규칙 반영 |
| `admin/app/ports/output` | `graph_retrieval_port.py` (신규) | Neo4j 하이브리드 검색 포트(Protocol) |
| `admin/app/use_cases` | `langgraph_interactor.py` (현재 0바이트 → 구현) | LangGraph 실행 오케스트레이션(그래프 invoke → 응답 반환) |
| `admin/adapter/outbound/graphs` | `reasoning_graph.py` (신규) | LangGraph `StateGraph` 정의(retrieve/answer 노드 + 조건부 엣지) |
| `admin/adapter/outbound/repositories` | `graph_retrieval_repository.py` (신규) | Neo4j Cypher/벡터 하이브리드 조회 구현체 |
| `admin/adapter/outbound/repositories` | `langchain_chat_repository.py` (수정) | `decision.destination == "reasoning"`일 때 `langgraph_interactor`로 분기 |

`domain/`은 프레임워크 비의존 원칙(`fastapi/CLAUDE.md` §2)에 따라 LangGraph·Neo4j 관련 타입을 노출하지 않는다. `ontology`(허브) 수정과 `admin`(스포크) 수정은 서로 다른 앱이므로, 각각 해당 앱의 `_docs`/레이어 규칙을 따로 지킨다.

---

## 5. 의존성 현황

```
langchain-core          # 이미 pyproject.toml에 반영됨 (실사용 코드는 chat repository뿐)
langchain-google-genai  # 이미 pyproject.toml에 반영됨
langgraph                # 이미 pyproject.toml에 반영됨 (실사용 코드 없음)
neo4j                    # 이미 pyproject.toml에 반영됨 (PDF 파이프라인에서 사용 중)
neo4j-graphrag            # 이미 pyproject.toml에 반영됨

langchain-neo4j          # 미설치 — GraphCypherQAChain/Neo4jGraph/Neo4jVector 도입 시 uv add 필요
langgraph-checkpoint     # 미설치 — 체크포인터 도입 시에만 uv add
```

패키지 추가는 `uv add`로만 반영하고, `pyproject.toml`/`uv.lock`이 바뀌었다는 이유로 임의로 빌드하지 않는다(루트 `CLAUDE.md` Docker 워크플로우 규칙).

---

## 6. Claude 하네스 체크리스트 (`reasoning` 라우팅 작업 시)

1. `ontology`(허브) 수정과 `admin`(스포크) 수정 범위를 먼저 사용자에게 확인한다 — 라우터 카테고리 추가는 허브 쪽 변경이라 다른 스포크(`kayfabe`, `titanic` 등)의 라우팅 동작에도 영향을 줄 수 있다.
2. §3-2 미정 사항(분류 기준, 그래프 스키마, 재시도 상한, 체크포인터) 중 필요한 항목을 실제로 질문하고 답을 받은 뒤 착수한다 — 가정하지 않는다(루트 `CLAUDE.md` §1).
3. `LangchainChatRepository.generate()`의 destination 무시 문제(§0)를 고치는 것이 선행 조건임을 인지한다 — `reasoning` 분기만 추가하고 나머지 목적지 처리를 건드리지 않는다(정밀한 수정, 루트 `CLAUDE.md` §3).
4. LangGraph `StateGraph`/노드 정의는 `adapter/outbound/graphs/`에만 두고 `domain/`·`app/`에 프레임워크 타입이 새지 않는지 확인한다(§4).
5. Neo4j 스키마를 확장(엔티티/관계 추출)할지, 벡터 검색만으로 축소할지 결정 후 `graph_retrieval_port.py` 시그니처를 그에 맞춘다.
6. 코드 작성 후 `uv run ruff check --fix` / `ruff format` / `PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports`를 실행해 스타 토폴로지 계약(허브만 스포크 import 가능, 스포크 간 직접 import 금지)이 깨지지 않았는지 확인한다(루트 `CLAUDE.md` §5, `fastapi/CLAUDE.md` §6-2).

---

## 7. 관련 문서

| 문서 | 역할 |
|------|------|
| `fastapi/CLAUDE.md` | 백엔드 행동 지침(레이어·경로·스타 토폴로지 규칙) |
| `apps/admin/_docs/langchain-harness.md` | LangChain 개념·도입 판단 체크리스트 |
| `apps/admin/_docs/langchain-ncl-strategy.md` | LangGraph 상태 그래프를 이 리포에 적용한 선행 사례(레이어 배치 템플릿) |
| `apps/admin/_docs/neo4j-harness.md` | Neo4j 그래프 데이터 모델(노드/라벨/관계/속성) 기본 개념 |
| `ontology/app/dtos/semantic_routing_dto.py` | `RoutingDestination` 정의 위치(신규 카테고리 추가 지점) |
| `ontology/app/use_cases/semantic_routing_interactor.py` | 라우팅 분류·폴백 로직 |
| `admin/adapter/outbound/repositories/langchain_chat_repository.py` | 현재 destination을 무시하는 단일 체인 구현(분기 추가 대상) |
