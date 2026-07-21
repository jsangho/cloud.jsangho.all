# Harness: ConvNeXt Nano 이미지 분류 에이전트 구축

## 목적 (Goal)
`timm`의 `convnext_nano` 모델을 사용하는 이미지 분류 기능을, MCP 툴로 노출 가능한 FastAPI 서비스로 구현한다. 최종 산출물은 다른 LLM 에이전트(EXAONE-3.5, Qwen2.5, Claude 등)가 신뢰도 기반으로 결과를 해석하고 후속 행동을 결정할 수 있는 구조여야 한다.

## 컨텍스트 (Context)
- 실행 환경: RTX 3050 8GB VRAM, 로컬 Ubuntu/WSL 서버 (`messi@DESKTOP-9E3A4EC`, `192.168.0.5`)
- 기존 스택: FastAPI 백엔드, PostgreSQL(pgvector), Neo4j, Redis, Docker Compose
- 패키지 관리: `uv` + `pyproject.toml` (requirements.txt 사용 안 함)
- MCP 라우팅: Cloudflare Tunnel 경유 `mcp.jsangho.cloud`
- 공개 API 엔드포인트 패턴: `api.jsangho.cloud` (Cloudflare Tunnel)
- 목표 모델: `convnext_nano` (timm, pretrained=True 기반, 커스텀 헤드 교체 가능성 있음)

## 범위 (Scope)
포함:
1. 모델 로딩/추론 모듈
2. FastAPI `/classify` 엔드포인트
3. MCP 서버 tool 등록 (`classify_image`)
4. Claude Code용 SKILL.md 작성
5. Docker Compose 서비스 통합
6. 기본 단위 테스트

제외 (별도 작업으로 분리):
- 커스텀 데이터셋 기반 파인튜닝 파이프라인 (헤드 교체 학습 루프)
- 프론트엔드(Next.js) UI 연동

---

## 작업 순서 (Tasks)

### Task 1. 프로젝트 구조 및 의존성 설정
- `services/image-classifier/` 디렉토리 생성
- `pyproject.toml`에 다음 의존성 추가 (uv 사용):
  - `timm`, `torch` (CUDA 12.x 빌드, RTX 3050 호환 버전 확인), `fastapi`, `uvicorn`, `pillow`, `pydantic`, `mcp`
- `uv sync`로 lock 파일 생성
- **완료 조건**: `uv run python -c "import timm, torch; print(torch.cuda.is_available())"` 가 `True` 반환

### Task 2. 모델 로딩 모듈 작성 (`model.py`)
- `timm.create_model('convnext_nano', pretrained=True, num_classes=N)` 로 모델 로드
- `timm.data.resolve_data_config` + `create_transform`으로 전처리 파이프라인 구성
- 모델은 서버 시작 시 1회만 로드하는 싱글턴 패턴으로 구현 (매 요청마다 재로딩 금지)
- GPU 사용 가능 시 `.to('cuda')`, 불가 시 CPU 폴백
- **완료 조건**: 샘플 이미지 1장으로 추론했을 때 `torch.Size([1, N])` 형태의 로짓 출력 확인

### Task 3. FastAPI 엔드포인트 작성 (`main.py`)
- `POST /classify` 엔드포인트, `UploadFile` 입력
- 응답 스키마 (Pydantic `ClassificationResult`):
  ```python
  class TopKPrediction(BaseModel):
      label: str
      score: float

  class ClassificationResult(BaseModel):
      label: str          # top-1 라벨
      confidence: float   # top-1 softmax 확률
      is_confident: bool  # confidence >= threshold (기본 0.5)
      top5: list[TopKPrediction]
  ```
- 이미지 검증 실패(포맷 오류, 손상 파일) 시 422 에러와 함께 명확한 메시지 반환
- softmax 후 top-5 추출 로직 포함
- confidence threshold는 환경변수로 조정 가능하게 (`CLASSIFIER_CONFIDENCE_THRESHOLD`, 기본값 0.5)
- **완료 조건**: `curl -F "image=@sample.jpg" http://localhost:PORT/classify` 로 위 스키마 형태 JSON 응답 확인

