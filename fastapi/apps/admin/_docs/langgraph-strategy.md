# LANGGRAPH-STRATEGY.md

외부 전략 문서("LangChain + PGVector → LangGraph + Neo4j 확장" 4단계)를 이 리포에 적용하기 위한 전략 문서. 코드는 아직 없다 — 구현은 별도 요청 시 진행한다.

LangGraph 상태 그래프 자체의 도입 근거·레이어 배치·`reasoning` 라우팅 신설은 [langgraph-harness](./langgraph-harness.md)가 이미 다룬다. 이 문서는 **원문 전략의 전제를 리포 실제와 대조**하고, harness 문서가 미정으로 남긴 **지식 그래프 적재(GraphRAG ingestion)** 쪽만 보탠다.

---

## 0. 전략 요약 (원문 4단계)

| 단계 | 원문 요지 |
|------|----------|
| 1 | 개념 전환 — 체인(Chain) → 상태를 가지는 순환 그래프(Cyclic Graph), 벡터 검색 → 지식 그래프/GraphRAG |
| 2 | 환경·라이브러리 교체 — `langgraph`, `langchain-neo4j` 설치 및 Neo4j 접속 설정 |
| 3 | 데이터 마이그레이션 — `LLMGraphTransformer`로 엔티티·관계 추출, Neo4j 벡터 인덱스 활용 |
| 4 | 워크플로우 구축 — `State`(TypedDict) 정의, Node 구현, 조건부 엣지로 순환 구조, 체크포인터(선택) |

원문 요약 팁: 전부 한 번에 바꾸지 말고 ① LangGraph로 제어 구조 뼈대를 먼저 잡고 ② 데이터 일부만 Neo4j 지식 그래프로 옮기는 하이브리드로 확장한다.

---

## 1. 전제 검증 — 원문과 이 리포의 실제 차이

원문은 일반론이라 이 리포의 실제 구성과 어긋나는 지점이 있다. **아래 표가 이 문서의 핵심**이다.

| 원문 전제 | 이 리포 실제 (확인함) | 판단 |
|-----------|---------------------|------|
| 현재 구성은 "LangChain + PGVector" | `admin`의 챗 경로는 LangChain(`langchain_chat_repository.py`, `ChatGoogleGenerativeAI`)이지만, **문서 경로는 이미 Neo4j**다 — `pdf_document_repository.py`가 `MERGE (:Document {id})`로 적재한다. `admin`에 PGVector는 **없다** | **전제 불일치.** `admin` 기준으로는 "PGVector → Neo4j 마이그레이션" 대상이 존재하지 않는다 |
| PGVector가 RAG 벡터 저장소 | 맞다 — 단 `admin`이 아니라 다른 스포크다. `soccer/adapter/outbound/repositories/soccer_chat_repository.py:111`과 `kayfabe/adapter/outbound/repositories/wrestler_chat_repository.py:75`가 `embedding.op("<=>")`(코사인 거리) 정렬로 **실제 유사도 검색을 수행 중**이다. 쓰기는 `heyman/adapter/outbound/repositories/receiver_repository.py:43` | **벡터 계층 이전은 반대**, 단 관계 계층 추가는 별개 판단 — §1-2 |
| 시맨틱 라우터가 벡터 DB 검색 | `ontology/adapter/outbound/embedding_router_generator.py`는 pgvector가 아니라 `intfloat/multilingual-e5-small` **인메모리 임베딩 + 하드코딩 예시문 센트로이드(numpy)** 방식이다 | 라우터는 마이그레이션 대상이 **아니다** — 지식베이스가 아니라 분류기다 |
| `pip install langgraph langchain-neo4j` | `langgraph>=1.2.9`는 이미 `pyproject.toml`에 있다(단, `fastapi/` 전체에서 `import langgraph` 0건). `langchain-neo4j`는 **미설치** | 명령 교체 필요 — 이 리포는 `pip`이 아니라 **`uv add`**를 쓴다(루트 `CLAUDE.md`) |
| Neo4j 접속을 새로 설정 | 이미 완료 — `core/matrix/grid_architect_graph_manager.py`의 `AsyncGraphDatabase` 드라이버 + `get_neo4j_session()`, `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`는 Keymaker 경유 | **작업 없음** |
| `Neo4jSaver`로 체크포인트 백엔드 연동 | LangGraph 공식 체크포인터에 Neo4j 백엔드가 있는지 **미검증**이다. `langgraph-checkpoint` 자체가 미설치 | 미검증 항목으로 남긴다. 도입 시 Redis·PG(둘 다 이미 스택에 있음)를 먼저 검토 |

