---
name: image-classifier
description: ConvNeXt Nano(timm) 이미지 분류 파이프라인 구축·디버깅 관련 요청 시 사용. ontology 앱의 image_classifier 기능(모델 로딩, /classify 엔드포인트, classify_image MCP 도구) 작업 시 참고.
---

# ConvNeXt Nano 이미지 분류 — ontology 앱 구현 가이드

## 환경
- GPU: RTX 3050 8GB VRAM (`messi@DESKTOP-9E3A4EC`, `192.168.0.5`)
- `torch.cuda.is_available()`가 `False`면 자동으로 CPU 폴백 (느리지만 동작은 함)
- 8GB VRAM 기준 배치 크기 권장값: 32~64 (convnext_nano는 매우 작은 모델이라 단일 이미지 추론은 수백 MB 수준만 사용)
- 의존성: `timm==1.0.28` (`pyproject.toml`에 이미 추가됨). `torch`/`torchvision`은 기존에 이미 있음(`pytorch-cu126` 인덱스)

## 파일 위치 (헥사고날, star topology 준수 — `services/` 같은 별도 디렉터리 아님)

| 레이어 | 파일 |
|---|---|
| DTO | `fastapi/apps/ontology/app/dtos/image_classification_dto.py` |
| Port(input) | `fastapi/apps/ontology/app/ports/input/image_classifier_use_case.py` |
| Port(output) | `fastapi/apps/ontology/app/ports/output/image_label_classifier.py` |
| Interactor | `fastapi/apps/ontology/app/use_cases/image_classifier_interactor.py` |
| 모델 로딩(어댑터) | `fastapi/apps/ontology/adapter/outbound/convnext_image_classifier.py` |
| Provider | `fastapi/apps/ontology/dependencies/image_classifier_provider.py` |
| API 스키마 | `fastapi/apps/ontology/adapter/inbound/api/schemas/image_classifier_schema.py` |
| API 라우터 | `fastapi/apps/ontology/adapter/inbound/api/v1/image_classifier_router.py` (`POST /api/ontology/image-classifier/classify`) |
| MCP 도구 | `fastapi/apps/ontology/adapter/inbound/mcp/classify_image_tool.py` (`classify_image`) |
| 검증 스크립트 | `fastapi/apps/ontology/tests/image_classifier_interactor_test.py` |

## 표준 워크플로우

1. **모델 로드**: `timm.create_model("convnext_nano", pretrained=True)` — 최초 호출 시 HuggingFace Hub에서 가중치 다운로드(`~/.cache/huggingface/hub/models--timm--convnext_nano.in12k_ft_in1k`), 이후는 캐시에서 즉시 로드.
2. **전처리 구성**: `timm.data.resolve_data_config({}, model=model)` → `timm.data.create_transform(**config)`. 모델마다 요구하는 입력 크기·정규화가 다르므로 반드시 이 방식으로 얻은 transform을 써야 한다(하드코딩 금지).
3. **싱글턴 캐시**: `ConvNextImageClassifier`는 클래스 변수(`ClassVar`)에 모델/transform/라벨 정보를 캐시한다 — `KcElectraSpamClassifier`(`ontology/adapter/outbound/kcelectra_spam_classifier.py`)와 동일한 패턴. 요청마다 재로딩하지 않는다.
4. **추론**: `torch.no_grad()` 블록 안에서 forward → `softmax` → `torch.topk(k=5)`. GPU 텐서 연산은 동기 함수이므로 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않는다.
5. **라벨 변환**: 클래스 인덱스(0~999) → 사람이 읽을 수 있는 이름은 `timm.data.ImageNetInfo().index_to_description(idx)`로 얻는다. `model.pretrained_cfg`에 라벨명이 직접 들어있지 않으니 이 방식을 써야 한다.
6. **confidence threshold**: `CLASSIFIER_CONFIDENCE_THRESHOLD` 환경변수(기본 `0.5`)로 `is_confident` 판정.

## 트러블슈팅

- **CUDA OOM**: convnext_nano 자체는 매우 가벼워 단일 이미지 추론에서 OOM이 나면 십중팔구 다른 프로세스(다른 모델)가 VRAM을 점유 중인 것 — `nvidia-smi`로 확인. 배치 처리로 확장할 경우 배치 크기를 8~16으로 줄여본다.
- **`pretrained=True` 다운로드 실패**: HF Hub 네트워크 문제. `HF_HOME` 또는 기본 캐시(`~/.cache/huggingface/hub/`)에 이미 받은 스냅샷이 있으면 오프라인으로도 로드된다(`local_files_only`는 별도 설정 안 해도 캐시 우선 사용됨). 사내망에서 막혀 있으면 `HF_TOKEN` 설정 또는 사전 다운로드 필요.
- **`UnidentifiedImageError`**: `ConvNextImageClassifier._classify_sync`에서 `ValueError`로 변환해 라우터가 422를 반환하도록 이미 처리돼 있음 — 새 진입점을 추가할 때도 이 예외를 그대로 잡아 422로 매핑할 것.
- **MCP 도구 직접 테스트**: `mcp.list_tools()` / `mcp.call_tool("classify_image", {"image_path": "..."})`로 FastAPI 서버 없이도 단독 검증 가능 (`FastMCP` 인스턴스가 프로세스 내에서 바로 동작).

## 알려진 한계 (구현하지 않은 부분)

- **MCP 서버 실서비스 노출**: 이 `classify_image` 도구는 `admin` 앱의 기존 MCP 도구들(`piper_*_tools.py`)과 마찬가지로 **아직 어디에도 마운트되어 있지 않다** — `mcp.jsangho.cloud` Cloudflare Tunnel로 실제로 라우팅하려면, 이 저장소에 아직 없는 "MCP 서버 프로세스를 어떻게 띄우고 노출할지"(stdio? streamable-http를 FastAPI에 mount? 별도 프로세스?)에 대한 결정이 먼저 필요하다. 이건 이 기능만의 문제가 아니라 저장소 전체의 미해결 사항.
- **Docker Compose 별도 서비스**: 이 저장소는 앱마다 별도 컨테이너를 두지 않고 하나의 `backend` 컨테이너(단일 FastAPI 프로세스)에 모든 hexagonal 앱을 몰아넣는 구조다. 따라서 `image-classifier`용 별도 `services:` 항목은 필요 없다 — `pyproject.toml`에 `timm`을 추가한 것으로 충분하며, 기존 `backend` 이미지를 재빌드(`docker compose build backend`, 사용자가 명시적으로 요청할 때만)하면 자동으로 포함된다.
