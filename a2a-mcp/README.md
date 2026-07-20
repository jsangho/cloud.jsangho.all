# a2a-mcp

A2A-over-MCP 멀티 에이전트 포트폴리오 프로젝트. 3개 에이전트가 각자 MCP 서버로 노출되고, 서로를
MCP 클라이언트로 호출한다 (Agent-to-Agent over Model Context Protocol).

## 아키텍처

- **온프레미스 우분투 서버 (RTX 3050 6GB)**: `agents/exaone`(EXAONE 3.5 2.4B), `agents/qwen`
  (Qwen2.5 3B) — 둘 다 Ollama로 구동. Neo4j 그래프 DB도 이 서버에 동거하며, **온프레미스 에이전트만
  Neo4j에 직접 접근**한다.
- **AWS (t4g.micro 또는 Lambda)**: `agents/aws_router` — LLM·GPU·그래프 DB 의존성이 전혀 없는
  오케스트레이터/라우터. 온프레미스 에이전트와는 Cloudflare Tunnel/Tailscale을 경유해 통신하며,
  그래프 DB 데이터는 반드시 MCP 경유로만 접근한다.
- 결과물은 온프레미스 FastAPI → Vercel fetch로 프론트엔드에 전달된다.

## 디렉터리 구조

```
a2a-mcp/
├── shared/            # a2a-shared — A2A 메시지 스키마(pydantic) 단일 소스
├── agents/
│   ├── exaone/        # agent-exaone
│   ├── qwen/          # agent-qwen
│   └── aws_router/     # agent-aws-router (LLM 없음)
└── README.md
```

## 패키징 원칙

- **uv workspace를 쓰지 않는다.** 배포 대상이 물리적으로 분리되어 있으므로(온프레미스 서버 vs AWS),
  `shared/`·`agents/exaone/`·`agents/qwen/`·`agents/aws_router/` 각각이 독립적인 `uv sync` 단위다.
- `a2a-shared`는 각 에이전트에서 `path = "../../shared", editable = true`로 로컬 참조한다. 배포 시
  `shared/` 디렉터리가 함께 복사되어야 하며, 모노레포 전체를 clone하는 한 항상 충족된다.
- 스키마 변경은 반드시 `shared/`에서만 한다. 에이전트 개별 디렉터리에 스키마를 복제하지 않는다.
- 버전 상한(`<`)은 지정하지 않는다. 잠금은 각 디렉터리의 `uv.lock`이 담당한다.
- 파이썬 버전은 `>=3.11` 고정. 온프레미스 서버와 AWS 인스턴스 간 버전 일치를 확인해야 한다.

## 로컬 검증

```bash
cd shared && uv sync && cd ..
cd agents/exaone && uv sync && cd ../..
cd agents/qwen && uv sync && cd ../..
cd agents/aws_router && uv sync && cd ../..

cd agents/exaone && uv run python -c "from a2a_shared.schemas import A2AMessage; print('ok')"

cd agents/aws_router && uv pip list | grep -E "ollama|neo4j" && echo "FAIL: 금지 의존성 발견" || echo "ok"
```
