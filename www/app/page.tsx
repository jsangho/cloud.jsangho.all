"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2, Database, RefreshCw } from "lucide-react";
import { GeminiChatPanel } from "@/components/gemini-chat-panel";
import { AiPredictionCard } from "@/components/home/ai-prediction-card";
import { KpiStrip } from "@/components/home/kpi-strip";
import { PleAiScoreboard } from "@/components/ple-ai-scoreboard";
import { LeaderboardPreview } from "@/components/leaderboard-preview";
import { NextPleCountdownCard } from "@/components/next-ple-countdown-card";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import { apiBaseUrl } from "@/lib/api";

interface SampleDataItem {
  [key: string]: string | number | boolean | null;
}

function TitanicQaAppContent() {
  const searchParams = useSearchParams();
  const currentView = searchParams.get("view") === "data" ? "data" : "qa";

  useEffect(() => {
    if (currentView !== "qa") return;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [currentView]);

  return (
    <WweArenaShell>
      {currentView === "qa" ? (
        <div className="flex flex-col">
          {/*
           * ── 히어로 (KAYFABE 2.0 §2) ─────────────────────────────────────
           * **비디오를 지우지 않았다.** 화면 전체를 먹던 것을 왼쪽 칸 안으로
           * 줄였을 뿐이다 — 오른쪽은 실제 AI 예측이 선다. 첫 화면에서
           * "무엇을 하는 서비스인가"와 "그래서 지금 뭘 아는가"가 같이 보여야 한다.
           */}
          <section className="mx-auto w-full max-w-6xl px-4 pt-8 pb-6 sm:pt-12">
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
                    className="inline-flex h-10 items-center rounded-full border border-border px-5 text-sm font-semibold text-foreground transition-colors hover:bg-card-2"
                  >
                    랭킹 보기
                  </Link>
                </div>

                <div className="relative mt-7 max-w-lg">
                  <div aria-hidden className="hero-title-backdrop" />
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
      ) : (
        <div className="mx-auto max-w-2xl px-4 py-6">
          <TitanicSampleDataPage />
        </div>
      )}
    </WweArenaShell>
  );
}

export default function TitanicQaApp() {
  return (
    <Suspense
      fallback={
        <WweArenaShell>
          <div className="mx-auto max-w-2xl px-4 py-6" />
        </WweArenaShell>
      }
    >
      <TitanicQaAppContent />
    </Suspense>
  );
}

type SampleDataPageState = {
  data: SampleDataItem[];
  isLoading: boolean;
  errorMessage: string | null;
};

const initialSampleDataState: SampleDataPageState = {
  data: [],
  isLoading: false,
  errorMessage: null,
};

function TitanicSampleDataPage() {
  const [state, setState] = useState<SampleDataPageState>(initialSampleDataState);

  const patchState = (patch: Partial<SampleDataPageState>) =>
    setState((prev) => ({ ...prev, ...patch }));

  const fetchData = async () => {
    patchState({ isLoading: true, errorMessage: null });

    try {
      const response = await fetch(`${apiBaseUrl}/titanic/data`);

      if (!response.ok) {
        patchState({ errorMessage: "데이터를 불러오지 못했습니다." });
        return;
      }

      const result: SampleDataItem[] = await response.json();
      patchState({ data: result, errorMessage: null });
    } catch {
      patchState({ errorMessage: "데이터를 불러오지 못했습니다." });
    } finally {
      patchState({ isLoading: false });
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const formatValue = (value: string | number | boolean | null): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "예" : "아니오";
    return String(value);
  };

  const formatKey = (key: string): string => {
    const keyMap: Record<string, string> = {
      PassengerId: "승객 ID",
      Survived: "생존 여부",
      Pclass: "객실 등급",
      Name: "이름",
      Sex: "성별",
      Age: "나이",
      SibSp: "형제/배우자 수",
      Parch: "부모/자녀 수",
      Ticket: "티켓 번호",
      Fare: "요금",
      Cabin: "객실",
      Embarked: "탑승항",
    };
    return keyMap[key] || key;
  };

  return (
    <div>
      {state.isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 size={32} className="animate-spin text-zinc-400" />
        </div>
      )}

      {state.errorMessage && (
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-400 mb-3">{state.errorMessage}</p>
          <button
            onClick={fetchData}
            aria-label="다시 불러오기"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium border border-red-300 dark:border-red-700 bg-white dark:bg-zinc-900 text-red-700 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
          >
            <RefreshCw size={14} />
            다시 불러오기
          </button>
        </div>
      )}

      {!state.isLoading && !state.errorMessage && state.data.length === 0 && (
        <div className="text-center text-zinc-400 dark:text-zinc-500 py-12">
          <Database size={48} className="mx-auto mb-3 opacity-50" />
          <p>데이터가 없습니다</p>
        </div>
      )}

      {!state.isLoading && state.data.length > 0 && (
        <div className="space-y-4">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            총 {state.data.length}개의 레코드
          </p>

          {state.data.map((item, idx) => (
            <div
              key={idx}
              className="p-4 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl"
            >
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {Object.entries(item).map(([key, value]) => (
                  <div key={key} className="flex flex-col">
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      {formatKey(key)}
                    </span>
                    <span className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                      {formatValue(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
