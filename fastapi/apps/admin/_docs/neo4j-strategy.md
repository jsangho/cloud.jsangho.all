# NEO4J-STRATEGY.md

[langgraph-harness](./langgraph-harness.md)의 GraphRAG 설계(§2)를 실제로 돌리기 위해 Docker의 Neo4j 서비스를 어떻게 구성할지 정리하는 전략 문서. **신규 컨테이너를 만드는 문서가 아니다** — Neo4j는 이미 떠 있으므로, 기존 서비스 설정을 확장하는 변경안만 다룬다. 설정은 아직 적용하지 않았다 — 적용은 사용자 승인 후 별도로 진행한다.

---

## 0. 현재 상태 (실제 확인한 내용)

루트 `docker-compose.yaml`에 이미 정의돼 있다(`docker-rules.md`의 "중복 생성 금지" 원칙에 따라, 이 문서는 새 서비스를 추가하지 않고 아래 정의를 확장하는 것만 다룬다):

```yaml
neo4j:
  image: neo4j:5
  restart: unless-stopped
  ports:
    - "7474:7474"   # Neo4j Browser (HTTP)
    - "7687:7687"   # Bolt (드라이버 접속)
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
  volumes:
    - neo4j_data:/data
  healthcheck:
    test: ["CMD-SHELL", "wget -q --spider http://localhost:7474 || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
    start_period: 30s
```

- `.env.example`에 `NEO4J_URI=bolt://neo4j:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=`가 이미 정의돼 있다.
- `backend` 서비스가 `depends_on: neo4j: condition: service_healthy`로 묶여 있어, Neo4j가 healthy해야 백엔드가 뜬다.
- 플러그인(`NEO4J_PLUGINS`)·메모리(`NEO4J_server_memory_*`) 설정은 **아무것도 지정돼 있지 않다** — 전부 이미지 기본값이다.
- 이미지 태그가 `neo4j:5`로, 마이너 버전이 고정돼 있지 않다(재빌드/재풀 시점마다 최신 5.x로 바뀔 수 있음).
- `langgraph-harness.md` §0에서 확인했듯, 실제로 쓰는 코드(`pdf_document_repository.py`)는 `(:Document)` 평면 노드 `MERGE` 정도만 한다 — 지금 설정은 그 정도 용도로는 충분했지만, GraphRAG(벡터 인덱스, 스키마 조회)를 쓰기엔 검증되지 않은 상태다.

---

## 1. langgraph-harness.md 요구사항 대비 설정 갭

| 필요 기능 (langgraph-harness §2 근거) | 필요 설정 | 현재 상태 | 갭 |
|---|---|---|---|
| 벡터 인덱스 기반 하이브리드 검색 (§2-3) | Neo4j 5.11+ 필요(`CREATE VECTOR INDEX` 네이티브 지원) | `neo4j:5`는 5.11 이상을 포함하지만 마이너 버전 미고정 | 버전 고정 여부 결정 필요 |
| `Neo4jGraph`/`GraphCypherQAChain` 스키마 조회 (§2-2, `langchain-neo4j` 도입 시) | 일부 버전은 스키마 조회에 `apoc.meta.data()` 사용 — APOC 플러그인 필요 | `NEO4J_PLUGINS` 미설정, APOC 없음 | `langchain-neo4j` 도입 시점에 실제 필요 여부 재확인 후 추가 |
| 지식 그래프 Ingestion(엔티티/관계 추출, §2-1) 시 대량 쓰기 | 힙/페이지캐시 메모리 여유 | `NEO4J_server_memory_*` 미지정(기본값) | 워크로드 커지면 튜닝 필요 |
| Cypher 디버깅 | Browser UI | `7474` 포트로 이미 노출됨 | 갭 없음 |
| 헬스체크 기반 기동 순서 | `backend`가 healthy 이후 기동 | 이미 구성됨 | 갭 없음 |

---

## 2. 적용할 docker-compose 변경안 (제안 — 미적용)

