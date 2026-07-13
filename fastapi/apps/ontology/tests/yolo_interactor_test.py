import os
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# "vision.*" 임포트를 위해 apps/ 디렉터리를 sys.path에 등록 (main.py와 동일한 방식)
_APPS_DIR = str(TESTS_DIR.parents[1])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from ontology.app.dtos.face_recognition_dto import FaceTrainConfig
from ontology.dependencies.yolo_provider import get_yolo_use_case

# 다운로드/결과 파일이 tests 디렉터리 밖으로 새지 않도록 cwd를 이 파일 위치로 고정한다.
os.chdir(TESTS_DIR)

use_case = get_yolo_use_case()

train_result = use_case.train(FaceTrainConfig(epochs=5, image_size=224, batch_size=16))
print("학습 완료:", train_result)

sample_image = (
    Path(__file__).resolve().parents[1] / "resources" / "yolo_train" / "val" / "madonna"
)
sample_image = next(sample_image.glob("*.jpg"))

recognition_result = use_case.recognize(
    image_path=str(sample_image), weights_path=train_result.best_weights_path
)
print("인식 결과:", recognition_result)
