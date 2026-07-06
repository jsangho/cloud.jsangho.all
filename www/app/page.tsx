"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, Database, RefreshCw } from "lucide-react";
import { GeminiChatPanel } from "@/components/gemini-chat-panel";
import { PleAiScoreboard } from "@/components/ple-ai-scoreboard";
import { KayfabeMark } from "@/components/kayfabe-logo";
import { PleEventGrid } from "@/components/ple-event-grid";
import { WweArenaShell } from "@/components/wwe-arena-shell";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

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
        <div className="flex min-h-[calc(100dvh-5.5rem)] flex-col">
          <section className="shrink-0 px-4 pt-6 pb-4 text-center sm:pt-10">
            <div className="relative mx-auto max-w-4xl">
              <KayfabeMark className="hero-ring-glow relative z-10 mx-auto mb-5 h-16 w-16 rounded-2xl sm:mb-6 sm:h-[4.5rem] sm:w-[4.5rem]" />
              <div className="relative mx-auto max-w-3xl px-2 py-2 sm:py-3">
                <div aria-hidden className="hero-title-backdrop" />
                <h2 className="font-kr-hero relative z-10 text-balance text-[1.75rem] text-stone-900 dark:text-white sm:text-[2.5rem] md:text-[2.875rem] lg:text-[3.25rem]">
                  <span className="font-sport text-[1.05em] tracking-[-0.05em] text-stone-900 dark:text-white">
                    WWE PLE
                  </span>{" "}
                  승부 예측,
                  <br />
                  당신의 본능을 증명하라
                </h2>
              </div>
              <p className="relative z-10 mx-auto mt-4 max-w-2xl text-balance text-base font-medium leading-relaxed text-stone-600 dark:text-stone-400 sm:mt-5 sm:text-lg">
                경기 결과를 예측하고 점수를 쌓아{" "}
                <span className="font-sport font-semibold text-stone-900 dark:text-white">
                  2026
                </span>
                년의{" "}
                <span className="text-head-of-table font-sport text-lg font-semibold sm:text-xl">
                  Head of the Table
                </span>{" "}
                자리를 차지하세요!
              </p>
            </div>
          </section>

          <section className="mx-auto flex w-full max-w-5xl min-h-0 flex-1 flex-col justify-center px-4 py-3 sm:py-5">
            <div className="ple-section-glow w-full rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/60 dark:bg-stone-950/60 p-4 backdrop-blur-sm sm:rounded-3xl sm:p-6">
              <div className="mb-3 text-center sm:mb-4">
                <p className="font-sport text-sm font-semibold tracking-[-0.04em] text-stone-500 dark:text-stone-400 sm:text-base">
                  <span className="text-stone-900 dark:text-white">2026</span>{" "}
                  Monthly PLE
                </p>
                <p className="mt-1 text-sm text-stone-500">
                  이벤트를 골라 승부 예측에 참여하세요
                </p>
              </div>
              <PleEventGrid
                variant="large"
                className="grid-cols-2 gap-2.5 sm:grid-cols-3 sm:gap-3 lg:grid-cols-4"
              />
            </div>
          </section>

          <div className="shrink-0 px-4">
            <PleAiScoreboard />
          </div>
          <div className="mx-auto w-full max-w-2xl shrink-0 px-4 pb-6 pt-3 sm:pt-4">
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
  const [state, setState] = useState<SampleDataPageState>(
    initialSampleDataState,
  );

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
          <p className="text-sm text-red-700 dark:text-red-400 mb-3">
            {state.errorMessage}
          </p>
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
