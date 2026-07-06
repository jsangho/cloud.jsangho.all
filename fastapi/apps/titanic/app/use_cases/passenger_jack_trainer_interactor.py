from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from titanic.adapter.inbound.api.schemas.passenger_jack_trainer_schema import (
    JackTrainerSchema,
)
from titanic.adapter.outbound.orm.passenger_rose_model_strategies import (
    build_all_strategies,
)
from titanic.app.dtos.passenger_jack_trainer_dto import (
    JackTrainerQuery,
    JackTrainerResponse,
)
from titanic.app.ports.output.passenger_jack_trainer_port import JackTrainerPort

logger = logging.getLogger(__name__)


class JackTrainerInteractor:
    _trained_strategies: dict = {}  # 클래스 변수 — 인스턴스 간 공유

    def __init__(self, repository: JackTrainerPort):
        self.repository = repository

    async def train_model(self, train_set: pd.DataFrame) -> dict[str, Any]:
        """로즈가 제안한 모델들을 훈련시키는 메소드"""
        logger.info("[JackTrainerInteractor] 학습 파이프라인 시작")

        df = train_set.copy()
        survived_col = "survived" if "survived" in df.columns else "Survived"
        gender_col = next(
            (c for c in ("gender", "sex", "Sex") if c in df.columns), None
        )

        # feature engineering
        df[survived_col] = df[survived_col].astype(float)
        if gender_col:
            df["gender_enc"] = (df[gender_col].isin(["female", "Female"])).astype(float)
        else:
            df["gender_enc"] = 0.0
        df["embarked_enc"] = (
            df.get("embarked", df.get("Embarked", "S"))
            .map({"S": 0.0, "C": 1.0, "Q": 2.0})
            .fillna(0.0)
        )

        feature_cols = [
            "pclass",
            "gender_enc",
            "age",
            "sibsp",
            "parch",
            "fare",
            "embarked_enc",
        ]
        for col in feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        mask = df[feature_cols + [survived_col]].notna().all(axis=1)
        X_train = df.loc[mask, feature_cols].values.tolist()
        y_label = df.loc[mask, survived_col].astype(int).tolist()

        if not X_train:
            return {"train_samples": 0, "trained_models": [], "trained_strategies": {}}

        # 로즈의 10개 전략으로 학습
        JackTrainerInteractor._trained_strategies = {}
        trained_names = []
        for key, StrategyClass in build_all_strategies().items():
            strategy = StrategyClass()
            try:
                strategy.fit(X_train, y_label)
                JackTrainerInteractor._trained_strategies[key] = strategy
                trained_names.append(strategy.name)
                logger.info(f"[JackTrainerInteractor] {strategy.name} 학습 완료")
            except Exception as e:
                logger.warning(f"[JackTrainerInteractor] {key} 학습 실패 | error={e}")

        return {
            "train_samples": len(X_train),
            "trained_models": trained_names,
            "trained_strategies": JackTrainerInteractor._trained_strategies,
        }

    async def introduce_myself(self, schema: JackTrainerSchema) -> JackTrainerResponse:
        """잭 트레이너의 자기소개 인터렉트"""
        return await self.repository.introduce_myself(
            JackTrainerQuery(
                id=schema.id,
                name=schema.name,
            )
        )