> `langchain-ncl-strategy.md` §1-2는 "`langgraph-checkpoint`는 이미 설치돼 있다"고 적었으나 사실이 아니다([langgraph-harness](./langgraph-harness.md) §0에서 확인). 해당 기술은 신뢰하지 않는다.

### 1-1. 전제 불일치의 결론

원문의 "PGVector → Neo4j"를 `admin`에 그대로 적용할 대상은 없다. `admin`에서 실제로 남은 확장 여지는 **이미 Neo4j에 들어가 있는 평면(flat) `(:Document)` 노드를 관계가 있는 지식 그래프로 고도화**하는 것이다. 이것이 원문 3단계에 해당하며, 이 문서가 다루는 범위다.

### 1-2. PGVector → Neo4j 판단 (2026-07-30 갱신)

당초 이 문서는 "원문 `PGVector → Neo4j`의 실제 의도"를 최우선 미정 항목으로 두고, 1차 조사 후 **일괄 기각**으로 적었다. 재검토 결과 그 결론은 **과했다.** 아래로 대체한다.

핵심은 **"변환(replace)"과 "관계 계층 추가(additive hybrid)"를 갈라야 한다**는 것이다. 원문은 이 둘을 구분하지 않는다.

| 대상 | 판단 | 근거 |
|------|------|------|
| 벡터 검색 계층을 Neo4j로 **이전** | **반대** | `<=>` 코사인 검색은 이미 동작한다. Neo4j 벡터 인덱스로 옮겨도 결과가 개선되지 않는다 — 작동하는 코드의 리라이트다 |
| `kayfabe` 타이틀 계보에 **관계 계층 추가** | **조건부 찬성 — 가장 값있는 후보** | `title_acquisitions`(`title_history_orm.py`)는 `competitor_name`·`belt_name`·`won_at`·`match_id`를 가진 **평면 이벤트 로그**이고 계보 링크가 없다. "누구에게서 벨트를 땄고 그 사람은 그 전에 누구에게서 땄나"는 `belt_name` 자기조인 + 날짜 정렬을 홉마다 반복해야 한다. **깊이가 가변인 질문은 SQL에서 재귀 CTE가 필요하지만 그래프에서는 `MATCH (a)-[:WON_FROM*1..5]->(b)` 한 줄이다** |
| `soccer` | **그래프보다 쿼리 개선이 먼저** | `soccer_chat_repository.py`의 `_search()`는 4개 테이블을 각각 독립 벡터 검색한 뒤 `_team_name_lookup()`·`_stadium_name_lookup()`이 **테이블 전체를 select해 파이썬 dict로 FK를 해소**한다. 이건 그래프가 없어서가 아니라 **JOIN을 안 써서** 생긴 문제다. 테이블 4개·FK 2개 수준은 SQL JOIN으로 해결된다 — 저장소만 갈아끼우면 진짜 원인(전체 테이블 메모리 로딩)이 남는다 |

즉 **하이브리드는 가능하고 표준적이지만, 값이 있는 쪽은 관계 계층이고 값이 없는 쪽은 벡터 계층이다.** 벡터까지 옮기는 것이 하이브리드의 비싼 절반이다.

#### 하이브리드 도입 시 실제 비용 (이 리포 특정)

