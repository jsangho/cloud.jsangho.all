import { PleEventGrid } from "@/components/ple-event-grid";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function PlePage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl min-w-0 px-4 py-10">
        <header className="mb-8 text-center">
          <h1 className="font-kr-hero text-3xl text-stone-900 dark:text-white sm:text-4xl">
            <span className="font-sport tracking-[-0.04em]">2026</span> 월별 PLE
          </h1>
          <p className="mt-3 text-base text-stone-400 sm:text-lg">
            예측할 이벤트를 선택하고{" "}
            <span className="text-head-of-table font-sport text-lg font-semibold sm:text-xl">
              Head of the Table
            </span>
            에 도전하세요
          </p>
        </header>
        <div className="ple-section-glow rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/60 dark:bg-stone-950/60 p-4 sm:p-6">
          <PleEventGrid variant="large" />
        </div>
      </div>
    </WweArenaShell>
  );
}
