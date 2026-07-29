"""kayfabe 테스트 부트스트랩.

저장소 루트에 `fastapi/` 디렉터리가 있고 그 안에 (빈) `__init__.py`가 있어서, 루트가
`sys.path`에 들어가면 `import fastapi`가 실제 FastAPI 패키지 대신 이 디렉터리로 해석된다.
컨테이너는 `fastapi/`를 작업 디렉터리로 쓰기 때문에 운영에서는 드러나지 않지만,
pytest는 rootdir(저장소 루트)를 기준으로 수집하므로 그대로 걸린다.
kayfabe 테스트는 `core.*`를 거쳐 FastAPI를 임포트하므로 이 충돌을 직접 만난다.

그래서 아래 두 가지를 한다.
1. `sys.path`에서 저장소 루트를 제거한다.
2. pytest가 수집 중 이미 임포트해 둔 `fastapi`(= 저장소 디렉터리) 캐시를 비운다.
   경로를 정확히 대조해 실제 패키지는 건드리지 않는다.

또한 이 트리에는 `__init__.py`를 두지 않는다(titanic 테스트와 다른 점). 두면 pytest가
모듈 이름을 `fastapi.apps.kayfabe...`로 만들어 같은 충돌을 되살린다.
실행 방법은 이 디렉터리의 테스트 모듈 상단 주석을 참고한다.
"""

import sys
from pathlib import Path

_here = Path(__file__).parent
_fastapi_dir = _here.parents[2]  # fastapi/
_repo_root = _here.parents[3]  # 저장소 루트

sys.path[:] = [p for p in sys.path if p != str(_repo_root)]

_shadow_init = str(_fastapi_dir / "__init__.py")
if getattr(sys.modules.get("fastapi"), "__file__", None) == _shadow_init:
    # 최상위 항목만 지운다. `fastapi.*` 하위 키에는 pytest가 등록해 둔 이 conftest
    # 모듈(`fastapi.apps.kayfabe.tests.conftest`)이 들어 있어 함께 지우면 임포트가 깨진다.
    del sys.modules["fastapi"]

# fastapi/apps/ → "kayfabe.*" 임포트 활성화
_apps_dir = str(_fastapi_dir / "apps")
if _apps_dir not in sys.path:
    sys.path.insert(0, _apps_dir)

# fastapi/ → "core.*" 임포트 활성화 (ORM이 core.entities 경로 사용)
if str(_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(_fastapi_dir))