### Task 4. MCP 서버 tool 등록 (`mcp_server.py`)
- MCP `Server` 인스턴스 생성, tool 이름: `classify_image`
- **description 작성 시 반드시 아래 내용 포함** (에이전트의 도구 선택 정확도에 직접 영향):
  - 이 도구가 하는 일: 단일 이미지에 대한 단일 라벨 분류 (다중 객체 탐지 아님)
  - 언제 쓰면 안 되는지: 이미지 내 여러 객체를 각각 구분해야 하는 경우 부적합
  - 출력 해석 가이드: `is_confident=false`인 경우 결과를 단정적으로 사용하지 말고 top5 후보를 사용자에게 제시하거나 재확인 요청할 것
- inputSchema: `image_path` (string, 필수) — 로컬 경로 또는 접근 가능한 URL
- 내부적으로 FastAPI `/classify`를 호출하거나, model.py를 직접 import하여 중복 로딩 없이 처리 (두 방식 중 인프라에 맞는 쪽 선택, 선택 이유를 주석으로 남길 것)
- 기존 `mcp.jsangho.cloud` 라우팅 설정에 새 tool이 등록되도록 Cloudflare Tunnel 설정 확인/업데이트
- **완료 조건**: MCP 클라이언트에서 `classify_image` tool 목록 조회 시 정상 노출, 실제 호출 시 Task 3과 동일한 스키마 응답

### Task 5. Claude Code용 SKILL.md 작성
- 경로: `services/image-classifier/SKILL.md` (또는 프로젝트 skill 디렉토리 컨벤션에 맞춰 배치)
- 프론트매터에 `name`, `description` 포함 — description은 "언제 이 스킬을 트리거해야 하는지"가 명확히 드러나도록 작성 (예: "ConvNeXt Nano 이미지 분류 파이프라인 구축, 디버깅, 파인튜닝 관련 요청 시 사용")
- 본문에 포함할 내용:
  - 환경 정보 (VRAM, 배치 크기 권장값: 8GB 기준 32~64)
  - 표준 워크플로우 (모델 로드 → 전처리 구성 → 추론 → top5+confidence 응답)
  - 트러블슈팅 섹션 (CUDA OOM 시 배치 크기 축소, pretrained 가중치 다운로드 실패 시 캐시 경로 확인 등)
- **완료 조건**: 새 Claude Code 세션에서 이 SKILL.md만 보고 별도 설명 없이 추론 코드 작성 가능한 수준의 자기완결성

### Task 6. Docker Compose 통합
- 기존 `docker-compose.yml`에 `image-classifier` 서비스 추가
- GPU 접근을 위한 `deploy.resources.reservations.devices` 설정 (nvidia runtime)
- 헬스체크 엔드포인트 `/health` 추가 및 compose healthcheck 연결
- **완료 조건**: `docker compose up image-classifier` 로 정상 기동, `/health` 200 응답

### Task 7. 테스트 작성
- `pytest` 기반 단위 테스트:
  - 정상 이미지 입력 시 응답 스키마 검증
  - 손상된 파일 입력 시 422 에러 검증
  - confidence threshold 경계값 테스트 (0.5 부근)
- **완료 조건**: `uv run pytest` 전체 통과

---

## 산출물 체크리스트
- [ ] `pyproject.toml` 업데이트 및 `uv.lock`
- [ ] `services/image-classifier/model.py`
- [ ] `services/image-classifier/main.py`
- [ ] `services/image-classifier/mcp_server.py`
- [ ] `services/image-classifier/SKILL.md`
- [ ] `docker-compose.yml` 수정본
- [ ] `tests/test_classifier.py`

## 제약사항 (Constraints)
- requirements.txt 방식 사용 금지, 반드시 `uv` + `pyproject.toml`
- 모델은 요청마다 재로딩하지 않는다 (싱글턴/앱 lifespan 이벤트 활용)
- 모든 신규 코드는 타입힌트 포함
- 민감 정보(내부 IP, 토큰 등)는 `.env`로 분리, 코드에 하드코딩 금지

## 후속 작업 (Out of Scope, 별도 요청 예정)
- 커스텀 라벨셋 기반 파인튜닝 (헤드 교체 + 학습 루프)
- 배치 이미지 업로드 처리
- 결과를 Neo4j 그래프에 저장하는 연동 로직
