# LANGCHAIN-MORNINGSTAR-STRATEGY.md

Morningstar 사례([[langchain-harness]] 참고)를 이 리포에 적용하기 위한 전략 문서. 코드는 아직 없다 — 구현은 별도 요청 시 진행한다.

---

## 0. 사례 요약

금융 서비스 제공업체 Morningstar는 LangChain을 사용해 방대한 재무 보고서와 시장 데이터를 분석하고, 이를 바탕으로 사용자 맞춤형 금융 인사이트를 제공하는 인텔리전스 엔진을 개발했다. 금융 전문가가 복잡한 질문에 정확한 답변을 얻도록 돕고, LangChain의 실시간 데이터 통합·맞춤형 프롬프팅 기능을 활용한다.

---

## 1. 이 리포에 적용할 구조

```
재무 보고서(PDF)            시장 데이터(선택 범위 — 미정)
      │                              │
      ▼                              ▼
PdfLoaderInteractor            (미정: 실시간 조회 Tool)
      │ (기존, neo4j-graphrag)        │
      ▼                              │
텍스트 추출 → 임베딩 저장(pgvector) ◄─┘
      │
      ▼
LangChain Retriever (pgvector 유사도 검색)
      │
      ▼
ChatGoogleGenerativeAI (langchain-google-genai)
      │  ← 프롬프트 템플릿(사용자 맞춤 컨텍스트 주입)
      ▼
맞춤형 금융 인사이트 응답
```

### 1-1. 확정된 결정

| 항목 | 결정 |
|------|------|
| 벡터 저장소 | **PostgreSQL pgvector** — 기존 의존성 재사용, Neo4j 문서 파이프라인과는 별도 테이블로 운영 |
| LLM 연동 | **langchain-google-genai + Keymaker** — API 키는 기존 `vault_keymaker_secret_manager.get_keymaker()`로 조회하되, 실제 호출은 LangChain의 `ChatGoogleGenerativeAI`로 감싸 체이닝/프롬프트 템플릿을 그대로 활용 |

### 1-2. 미정 사항 (구현 전 재확인 필요)

- **실시간 시장 데이터 조회 포함 여부** — 이번 전략 수립 시점에는 미결정. 포함 시 별도 LangChain Tool(외부 시세 API 연동 또는 플레이스홀더)을 추가하는 방식으로 확장.
- 임베딩 모델 선택(Google embedding vs 별도 오픈소스).
- 청킹 전략(문단 단위 vs 토큰 윈도우) — `pdf_loader_interactor.py`가 현재 문서 전체 텍스트를 그대로 저장하므로, 검색 품질을 위한 청킹 단계 추가 여부 결정 필요.

---

## 2. 레이어 배치 (fastapi/CLAUDE.md 규칙 적용)

| 레이어 | 파일(예정) | 역할 |
|--------|-----------|------|
| `app/ports/input` | `langchain_morningstar_use_case.py` | 맞춤형 인사이트 조회 UseCase(Protocol) |
| `app/use_cases` | `langchain_morningstar_interactor.py` | 검색(pgvector) → 프롬프트 조립 → LLM 호출 오케스트레이션 |
| `app/ports/output` | `langchain_morningstar_port.py` | 벡터 검색 포트(Protocol) |
| `adapter/outbound/repositories` | `langchain_morningstar_repository.py` | pgvector 기반 벡터 검색 구현체 |
| `adapter/inbound/api` | `langchain_morningstar_router.py` / `_schema.py` | 질의 API 엔드포인트 |
| `dependencies` | `langchain_morningstar_provider.py` | DI 팩토리 |

domain 레이어는 프레임워크 비의존 유지 원칙(`fastapi/CLAUDE.md` §2)을 따라, LangChain·pgvector 관련 타입은 `adapter`/`app` 레이어에만 존재하고 `domain/`에는 노출하지 않는다.

---

## 3. 신규 의존성 (구현 시 추가 필요, 아직 미추가)

```
langchain
langchain-google-genai
langchain-postgres   # 또는 langchain-community의 PGVector
```

> `pyproject.toml`에는 아직 반영되지 않았다. Docker 개발 원칙(루트 `CLAUDE.md`)에 따라 우선 `docker compose exec`로 설치해 검증 후, 사용자가 "빌드해줘"라고 명시할 때 이미지에 반영한다.

---

## 4. 관련 문서

| 문서 | 역할 |
|------|------|
| `apps/admin/_docs/langchain-harness.md` | LangChain 개념·현재 상태 하네스 |
| `apps/admin/_docs/neo4j-harness.md` | 기존 Neo4j 문서 저장 파이프라인 |
| `apps/admin/app/use_cases/pdf_loader_interactor.py` | 현재 구현된 PDF 텍스트 추출(재무 보고서 소스) |