1. **이중 쓰기 동기화** — PG가 system of record이고 `kayfabe/scripts/sync_championship_board.py`가 이미 적재 파이프라인이다. Neo4j에도 쓰면 이 스크립트가 양쪽을 책임지며, 드리프트가 생겼을 때 어느 쪽이 맞는지 판단할 근거가 없다. **하이브리드의 진짜 비용은 대개 여기다.**
2. **스타 토폴로지 제약** — `soccer`·`kayfabe`는 스포크로 서로 import가 금지되고 `lint-imports`가 차단한다. 단일 앱 내부 그래프는 그 앱에서 가능하지만, **두 도메인을 잇는 통합 그래프는 조정 로직이 `ontology` 허브로 올라가야 한다**(`fastapi/CLAUDE.md` §6-2). 스코프가 달라진다.
3. **Neo4j 벡터 인덱스 지원 미확인** — [neo4j-strategy](./neo4j-strategy.md) §2의 `docker-compose` 변경안이 아직 미적용이다.

#### 아직 검증되지 않은 게이팅 조건

**다중 홉 질문을 실제로 할 의도가 있는지**는 확인되지 않았다. 스키마상 계보 구조가 존재한다는 것은 확인했지만, "몇 다리 건너 누가 이겼나"를 묻는 사용자가 있는지는 데이터가 아니라 의도의 문제다. **이 답이 "예"일 때만 `kayfabe` 계보 그래프에 값이 있다** — 착수 전 확인 항목.

#### 작업 범위

이 문서와 `langgraph-harness.md`의 **현재 스코프에서는 `soccer`·`kayfabe`·`heyman`을 건드리지 않는다.** 위 판단은 "언젠가 별건으로 다룰 후보"를 기록한 것이며, 착수 승인이 아니다. 특히 §5의 순서(조회 경로 선행)는 이 판단과 무관하게 유지된다.

> **곁가지 발견 (본 문서 범위 밖, 별건 권장):** `alembic/versions/`에 HNSW·IVFFlat 인덱스 생성이 없다. 위 두 유사도 검색은 매번 순차 스캔이다. 행 수가 적으면 당장 문제는 아니지만, Neo4j 도입보다 **인덱스 추가가 훨씬 값싼 개선**이다.

---

## 2. 이 리포에 적용할 구조

```
PDF 업로드 (기존 pdf_loader_router)
     │
     ▼
PdfLoaderInteractor  (기존: neo4j_graphrag PdfLoader로 텍스트 추출)
     │
     ├─────────────► MERGE (:Document {id, filename, text})      ← 기존, 변경 없음
     │
     └─ (신규) 청킹 → 임베딩 → 엔티티·관계 추출
                    │
                    ├──► (:Chunk {text, embedding}) + Neo4j 벡터 인덱스
                    │
                    └──► (:Entity)-[:관계]->(:Entity)  ← LLM 추출
                                 │
                                 ▼
                    reasoning 경로의 retrieve 노드가 조회
                    (그래프 탐색 + 벡터 하이브리드)
                                 │
                                 ▼
                    langgraph-harness.md §3 StateGraph
```

`reasoning` 라우팅과 `StateGraph`(retrieve/answer 노드, 조건부 엣지, 재검색 루프)의 상세는 [langgraph-harness](./langgraph-harness.md) §3에 있다 — 여기서 다시 정의하지 않는다.

### 2-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| 대상 앱 | **`admin` 스포크** — PDF 파이프라인이 이미 여기 있어 신규 앱을 만들지 않는다 |
| 그래프 DB | **Neo4j** — 이미 연결돼 있고 `(:Document)` 적재까지 동작 중(§1) |
| 적재 위치 | **기존 `PdfLoaderInteractor` 확장** — 별도 배치 파이프라인을 신설하지 않는다 |
| 기존 동작 보존 | `(:Document)` 저장과 `PdfLoaderResult` 응답 형태는 **그대로 둔다** — 추출 단계는 뒤에 덧붙인다(루트 `CLAUDE.md` §3 정밀한 수정) |
| 오케스트레이션 | **LangGraph `StateGraph`** — 정의·레이어는 langgraph-harness.md §3·§4를 따른다 |
| 패키지 반영 | **`uv add`만** 사용하고, `pyproject.toml`/`uv.lock`이 바뀌었다는 이유로 빌드하지 않는다 |
| PGVector 처리 | **벡터 검색은 PG에 그대로 둔다** — `soccer`/`kayfabe`의 `<=>` 검색은 작동 중이므로 이전하지 않는다(§1-2) |
| 관계 계층(그래프) 확대 | **현재 스코프 제외 — 후보로만 기록** — `kayfabe` 타이틀 계보가 유력 후보이나, 다중 홉 질문 의도 확인이 선행 조건이다(§1-2) |
| 착수 순서 | **`langgraph-harness.md` 1단계가 선행** — `destination` 분기가 없으면 이 문서의 적재분을 조회할 경로가 없다(§5) |

