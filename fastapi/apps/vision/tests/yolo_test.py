import os
from pathlib import Path

from ultralytics import YOLO

# 다운로드/결과 파일이 tests 디렉터리 밖으로 새지 않도록 cwd를 이 파일 위치로 고정한다.
os.chdir(Path(__file__).resolve().parent)

# ultralytics 공식 헬로우 월드: 사전학습 모델로 샘플 이미지 추론 후 결과 저장
# 컨테이너는 headless라 result.show()로 창을 띄울 수 없어 save()로 확인한다.
model = YOLO("yolov8n.pt")
results = model("https://ultralytics.com/images/bus.jpg")

for result in results:
    result.save(filename="yolo_result.jpg")
