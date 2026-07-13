import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# "vision.*" 임포트를 위해 apps/ 디렉터리를 sys.path에 등록 (main.py와 동일한 방식)
_APPS_DIR = str(TESTS_DIR.parents[1])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from ontology.dependencies.face_identification_provider import (
    get_face_identification_use_case,
)

use_case = get_face_identification_use_case()

if len(sys.argv) > 1:
    sample_image = Path(sys.argv[1])
else:
    sample_image = next(
        (TESTS_DIR.parents[0] / "resources" / "yolo_train" / "val" / "madonna").glob(
            "*.jpg"
        )
    )
classifier_weights = TESTS_DIR / "runs" / "classify" / "train-2" / "weights" / "best.pt"

result = use_case.identify(
    str(sample_image), classifier_weights_path=str(classifier_weights)
)
print("파이프라인 결과:", result)
