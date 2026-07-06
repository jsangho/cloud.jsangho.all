"""파인튜닝한 KcELECTRA 스팸 분류 모델을 검증한다.

finetune_kcelectra.py와 동일한 seed·split으로 검증셋을 재구성해
저장된 모델(ontology/_models/kcelectra_spam)의 held-out 성능을 재확인하고,
클래스별 리포트와 임의 샘플 예측을 함께 출력한다.

실행 (host, pytorch_env):
  pytorch_env/Scripts/python.exe fastapi/apps/ontology/scripts/spam_classifier/test_finetune.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report
from transformers import AutoModelForSequenceClassification, AutoTokenizer

_DATA_PATH = Path(__file__).resolve().parent / "data" / "dataset.jsonl"
_MODEL_DIR = Path(__file__).resolve().parents[2] / "_models" / "kcelectra_spam"
_LABELS = ["ham", "phishing", "advertisement", "scam", "malware", "abusive"]
_LABEL2ID = {label: i for i, label in enumerate(_LABELS)}
_MAX_LENGTH = 256
_VAL_RATIO = 0.1
_SEED = 42


def _load_dataset() -> tuple[list[str], list[int]]:
    texts, labels = [], []
    with _DATA_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts.append(f"{row['subject']} {row['body']}")
            labels.append(_LABEL2ID[row["label"]])
    return texts, labels


def main() -> None:
    texts, labels = _load_dataset()
    rng = np.random.default_rng(_SEED)
    indices = rng.permutation(len(texts))
    val_size = max(1, int(len(texts) * _VAL_RATIO))
    val_idx = indices[:val_size]
    val_texts = [texts[i] for i in val_idx]
    val_labels = [labels[i] for i in val_idx]
    print(
        f"검증셋 크기: {len(val_texts)} (전체 {len(texts)}개 중 동일 seed·split 재구성)"
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(str(_MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(_MODEL_DIR))
    model.to(device)
    model.eval()

    preds: list[int] = []
    with torch.no_grad():
        for i in range(0, len(val_texts), 32):
            batch = val_texts[i : i + 32]
            enc = tokenizer(
                batch,
                truncation=True,
                padding="max_length",
                max_length=_MAX_LENGTH,
                return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits
            preds.extend(torch.argmax(logits, dim=-1).cpu().tolist())

    print("\n=== 검증셋 classification report ===")
    print(
        classification_report(
            val_labels, preds, target_names=_LABELS, digits=4, zero_division=0
        )
    )

    print("=== 오분류 샘플 (최대 10개) ===")
    shown = 0
    for text, true_id, pred_id in zip(val_texts, val_labels, preds, strict=False):
        if true_id != pred_id and shown < 10:
            print(f"- 정답={_LABELS[true_id]} 예측={_LABELS[pred_id]} | {text[:60]}...")
            shown += 1
    if shown == 0:
        print("(오분류 없음)")

    print("\n=== 임의 문장 스팟체크 ===")
    samples = [
        (
            "[Web발신] 무료 쿠폰 즉시 지급",
            "지금 클릭하면 5만원 상당 상품권을 드립니다. 선착순 마감!",
        ),
        (
            "계정 보안 경고",
            "고객님의 계정이 잠겼습니다. 아래 링크에서 본인 인증을 완료해 주세요. http://bit.ly/xxx",
        ),
        (
            "팀 회의 일정 공유",
            "내일 오후 3시 회의실 A에서 정기 회의가 있습니다. 참석 부탁드립니다.",
        ),
        (
            "무료 코인 지급 이벤트",
            "지금 가입하면 100만원 상당 코인을 즉시 드립니다. 원금 보장!",
        ),
        (
            "첨부파일 확인 요청",
            "이력서.exe 파일을 첨부했습니다. 실행 후 확인 부탁드립니다.",
        ),
        ("너 진짜 정신 나갔냐", "이 XX야 당장 꺼져 다시는 연락하지마"),
    ]
    for subject, body in samples:
        text = f"{subject} {body}"
        enc = tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=_MAX_LENGTH,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1)[0]
        pred_id = int(torch.argmax(probs).item())
        print(f"[{_LABELS[pred_id]} {probs[pred_id]:.2%}] {subject}")


if __name__ == "__main__":
    main()
