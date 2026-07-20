# Ontology Hub — Graph DB · Vector DB 파이프라인 전략

## 1. 목적

`ontology` 는 스타 토폴로지의 **허브** 앱이다.  
모든 스포크(titanic, kayfabe, user, human_resource …)의 도메인 지식을 중앙에서 조율하기 위해 두 가지 전문 DB가 필요하다.

| DB 종류 | 역할 |
|---------|------|
| **Graph DB** (Neo4j) | 스포크 간 엔티티 관계·온톨로지 인덱스 저장 |
| **Vector DB** (Qdrant) | 도메인 임베딩 저장 · 시맨틱 검색 · RAG 컨텍스트 조회 |

---

## 2. Docker 서비스 구성

```yaml
# docker-compose.yml 추가 서비스
services:
  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt (Python 드라이버 연결)
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"   # HTTP REST
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  neo4j_data:
  qdrant_data:
```

### 환경변수 (.env)

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## 3. 헥사고날 레이어 매핑

```
ontology/
├── domain/
│   ├── entities/          ← 온톨로지 노드·엣지 엔티티 (순수 파이썬)
│   └── value_objects/     ← NodeId, EdgeType, EmbeddingVector
│
├── app/
│   ├── ports/output/
│   │   ├── graph_repository.py    ← GraphRepository (Protocol)
│   │   └── vector_repository.py   ← VectorRepository (Protocol)
│   └── use_cases/
│       ├── ontology_index_use_case.py   ← 관계 등록·조회
│       └── context_router_use_case.py   ← 시맨틱 라우팅
│
├── adapter/outbound/
│   ├── graph/
│   │   ├── neo4j_client.py              ← Neo4j AsyncDriver 래퍼
│   │   └── neo4j_graph_repository.py    ← GraphRepository 구현체
│   └── vector/
│       ├── qdrant_client.py             ← Qdrant AsyncClient 래퍼
│       └── qdrant_vector_repository.py  ← VectorRepository 구현체
│
└── dependencies/
    ├── graph_provider.py    ← get_graph_repository()
    └── vector_provider.py   ← get_vector_repository()
```

의존성 방향: `adapter/outbound → app/ports → domain` (역방향 금지)

---

## 4. Graph DB 파이프라인 (Neo4j)

### 목적
- 스포크 앱 엔티티(user, passenger, fighter …) 간 **관계(Relationship)** 를 그래프로 저장
- 허브가 컨텍스트 라우팅 시 "어느 스포크가 이 질의와 연관되는가"를 그래프 탐색으로 결정

### 데이터 모델 (예시)

```cypher
// 노드
(:Domain {name: "kayfabe"})
(:Domain {name: "titanic"})
(:Concept {name: "생존율", domain: "titanic"})
(:Concept {name: "챔피언십", domain: "kayfabe"})

// 관계
(:Concept)-[:BELONGS_TO]->(:Domain)
(:Concept)-[:RELATED_TO {weight: 0.8}]->(:Concept)
```

### 핵심 인터페이스

```python
# app/ports/output/graph_repository.py
from typing import Protocol

class GraphRepository(Protocol):
    async def upsert_node(self, label: str, props: dict) -> str: ...
    async def upsert_edge(self, from_id: str, to_id: str, rel_type: str, props: dict = {}) -> None: ...
    async def find_related(self, node_id: str, depth: int = 2) -> list[dict]: ...
```

### 연결 전략

- 드라이버: `neo4j` Python 패키지 (`AsyncGraphDatabase.driver`)
- 연결은 앱 시작 시 1회 생성, `lifespan` 훅에서 `close()`
- 세션은 요청마다 `async with driver.session() as session:` 으로 단위 관리

---

## 5. Vector DB 파이프라인 (Qdrant)

### 목적
- 스포크 도메인 문서·지식의 **임베딩** 을 컬렉션별로 저장
- LLM(exaone3.5:2.4b) RAG 파이프라인에서 시맨틱 검색으로 관련 컨텍스트 주입
- `FakerOrchestrator.chat()` 호출 전 벡터 검색 결과를 system prompt에 삽입

### 컬렉션 설계

| 컬렉션 | 스포크 | 벡터 크기 |
|--------|-------|-----------|
| `ontology_hub` | hub | 모델 의존 |
| `titanic_docs` | titanic | 모델 의존 |
| `kayfabe_docs` | kayfabe | 모델 의존 |

### 핵심 인터페이스

```python
# app/ports/output/vector_repository.py
from typing import Protocol

class VectorRepository(Protocol):
    async def upsert(self, collection: str, doc_id: str, vector: list[float], payload: dict) -> None: ...
    async def search(self, collection: str, query_vector: list[float], top_k: int = 5) -> list[dict]: ...
    async def ensure_collection(self, collection: str, vector_size: int) -> None: ...
```

### 연결 전략

- 클라이언트: `qdrant-client` Python 패키지 (`AsyncQdrantClient`)
- `ensure_collection()` 을 앱 시작 시 호출해 컬렉션 자동 생성
- 임베딩 생성은 `FakerOrchestrator.generate()` 또는 별도 embedding 모델로 위임

---

## 6. 전체 데이터 흐름

```
사용자 질의
    │
    ▼
[ontology] ContextRouterUseCase
    │
    ├─① VectorRepository.search()  ──→ Qdrant  ──→ 관련 청크 top-k
    │                                               │
    ├─② GraphRepository.find_related() → Neo4j ──→ 연관 스포크·개념
    │                                               │
    └─③ FakerOrchestrator.chat()   ──→ Ollama (exaone3.5:2.4b)
           ↑ system prompt에 ①②를 주입
```

---

## 7. 구현 순서 (단계별)

| 단계 | 작업 | 검증 |
|------|------|------|
| 1 | `docker-compose.yml` 에 Neo4j · Qdrant 서비스 추가 | `docker compose up` 정상 기동 |
| 2 | `Neo4jClient` · `QdrantClient` 래퍼 작성 | 연결 ping 성공 |
| 3 | `GraphRepository` · `VectorRepository` Protocol 정의 | `mypy` 통과 |
| 4 | Neo4j · Qdrant 구현체 작성 | 단위 테스트 (mock 없이 로컬 Docker) |
| 5 | `dependencies/` 프로바이더 등록 | FastAPI DI 주입 확인 |
| 6 | `ContextRouterUseCase` 에 두 저장소 연결 | E2E 시나리오 테스트 |
| 7 | `FakerOrchestrator` RAG 통합 | 질의 응답 품질 확인 |

---

## 8. 패키지 의존성

```toml
# pyproject.toml 추가
neo4j = ">=5.0"
qdrant-client = ">=1.9"
```
