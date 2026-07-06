# ⚓ [Titanic App] Walter Nichols (Crew Roaster) 개발 및 검증 보고서

> **작성일:** 2026-06-17  
> **도메인:** titanic · crew_walter_roaster  
> **담당 캐릭터:** Walter Nichols (일등 항해사 — 승객 명단 관리)  
> **관련 문서:** [[titanic-features]] · [[titanic-erd]] · [[titanic-machine-learning]]

---

## 1. 아키텍처 명세 및 변경 요약

Walter Nichols의 요구사항에 맞춰 데이터셋 조회 엔드포인트를 구현하고, 기존 의존성 주입(DI) 버그를 전면 수정했습니다.

```
[Inbound Adapter]                   [Core / Input Port]              [Outbound Adapter]
  Router: /walter/train (def)  ──>    WalterRoasterUseCase   ──>    WalterRoasterRepository
  Router: /walter/test  (def)          (pd.DataFrame 반환)            (Pandas + Sync Engine)
```

### 포트 및 인터페이스 변경 사항

**동기(Sync) 처리 원칙 적용**  
Pandas + SQLAlchemy 조합으로 DB를 읽는 작업은 CPU/I/O 혼합 작업이므로 `async def`로 이벤트 루프를 블로킹하지 않도록 일반 `def`로 선언했습니다. FastAPI가 내부 스레드풀에서 안전하게 처리합니다.

> 참고: `sangho/CLAUDE.md` §9 — async def vs def 선택 기준

**반환 타입 정립**  
DTO(`WalterRoasterResponse`) 규격 제한을 탈피하고 ML 분석 목적에 맞게 `pd.DataFrame`을 직접 반환하도록 포트 인터페이스를 통일했습니다.

---

## 2. 레이어별 코드 구현 현황

### Input Port

`apps/titanic/app/ports/input/crew_walter_roaster_use_case.py`

```python
from abc import ABC, abstractmethod
import pandas as pd

class WalterRoasterUseCase(ABC):

    @abstractmethod
    def get_train_set(self) -> pd.DataFrame:
        """월터가 DB에서 train set 만 가져오는 메소드"""
        pass

    @abstractmethod
    def get_test_set(self) -> pd.DataFrame:
        """월터가 DB에서 test set 만 가져오는 메소드"""
        pass
```

### Use Case (Interactor)

`apps/titanic/app/use_cases/crew_walter_roaster_interactor.py`

```python
import pandas as pd
from titanic.app.ports.output.crew_walter_roaster_port import WalterRoasterPort

class WalterRoasterInteractor(WalterRoasterUseCase):
    def __init__(self, repository: WalterRoasterPort) -> None:
        self.repository = repository

    def get_train_set(self) -> pd.DataFrame:
        return self.repository.get_train_set()

    def get_test_set(self) -> pd.DataFrame:
        return self.repository.get_test_set()
```

### Outbound Repository

`apps/titanic/adapter/outbound/repositories/crew_walter_roaster_repository.py`

```python
from sqlalchemy import create_engine
import pandas as pd
import jsangho.core.matrix.grid_oracle_database_manager as _db_manager

class WalterRoasterRepository(WalterRoasterPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def get_train_set(self) -> pd.DataFrame:
        """Survived 컬럼이 있는 데이터 전체를 데이터프레임으로 반환"""
        sync_url = _to_sync_url(
            _db_manager.engine.url.render_as_string(hide_password=False)
        )
        sync_engine = create_engine(sync_url)
        return pd.read_sql(
            "SELECT * FROM passengers WHERE survived IS NOT NULL", sync_engine
        )

    def get_test_set(self) -> pd.DataFrame:
        """Survived 컬럼이 없는 데이터 전체를 데이터프레임으로 반환"""
        sync_url = _to_sync_url(
            _db_manager.engine.url.render_as_string(hide_password=False)
        )
        sync_engine = create_engine(sync_url)
        return pd.read_sql(
            "SELECT * FROM passengers WHERE survived IS NULL", sync_engine
        )
```

---

## 3. 디버깅 및 트러블슈팅 내역

서버 기동 및 격리 검증 단계에서 발견된 구조적 결함과 기존 버그를 일괄 수정했습니다.

| 발생 지점 | 현상 및 원인 | 조치 |
|-----------|-------------|------|
| SQLAlchemy Engine URL | `str(engine.url)` 사용 시 패스워드가 `***`로 마스킹되어 동기 엔진 생성 시 인증 실패 | `url.render_as_string(hide_password=False)` 로 명시하여 원본 자격증명 주입 |
| 모듈 단위 결합도 결함 | `from module import engine` 실행 시 `init_engine()` 호출 전의 `None` 객체를 조기 스냅숏 캡처하는 문제 | 모듈 객체 전체를 가져온 후(`import module as _m`), 런타임 시점에 `_m.engine`으로 안전하게 접근 |
| Titanic Providers (기존 버그) | `adapter.outbound.pg.*` 경로 오지정 및 팩토리 메소드 식별자 오타로 전면 실행 불가 상태 | 전역 프로바이더·라우터 의존성 import 경로 및 식별자 네이밍 전수 교정 완료 |

---

## 4. 최종 통합 검증 결과

**검증 방식:** Walter 라우터 스코프를 격리한 단독 미니 FastAPI 테스트 하네스로 실제 런타임 파이프라인 검증 수행.

**최종 판정: PASS (정상 작동)**

| 엔드포인트 | 상태 | 결과 |
|------------|------|------|
| `GET /api/titanic/walter/train` | **200 OK** | 891건 반환 — `passenger_id`, `name`, `gender`, `age`, `survived`(0 또는 1) 등 원천 변수 전수 포함 |
| `GET /api/titanic/walter/test` | **200 OK** | 0건 반환 — DB 내 `survived IS NULL` 레코드 부재 상태를 정상 반영 |

---

래그테일러(Ragtailor) 프로젝트의 타이타닉 도메인 중 명단 관리(Walter Nichols) 기능은 완벽히 안착했습니다. 다음 단계로 진행할 아키텍처 설계나 유스케이스 구현 작업이 있다면 말씀해 주세요!
