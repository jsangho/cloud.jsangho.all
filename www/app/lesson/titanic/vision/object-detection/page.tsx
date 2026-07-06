import { FaceObjectDetection } from "@/components/face-object-detection";

export default function LessonTitanicVisionObjectDetectionPage() {
  return (
    <main className="px-4 py-8">
      <div className="mx-auto grid max-w-2xl gap-8">
        <div>
          <h1 className="mb-2 text-3xl font-bold tracking-tight md:text-4xl">
            객체 탐지
          </h1>
          <p className="text-sm text-stone-600 dark:text-stone-300">
            YOLO 얼굴 탐지 모델로 이미지 속 얼굴 위치를 찾고, 크롭한 영역을 분류
            모델에 전달해 누구인지 예측합니다.
          </p>
          <p className="mt-4 text-sm text-stone-600 dark:text-stone-300">
            현재 분류 모델은 ben_afflek, elton_john, jerry_seinfeld, madonna,
            mindy_kaling 5명만 학습되어 있어, 이 5명이 아닌 얼굴을 넣으면
            확신도가 낮게 나오는 게 정상입니다.
          </p>
        </div>
        <FaceObjectDetection />
      </div>
    </main>
  );
}
