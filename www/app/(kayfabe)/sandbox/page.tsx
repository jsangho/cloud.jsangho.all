"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { WweArenaShell } from "@/components/wwe-arena-shell";
import { fetchCompetitorNames } from "@/lib/records-api";
import { simulateMatch, type SimResult } from "@/lib/sandbox-api";

/**
 * 장난감 경기 시뮬레이터.
 *
 * **화면이 "장난감"이라고 말하는 것이 설계의 절반이다.** 나머지 절반은 경로
 * (`/sandbox`)다. 둘 중 하나가 빠지면 공식 하나로 뽑은 숫자가 AI Lab의 예측과
 * 같은 무게로 읽힌다.
 *
 * 저장하지 않는다 — 전적도 기록도 남기지 않는다. 그 제약이 이전 커리어
 * 시뮬레이터가 38,326줄로 불어난 길을 막는다.
 */
export default function SandboxPage() {
  const [names, setNames] = useState<string[]>([]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [result, setResult] = useState<SimResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const list = await fetchCompetitorNames();
      if (cancelled) return;
      setNames(list);
      if (list.length >= 2) {
        setA(list[0]);
        setB(list[1]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function run() {
    if (!a || !b || a === b) return;
    setBusy(true);
    setResult(await simulateMatch(a, b));
    setBusy(false);
  }

  const pct = (p: number) => `${Math.round(p * 100)}%`;

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-10">
        <header className="mb-6">
          <h1 className="font-sport text-2xl text-foreground sm:text-3xl">경기 시뮬레이터</h1>
          <p className="mt-2 rounded-xl border border-dashed border-border px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            <strong className="text-foreground">장난감입니다.</strong> 공식 하나와 고정 난수로
            승자를 뽑습니다 — 타이틀 획득 수와 나이만 봅니다. 승률은 쓰지 않습니다(결과 있는 경기가
            5건 이상인 선수가 169명 중 11명뿐이라 잡음입니다). 실제 예측은{" "}
            <Link href="/ai-lab" className="text-foreground underline">
              AI Lab
            </Link>
            이 세 축과 누수 검사를 거쳐 만듭니다. 결과는 저장되지 않습니다.
          </p>
        </header>

        <section className="mb-6 grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
          <Picker label="선수 A" value={a} onChange={setA} names={names} />
          <div className="pb-2 text-center text-sm font-bold text-muted-foreground">vs</div>
          <Picker label="선수 B" value={b} onChange={setB} names={names} />
        </section>

        <button
          type="button"
          onClick={run}
          disabled={busy || !a || !b || a === b}
          className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm font-bold text-foreground transition-colors hover:bg-card-2 disabled:opacity-50"
        >
          {busy ? "뽑는 중…" : a === b ? "서로 다른 선수를 고르세요" : "붙여 보기"}
        </button>

        {result ? (
          <section className="mt-6 rounded-xl border border-border bg-card p-4 sm:p-5">
            <p className="text-xs font-bold text-muted-foreground">승자</p>
            <p className="mt-1 font-sport text-2xl text-foreground">{result.winner}</p>

            {/* **근거를 숨기지 않는다.** 두 입력과 뽑기 값을 그대로 적는다. */}
            <div className="mt-4 overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[22rem] border-collapse text-sm">
                <thead>
                  <tr className="bg-card-2 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-3 py-2 font-medium">선수</th>
                    <th className="px-3 py-2 text-right font-medium">타이틀</th>
                    <th className="px-3 py-2 text-right font-medium">나이</th>
                    <th className="px-3 py-2 text-right font-medium">점수</th>
                    <th className="px-3 py-2 text-right font-medium">확률</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { c: result.a, p: result.probabilityA },
                    { c: result.b, p: 1 - result.probabilityA },
                  ].map(({ c, p }) => (
                    <tr key={c.name} className="border-t border-border">
                      <td className="px-3 py-2 text-foreground">{c.name}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                        {c.titles}회
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                        {c.age ?? "미상"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                        {c.score.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums text-foreground">
                        {pct(p)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
              뽑기 값 {result.roll.toFixed(3)} — 두 이름에서 나온 고정값이라{" "}
              <strong className="text-foreground">같은 쌍이면 항상 같은 결과</strong>
              입니다. 확률은 15%~85% 안에 머물게 눌러 두었습니다(업셋이 항상 남습니다). 그래서
              확률이 높은 쪽이 지는 일이 있습니다.
            </p>
          </section>
        ) : null}
      </div>
    </WweArenaShell>
  );
}

function Picker({
  label,
  value,
  onChange,
  names,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  names: string[];
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-bold text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
      >
        {names.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </label>
  );
}
