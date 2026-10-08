"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const SEEN_KEY = "kayfabe_intro_seen";

/**
 * 전체 길이(ms) — 0.7초 등장 · 0.7초 룰 · 1.3초 정지 · 0.4초 걷힘.
 *
 * 1.2초로 시작했다가 **3초로 늘렸다** (2026-10-08 사용자). 늘어난 시간은 전부
 * 가운데 **정지 구간**으로 갔다 — 모션을 길게 끌면 느려 보이지만, 다 그려진
 * 워드마크가 잠깐 서 있는 것은 길이가 아니라 무게로 읽힌다.
 */
const TOTAL_MS = 3000;

/**
 * 랜딩 인트로 — Oswald 워드마크와 골드 룰 한 줄.
 *
 * **왜 랜딩에만 있나.** DESIGN.md §15는 표현적인 브랜드 모션이 사는 자리를
 * 랜딩·마케팅 표면으로 못 박는다 — 돌아가는 경기 위에는 얹지 않는다. 그래서
 * 이 컴포넌트는 `/kayfabe` 한 곳에서만 마운트되고, 공유 링크로 바로 들어온
 * 사람(PLE·AI LAB·감사 화면)은 아무것도 보지 않는다.
 *
 * **왜 SUPER-SUB의 잉크 번짐을 가져오지 않았나.** 그쪽은 셰이더로 그리는
 * 그 프로젝트의 브랜드 마크다. 같은 연출을 두 프로젝트가 쓰면 포트폴리오에서
 * 둘 다 템플릿으로 읽히고, KAYFABE 쪽 §7은 "과한 장식을 쓰지 않는다"이다.
 * 가져온 것은 연출이 아니라 **장치** — 진입 화면에서만, 세션 한 번, 막히면
 * 조용히 건너뛴다.
 *
 * 색은 전부 토큰이다(`--background` · `--foreground` · `--primary`). 라이트·
 * 다크가 각자 자기 값으로 뜨고, 이 파일에 hex 가 없다.
 */
export function KayfabeIntro() {
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    // `sessionStorage` 와 `matchMedia` 는 서버에 없다 — 재생 여부 자체가
    // 마운트 뒤에만 정해지는 값이라 effect 안에서 켠다.
    if (hasSeenIntro()) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      // 모션을 줄여 달라고 한 사람에게는 **아예 띄우지 않는다.** 정지된
      // 화면으로 3초를 막는 것은 배려가 아니라 그냥 지연이다.
      markIntroSeen();
      return;
    }
    setPlaying(true);
  }, []);

  useEffect(() => {
    if (!playing) return;

    const end = () => {
      setPlaying(false);
      markIntroSeen();
    };
    const timer = window.setTimeout(end, TOTAL_MS);

    // 아무 데나 누르거나 아무 키나 치면 바로 걷는다 — 3초를 기다릴지 말지는
    // 들어온 사람이 정한다.
    window.addEventListener("pointerdown", end);
    window.addEventListener("keydown", end);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", end);
      window.removeEventListener("keydown", end);
    };
  }, [playing]);

  if (!playing) return null;

  /* **`body` 로 포털한다.** 이 컴포넌트가 선 자리는 아레나 셸 안쪽의
     `relative z-10` 블록인데, 그 블록이 쌓임 맥락을 만들어서 아무리 높은
     z 를 줘도 그 안에서만 높다 — 헤더(body 직계 · z-50)가 그대로 위를 덮었다
     (실측: `elementFromPoint` 가 내비 링크를 집었다). 전면을 덮어야 하는
     오버레이는 맥락 밖에서 떠야 한다. */
  return createPortal(
    <div
      /* 화면을 덮는 장식이다 — 보조기기에는 읽히지 않게 둔다. 뒤에 있는 실제
         화면은 이미 렌더되어 있으므로 무엇도 가려지지 않는다. */
      aria-hidden
      className="fixed inset-0 z-[70] flex flex-col items-center justify-center bg-background"
      style={{
        animation: `kayfabe-intro-lift 400ms cubic-bezier(0.2, 0.6, 0.25, 1) ${TOTAL_MS - 400}ms both`,
      }}
    >
      <span
        className="font-sport text-5xl leading-none tracking-[0.04em] text-foreground sm:text-7xl"
        style={{ animation: "kayfabe-intro-mark 700ms cubic-bezier(0.2, 0.6, 0.25, 1) both" }}
      >
        KAYFABE
      </span>
      <span
        /* `bg-primary` 가 아니라 `bg-brand` 다 — 다크에서 `--primary` 는 금색이
           아니라 근백색으로 계산된다(실측 `lab(98.26% 0 0)`). 챔피언십 골드를
           테마별로 바로 가리키는 토큰은 `--brand` 쪽이다: 라이트 `#dd7400` ·
           다크 `#fcbb00` (DESIGN.md §2). */
        className="mt-6 block h-1 w-24 origin-left bg-brand sm:w-28"
        style={{ animation: "kayfabe-intro-rule 700ms cubic-bezier(0.2, 0.6, 0.25, 1) 600ms both" }}
      />
    </div>,
    document.body,
  );
}

/**
 * 사파리 프라이빗 모드 등에서는 `sessionStorage` 접근이 던진다. 던지면
 * "이미 봤다"로 친다 — 연출 때문에 화면이 안 열리는 것보다 건너뛰는 편이 낫다.
 */
function hasSeenIntro(): boolean {
  try {
    return sessionStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return true;
  }
}

function markIntroSeen(): void {
  try {
    sessionStorage.setItem(SEEN_KEY, "1");
  } catch {
    // 못 써도 그냥 둔다 — 다음 진입에 한 번 더 돌 뿐 화면은 정상이다.
  }
}
