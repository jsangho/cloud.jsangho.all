import { BarChart3, Bot, Search, Ship } from "lucide-react";

const LEARNING_OBJECTIVES = [
  "데이터 수집 및 전처리 기술 습득",
  "탐색적 데이터 분석 (EDA) 실습",
  "분류 모델 개발 및 성능 평가",
  "실제 데이터 기반 인사이트 도출",
] as const;

const MAIN_TOPICS = [
  "타이타닉 탑승객 데이터셋 분석",
  "성별, 연령, 좌석 등급에 따른 생존율 분석",
  "로지스틱 회귀 모델을 이용한 생존 예측",
  "모델 성능 평가 및 해석",
] as const;

const HIGHLIGHTS = [
  {
    icon: Ship,
    title: "Titanic",
    lines: ["1912년 침몰", "1,500명 이상 사망"],
  },
  {
    icon: BarChart3,
    title: "2,224명",
    lines: ["탑승객"],
  },
  {
    icon: Search,
    title: "데이터 분석",
    lines: [],
  },
  {
    icon: Bot,
    title: "머신러닝 모델",
    lines: [],
  },
] as const;

function BulletList({ items }: { items: readonly string[] }) {
  return (
    <ul className="mt-3 space-y-2 text-sm leading-relaxed text-stone-600 dark:text-stone-300">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span
            className="mt-2 size-1.5 shrink-0 rounded-full bg-stone-400"
            aria-hidden
          />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function LessonTitanicOverview() {
  return (
    <div className="mx-auto max-w-5xl">
      <p className="text-xs font-semibold uppercase tracking-widest text-stone-500">
        Lesson
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-50 md:text-4xl">
        타이타닉 모델 분석
      </h1>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-stone-600 dark:text-stone-300 md:text-base">
        역사 속 가장 유명한 해양사고인 타이타닉 침몰 사건을 데이터 분석을 통해
        살펴봅니다. 머신러닝 모델을 활용하여 승객의 생존 확률을 예측하는 방법을
        배웁니다.
      </p>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_minmax(220px,280px)] lg:gap-10">
        <div className="min-w-0 space-y-8">
          <section>
            <h2 className="text-lg font-bold text-stone-800 dark:text-stone-100">
              학습 목표
            </h2>
            <BulletList items={LEARNING_OBJECTIVES} />
          </section>
          <section>
            <h2 className="text-lg font-bold text-stone-800 dark:text-stone-100">
              주요 내용
            </h2>
            <BulletList items={MAIN_TOPICS} />
          </section>
        </div>

        <aside className="h-fit rounded-2xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-950/50 p-5 shadow-lg shadow-black/20 backdrop-blur-sm">
          <ul className="space-y-5">
            {HIGHLIGHTS.map(({ icon: Icon, title, lines }) => (
              <li
                key={title}
                className="flex flex-col items-center text-center"
              >
                <div className="flex size-12 items-center justify-center rounded-xl bg-stone-200/80 dark:bg-stone-800/80 text-stone-700 dark:text-stone-200">
                  <Icon className="size-6" aria-hidden />
                </div>
                <p className="mt-2 text-sm font-semibold text-stone-800 dark:text-stone-100">
                  {title}
                </p>
                {lines.map((line) => (
                  <p key={line} className="text-xs text-stone-400">
                    {line}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
