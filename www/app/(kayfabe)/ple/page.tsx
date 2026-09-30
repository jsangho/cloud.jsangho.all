import { PleStatusBoard } from "@/components/ple/ple-status-board";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function PlePage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-6xl min-w-0 px-4 py-10">
        <header className="mb-8">
          <h1 className="font-kr-display text-3xl text-foreground sm:text-4xl">
            <span className="font-sport tracking-[-0.04em]">2026</span> PLE 예측
          </h1>
          <p className="mt-3 text-base text-muted-foreground sm:text-lg">
            진행 중 · 예정 · 종료로 나눠 봅니다. 예측할 대회를 고르고{" "}
            <span className="text-head-of-table font-sport text-lg font-semibold sm:text-xl">
              Head of the Table
            </span>
            에 도전하세요.
          </p>
        </header>
        <PleStatusBoard />
      </div>
    </WweArenaShell>
  );
}
