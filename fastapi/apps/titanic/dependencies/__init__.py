"""
Titanic 의존성 조립소 (DIP 팩토리).

각 슬라이스 provider 모듈의 FastAPI Depends 팩토리를 re-export 한다.

DIP 원칙:
  - 라우터는 PgRepository 구현체를 직접 알지 못한다.
  - 리턴 타입은 구현체가 아닌 UseCase 포트로 선언한다.
  - 세션은 core 의 get_db 에서 주입받는다 (AsyncSession).
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "get_andrews_architect",
    "get_hartley_violin",
    "get_james_director",
    "get_lowe_boat",
    "get_smith_captain",
    "get_walter_roaster",
    "get_cal_tester",
    "get_isidor_couple",
    "get_jack_trainer",
    "get_molly_scaler",
    "get_rose_model",
    "get_ruth_validation",
]

_LAZY_IMPORTS: dict[str, str] = {
    "get_andrews_architect": "titanic.dependencies.crew_andrews_architect_provider",
    "get_hartley_violin": "titanic.dependencies.crew_hartley_violin_provider",
    "get_james_director": "titanic.dependencies.crew_james_director_provider",
    "get_lowe_boat": "titanic.dependencies.crew_lowe_boat_provider",
    "get_smith_captain": "titanic.dependencies.crew_smith_captain_provider",
    "get_walter_roaster": "titanic.dependencies.crew_walter_roaster_provider",
    "get_cal_tester": "titanic.dependencies.passenger_cal_tester_provider",
    "get_isidor_couple": "titanic.dependencies.passenger_isidor_couple_provider",
    "get_jack_trainer": "titanic.dependencies.passenger_jack_trainer_provider",
    "get_molly_scaler": "titanic.dependencies.passenger_molly_scaler_provider",
    "get_rose_model": "titanic.dependencies.passenger_rose_model_provider",
    "get_ruth_validation": "titanic.dependencies.passenger_ruth_validation_provider",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path)
    return getattr(module, name)
