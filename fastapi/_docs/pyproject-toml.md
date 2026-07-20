# A2A 멀티 에이전트 프로젝트 — pyproject.toml 하네스 스펙

## 실행 결과 (요약)

`cloud.jsangho.all/a2a-mcp/`에 아래 스펙대로 디렉터리·파일을 생성하고, 실행 지침에 명시된 검증을
모두 통과시켰다.

- `shared/`, `agents/exaone/`, `agents/qwen/`, `agents/aws_router/` 4곳 모두 `uv sync` 성공
  (호스트에 `uv`가 없어 `pipx install uv`로 설치 후 실행).
- `agents/exaone`에서 `uv run python -c "from a2a_shared.schemas import A2AMessage; print('ok')"` → `ok`.
  `a2a-shared`의 로컬 editable path 의존성(`../../shared`)이 정상 작동함을 확인.
- `agents/aws_router`의 `uv pip list`에 `ollama`/`neo4j`가 없음을 확인 (`ok`) — LLM·그래프 DB 의존성이
  섞여 들어가지 않았다.
- 각 디렉터리에 `.venv/`와 `uv.lock`이 생성됨. `.venv/`는 루트 `.gitignore`의 `.venv/` 패턴(깊이 무관 매치)
  으로 이미 커밋 제외 대상이고, `uv.lock`은 잠금 목적상 커밋 대상.
- `fastapi/` 앱과는 별개의 독립 프로젝트다 (기존 `fastapi/`의 `mcp`·`neo4j`·`ollama` 의존성과는 무관하게
  분리 배포).

---

## 목적

3개 에이전트(온프레미스 EXAONE, 온프레미스 Qwen, AWS 라우터)로 구성된 A2A-over-MCP 포트폴리오
프로젝트의 파이썬 패키징 구조를 생성한다. 패키지 관리자는 `uv`를 사용한다.

## 아키텍처 전제

- 온프레미스 우분투 서버(RTX 3050 6GB): EXAONE 3.5 2.4B, Qwen2.5 3B를 Ollama로 구동. 그래프 DB
  (Neo4j) 동거.
- AWS(t4g.micro 또는 Lambda): LLM 없는 오케스트레이터/라우터 에이전트. 온프레미스와 Cloudflare
  Tunnel/Tailscale 경유 통신.
- 각 에이전트는 MCP 서버로 노출되며, 상대 에이전트를 MCP 클라이언트로 호출한다 (A2A over MCP).
- 그래프 DB는 온프레미스 에이전트만 직접 접근한다. AWS 라우터는 MCP 경유로만 데이터에 접근한다.
- 결과물은 Vercel 프론트엔드로 전달된다 (온프레미스 FastAPI → Vercel fetch).

## 디렉터리 구조 (생성 대상)

```
a2a-mcp/
├── shared/
│   ├── pyproject.toml
│   └── src/
│       └── a2a_shared/
│           ├── __init__.py
│           └── schemas.py          # A2A 메시지 스키마 (pydantic)
├── agents/
│   ├── exaone/
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── agent_exaone/
│   │           └── __init__.py
│   ├── qwen/
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── agent_qwen/
│   │           └── __init__.py
│   └── aws_router/
│       ├── pyproject.toml
│       └── src/
│           └── agent_aws_router/
│               └── __init__.py
└── README.md
```

주의: uv workspace를 사용하지 않는다. 배포 대상이 물리적으로 분리되어 있으므로(우분투 서버 vs AWS),
각 에이전트 디렉터리가 독립적인 `uv sync` 단위가 된다.

## 제약 사항

- 파이썬 버전은 3.11 고정 (`requires-python = ">=3.11"`). 서버와 AWS 인스턴스 간 버전 일치 확인 필요.
- `a2a-shared`는 editable 로컬 경로 의존성이다. 배포 시 각 서버에 `shared/` 디렉터리가 함께 복사되어야
  한다 (git clone 단위가 모노레포 전체이므로 충족됨).
- 버전 상한(`<`)은 지정하지 않는다. 잠금은 `uv.lock`이 담당한다.
- 스키마 변경은 반드시 `shared/`에서만 한다. 에이전트 개별 디렉터리에 스키마를 복제하지 않는다.

## 실행 지침

1. 디렉터리 구조 생성. 각 `__init__.py`는 빈 파일.
2. `shared/pyproject.toml`, `agents/{exaone,qwen,aws_router}/pyproject.toml`,
   `shared/src/a2a_shared/schemas.py` 작성 (내용은 `a2a-mcp/` 각 파일 참조).
3. 각 에이전트 디렉터리에서 `uv sync` 성공 검증.
4. `agents/exaone`에서 공통 스키마 import 검증
   (`uv run python -c "from a2a_shared.schemas import A2AMessage; print('ok')"`).
5. `agents/aws_router` 환경에 `ollama`, `neo4j`가 설치되지 않았음을 확인
   (`uv pip list | grep -E "ollama|neo4j"` → 미검출이어야 `ok`).

실제 파일 내용과 검증 명령 결과는 `a2a-mcp/README.md`와 이 문서 상단의 "실행 결과" 절 참고.