### 2-2. 미정 사항 (구현 전 재확인 필요)

> 당초 최우선 미정이던 "원문 `PGVector → Neo4j`의 실제 의도"는 **§1-2로 이동**했다(벡터 이전은 반대 / 관계 계층 추가는 조건부 후보). 아래 목록에서는 제외하되, §1-2의 게이팅 조건(다중 홉 질문 의도)은 그쪽에서 미해결로 남아 있다.

- **엔티티 추출을 할 필요가 있는지 자체** — 3단계(엔티티·관계 추출)는 "관계를 타야만 답할 수 있는 질문"이 실제로 있을 때만 값이 있다. 없다면 2단계(`(:Chunk)` 벡터 검색)까지로 충분하고, 3단계는 Gemini 쿼터만 소비한다. **착수 전에 그런 질문 예시를 확보한다.**
- **엔티티·관계 추출 도구** — `neo4j-graphrag`(이미 설치, PDF 로더로 이미 사용 중)의 파이프라인을 쓸지, `langchain-neo4j`의 `LLMGraphTransformer`를 `uv add`해서 쓸지. 이미 있는 쪽을 재사용하는 편이 의존성이 덜 늘지만, 두 API의 실제 기능 차이는 확인하지 않았다.
- **그래프 스키마(허용 노드 라벨·관계 타입)** — 무제한 추출은 라벨이 폭발해 그래프 품질이 떨어진다. 허용 목록을 먼저 정의할지, 자유 추출 후 정리할지 미정. 노드/라벨/관계/속성 기본 개념은 [neo4j-harness](./neo4j-harness.md) §1 참고.
- **청킹 전략과 임베딩 모델** — 라우터의 `multilingual-e5-small`을 재사용할지, Gemini 임베딩을 쓸지. 차원 수가 `(:Chunk)` 벡터 인덱스 정의에 직접 들어간다.
- **Neo4j 벡터 인덱스 지원 여부** — [neo4j-strategy](./neo4j-strategy.md) §2의 `docker-compose` 변경안이 **아직 미적용**이다. 현재 기동 중인 Neo4j 버전이 벡터 인덱스를 지원하는지 확인이 선행 조건이다.
- **Gemini 쿼터** — 문서마다 LLM 추출 호출이 붙으면 소비량이 급증한다. Google Search grounding을 쿼터 초과로 껐다 되돌린 이력이 있으므로(langgraph-harness.md §3-2) 문서 건수 기준으로 먼저 가늠해야 한다.
- **체크포인터** — `langgraph-checkpoint` 미설치. 도입 시 저장소(in-memory / Redis / PG) 선택 필요. `Neo4jSaver`는 §1대로 미검증.

---

## 3. 레이어 배치 (fastapi/CLAUDE.md §2 규칙 적용)

langgraph-harness.md §4가 정의한 `reasoning` 경로(포트·그래프·조회 구현체)와 **겹치지 않는 신규분만** 적는다.

