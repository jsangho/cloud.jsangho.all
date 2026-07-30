"""core 테스트 부트스트랩.

저장소 루트에 `fastapi/` 디렉터리가 있고 그 안에 (빈) `__init__.py`가 있어서, 루트가
`sys.path`에 들어가면 `import fastapi`가 실제 FastAPI 패키지 대신 이 디렉터리로 해석된다.
core 모듈은 FastAPI를 직접 임포트하므로 이 충돌을 그대로 만난다.
배경과 대응은 `apps/kayfabe/tests/conftest.py`와 동일하다 — 이 트리에도 `__init__.py`를
두지 않는다.
"""

import sys
from pathlib import Path

_here = Path(__file__).parent
_fastapi_dir = _here.parents[1]  # fastapi/
_repo_root = _here.parents[2]  # 저장소 루트

sys.path[:] = [p for p in sys.path if p != str(_repo_root)]

_shadow_init = str(_fastapi_dir / "__init__.py")
if getattr(sys.modules.get("fastapi"), "__file__", None) == _shadow_init:
    del sys.modules["fastapi"]

# fastapi/ → "core.*" 임포트 활성화
if str(_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(_fastapi_dir))
