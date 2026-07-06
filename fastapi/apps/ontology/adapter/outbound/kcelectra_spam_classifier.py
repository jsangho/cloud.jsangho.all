from __future__ import annotations

import asyncio
from pathlib import Path
from typing import ClassVar

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from ontology.app.dtos.spam_classification_dto import SpamClassificationDto
from ontology.app.ports.output.spam_label_classifier import SpamLabelClassifier
from ontology.domain.enums.spam_classes import SpamLabel

_MODEL_DIR = Path(__file__).resolve().parents[2] / "_models" / "kcelectra_spam"
_MAX_LENGTH = 256
_VALID_LABELS = {member.value for member in SpamLabel}


class KcElectraSpamClassifier(SpamLabelClassifier):
    """`ontology/scripts/spam_classifier/finetune_kcelectra.py`로 파인튜닝한 KcELECTRA-base(6-way) 어댑터.

    모델·토크나이저는 프로세스에서 한 번만 로드해 재사용한다(클래스 변수 캐시).
    """

    _tokenizer: ClassVar[PreTrainedTokenizerBase | None] = None
    _model: ClassVar[torch.nn.Module | None] = None
    _device: ClassVar[str] = "cuda" if torch.cuda.is_available() else "cpu"

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir = model_dir or _MODEL_DIR

    def _ensure_loaded(self) -> None:
        if KcElectraSpamClassifier._model is not None:
            return
        if not (self._model_dir / "config.json").exists():
            raise RuntimeError(
                f"KcELECTRA 모델을 찾을 수 없습니다: {self._model_dir}. "
                "ontology/scripts/spam_classifier/finetune_kcelectra.py로 먼저 학습해 주세요."
            )

        tokenizer = AutoTokenizer.from_pretrained(str(self._model_dir))
        model = AutoModelForSequenceClassification.from_pretrained(str(self._model_dir))
        model.to(KcElectraSpamClassifier._device)
        model.eval()

        KcElectraSpamClassifier._tokenizer = tokenizer
        KcElectraSpamClassifier._model = model

    def _classify_sync(self, subject: str, body: str) -> SpamClassificationDto:
        self._ensure_loaded()
        tokenizer = KcElectraSpamClassifier._tokenizer
        model = KcElectraSpamClassifier._model

        text = f"{subject} {body}".strip()
        inputs = tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=_MAX_LENGTH,
            return_tensors="pt",
        ).to(KcElectraSpamClassifier._device)

        with torch.no_grad():
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        pred_id = int(torch.argmax(probs).item())
        label = model.config.id2label[pred_id]
        if label not in _VALID_LABELS:
            label = SpamLabel.HAM.value
        confidence = float(probs[pred_id].item())

        return SpamClassificationDto(label=label, confidence=confidence)

    async def classify(self, subject: str, body: str) -> SpamClassificationDto:
        return await asyncio.to_thread(self._classify_sync, subject, body)
