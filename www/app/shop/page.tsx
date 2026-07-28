"use client";

import { ShoppingBag } from "lucide-react";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function ShopPage() {
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
            상점
          </h1>
          <p className="relative z-10 mx-auto mt-3 max-w-lg text-sm font-medium leading-relaxed text-stone-400 sm:text-base">
            예측으로 모은{" "}
            <span className="font-semibold text-stone-700 dark:text-stone-200">
              점수
            </span>
            를 아이템으로 교환할 수 있는 상점을 준비 중입니다.
          </p>
        </header>

        <div className="rankings-panel ple-section-glow flex flex-col items-center gap-3 rounded-2xl px-4 py-16 text-center sm:rounded-3xl">
          <ShoppingBag className="h-8 w-8 text-amber-400/80" aria-hidden />
          <p className="text-sm font-medium text-stone-400">
            상점 기능은 아직 준비 중입니다. 오픈되면 이곳에서 안내됩니다.
          </p>
        </div>
      </div>
    </WweArenaShell>
  );
}
