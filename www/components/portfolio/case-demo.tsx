"use client";

import { useState } from "react";
import { ChevronUp, Play } from "lucide-react";

import type { CaseStudy } from "@/lib/portfolio-cases";

type Demo = NonNullable<CaseStudy["demo"]>;
type CaseDemoProps = { demo: Demo; name: string };

/**
 * 시연영상 — **접힌 상태가 기본이다** (2026-10-08 사용자).
 *
 * 누르기 전에는 재생 요소(`<video>` · YouTube `<iframe>`)를 아예 마운트하지 않는다.
 * `preload="none"` 으로도 포스터는 받고 일부 브라우저는 메타데이터를 당겨 가며,
 * YouTube 임베드는 그보다 훨씬 무겁다 — 요소를 안 만들면 그마저 없다. 읽으러 온
 * 사람이 영상을 먼저 받지 않게 하는 것이 접어 두는 이유이므로, 접힘은 **시각적
 * 접힘이 아니라 네트워크 접힘**이어야 한다.
 *
 * 접을 때도 요소를 내린다. 그래야 재생이 함께 멈춘다 — 접었는데 뒤에서 계속
 * 도는 상태를 만들지 않는다.
 *
 * **버튼에 골드를 쓰지 않는다.** 이 페이지의 단일 골드 액션은 대표 링크다
 * (DESIGN.md §7). 영상 토글까지 금색이면 둘 중 무엇이 주인지 사라진다.
 */
export function CaseDemo({ demo, name }: CaseDemoProps) {
  const [open, setOpen] = useState(false);

  return (
    <section className="mt-6" aria-label="시연영상">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="case-demo-panel"
        className="group flex w-full items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:bg-card-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-link"
      >
        <span
          aria-hidden
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-surface-2 text-foreground"
        >
          {open ? <ChevronUp className="size-4" /> : <Play className="size-4" />}
        </span>

        <span className="min-w-0 flex-1">
          <span className="block text-base font-semibold leading-tight text-foreground">
            {open ? "시연영상 접기" : "시연영상 보기"}
          </span>
          {/* 누르기 전에 길이를 알려 준다 — 재생 시간을 숨기고 유도하지 않는다. */}
          <span className="mt-1 block text-xs text-muted-foreground">
            {demo.length} · {demo.note}
          </span>
        </span>
      </button>

      {open && (
        <div
          id="case-demo-panel"
          /* **열리는 자리가 버튼 아래**라 화면 밖에서 열릴 수 있다 —
             `nearest` 로 딱 보이는 만큼만 끌어온다 (가운데 정렬은 과하다). */
          ref={(el) => {
            el?.scrollIntoView({
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "auto"
                : "smooth",
              block: "nearest",
            });
          }}
          className="mt-3 overflow-hidden rounded-2xl border border-border bg-black"
        >
          <DemoPlayer demo={demo} name={name} />
        </div>
      )}
    </section>
  );
}

function DemoPlayer({ demo, name }: CaseDemoProps) {
  if (demo.kind === "youtube") {
    return (
      /* `youtube-nocookie` 를 쓴다 — 재생 전까지 쿠키를 심지 않는 쪽이다.
         `rel=0` 은 끝났을 때 남의 영상을 추천 카드로 깔지 않게 한다. */
      <iframe
        className="block aspect-video w-full"
        src={`https://www.youtube-nocookie.com/embed/${demo.youtubeId}?autoplay=1&rel=0`}
        title={`${name} 시연영상`}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
      />
    );
  }

  return (
    /* 캡션 트랙(`<track>`)을 달지 않는다 — 음성 트랙 자체가 없는 영상이고,
       말에 해당하는 것은 전부 화면에 구워 넣은 자막이다. */
    <video
      /* 눌러서 연 것이므로 사용자 제스처 안이고, 소리가 없으니 바로 튼다.
         자동 재생이 막힌 환경에서는 조용히 포스터 + 재생 버튼으로 남는다. */
      ref={(el) => {
        void el?.play().catch(() => undefined);
      }}
      className="block aspect-video w-full"
      src={demo.src}
      poster={demo.poster}
      controls
      autoPlay
      muted
      playsInline
      aria-label={`${name} 시연영상`}
    />
  );
}
