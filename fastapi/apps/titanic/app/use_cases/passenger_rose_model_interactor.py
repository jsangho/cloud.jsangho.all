from __future__ import annotations

from abc import abstractmethod

from titanic.app.dtos.passenger_rose_model_dto import (
    PassengerFeaturesQuery,
    RoseModelQuery,
    RoseModelResponse,
    SurvivalPredictionResponse,
)
from titanic.app.ports.input.passenger_rose_model_use_case import (
    RoseModelUseCase,
    SurvivalPredictionStrategy,
)
from titanic.app.ports.output.passenger_rose_model_port import RoseModelPort

# ── 피처 인코딩 ───────────────────────────────────────────────────────────────


def _encode(f: PassengerFeaturesQuery) -> list[float]:
    sex = 1.0 if f.sex.lower() == "female" else 0.0
    embarked = {"s": 0.0, "c": 1.0, "q": 2.0}.get(f.embarked.lower(), 0.0)
    return [
        float(f.pclass),
        sex,
        float(f.age),
        float(f.sibsp),
        float(f.parch),
        float(f.fare),
        embarked,
    ]


# ── sklearn 기반 공통 베이스 ──────────────────────────────────────────────────


class _SklearnStrategy(SurvivalPredictionStrategy):
    def __init__(self) -> None:
        self._model = self._build_model()
        self._fitted = False

    @abstractmethod
    def _build_model(self): ...

    def fit(self, X: list[list[float]], y: list[int]) -> None:
        self._model.fit(X, y)
        self._fitted = True

    def _require_fit(self) -> None:
        if not self._fitted:
            raise ValueError(
                f"{self.algorithm_name} 모델이 학습되지 않았습니다. train()을 먼저 호출하세요."
            )

    def predict(self, features: PassengerFeaturesQuery) -> SurvivalPredictionResponse:
        self._require_fit()
        prob = float(self._model.predict_proba([_encode(features)])[0][1])
        return SurvivalPredictionResponse(
            survived=prob >= 0.5,
            probability=round(prob, 4),
            algorithm=self.algorithm_name,
        )

    def batch_predict(self, X: list[list[float]]) -> list[int]:
        self._require_fit()
        return [int(p) for p in self._model.predict(X)]


# ── 10대 알고리즘 전략 ─────────────────────────────────────────────────────────


class XGBoostStrategy(_SklearnStrategy):
    """1위: 그래디언트 부스팅. 강력한 규제로 과적합 방지."""

    @property
    def algorithm_name(self) -> str:
        return "XGBoost"

    def _build_model(self):
        from xgboost import XGBClassifier

        return XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")


class RandomForestStrategy(_SklearnStrategy):
    """2위: 결정 트리 배깅. 튜닝 없이도 안정적인 Baseline."""

    @property
    def algorithm_name(self) -> str:
        return "RandomForest"

    def _build_model(self):
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(n_estimators=100, random_state=42)


class LightGBMStrategy(_SklearnStrategy):
    """3위: 리프 중심 트리 분할. 대용량 고속 처리."""

    @property
    def algorithm_name(self) -> str:
        return "LightGBM"

    def _build_model(self):
        from lightgbm import LGBMClassifier

        return LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)


class LogisticRegressionStrategy(_SklearnStrategy):
    """5위: 선형 이진 분류. 피처별 영향력 해석에 최적."""

    @property
    def algorithm_name(self) -> str:
        return "LogisticRegression"

    def _build_model(self):
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=1000, random_state=42)


class DecisionTreeStrategy(_SklearnStrategy):
    """6위: 규칙 기반 트리. 분류 기준 시각화에 유리하나 과적합 주의."""

    @property
    def algorithm_name(self) -> str:
        return "DecisionTree"

    def _build_model(self):
        from sklearn.tree import DecisionTreeClassifier

        return DecisionTreeClassifier(max_depth=5, random_state=42)


class SVMStrategy(_SklearnStrategy):
    """7위: 마진 최대화 결정 경계. 표준화 전처리 시 비선형 관계에 강점."""

    @property
    def algorithm_name(self) -> str:
        return "SVM"

    def _build_model(self):
        from sklearn.svm import SVC

        return SVC(probability=True, random_state=42)


class KNNStrategy(_SklearnStrategy):
    """8위: K-최근접 이웃. 승객 유사도(나이·요금·객실) 기반 분류."""

    @property
    def algorithm_name(self) -> str:
        return "KNN"

    def _build_model(self):
        from sklearn.neighbors import KNeighborsClassifier

        return KNeighborsClassifier(n_neighbors=5)