| 레이어 | 파일(예정) | 역할 |
|--------|-----------|------|
| `admin/app/ports/output` | `graph_ingestion_port.py` (신규) | 청크·엔티티·관계 적재 포트(ABC) |
| `admin/app/use_cases` | `pdf_loader_interactor.py` (수정) | `(:Document)` 저장 후 추출·적재 단계 추가 |
| `admin/adapter/outbound/repositories` | `graph_ingestion_repository.py` (신규) | 추출 결과를 Cypher로 적재(`(:Chunk)`, `(:Entity)` + 관계) |
| `admin/app/dtos` | `graph_ingestion_dto.py` (신규) | 추출 결과 전달용 DTO |
| `admin/dependencies` | `pdf_loader_provider.py` (수정) | 신규 리포지토리 DI 배선 |

- `admin/app/ports/output/pdf_document_port.py`와 `pdf_document_repository.py`는 **변경하지 않는다** — `(:Document)` 저장 책임을 그대로 유지한다(단일 책임).
- `domain/`에는 LangGraph·Neo4j·LangChain 타입을 노출하지 않는다(`fastapi/CLAUDE.md` §2).
- 네이밍은 `fastapi/CLAUDE.md` §4 표를 따른다. 다만 이 리포의 `admin` 기존 파일은 Neo4j 어댑터를 `{resource}_repository.py`로 두고 있어(`pdf_document_repository.py`) `_pg_repository` 접미사를 쓰지 않는다 — 기존 관례를 따른다.

---

## 4. 의존성 현황

```
langgraph                # 이미 pyproject.toml (langgraph>=1.2.9, 실사용 코드 0건)
langchain-core           # 이미 pyproject.toml (챗 리포지토리에서 사용)
langchain-google-genai   # 이미 pyproject.toml (ChatGoogleGenerativeAI)
neo4j                    # 이미 pyproject.toml (neo4j==6.2.0, PDF 파이프라인에서 사용 중)
neo4j-graphrag           # 이미 pyproject.toml (>=1.18.0, PdfLoader로 사용 중)

langchain-neo4j          # 미설치 — LLMGraphTransformer/Neo4jVector/GraphCypherQAChain 도입 시에만 uv add
langgraph-checkpoint     # 미설치 — 체크포인터 도입 시에만 uv add
```

원문 2단계의 `pip install`은 이 리포에서 쓰지 않는다. 새 패키지는 먼저 실행 중인 컨테이너에서 검증하고(`docker compose exec backend uv pip install <pkg>`), 확정되면 `uv add`로 반영한다. **빌드는 사용자가 명시적으로 요청할 때만** 한다(루트 `CLAUDE.md` Docker 워크플로우 §3·§4).

---

## 5. 단계적 롤아웃 (원문 요약 팁 적용)

원문 팁대로 하이브리드로 쪼갠다. 각 단계는 독립적으로 검증 가능해야 한다(루트 `CLAUDE.md` §4).

| 단계 | 범위 | 검증 지점 | 담당 문서 |
|------|------|----------|----------|
| 1 | `reasoning` 라우팅 + LangGraph 뼈대. retrieve 노드는 기존 `(:Document)` 텍스트만 조회 | `reasoning` 질문이 그래프 경로를 타고 응답이 오는가 | langgraph-harness.md |
| 2 | 청킹 + `(:Chunk)` 노드 + Neo4j 벡터 인덱스 | 벡터 유사도 검색이 관련 청크를 반환하는가 | 본 문서 §2·§3 |
| 3 | 엔티티·관계 추출 → 진짜 GraphRAG (다중 홉 탐색) | 관계를 타야만 답할 수 있는 질문이 개선되는가 | 본 문서 §2·§3 |
| 4 | 체크포인터(대화 재개) — **선택** | 세션 중단 후 재개가 되는가 | 미정(§2-2) |

**1단계를 건너뛰고 2·3단계부터 시작하지 않는다.** 지금 `langchain_chat_repository.py:40-47`은 시맨틱 라우터를 호출해 `decision`을 받고도 `entities`만 힌트로 쓰고 **`destination`은 버린다** — `crud`·`gemini`·`exaone_rag` 전부 동일한 `ainvoke()` 한 번으로 끝난다. `langgraph_interactor.py`는 0바이트 플레이스홀더다. 이 분기가 생기기 전에는 지식 그래프를 아무리 잘 쌓아도 **그것을 조회할 경로 자체가 존재하지 않는다.**

