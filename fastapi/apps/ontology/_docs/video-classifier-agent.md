# 비디오 분류 모델 교체: 3D CNN → QLoRA 파인튜닝 Video Transformer

**목적**: 기존 3D CNN 기반 동영상 분류 모델을 대체할 모델을 선정하고, RTX 3050 (VRAM 8GB) 환경에서 QLoRA로 파인튜닝 및 서빙하기 위한 툴/스킬 스택을 정리한다.

**대상 환경**: 로컬 RTX 3050 (8GB VRAM), EXAONE-3.5-2.4B / Qwen2.5-1.5B와 함께 멀티에이전트 파이프라인의 일부로 동작. Neo4j 그래프 DB, Cloudflare Tunnel MCP 라우팅과 연동 가능해야 함.

---

## 1. 하드웨어 제약 분석

| 항목 | 값 | 비고 |
|---|---|---|
| VRAM | 8GB (RTX 3050) | 3D CNN(C3D, I3D, SlowFast) 대비 여유는 있으나 대형 ViT는 불가 |
| 동시 로드 모델 | EXAONE 2.4B + Qwen 1.5B 이미 상주 가능성 | 비디오 모델은 **온디맨드 로드/언로드** 전제로 설계 |
| 파인튜닝 방식 | QLoRA (4-bit NF4 + LoRA adapter) | full fine-tuning 불가, LoRA만으로도 8GB 초과 가능성 있어 4-bit 필수 |

8GB 환경에서 QLoRA는 실측 사례상 **7B급 LLM도 페이징 옵티마이저 + gradient checkpointing으로 겨우 맞추는 수준**이므로, 비디오 모델은 이보다 훨씬 작은 파라미터 규모(수십~수백M)를 골라야 안정적이다.

---

## 2. 추천 모델

### 1순위: **VideoMAE v2 (Base, ~86M params)**
- 3D CNN이 하던 "영상 클립 → 클래스" 분류 작업을 직접 대체하는 순수 비디오 트랜스포머.
- Masked Autoencoder 사전학습 기반이라 소량의 라벨 데이터로도 파인튜닝 효율이 좋음 (적은 데이터셋 상황에 유리).
- HuggingFace `transformers`에 `VideoMAEForVideoClassification`으로 이미 통합되어 있어 PEFT/LoRA 적용이 표준 워크플로우로 가능.
- 8GB VRAM에서 4-bit 양자화 + LoRA + gradient checkpointing 조합이면 batch size 1~2로 충분히 학습 가능한 크기.

### 2순위(대안): **TimeSformer (Base, Divided Space-Time Attention)**
- VideoMAE보다 연산량이 크지만 프레임 간 시간적 관계 모델링이 더 명시적 (Royal Rumble/경기 흐름처럼 "순서"가 중요한 이벤트 분류에 유리할 수 있음).
- 8GB에서는 프레임 수(8→4~6)와 해상도를 낮춰야 안전.

### 3순위(멀티에이전트 통합 지향): **X-CLIP (B/16)**
- CLIP 기반이라 텍스트 프롬프트와 결합한 zero-shot/few-shot 분류가 가능 — 에이전트가 "이 클립이 스플래시 공격인가?" 같은 자연어 질의로 분류를 요청하는 구조를 만들 경우 적합.
- 라벨을 새로 정의할 때마다 재학습이 필요 없다는 장점이 있어, 클래스 체계가 자주 바뀌는 초기 개발 단계에 유리.

**권장**: 클래스가 고정적이고 정확도가 최우선이면 **VideoMAE v2**, 클래스 체계가 유동적이거나 에이전트가 자연어로 질의해야 하면 **X-CLIP**을 우선 검토.

---

## 3. QLoRA 파인튜닝 전략

### 3.1 양자화 설정
```python
from transformers import BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
    bnb_4bit_use_double_quant=True,  # 양자화 상수 재압축으로 추가 절감
)
```

### 3.2 LoRA 어댑터 설정 (PEFT)
```python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=16,                     # 8GB 환경에서는 8~16 권장 (32 이상은 VRAM 부담 증가)
    lora_alpha=32,
    target_modules=["query", "value"],  # ViT/VideoMAE의 attention proj
    lora_dropout=0.05,
    bias="none",
    task_type="FEATURE_EXTRACTION",  # 분류 헤드는 별도 학습
)
model = get_peft_model(base_model, lora_config)
```