class NaiveBayesStrategy(_SklearnStrategy):
    """9위: 베이즈 조건부 확률. 빠른 연산, 희소 데이터에도 준수한 성능."""

    @property
    def algorithm_name(self) -> str:
        return "NaiveBayes"

    def _build_model(self):
        from sklearn.naive_bayes import GaussianNB

        return GaussianNB()


class KMeansPCAStrategy(SurvivalPredictionStrategy):
    """10위: 비지도 학습 — PCA 차원 축소 후 K-Means 군집 기반 예측."""

    @property
    def algorithm_name(self) -> str:
        return "KMeans+PCA"

    def __init__(self) -> None:
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        self._scaler = StandardScaler()
        self._pca = PCA(n_components=3)
        self._kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        self._cluster_survival: dict[int, float] = {}
        self._fitted = False

    def fit(self, X: list[list[float]], y: list[int]) -> None:
        import numpy as np

        arr = np.array(X)
        scaled = self._scaler.fit_transform(arr)
        reduced = self._pca.fit_transform(scaled)
        labels = self._kmeans.fit_predict(reduced)
        for cluster in range(2):
            mask = labels == cluster
            self._cluster_survival[cluster] = float(np.mean(np.array(y)[mask]))
        self._fitted = True

    def _require_fit(self) -> None:
        if not self._fitted:
            raise ValueError(
                "KMeans+PCA 모델이 학습되지 않았습니다. train()을 먼저 호출하세요."
            )

    def _transform(self, X):
        import numpy as np

        scaled = self._scaler.transform(np.array(X))
        return self._pca.transform(scaled)

    def predict(self, features: PassengerFeaturesQuery) -> SurvivalPredictionResponse:
        self._require_fit()
        cluster = int(self._kmeans.predict(self._transform([_encode(features)]))[0])
        prob = self._cluster_survival.get(cluster, 0.5)
        return SurvivalPredictionResponse(
            survived=prob >= 0.5,
            probability=round(prob, 4),
            algorithm=self.algorithm_name,
        )

    def batch_predict(self, X: list[list[float]]) -> list[int]:
        self._require_fit()
        clusters = self._kmeans.predict(self._transform(X))
        return [int(self._cluster_survival.get(int(c), 0.5) >= 0.5) for c in clusters]


# ── 전략 레지스트리 ────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[SurvivalPredictionStrategy]] = {
    "xgboost": XGBoostStrategy,
    "random_forest": RandomForestStrategy,
    "lightgbm": LightGBMStrategy,
    "logistic_regression": LogisticRegressionStrategy,
    "decision_tree": DecisionTreeStrategy,
    "svm": SVMStrategy,
    "knn": KNNStrategy,
    "naive_bayes": NaiveBayesStrategy,
    "kmeans_pca": KMeansPCAStrategy,
}


# ── Interactor (Context) ──────────────────────────────────────────────────────


class RoseModelInteractor(RoseModelUseCase):
    def __init__(self, repository: RoseModelPort) -> None:
        self.repository = repository
        self._strategies: dict[str, SurvivalPredictionStrategy] = {}

    def _get_strategy(self, algorithm: str) -> SurvivalPredictionStrategy:
        key = algorithm.lower().replace("-", "_").replace(" ", "_")
        if key not in self._strategies:
            cls = _REGISTRY.get(key)
            if cls is None:
                raise ValueError(
                    f"알 수 없는 알고리즘: {algorithm!r}. "
                    f"사용 가능: {', '.join(_REGISTRY)}"
                )
            self._strategies[key] = cls()
        return self._strategies[key]

    async def introduce_myself(self, query: RoseModelQuery) -> RoseModelResponse:
        return await self.repository.introduce_myself(
            RoseModelQuery(id=query.id, name=query.name)
        )

    def list_algorithms(self) -> list[str]:
        return list(_REGISTRY.keys())

    async def train(self, X: list[list[float]], y: list[int], algorithm: str) -> None:
        self._get_strategy(algorithm).fit(X, y)

    async def predict(
        self, features: PassengerFeaturesQuery, algorithm: str
    ) -> SurvivalPredictionResponse:
        return self._get_strategy(algorithm).predict(features)

    async def batch_predict(self, X: list[list[float]], algorithm: str) -> list[int]:
        return self._get_strategy(algorithm).batch_predict(X)
