"""wwe_game 테스트 부트스트랩.

저장소 루트에 `fastapi/` 디렉터리가 있고 그 안에 (빈) `__init__.py`가 있어서, 루트가
`sys.path`에 들어가면 `import fastapi`가 실제 FastAPI 패키지 대신 이 디렉터리로 해석된다.
pytest는 rootdir(저장소 루트)를 기준으로 수집하므로 그대로 걸린다. kayfabe conftest와
같은 처리다.

wwe_game의 도메인은 FastAPI를 임포트하지 않지만(§4-6), 같은 pytest 세션에서 다른 앱
테스트가 함께 돌면 캐시가 오염되므로 동일하게 막는다.
"""

import sys
from pathlib import Path

_here = Path(__file__).parent
_fastapi_dir = _here.parents[2]  # fastapi/
_repo_root = _here.parents[3]  # 저장소 루트

sys.path[:] = [p for p in sys.path if p != str(_repo_root)]

_shadow_init = str(_fastapi_dir / "__init__.py")
if getattr(sys.modules.get("fastapi"), "__file__", None) == _shadow_init:
    del sys.modules["fastapi"]

# fastapi/apps/ → "wwe_game.*" 임포트 활성화
_apps_dir = str(_fastapi_dir / "apps")
if _apps_dir not in sys.path:
    sys.path.insert(0, _apps_dir)

# `domain/_helpers.py`의 `make_run`을 어댑터 테스트에서도 쓴다. pytest는 테스트 파일이
# 있는 디렉터리만 sys.path에 넣으므로 `tests/adapter/`에서는 안 보인다. 빌더가 둘로
# 갈리면 두 곳이 서로 다른 CareerRun을 만들어, 같은 버그를 한쪽만 재현하게 된다.
_domain_tests = str(_here / "domain")
if _domain_tests not in sys.path:
    sys.path.insert(0, _domain_tests)