### 3.3 8GB에서 안정적으로 돌리기 위한 필수 옵션
- `gradient_checkpointing=True`
- `per_device_train_batch_size=1~2` + `gradient_accumulation_steps=8~16`
- `optim="paged_adamw_8bit"` (bitsandbytes 페이징 옵티마이저)
- 입력 프레임 수 축소 (기본 16프레임 → 8프레임)로 시작, VRAM 여유 보고 조정
- `fp16`/`bf16` mixed precision 필수 (RTX 3050은 bf16 미지원일 수 있으니 fp16 우선 확인)

---

## 4. 최적화 툴·라이브러리 스택

| 목적 | 툴 |
|---|---|
| 모델 로드/추론 | `transformers` (VideoMAEForVideoClassification / XCLIPModel) |
| 4-bit 양자화 | `bitsandbytes` |
| LoRA/QLoRA | `peft` |
| 학습 루프 | `transformers.Trainer` 또는 `trl` (SFTTrainer는 LLM용이라 비디오 분류엔 커스텀 Trainer 권장) |
| 비디오 디코딩 | `decord` (GPU 친화적, PyAV보다 빠름) 또는 `torchcodec` |
| 데이터 증강 | `torchvision.transforms.v2` (RandomCrop, RandAugment) |
| 실험 추적 | `wandb` 또는 로컬 `tensorboard` (Cloudflare Tunnel로 원격 조회 가능) |
| 서빙(온디맨드 로드) | FastAPI 엔드포인트 + `torch.cuda.empty_cache()` 기반 모델 언로드 로직 |
| 의존성 관리 | 기존 `uv` + `pyproject.toml` 체계에 편입 (`[project.optional-dependencies].video`) |

### 의존성 그룹 예시 (`pyproject.toml`)
```toml
[project.optional-dependencies]
video = [
    "transformers>=4.44",
    "peft>=0.12",
    "bitsandbytes>=0.43",
    "decord>=0.6",
    "accelerate>=0.33",
]
```

---

## 5. 멀티에이전트 파이프라인 통합 방향

1. **에이전트 역할 분리**: 비디오 분류 모델은 별도 마이크로서비스(FastAPI)로 감싸고, MCP 툴로 노출 (`mcp.jsangho.cloud`에 `classify_video` 툴 추가).
2. **온디맨드 VRAM 관리**: EXAONE/Qwen과 VRAM을 공유해야 하므로, 분류 요청이 들어올 때만 비디오 모델을 로드하고 추론 후 언로드하는 스케줄러 필요 (예: 간단한 LRU 기반 모델 매니저).
3. **결과를 그래프로 연결**: 분류 결과(이벤트 타입, confidence)를 Neo4j에 노드/엣지로 기록해 기존 star-topology RAG 구조와 통합.
4. **Claude Code 핸드오프**: 아래와 같은 후속 harness 파일 분리를 권장
   - `video_model_finetune_harness.md` — 데이터셋 준비, 학습 스크립트, 평가 지표
   - `video_model_serving_harness.md` — FastAPI 엔드포인트, 모델 로드/언로드, MCP 툴 스펙

---

## 6. 다음 단계 체크리스트

- [ ] 기존 3D CNN 학습 데이터셋을 VideoMAE/X-CLIP 입력 포맷(프레임 시퀀스)으로 변환하는 전처리 스크립트 작성
- [ ] `r=16` LoRA로 소규모 파일럿 학습 후 VRAM 피크 측정, 필요시 `r` 또는 프레임 수 조정
- [ ] 분류 헤드(클래스 수)를 기존 3D CNN 라벨 체계와 매핑
- [ ] FastAPI 서빙 엔드포인트 + MCP 툴 정의
- [ ] Neo4j 스키마에 비디오 분류 결과 노드 타입 추가

---

*참고: 위 VRAM 수치는 배치 크기 1, 시퀀스 길이 기본값 기준 추정치이며, 실제 환경에서는 프레임 수·해상도·rank 값에 따라 변동 폭이 크므로 파일럿 학습으로 반드시 검증할 것.*