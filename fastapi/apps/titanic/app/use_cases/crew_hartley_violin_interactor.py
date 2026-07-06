from __future__ import annotations

import io

from pandas import DataFrame

from titanic.app.dtos.crew_hartley_violin_dto import (
    HartleyViolinQuery,
    HartleyViolinResponse,
)
from titanic.app.ports.input.crew_hartley_violin_use_case import HartleyViolinUseCase
from titanic.app.ports.output.crew_hartley_violin_port import HartleyViolinPort


class HartleyViolinInteractor(HartleyViolinUseCase):
    def __init__(self, repository: HartleyViolinPort):
        self.repository = repository

    async def introduce_myself(
        self, query: HartleyViolinQuery
    ) -> HartleyViolinResponse:
        return await self.repository.introduce_myself(query)

    # 컬럼명 = VO 파일명 (9개 단독 + ticket_vo)
    # sib_sp_vo 삭제 (survived 상관계수 -0.04, 유의미하지 않음)
    _FEATURES = [
        "survived_vo",
        "pclass_vo",
        "gender_vo",
        "age_vo",
        "parch_vo",
        "fare_vo",
        "embarked_vo",
        "cabin_vo",
        "title_vo",
        "ticket_vo",
    ]

    _TITLE_ENCODING: dict[str, int] = {
        "Mr": 1,
        "Mlle": 1,
        "Miss": 2,
        "Ms": 2,
        "Mrs": 3,
        "Master": 4,
        "Lady": 5,
        "Countess": 5,
        "Sir": 5,
        "Capt": 6,
        "Col": 6,
        "Don": 6,
        "Dr": 6,
        "Major": 6,
        "Rev": 6,
        "Jonkheer": 6,
        "Dona": 6,
        "Mme": 6,
    }

    def get_correlation_heatmap(self, df: DataFrame) -> bytes:
        df = df.copy()

        # gender_vo: female=0, male=1
        gender_col = next(
            (c for c in ("gender", "Sex", "sex") if c in df.columns), None
        )
        df["gender_vo"] = df[gender_col].map(
            {"female": 0, "male": 1, "Female": 0, "Male": 1}
        )

        # embarked_vo: C=0, Q=1, S=2
        emb_col = "Embarked" if "Embarked" in df.columns else "embarked"
        df["embarked_vo"] = df[emb_col].map({"C": 0, "Q": 1, "S": 2})

        # cabin_vo: Cabin 첫 글자 A-G → 1-7, NaN=0
        if "Cabin" in df.columns:
            df["cabin_vo"] = (
                df["Cabin"]
                .str[0]
                .map({"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7})
                .fillna(0)
                .astype(int)
            )
        else:
            df["cabin_vo"] = (
                df["deck"]
                .astype(object)
                .map({"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7})
                .fillna(0)
                .astype(int)
            )

        # title_vo: Name에서 추출 → TitleCategory 인코딩
        if "Name" in df.columns:
            df["title_vo"] = (
                df["Name"]
                .str.extract(r",\s*([^\.]+)\.")
                .squeeze()
                .str.strip()
                .map(self._TITLE_ENCODING)
                .fillna(0)
                .astype(int)
            )
        else:
            df["title_vo"] = df["who"].map({"man": 1, "woman": 3, "child": 4})

        # ticket_vo: 같은 티켓 번호 공유 승객 수 (titanic-features.md 기준)
        if "Ticket" in df.columns:
            df["ticket_vo"] = df["Ticket"].map(df["Ticket"].value_counts())
        else:
            df["ticket_vo"] = (
                df["sibsp"] + df["parch"] + 1
            )  # DB에 Ticket 없을 때 FamilyRelation 대체

        survived_col = "Survived" if "Survived" in df.columns else "survived"
        pclass_col = "Pclass" if "Pclass" in df.columns else "pclass"
        age_col = "Age" if "Age" in df.columns else "age"
        parch_col = "Parch" if "Parch" in df.columns else "parch"
        fare_col = "Fare" if "Fare" in df.columns else "fare"

        df = df.rename(
            columns={
                survived_col: "survived_vo",
                pclass_col: "pclass_vo",
                age_col: "age_vo",
                parch_col: "parch_vo",
                fare_col: "fare_vo",
            }
        )

        import matplotlib.pyplot as plt
        import seaborn as sns

        corr = df[self._FEATURES].corr()
        fig, ax = plt.subplots(figsize=(13, 11))
        sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5, ax=ax)
        ax.set_title("Titanic Feature Correlation Heatmap (10 VO Features)")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf.read()

    _DISPLAY_LABEL: dict[str, str] = {
        "gender": "Gender",
        "pclass": "Pclass",
        "embarked": "Embarked",
    }

    def get_survival_rate_chart(self, df: DataFrame) -> bytes:
        import matplotlib.pyplot as plt

        features = ["pclass", "gender", "embarked"]
        valid = [f for f in features if f in df.columns and "survived" in df.columns]
        fig, axes = plt.subplots(1, len(valid), figsize=(14, 5))
        if len(valid) == 1:
            axes = [axes]
        for ax, feature in zip(axes, valid, strict=False):
            label = self._DISPLAY_LABEL.get(feature, feature.capitalize())
            df.groupby(feature)["survived"].mean().plot(
                kind="bar", ax=ax, color="steelblue", edgecolor="black"
            )
            ax.set_title(f"Survival Rate by {label}")
            ax.set_ylabel("Survival Rate")
            ax.set_xlabel(label)
            ax.tick_params(axis="x", rotation=0)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)
        plt.close(fig)
        return buf.read()
