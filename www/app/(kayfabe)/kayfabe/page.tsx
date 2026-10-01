"use client";

import { useEffect } from "react";
import Link from "next/link";
import { GeminiChatPanel } from "@/components/gemini-chat-panel";
import { AiPredictionCard } from "@/components/home/ai-prediction-card";
import { KpiStrip } from "@/components/home/kpi-strip";
import { PleAiScoreboard } from "@/components/ple-ai-scoreboard";
import { LeaderboardPreview } from "@/components/leaderboard-preview";
import { NextPleCountdownCard } from "@/components/next-ple-countdown-card";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function HomePage() {
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, []);

  return (
    <WweArenaShell>
      <div className="flex flex-col">
        {/*
         * ── 히어로 (KAYFABE 2.0 §2) ─────────────────────────────────────
         * **비디오를 지우지 않았다.** 화면 전체를 먹던 것을 왼쪽 칸 안으로
         * 줄였을 뿐이다 — 오른쪽은 실제 AI 예측이 선다. 첫 화면에서
         * "무엇을 하는 서비스인가"와 "그래서 지금 뭘 아는가"가 같이 보여야 한다.
         */}
        {/*
         * **밴드는 전폭이고 안쪽만 폭을 잡는다.** 경계가 화면 끝까지 닿아야
         * 아래 구역과 갈리는 선이 의도로 읽힌다 — 가운데만 색이 다르면
         * 카드 하나가 커진 것처럼 보인다. 글자·테두리는 토큰 그대로다:
         * 밴드는 밝은 면이라 대비 방향이 바뀌지 않는다.
         */}
        <section className="arena-band relative w-full py-10 sm:py-14">
          <div className="mx-auto w-full max-w-6xl px-4">
            <div className="grid grid-cols-1 items-center gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-10">
              <div className="min-w-0">
                <p className="font-sport text-sm tracking-[0.3em] text-brand-link">KAYFABE</p>
                <h1 className="mt-3 font-sport text-4xl leading-[1.05] text-foreground sm:text-5xl lg:text-6xl">
                  WWE DATA &<br />
                  PREDICTION
                  <br />
                  PLATFORM
                </h1>
                <p className="mt-4 max-w-lg text-base text-muted-foreground sm:text-lg">
                  경기를 예측하고 데이터를 분석합니다.
                </p>

                <div className="mt-6 flex flex-wrap items-center gap-3">
                  <Link
                    href="/ple"
                    className="inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-brand-hover"
                  >
                    PLE 예측하기
                  </Link>
                  <Link
                    href="/rankings"
                    className="inline-flex h-10 items-center rounded-full border border-border bg-card px-5 text-sm font-semibold text-foreground transition-colors hover:bg-card-2"
                  >
                    랭킹 보기
                  </Link>
                </div>

                {/* 골드 블러(`hero-title-backdrop`)는 뺐다 — 크림 면 위에서
                    다시 번짐으로 읽힌다. 영상 자체가 이미 어두운 덩어리라
                    뒤에 빛을 깔 이유도 없다. */}
                <div className="relative mt-7 max-w-lg">
                  <video
                    className="hero-ring-glow relative z-10 aspect-video w-full rounded-2xl border border-border object-cover"
                    src="/intro/kayfabe-hero.mp4"
                    poster="/intro/kayfabe-hero-poster.jpg"
                    autoPlay
                    loop
                    muted
                    playsInline
                    preload="auto"
                    aria-label="KAYFABE · WWE PLE 예측 게임 인트로 영상"
                  />
                </div>
              </div>

              <AiPredictionCard className="w-full" />
            </div>
          </div>
        </section>

        {/* ── KPI — 실제 수치만 (§7·§12) ───────────────────────────────── */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-8" aria-label="서비스 현황">
          <KpiStrip />
        </section>

        {/* ── 다음 PLE · 리더보드 (§4·§6) ──────────────────────────────── */}
        <section className="mx-auto w-full max-w-6xl px-4 pb-8">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <NextPleCountdownCard />
            <LeaderboardPreview />
          </div>
        </section>

        {/* ── AI 예측 기록 (§5) — 기존 스코어보드를 그대로 둔다 ─────────── */}
        <div className="pb-2">
          <PleAiScoreboard />
        </div>

        <div className="mx-auto w-full max-w-2xl px-4 pb-8 pt-4">
          <GeminiChatPanel className="min-h-[240px] h-[min(40dvh,480px)] max-h-[46dvh] sm:min-h-[280px] sm:h-[min(46dvh,560px)] sm:max-h-[52dvh]" />
        </div>
      </div>
    </WweArenaShell>
  );
}
