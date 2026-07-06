"use client";

import { ChampionshipBoard } from "@/components/championship/championship-board";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function ChampionshipPage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
        <header className="relative mb-8 text-center sm:mb-10">
          <div
            aria-hidden
            className="hero-title-backdrop mx-auto"
            style={{ height: "8rem", width: "min(100%, 22rem)" }}
          />
          <h1 className="font-kr-hero relative z-10 text-2xl text-stone-900 dark:text-white sm:text-3xl md:text-4xl">
            챔피언십
          </h1>
          <p className="relative z-10 mx-auto mt-3 max-w-lg text-sm font-medium leading-relaxed text-stone-400 sm:text-base">
            브랜드별{" "}
            <span className="font-semibold text-stone-700 dark:text-stone-200">
              현역 챔피언
            </span>
            을 메인·2선·태그·기타 순으로 확인할 수 있습니다.
          </p>
        </header>

        <ChampionshipBoard />
      </div>
    </WweArenaShell>
  );
}
