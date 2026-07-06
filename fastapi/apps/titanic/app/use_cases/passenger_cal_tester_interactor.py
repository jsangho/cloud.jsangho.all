from __future__ import annotations

from typing import Any

from titanic.app.dtos.passenger_cal_tester_dto import CalTesterQuery, CalTesterResponse
from titanic.app.ports.input.passenger_cal_tester_use_case import CalTesterUseCase
from titanic.app.ports.input.passenger_rose_model_use_case import RoseModelUseCase
from titanic.app.ports.output.passenger_cal_tester_port import CalTesterPort


class CalTesterInteractor(CalTesterUseCase):
    def __init__(self, repository: CalTesterPort, rose: RoseModelUseCase):
        self.repository = repository
        self.rose = rose

    async def test_model(self, test_set) -> dict[str, Any]:
        """칼이 로즈가 제안한 10개 모델의 트레이닝 정도를 점수화해서 1등을 뽑는 메소드"""
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
        )

        # ── 1. test_set 전처리 ────────────────────────────────────────────────
        df = test_set.copy()

        if df.empty or "survived" not in df.columns:
            return {"test_samples": 0, "ranking_metric": "f1", "rankings": []}

        df["gender"] = (df["gender"] == "female").astype(float)
        df["embarked"] = df["embarked"].map({"S": 0.0, "C": 1.0, "Q": 2.0}).fillna(0.0)

        feature_cols = ["pclass", "gender", "age", "sibsp", "parch", "fare", "embarked"]
        mask = df[feature_cols + ["survived"]].notna().all(axis=1)
        X_test = df.loc[mask, feature_cols].values.tolist()
        y_test = df.loc[mask, "survived"].astype(int).tolist()

        # ── 2. 훈련된 모델 평가 (훈련은 JackTrainerInteractor에 위임) ─────────
        success: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for algorithm in self.rose.list_algorithms():
            try:
                y_pred = await self.rose.batch_predict(X_test, algorithm)
                success.append(
                    {
                        "algorithm": algorithm,
                        "accuracy": round(accuracy_score(y_test, y_pred), 4),
                        "precision": round(
                            precision_score(y_test, y_pred, zero_division=0), 4
                        ),
                        "recall": round(
                            recall_score(y_test, y_pred, zero_division=0), 4
                        ),
                        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
                        "status": "success",
                    }
                )
            except ValueError as e:
                failed.append(
                    {"algorithm": algorithm, "status": "not_trained", "reason": str(e)}
                )
            except ImportError as e:
                failed.append(
                    {
                        "algorithm": algorithm,
                        "status": "skipped",
                        "reason": f"패키지 미설치: {e}",
                    }
                )
            except Exception as e:
                failed.append(
                    {"algorithm": algorithm, "status": "error", "reason": str(e)}
                )

        # ── 3. F1 기준 내림차순 정렬 후 1~10위 부여 ──────────────────────────
        ranked = sorted(success, key=lambda r: r["f1"], reverse=True)
        for i, r in enumerate(ranked):
            r["rank"] = i + 1

        return {
            "test_samples": len(X_test),
            "ranking_metric": "f1",
            "rankings": ranked + failed,
        }

    async def introduce_myself(self, query: CalTesterQuery) -> CalTesterResponse:
        return await self.repository.introduce_myself(query)
