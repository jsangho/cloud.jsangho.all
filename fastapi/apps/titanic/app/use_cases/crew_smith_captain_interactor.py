from __future__ import annotations

import logging
import re

from pandas import DataFrame

from titanic.adapter.inbound.api.schemas.crew_smith_captain_schema import (
    SmithCaptainSchema,
)
from titanic.app.dtos.crew_smith_captain_dto import (
    SmithCaptainChatCommand,
    SmithCaptainQuery,
    SmithCaptainResponse,
)
from titanic.app.ports.input.crew_andrews_architect_use_case import (
    AndrewsArchitectUseCase,
)
from titanic.app.ports.input.crew_hartley_violin_use_case import HartleyViolinUseCase
from titanic.app.ports.input.crew_lowe_boat_use_case import LoweBoatUseCase
from titanic.app.ports.input.crew_smith_captain_use_case import SmithCaptainUseCase
from titanic.app.ports.input.crew_walter_roaster_use_case import WalterRoasterUseCase
from titanic.app.ports.input.passenger_cal_tester_use_case import CalTesterUseCase
from titanic.app.ports.input.passenger_jack_trainer_use_case import JackTrainerUseCase
from titanic.app.ports.input.passenger_rose_model_use_case import RoseModelUseCase
from titanic.app.ports.output.crew_smith_captain_port import SmithCaptainPort

logger = logging.getLogger(__name__)


