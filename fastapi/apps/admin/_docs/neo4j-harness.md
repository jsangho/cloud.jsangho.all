# NEO4J-HARNESS.md

`admin` 앱에서 그래프 DB(Neo4j)를 운영하기 위한 하네스 문서.

---

## 0. 현재 상태 (실제 확인한 내용)

- Neo4j는 리포 루트 `docker-compose.yaml`의 `neo4j` 서비스로 이미 떠 있다(`image: neo4j:5`, 포트 `7474`(브라우저 UI)/`7687`(Bolt), 볼륨 `neo4j_data`).
- 인증 정보는 `.env`의 `NEO4J_URI`(`bolt://neo4j:7687`) · `NEO4J_USER`(`neo4j`) · `NEO4J_PASSWORD`로 주입된다.
- `admin` 앱에는 `domain/piper_hendricks_ceo_topology.py`에 `# 그래프 노드 정의`라는 주석만 있고, 실제로 Neo4j 드라이버를 호출하는 코드는 아직 없다(리포 전체에서 `neo4j`/`GraphDatabase` import는 0건).
- 즉 지금은 컨테이너만 기동돼 있고, 실제 그래프 모델링·연동은 이 문서를 기준으로 시작하는 단계다.

---

## 1. 그래프 데이터 모델 — 노드 · 라벨 · 관계 · 속성

그래프 데이터는 **노드(node)**, **라벨(label)**, **관계(relationship)**, **속성(property)** 네 가지로 정의되며, 노드와 관계가 그래프를 구성하는 기본 단위다.

### 1-1. 노드 (Node)

그래프에서 동그라미로 표현되는 각각의 것. 노드를 통해 엔티티(개체)를 식별한다.

### 1-2. 라벨 (Label)

노드에 적힌 `Person`, `Book` 같은 이름으로, 노드의 분류에 사용된다.

- 예: `Person` 라벨을 가진 노드 두 개, `Book` 라벨을 가진 노드 한 개.

### 1-3. 관계 (Relationship)

두 노드를 연결하며, 화살표로 방향을 표현할 수 있다.

- 두 명의 `Person`이 한 권의 `Book`을 "읽었다"는 것을 표현하려면 `:HAS_READ` 관계로 `Person`→`Book`을 연결한다.
- 두 `Person`이 "친구다"는 것을 표현하려면 `:IS_FRIENDS_WITH` 관계로 연결한다.

### 1-4. 속성 (Property)

노드 및 관계에 설명을 추가하기 위한 key-value 값.

- `Person` 노드에 이름과 나이를 표현하려면 `name`, `age` 속성을 추가한다. 이 속성으로 각 노드를 식별할 수 있다.
- `:HAS_READ` 관계에 "언제 읽었는지"를 표현하려면 관계 자체에 `on` 속성(날짜)을 추가한다.

### 1-5 예시 (Cypher)

위 모델을 Neo4j 브라우저(`http://<host>:7474`)나 드라이버로 그대로 만들면:

```cypher
CREATE (a:Person {name: "Alice", age: 30})
CREATE (b:Person {name: "Bob", age: 32})
CREATE (book:Book {title: "The Pragmatic Programmer"})

CREATE (a)-[:HAS_READ {on: date("2026-05-01")}]->(book)
CREATE (b)-[:HAS_READ {on: date("2026-06-12")}]->(book)
CREATE (a)-[:IS_FRIENDS_WITH]->(b)
```

- `Person`·`Book`은 라벨, `Alice`/`Bob`/`The Pragmatic Programmer`가 각 노드, `name`/`age`/`title`이 노드 속성, `HAS_READ`/`IS_FRIENDS_WITH`가 관계, `on`이 관계 속성이다.

---

## 2. 관련 문서

| 문서 | 역할 |
|------|------|
| `fastapi/CLAUDE.md` | 백엔드 행동 지침(레이어·경로 규칙) |
| `docker-compose.yaml` (`neo4j` 서비스) | 실제 컨테이너 설정 |
| `.env.example` (`NEO4J_*`) | 접속 정보 키 목록 |
