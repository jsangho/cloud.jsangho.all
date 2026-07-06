"""KcELECTRA-base를 스팸 라벨(6-way)로 파인튜닝한다.

실행 (host, pytorch_env):
  pytorch_env/Scripts/python.exe fastapi/apps/ontology/scripts/spam_classifier/finetune_kcelectra.py

입력: ontology/scripts/spam_classifier/data/dataset.jsonl (generate_dataset.py 산출물)
출력: ontology/_models/kcelectra_spam/ (모델 체크포인트 + 토크나이저)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

_DATA_PATH = Path(__file__).resolve().parent / "data" / "dataset.jsonl"
_OUT_DIR = Path(__file__).resolve().parents[2] / "_models" / "kcelectra_spam"
_MODEL_NAME = "beomi/KcELECTRA-base"
_LABELS = ["ham", "phishing", "advertisement", "scam", "malware", "abusive"]
_LABEL2ID = {label: i for i, label in enumerate(_LABELS)}
_ID2LABEL = dict(enumerate(_LABELS))
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


class SpamDataset(torch.utils.data.Dataset):
    def __init__(self, encodings: dict, labels: list[int]) -> None:
        self._encodings = encodings
        self._labels = labels

    def __len__(self) -> int:
        return len(self._labels)

    def __getitem__(self, idx: int) -> dict:
        item = {k: v[idx] for k, v in self._encodings.items()}
        item["labels"] = torch.tensor(self._labels[idx])
        return item


def _compute_metrics(eval_pred) -> dict:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
    }


def main() -> None:
    if not _DATA_PATH.exists():
        raise SystemExit(
            f"데이터셋이 없습니다: {_DATA_PATH}. generate_dataset.py를 먼저 실행하세요."
        )

    texts, labels = _load_dataset()
    print(f"총 {len(texts)}개 샘플 로드")

    rng = np.random.default_rng(_SEED)
    indices = rng.permutation(len(texts))
    val_size = max(1, int(len(texts) * _VAL_RATIO))
    val_idx, train_idx = indices[:val_size], indices[val_size:]

    tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)

    def _encode(idx_list: np.ndarray) -> tuple[dict, list[int]]:
        subset_texts = [texts[i] for i in idx_list]
        subset_labels = [labels[i] for i in idx_list]
        enc = tokenizer(
            subset_texts,
            truncation=True,
            padding="max_length",
            max_length=_MAX_LENGTH,
            return_tensors="pt",
        )
        return enc, subset_labels

    train_enc, train_labels = _encode(train_idx)
    val_enc, val_labels = _encode(val_idx)
    train_dataset = SpamDataset(train_enc, train_labels)
    val_dataset = SpamDataset(val_enc, val_labels)
    print(f"train={len(train_dataset)} val={len(val_dataset)}")

    model = AutoModelForSequenceClassification.from_pretrained(
        _MODEL_NAME,
        num_labels=len(_LABELS),
        id2label=_ID2LABEL,
        label2id=_LABEL2ID,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    args = TrainingArguments(
        output_dir=str(_OUT_DIR / "_checkpoints"),
        num_train_epochs=8,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_steps=10,
        report_to=[],
        fp16=torch.cuda.is_available(),
        seed=_SEED,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=_compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()
    print("최종 검증 지표:", metrics)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(_OUT_DIR))
    tokenizer.save_pretrained(str(_OUT_DIR))
    print(f"모델 저장 완료 → {_OUT_DIR}")


if __name__ == "__main__":
    main()
