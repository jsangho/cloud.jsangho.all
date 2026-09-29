import asyncio
import os
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# "ontology.*" 임포트를 위해 apps/ 디렉터리를 sys.path에 등록 (main.py와 동일한 방식)
_APPS_DIR = str(TESTS_DIR.parents[1])
if _APPS_DIR not in sys.path:
    sys.path.insert(0, _APPS_DIR)

from ontology.dependencies.image_classifier_provider import (
    get_image_classifier_use_case,
)

# 샘플은 이 디렉터리의 일반 사진 하나다. 전에는 얼굴 인식 학습 데이터셋
# (`resources/yolo_train`)에서 한 장을 빌려 썼는데, 2026-09-29에 얼굴 인식을
# 지우면서 그 디렉터리가 함께 사라졌다. 이 스크립트가 보는 것은 ImageNet 분류기라
# 인물 사진일 이유가 없다.
_SAMPLE_IMAGE = TESTS_DIR / "bus.jpg"

use_case = get_image_classifier_use_case()


async def main() -> None:
    image_bytes = _SAMPLE_IMAGE.read_bytes()

    print("1) 정상 이미지 분류")
    result = await use_case.classify(image_bytes)
    print("   label:", result.label, "confidence:", result.confidence)
    assert result.label
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.top5) == 5

    print("2) 손상된 파일 -> ValueError")
    try:
        await use_case.classify(b"not a real image")
        raise AssertionError("ValueError가 발생해야 합니다")
    except ValueError:
        print("   OK")

    print("3) confidence threshold 경계값")
    os.environ["CLASSIFIER_CONFIDENCE_THRESHOLD"] = "0.99"
    strict_result = await use_case.classify(image_bytes)
    assert strict_result.is_confident is False, (
        "임계값을 극단적으로 높이면 is_confident=False여야 함"
    )

    os.environ["CLASSIFIER_CONFIDENCE_THRESHOLD"] = "0.01"
    lenient_result = await use_case.classify(image_bytes)
    assert lenient_result.is_confident is True, (
        "임계값을 매우 낮추면 is_confident=True여야 함"
    )
    print("   OK")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
