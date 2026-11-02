"use client";

import type { CareerView } from "@/lib/career-api";

/**
 * 단계마다 눌릴 버튼이 하나다. **결산과 다음 시즌 시작은 갈라져 있다** — 서버가
 * 두 호출로 나눠 뒀고(`/settle` · `/next-season`), 합치면 "결산은 봤고 다음 시즌은
 * 아직" 상태를 화면이 표현할 수 없다.
 */
export function PhaseAction({
  view,
  busy,
  onAdvance,
  onSettle,
  onNextSeason,
  size = "md",
}: {
  view: CareerView;
  busy: string | null;
  onAdvance: () => void;
  onSettle: () => void;
  onNextSeason: () => void;
  /** 대시보드 히어로에서는 크게 — 커리어에서 가장 중요한 행동이다. */
  size?: "md" | "lg";
}) {
  if (view.phase === "ended") {
    return (
      <p className="arena-panel p-4 text-sm text-stone-300">
        커리어가 끝났습니다. 기록은 그대로 남습니다 — 「타이틀」과 「커리어 기록」 탭에서 읽을 수
        있습니다.
      </p>
    );
  }

  const [label, handler, hint] =
    view.phase === "settlement"
      ? ([
          busy === "settle" ? "결산 중…" : `시즌 ${view.season} 결산`,
          onSettle,
          "주차를 다 썼습니다. 결산에서 나이가 한 살 오르고 시즌 요약이 쌓입니다.",
        ] as const)
      : view.phase === "offseason"
        ? ([
            busy === "next-season" ? "시작 중…" : `시즌 ${view.season + 1} 시작`,
            onNextSeason,
            "주차만 1로 돌아가고 전적·벨트·관계는 그대로 이어집니다.",
          ] as const)
        : ([
            busy === "advance" ? "진행 중…" : "주차 진행",
            onAdvance,
            view.actionPoints > 0
              ? `행동 포인트가 ${view.actionPoints}점 남았습니다 — 진행하면 사라집니다.`
              : "행동을 다 썼습니다.",
          ] as const);

  return (
    <div>
      <button
        type="button"
        onClick={handler}
        disabled={busy != null}
        aria-busy={busy != null}
        className={
          size === "lg"
            ? "arena-cta h-16 w-full px-8 font-sport text-2xl uppercase"
            : "arena-cta h-12 w-full px-6 font-sport text-lg uppercase"
        }
      >
        <svg aria-hidden viewBox="0 0 16 16" className={size === "lg" ? "size-5" : "size-4"}>
          <path d="M4 2.5v11l9-5.5z" fill="currentColor" />
        </svg>
        {label}
      </button>
      <p className="mt-2 text-center text-[11px] text-stone-400">{hint}</p>
    </div>
  );
}