```yaml
neo4j:
  image: neo4j:5.26          # (안) 마이너 버전 고정 — §2-2 미정 사항 참고
  restart: unless-stopped
  ports:
    - "7474:7474"
    - "7687:7687"
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    NEO4J_PLUGINS: '["apoc"]'                        # (안) langchain-neo4j 스키마 조회용
    NEO4J_server_memory_heap_max__size: 1G            # (안) §2-2 미정 — 실제 EC2 스펙 확인 후 조정
    NEO4J_server_memory_pagecache_size: 512M          # (안) 동일
  volumes:
    - neo4j_data:/data
  healthcheck:
    test: ["CMD-SHELL", "wget -q --spider http://localhost:7474 || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
    start_period: 60s        # (안) APOC 플러그인 최초 다운로드 시간 고려해 상향
```

### 2-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| 신규 컨테이너 생성 여부 | **하지 않는다** — 기존 `neo4j` 서비스 정의를 그대로 확장한다(`docker-rules.md`) |
| 데이터 볼륨 | `neo4j_data`(named volume) 그대로 유지 — 환경변수/플러그인 변경은 데이터에 영향 없음 |
| 적용 시점 | 사용자가 명시적으로 요청할 때만 `docker compose up -d neo4j`로 재기동(루트 `CLAUDE.md` Docker 워크플로우 원칙 — 빌드/재기동은 AI가 임의로 하지 않는다) |

### 2-2. 미정 사항 (적용 전 재확인 필요)

- **이미지 마이너 버전 고정** — `neo4j:5.26`은 예시일 뿐, 실제로 고정할지·어떤 버전으로 고정할지 결정 필요. 고정하지 않으면 향후 `docker compose pull` 시 예고 없이 버전이 바뀔 수 있다는 리스크만 문서화해둔다.
- **APOC 플러그인 실제 필요 여부** — `langchain-neo4j`는 현재 미설치(`langgraph-harness.md` §0)라 지금은 확정할 수 없다. 도입 시점에 해당 버전 문서로 `Neo4jGraph.refresh_schema()`가 APOC 없이도 동작하는지 재확인 후 결정한다.
- **메모리 튜닝 값** — 실제 운영 환경은 AWS EC2(`ssh aws-ec2`)이며, 인스턴스 스펙(가용 RAM)을 확인하지 않고 하드코딩하면 다른 컨테이너(backend·pgvector·redis·n8n)와 리소스 경합이 날 수 있다. 적용 전 EC2 인스턴스 스펙 확인 필요.
- **healthcheck `start_period` 상향 여부** — APOC 최초 설치 시 기동이 느려질 수 있어 60초로 늘리는 안을 제시했지만, 실측 없이 확정하지 않는다.
- **NEO4J_PLUGINS 확장 여부** — GraphRAG 벡터 인덱스 자체는 APOC 없이도 네이티브로 동작하므로, APOC이 정말 불필요하다고 확인되면 이 항목은 통째로 빠질 수 있다.

---

## 3. 적용 절차 (변경 확정 시)

1. §2-2 미정 사항에 대한 답을 사용자에게 받는다.
2. `docker-compose.yaml`의 `neo4j` 서비스 블록만 수정한다(다른 서비스는 건드리지 않는다).
3. 새 환경변수가 필요하면 `.env.example`에도 키를 추가한다(값은 비워둔다).
4. 사용자 승인 후에만 `docker compose up -d neo4j`로 재기동한다 — `docker compose build`/`--build`는 이미지가 `neo4j:5`(공식 이미지) 그대로이므로 애초에 불필요하다.
5. 재기동 후 `docker compose ps`로 `healthy` 상태를 확인하고, 필요하면 Neo4j Browser(`http://<host>:7474`)에서 `CALL dbms.components()`로 버전을, `CALL apoc.help("meta")`(APOC 추가 시)로 플러그인 로드를 확인한다.

---

## 4. 관련 문서

| 문서 | 역할 |
|------|------|
| `apps/admin/_docs/langgraph-harness.md` | 이 설정이 필요한 이유(GraphRAG/reasoning 라우팅 설계) |
| `apps/admin/_docs/neo4j-harness.md` | Neo4j 그래프 데이터 모델(노드/라벨/관계/속성) 기본 개념 |
| `_docs/docker-rules.md` | 컨테이너 중복 생성 금지 원칙(이 문서가 신규 서비스를 만들지 않는 근거) |
| `docker-compose.yaml` (`neo4j` 서비스) | 실제 변경 대상 |
| `.env.example` (`NEO4J_*`) | 접속 정보·신규 환경변수 키 목록 |
| 루트 `CLAUDE.md` "Docker 개발 워크플로우" | 빌드/재기동을 사용자 명시 요청 시에만 하는 원칙 |
