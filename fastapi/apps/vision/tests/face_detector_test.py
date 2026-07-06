import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# "vision.*" 임포트를 위해 apps/ 디렉터리를 sys.path에 등록 (main.py와 동일한 방식)
_APPS_DIR = str(TESTS_DIR.parents[1])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from vision.dependencies.face_detector_provider import get_face_detector_use_case

use_case = get_face_detector_use_case()

sample_image = next(
    (TESTS_DIR.parents[0] / "resources" / "yolo_train" / "val" / "madonna").glob(
        "*.jpg"
    )
)

result = use_case.detect(str(sample_image))
print("탐지 결과:", result)
