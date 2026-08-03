import sys
from pathlib import Path

_here = Path(__file__).parent

# apps/ → "lion_king.*" 임포트 활성화 (apps/titanic/tests/conftest.py와 같은 패턴)
_apps_dir = str(_here.parent.parent)
if _apps_dir not in sys.path:
    sys.path.insert(0, _apps_dir)

# fastapi/ → "core.*" 임포트 활성화
_root_dir = str(_here.parent.parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