class SmithCaptainInteractor(SmithCaptainUseCase):
    def __init__(
        self,
        repository: SmithCaptainPort,
        andrews: AndrewsArchitectUseCase,
        jack: JackTrainerUseCase,
        rose: RoseModelUseCase,
        cal: CalTesterUseCase,
        walter: WalterRoasterUseCase,
        lowe: LoweBoatUseCase,
        hartley: HartleyViolinUseCase,
    ):
        self.repository = repository
        self.andrews = andrews
        self.jack = jack
        self.rose = rose
        self.cal = cal
        self.walter = walter
        self.lowe = lowe
        self.hartley = hartley

    async def chat(self, command: SmithCaptainChatCommand) -> str:
        user_messages = [m for m in command.messages if m.role == "user"]
        if not user_messages:
            return "질문을 입력해주세요."
        question: str = user_messages[-1].text

        # 이전 메시지 전체에서 나이 컨텍스트 추출 (follow-up 질문 대응)
        all_user_text = " ".join(m.text for m in user_messages)

        intent_result: dict = self.andrews.analyze_intent(question)
        intent: str = intent_result["intent"]
        scores: dict = intent_result["scores"]

        # 동점 시 SURVIVAL_PREDICT보다 STATISTICS 우선 (정보형 질문)
        if (
            intent == "SURVIVAL_PREDICT"
            and scores.get("STATISTICS", 0) >= scores.get("SURVIVAL_PREDICT", 0)
            and not re.search(r"\d+\s*세|여자|남자|여성|남성", question)
        ):
            intent = "STATISTICS"

        train_set: DataFrame = await self.walter.get_train_set()
        test_set: DataFrame = await self.walter.get_test_set()

        # ① 수치 조회 패턴 — intent 무관하게 passenger_search로
        if re.search(r"몇\s*명|몇\s*분|인원|명수", question) or re.search(
            r"평균\s*나이|나이\s*평균|나이는|평균\s*연령", question
        ):
            return await self._answer_passenger_search(train_set, test_set, question)

        # ② 개인 생존 가능성 질문 (Kiwi 형태소 분리 오류 보완)
        #    "살 수 있었을까?" → Kiwi가 사(VV)+ᆯ(ETM)으로 분리해 INTENT_MAP 매칭 실패
        if re.search(
            r"살\s*수\s*있|살아남을\s*수|살았을까|죽었을까|살아남았|생존\s*가능",
            question,
        ):
            return self._predict_survival(question, all_user_text)

        # ③ 비교 생존 시뮬레이션 — 이전 대화에 생존 컨텍스트가 있을 때
        if re.search(r"달라|다르|차이|비교", question) and re.search(
            r"살|죽|생존|사망|확률", all_user_text
        ):
            return self._predict_survival(question, all_user_text)

        if intent == "STATISTICS":
            return self._explain_survival_factors(train_set)
        elif intent == "SURVIVAL_PREDICT":
            return self._predict_survival(question, all_user_text)
        elif intent == "MODEL_TRAIN":
            return self._explain_model_info()
        elif intent == "PASSENGER_SEARCH":
            return await self._answer_passenger_search(train_set, test_set, question)
        else:
            return self._explain_survival_factors(train_set)

    def _explain_survival_factors(self, train_set: DataFrame) -> str:
        df = train_set.copy()
        survived_col = "survived" if "survived" in df.columns else "Survived"
        gender_col = next(
            (c for c in ("gender", "sex", "Sex") if c in df.columns), None
        )
        pclass_col = "pclass" if "pclass" in df.columns else "Pclass"

        if survived_col not in df.columns:
            return "생존 데이터를 불러올 수 없습니다."

        s = df[survived_col].astype(float)
        lines = ["타이타닉 생존에 영향을 미치는 주요 요인:\n"]

        if gender_col:
            female_mask = df[gender_col].isin(["female", "Female"])
            female_rate = s[female_mask].mean()
            male_rate = s[~female_mask].mean()
            lines.append("① 성별 (가장 중요, 상관계수 -0.54)")
            lines.append(f"   - 여성 생존율: {female_rate:.1%}")
            lines.append(f"   - 남성 생존율: {male_rate:.1%}")

        if pclass_col in df.columns:
            lines.append("\n② 객실 등급 (상관계수 -0.34)")
            for cls in [1, 2, 3]:
                mask = df[pclass_col].astype(str) == str(cls)
                rate = s[mask].mean()
                lines.append(f"   - {cls}등석 생존율: {rate:.1%}")

        lines.append("\n③ 요금 (상관계수 +0.26): 높은 요금일수록 생존율 높음")
        lines.append("④ 나이 (상관계수 -0.08): 어릴수록 약간 생존율 높음")
        lines.append(
            "\n결론: 성별(여성 우선)과 객실 등급(1등석)이 생존의 핵심 결정 요인입니다."
        )

        return "\n".join(lines)

    def _predict_survival(self, question: str, context: str = "") -> str:
        # 나이: 현재 질문 우선, 없으면 대화 히스토리에서 추출
        age_match = re.search(r"(\d+)\s*세", question) or re.search(
            r"(\d+)\s*세", context
        )
        age = float(age_match.group(1)) if age_match else 30.0

        pclass_match = re.search(r"([123])\s*등석", question) or re.search(
            r"([123])\s*등석", context
        )
        pclass = int(pclass_match.group(1)) if pclass_match else 3
        fare_by_pclass = {1: 60.0, 2: 15.0, 3: 8.0}
        fare = fare_by_pclass.get(pclass, 14.45)

        is_female = any(
            kw in question for kw in ["여자", "여성", "여인", "female", "woman"]
        )
        _is_male = any(kw in question for kw in ["남자", "남성", "male", "man"])
        is_compare = any(
            kw in question for kw in ["달라", "차이", "비교", "얼마나", "다르"]
        )

        trained_strategies: dict = getattr(self.jack, "_trained_strategies", {})
        if not trained_strategies:
            sex_label = "여성" if is_female else "남성"
            return (
                f"{age:.0f}세 {sex_label} 승객의 생존 예측을 위해 먼저 모델 훈련이 필요합니다. "
                "/titanic/jack/train 엔드포인트를 실행한 후 다시 질문해주세요."
            )

        def _vote(sex_value: float) -> tuple[int, int]:
            fv = [[float(pclass), sex_value, age, 0.0, 0.0, fare, 0.0]]
            votes = 0
            total = 0
            for strategy in trained_strategies.values():
                try:
                    pred = strategy.predict(fv)
                    votes += int(pred[0])
                    total += 1
                except Exception:
                    continue
            return votes, total

        # 비교 질문: "달라", "차이", "얼마나" 등 명시적 비교 키워드가 있을 때만
        if is_compare:
            f_votes, total = _vote(1.0)
            m_votes, _ = _vote(0.0)
            if total == 0:
                return "예측 모델 실행 중 오류가 발생했습니다."
            f_rate = f_votes / total
            m_rate = m_votes / total
            diff = f_rate - m_rate
            logger.info(
                f"[SmithCaptainInteractor] compare | age={age} pclass={pclass} f={f_rate:.0%} m={m_rate:.0%}"
            )
            return (
                f"{age:.0f}세 기준 성별에 따른 생존 확률 비교 ({pclass}등석):\n\n"
                f"• 여성: {f_votes}/{total}개 모델 생존 예측 → {f_rate:.0%}\n"
                f"• 남성: {m_votes}/{total}개 모델 생존 예측 → {m_rate:.0%}\n\n"
                f"차이: {diff:+.0%} — 여성이 {'더 유리' if diff > 0 else '더 불리'}\n"
                f"타이타닉은 'Women and Children First' 원칙이 적용되어 여성 구명정 탑승 우선권이 있었습니다."
            )

        # 단일 예측
        sex_value = 1.0 if is_female else 0.0
        sex_label = "여성" if is_female else "남성"
        votes, total = _vote(sex_value)
        if total == 0:
            return "예측 모델 실행 중 오류가 발생했습니다."
        rate = votes / total
        result_text = (
            "생존했을 가능성이 높습니다"
            if rate >= 0.5
            else "생존하지 못했을 가능성이 높습니다"
        )
        gender_reason = (
            "여성으로 구명정 탑승 우선권 부여"
            if is_female
            else "남성으로 생존 우선순위 낮음"
        )
        logger.info(
            f"[SmithCaptainInteractor] predict | age={age} sex={sex_label} pclass={pclass} votes={votes}/{total}"
        )
        return (
            f"{age:.0f}세 {sex_label}이라면 타이타닉에서 {result_text}.\n"
            f"예측 근거: {total}개 모델 중 {votes}개가 생존 예측 ({rate:.0%})\n"
            f"주요 요인: {gender_reason}, {pclass}등석 탑승"
        )

    def _preprocess_features(self, df: DataFrame):
        import pandas as pd

        d = df.copy()
        gender_col = next((c for c in ("gender", "sex", "Sex") if c in d.columns), None)
        d["gender_enc"] = (
            d[gender_col].isin(["female", "Female"]).astype(float)
            if gender_col
            else 0.0
        )
        emb = d.get("embarked", d.get("Embarked", None))
        d["embarked_enc"] = (
            emb.map({"S": 0.0, "C": 1.0, "Q": 2.0}) if emb is not None else 0.0
        ).fillna(0.0)
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
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        mask = d[feature_cols].notna().all(axis=1)
        X = d.loc[mask, feature_cols].values.tolist()
        return X, mask

    def _predict_bulk(self, X: list) -> int:
        import numpy as np

        trained_strategies: dict = getattr(self.jack, "_trained_strategies", {})
        if not trained_strategies or not X:
            return 0
        all_preds = []
        for strategy in trained_strategies.values():
            try:
                preds = strategy.predict(X)
                all_preds.append(preds)
            except Exception:
                continue
        if not all_preds:
            return 0
        ensemble = (np.mean(all_preds, axis=0) >= 0.5).astype(int)
        return int(ensemble.sum())

    async def _answer_passenger_search(
        self, train_set: DataFrame, test_set: DataFrame, question: str
    ) -> str:
        import pandas as pd

        full_df = pd.concat(
            [train_set.drop(columns=["survived"], errors="ignore"), test_set],
            ignore_index=True,
        )
        gender_col = next(
            (c for c in ("gender", "sex", "Sex") if c in full_df.columns), None
        )
        pclass_col = "pclass" if "pclass" in full_df.columns else "Pclass"
        age_col = "age" if "age" in full_df.columns else "Age"
        total = len(full_df)

        asks_survival = any(kw in question for kw in ["생존", "살아남", "살았"])
        asks_female = any(kw in question for kw in ["여자", "여성"])
        asks_male = any(kw in question for kw in ["남자", "남성"])
        pclass_match = re.search(r"([123])\s*등석", question)
        decade_match = re.search(r"(\d+)\s*대", question)  # 20대, 30대
        exact_age_match = re.search(r"(\d+)\s*세", question)  # 25세
        asks_avg_age = any(kw in question for kw in ["나이", "평균"])

        # ── 복합 필터 마스크 구성 ──────────────────────────────────
        mask = pd.Series([True] * total, index=full_df.index)

        label_parts: list[str] = []

        if pclass_match:
            cls = pclass_match.group(1)
            mask &= full_df[pclass_col].astype(str) == cls
            label_parts.append(f"{cls}등석")

        if decade_match:
            decade = int(decade_match.group(1))
            ages = full_df[age_col].astype(float)
            mask &= (ages >= decade) & (ages < decade + 10)
            label_parts.append(f"{decade}대")
        elif exact_age_match and not asks_survival:
            exact_age = int(exact_age_match.group(1))
            ages = full_df[age_col].astype(float)
            mask &= (ages >= exact_age) & (ages < exact_age + 1)
            label_parts.append(f"{exact_age}세")

        if asks_female and gender_col:
            mask &= full_df[gender_col].isin(["female", "Female"])
            label_parts.append("여성")
        elif asks_male and gender_col:
            mask &= ~full_df[gender_col].isin(["female", "Female"])
            label_parts.append("남성")

        label = " ".join(label_parts) if label_parts else "전체"
        filtered_df = full_df[mask]

        # ── 생존/사망 예측 ─────────────────────────────────────────
        if asks_survival:
            trained_strategies: dict = getattr(self.jack, "_trained_strategies", {})
            if not trained_strategies:
                return "생존/사망 예측을 위해 먼저 /titanic/jack/train 으로 모델을 훈련해주세요."
            X, valid_mask = self._preprocess_features(filtered_df)
            survived = self._predict_bulk(X)
            valid_n = int(valid_mask.sum())
            dead = valid_n - survived
            rate = survived / valid_n if valid_n else 0
            return (
                f"모델 예측 기준 {label} 탑승객 생존: {survived}명({rate:.1%}), "
                f"사망: {dead}명({1 - rate:.1%}) (유효 {valid_n}명)"
            )

        # ── 평균 나이 ─────────────────────────────────────────────
        if asks_avg_age and not label_parts and age_col in full_df.columns:
            avg = full_df[age_col].astype(float).mean()
            return f"탑승객 평균 나이는 {avg:.1f}세입니다."

        # ── 인원 수 ───────────────────────────────────────────────
        n = int(mask.sum())
        if label == "전체":
            return f"타이타닉 탑승객은 총 {n}명입니다."
        return f"{label} 탑승객은 {n}명입니다."

    def _explain_model_info(self) -> str:
        trained_strategies: dict = getattr(self.jack, "_trained_strategies", {})
        if not trained_strategies:
            return (
                "현재 훈련된 모델이 없습니다.\n"
                "생존 예측 모델을 사용하려면 먼저 훈련을 실행해야 합니다.\n"
                "훈련 가능한 알고리즘: 로지스틱 회귀, 랜덤 포레스트, XGBoost, LightGBM, CatBoost 등 10종"
            )
        names = list(trained_strategies.keys())
        return (
            f"현재 {len(names)}개 모델이 훈련되어 있습니다.\n"
            f"훈련된 모델: {', '.join(names)}\n"
            "생존 예측 질문을 하면 전체 모델의 다수결로 답변합니다."
        )

    async def introduce_myself(
        self, schema: SmithCaptainSchema
    ) -> SmithCaptainResponse:
        return await self.repository.introduce_myself(
            SmithCaptainQuery(id=schema.id, name=schema.name)
        )