즉 1단계는 선택이 아니라 2·3단계의 전제다. 반대로 1단계만 해도 그 자체로 동작하는 개선이 된다.

---

## 6. Claude 하네스 체크리스트

1. **현재 스코프에서 `soccer`·`kayfabe`·`heyman`을 건드리지 않는다.** §1-2가 `kayfabe` 계보를 후보로 기록해 뒀지만 그건 **후보 기록이지 착수 승인이 아니다** — 손대려면 §1-2의 게이팅 조건(다중 홉 질문 의도)을 먼저 사용자에게 확인한다. 벡터 검색을 Neo4j로 이전하는 것은 원문에 그 문장이 있다는 이유로 되살리지 않는다.
2. **§5 1단계(`destination` 분기 + LangGraph 뼈대)가 끝났는지 먼저 확인한다.** 안 끝났으면 이 문서의 적재 작업은 착수하지 않는다 — 조회 경로가 없다(§5). 1단계는 이 문서가 아니라 langgraph-harness.md §6 체크리스트를 따른다.
3. **3단계(엔티티 추출)를 하기 전에 그것이 필요한 질문 예시를 확보한다**(§2-2). 확보되지 않으면 2단계까지만 한다.
4. `PdfLoaderInteractor` 수정 시 기존 `(:Document)` 저장과 `PdfLoaderResult` 필드를 깨지 않는지 확인한다 — 추출 실패가 업로드 자체를 실패시키지 않도록 경계를 정한다.
5. `langchain-neo4j`를 추가하기 전에 이미 설치된 `neo4j-graphrag`로 되는지 먼저 확인한다(§2-2). 추가하더라도 `uv add`까지만 하고 빌드하지 않는다.
6. `(:Chunk)` 벡터 인덱스를 만들기 전에 기동 중인 Neo4j 버전의 지원 여부와 neo4j-strategy.md §2 변경안 적용 상태를 확인한다.
7. `domain/`에 프레임워크 타입이 새지 않는지 확인한다(§3).
8. 코드 작성 후 하네스 게이트를 실행한다 — `uv run ruff check fastapi/ --config pyproject.toml --fix` · `uv run ruff format` · `cd fastapi && PYTHONUTF8=1 PYTHONPATH=apps uv run lint-imports`. 스포크(`admin`)에서 다른 스포크를 직접 import하지 않았는지(허브 `ontology` 경유) 계약 검증으로 확인한다(루트 `CLAUDE.md` §5, `fastapi/CLAUDE.md` §6-2).

---

## 7. 관련 문서

| 문서 | 역할 |
|------|------|
| [langgraph-harness](./langgraph-harness.md) | **선행 문서** — LangGraph 도입 근거, `reasoning` 라우팅 신설, StateGraph·레이어 배치, 현재 상태 확인 |
| [neo4j-harness](./neo4j-harness.md) | 그래프 데이터 모델(노드·라벨·관계·속성) 기본 개념 |
| [neo4j-strategy](./neo4j-strategy.md) | Neo4j `docker-compose` 설정 갭·변경안(미적용) — 벡터 인덱스 선행 조건 |
| [langchain-harness](./langchain-harness.md) | LangChain 개념·도입 판단 체크리스트 |
| [langchain-ncl-strategy](./langchain-ncl-strategy.md) | LangGraph 상태 그래프 적용 선행 사례(단, §1-2의 체크포인터 기술은 부정확 — §1 참고) |
| `fastapi/CLAUDE.md` | 백엔드 레이어·경로·네이밍·스타 토폴로지 규칙 |
| `admin/app/use_cases/pdf_loader_interactor.py` | 확장 대상 — 현재 텍스트 추출 후 `(:Document)` 저장까지만 |
| `admin/adapter/outbound/repositories/pdf_document_repository.py` | 현재 `(:Document)` 평면 노드 적재 구현 |
| `ontology/adapter/outbound/embedding_router_generator.py` | 시맨틱 라우터 실제 구현(pgvector 아님 — §1 참고) |
