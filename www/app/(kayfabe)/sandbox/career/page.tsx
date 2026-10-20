"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { WweArenaShell } from "@/components/wwe-arena-shell";
import { careerStep, type CareerState, type CareerStep } from "@/lib/sandbox-api";

/**
 * 가상 선수 키우기 — NXT에서 월챔까지, 그리고 은퇴까지.
 *
 * **런을 들고 다니는 쪽이 이 화면이다.** 서버는 상태를 받아 다음 상태를 돌려줄
 * 뿐 저장하지 않는다. 그 제약이 이전 커리어 시뮬레이터(38,326줄)가 불어난 길을
 * 막는다 — `career_runs` 테이블이 생기자 세이브·버전 호환·트로피가 따라왔다.
 *
 * 그래서 저장은 `localStorage` 하나다. 탭을 닫아도 이어지고 서버에는 남지 않는다.
 */
const STYLES = ["파워", "테크니션", "하이플라이어"] as const;
const STYLE_NOTE: Record<string, string> = {
  파워: "잘 이긴다 · 부상 보통",
  테크니션: "안전하다 · 상승 느림",
  하이플라이어: "빨리 뜬다 · 자주 다친다",
};
const SAVE_KEY = "kayfabe:career:v1";

export default function CareerPage() {
  const [state, setState] = useState<CareerState | null>(null);
  const [nextBelt, setNextBelt] = useState<string | null>(null);
  const [defending, setDefending] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [style, setStyle] = useState<string>(STYLES[0]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem(SAVE_KEY);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as {
        state: CareerState;
        nextBelt: string | null;
        defending: boolean;
        log: string[];
      };
      setState(saved.state);
      setNextBelt(saved.nextBelt);
      setDefending(saved.defending);
      setLog(saved.log ?? []);
    } catch {
      window.localStorage.removeItem(SAVE_KEY);
    }
  }, []);

  /** 주차 한 줄. **서술 템플릿 뱅크를 두지 않는다** — 사실만 적는다. */
  function describe(step: CareerStep): string {
    const head = `W${step.week}`;
    if (step.kind === "결장") return `${head} 결장 (부상 회복)`;
    const result = step.won ? "승" : "패";
    const who = step.opponent ? ` vs ${step.opponent}` : "";
    const belt = step.belt ? ` — ${step.belt}` : "";
    const promo = step.promotedTo ? ` · ${step.promotedTo} 승격!` : "";
    const hurt = step.injuredWeeks > 0 ? ` · 부상 ${step.injuredWeeks}주` : "";
    const delta =
      step.popularityDelta >= 0 ? `+${step.popularityDelta}` : `${step.popularityDelta}`;
    return `${head} ${step.kind} ${result}${who}${belt}${promo} (인기 ${delta})${hurt}`;
  }

  async function step(choice: "경기" | "도전") {
    const payload = state ?? { name: name.trim(), style };
    if (!("week" in payload) && !payload.name) return;
    setBusy(true);
    const next = await careerStep(payload, choice);
    setBusy(false);
    if (!next) return;
    const lines = [describe(next), ...log].slice(0, 60);
    setState(next.state);
    setNextBelt(next.nextBelt);
    setDefending(next.defending);
    setLog(lines);
    window.localStorage.setItem(
      SAVE_KEY,
      JSON.stringify({
        state: next.state,
        nextBelt: next.nextBelt,
        defending: next.defending,
        log: lines,
      }),
    );
  }

  function reset() {
    window.localStorage.removeItem(SAVE_KEY);
    setState(null);
    setNextBelt(null);
    setLog([]);
  }

  const done = state?.outcome != null;
  const worldReigns =
    state?.reigns.filter((b) => b === "World Heavyweight Championship").length ?? 0;

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:py-10">
        <header className="mb-6">
          <h1 className="font-sport text-2xl text-foreground sm:text-3xl">선수 키우기</h1>
          <p className="mt-2 rounded-xl border border-dashed border-border px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            NXT에서 시작해 월드 챔피언을 거쳐 <strong className="text-foreground">은퇴</strong>까지
            40주. 월챔은 끝이 아니라 중간 목표이고, 점수는{" "}
            <strong className="text-foreground">역대 재위 수</strong>입니다. 인기도가 승률·승격·도전
            자격을 모두 정합니다.{" "}
            <strong className="text-foreground">서버에 저장되지 않습니다</strong> — 런은 이
            브라우저에만 남습니다. 실제 예측은{" "}
            <Link href="/ai-lab" className="text-foreground underline">
              AI Lab
            </Link>
            이 합니다.
          </p>
        </header>

        {!state ? (
          <section className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-xs font-bold text-muted-foreground">링네임</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={40}
                placeholder="예: Ho"
                className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
              />
            </label>
            <div>
              <span className="mb-1 block text-xs font-bold text-muted-foreground">스타일</span>
              <div className="grid gap-2 sm:grid-cols-3">
                {STYLES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStyle(s)}
                    className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
                      style === s
                        ? "border-brand-500 bg-brand-950/20 text-foreground"
                        : "border-border bg-card text-muted-foreground hover:bg-card-2"
                    }`}
                  >
                    <span className="block font-bold">{s}</span>
                    <span className="block text-[11px]">{STYLE_NOTE[s]}</span>
                  </button>
                ))}
              </div>
            </div>
            <button
              type="button"
              onClick={() => step("경기")}
              disabled={busy || !name.trim()}
              className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm font-bold text-foreground hover:bg-card-2 disabled:opacity-50"
            >
              데뷔
            </button>
          </section>
        ) : (
          <section className="space-y-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="주차" value={`${Math.min(state.week, 40)} / 40`} />
              <Stat label="브랜드" value={state.brand} />
              <Stat label="인기도" value={`${state.popularity}`} />
              <Stat label="전적" value={`${state.wins}승 ${state.losses}패`} />
            </div>

            <div className="rounded-xl border border-border bg-card p-3 text-sm">
              <p className="text-xs font-bold text-muted-foreground">보유 벨트</p>
              <p className="mt-0.5 text-foreground">{state.held ?? "없음"}</p>
              <p className="mt-2 text-xs font-bold text-muted-foreground">역대 재위</p>
              <p className="mt-0.5 text-foreground">
                {state.reigns.length}회{worldReigns > 0 ? ` (월챔 ${worldReigns}회)` : ""}
              </p>
            </div>

            {done ? (
              <div className="rounded-xl border border-brand-700/50 bg-brand-950/20 p-4">
                <p className="font-sport text-xl text-foreground">은퇴</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {state.name} — {state.wins}승 {state.losses}패 · 역대 재위 {state.reigns.length}회
                  {worldReigns > 0
                    ? ` · 월드 챔피언 ${worldReigns}회`
                    : " · 월드 챔피언에는 닿지 못했습니다"}
                </p>
              </div>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => step("경기")}
                  disabled={busy}
                  className="rounded-xl border border-border bg-card px-4 py-3 text-sm font-bold text-foreground hover:bg-card-2 disabled:opacity-50"
                >
                  {state.outWeeks > 0 ? `회복 (${state.outWeeks}주 남음)` : "경기"}
                </button>
                <button
                  type="button"
                  onClick={() => step("도전")}
                  disabled={busy || !nextBelt || state.outWeeks > 0}
                  className="rounded-xl border border-brand-700/50 bg-brand-950/20 px-4 py-3 text-sm font-bold text-foreground hover:bg-brand-950/40 disabled:opacity-40"
                >
                  {nextBelt ? `${defending ? "방어" : "도전"} — ${nextBelt}` : "도전 자격 없음"}
                </button>
              </div>
            )}

            <div className="rounded-xl border border-border bg-card p-3">
              <p className="mb-2 text-xs font-bold text-muted-foreground">기록</p>
              <ul className="max-h-72 space-y-1 overflow-auto text-xs text-muted-foreground">
                {log.map((line, i) => (
                  <li key={`${line}:${i}`} className="tabular-nums">
                    {line}
                  </li>
                ))}
              </ul>
            </div>

            <button
              type="button"
              onClick={reset}
              className="w-full rounded-xl border border-dashed border-border px-4 py-2 text-xs text-muted-foreground hover:bg-card-2"
            >
              처음부터 다시
            </button>
          </section>
        )}
      </div>
    </WweArenaShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2">
      <div className="text-[11px] font-bold text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums text-foreground">{value}</div>
    </div>
  );
}
