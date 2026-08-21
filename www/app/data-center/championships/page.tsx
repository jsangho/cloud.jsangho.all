"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import { fetchChampionshipStats, type ChampionshipStats } from "@/lib/data-center-api";
import { fetchChampionshipBoard } from "@/lib/championship-api";
import type { ChampionshipBoard } from "@/lib/championship-api";

/**
 * 챔피언십 (Phase 2 §9).
 *
 * 현 챔피언은 **이미 있던** `/api/title-acquisitions/` 보드를 그대로 쓰고,
 * 획득 집계만 데이터 센터 API가 낸다 — 같은 것을 두 곳에서 만들지 않는다.
 *
 * **최장 재위는 없다.** `won_at`이 `"Payback — June 16, 2013"` 같은 자유 텍스트라
 * 재위 기간을 낼 수 없다(2026-08-20 사용자 결정). 날짜를 추정해 넣지 않는다.
 */
export default function DataCenterChampionshipsPage() {
  const [stats, setStats] = useState<ChampionshipStats | null>(null);
  const [board, setBoard] = useState<ChampionshipBoard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [s, b] = await Promise.all([fetchChampionshipStats(), fetchChampionshipBoard()]);
      if (cancelled) return;
      setStats(s);
      setBoard(b);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <DataCenterShell
      title="Championships"
      description="현 챔피언과 벨트별 획득 기록입니다. 재위 기간은 원본이 자유 텍스트라 계산하지 않습니다."
    >
      {loading ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="flex flex-col gap-8">
          {stats && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile value={stats.beltCount} label="Belts" tone="gold" />
              <StatTile value={stats.totalAcquisitions} label="Reigns" />
              <StatTile value={stats.holderCount} label="Champions" />
              <StatTile
                value={stats.topHolders[0]?.name ?? null}
                label="Most Reigns"
                note={
                  stats.topHolders[0]
                    ? `${stats.topHolders[0].reigns}회 · 벨트 ${stats.topHolders[0].belts}종`
                    : undefined
                }
                tone="gold"
              />
            </div>
          )}

          <section aria-labelledby="current-champions">
            <h2 id="current-champions" className="mb-3 font-sport text-lg text-foreground">
              현 챔피언
              {board && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  {board.asOf} 기준
                </span>
              )}
            </h2>
            {!board ? (
              <DataUnavailable what="현 챔피언 보드" />
            ) : (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {board.brands.map((brand) => (
                  <div key={brand.id} className="rounded-xl border border-border bg-card p-4">
                    <p className="font-sport text-base text-foreground">{brand.label}</p>
                    <ul className="mt-2 flex flex-col gap-2">
                      {brand.titles.map((title) => (
                        <li
                          key={`${brand.id}-${title.beltName}`}
                          className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-border pt-2 first:border-0 first:pt-0"
                        >
                          <span className="min-w-0 flex-1 text-xs text-muted-foreground">
                            {title.beltName}
                          </span>
                          <span className="text-sm text-brand-link">
                            {title.champions.map((name, index) => (
                              <span key={name}>
                                {index > 0 && " & "}
                                <Link
                                  href={`/records/${encodeURIComponent(name)}`}
                                  className="underline-offset-4 hover:underline"
                                >
                                  {name}
                                </Link>
                              </span>
                            ))}
                          </span>
                          <span className="text-xs tabular-nums text-muted-foreground">
                            {title.wonAt}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>

          {!stats ? (
            <DataUnavailable what="벨트 집계" />
          ) : (
            <>
              <section aria-labelledby="most-reigns">
                <h2 id="most-reigns" className="mb-3 font-sport text-lg text-foreground">
                  최다 획득
                </h2>
                <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {stats.topHolders.map((holder, index) => (
                    <li key={holder.name}>
                      <Link
                        href={`/records/${encodeURIComponent(holder.name)}`}
                        className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:bg-card-2"
                      >
                        <span className="w-5 shrink-0 text-sm font-bold tabular-nums text-muted-foreground">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                          {holder.name}
                        </span>
                        <span className="shrink-0 text-sm font-bold tabular-nums text-brand-link">
                          {holder.reigns}회
                        </span>
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                          벨트 {holder.belts}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-labelledby="belt-table">
                <h2 id="belt-table" className="mb-3 font-sport text-lg text-foreground">
                  벨트별 획득 횟수
                </h2>
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full min-w-[34rem] border-collapse text-sm">
                    <thead>
                      <tr className="bg-card-2 text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="px-4 py-2 font-medium">벨트</th>
                        <th className="px-4 py-2 text-right font-medium">획득</th>
                        <th className="px-4 py-2 text-right font-medium">보유자</th>
                        <th className="px-4 py-2 font-medium">최다</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.belts.map((belt) => (
                        <tr key={belt.beltName} className="border-t border-border bg-card">
                          <td className="px-4 py-2 text-foreground">{belt.beltName}</td>
                          <td className="px-4 py-2 text-right tabular-nums text-foreground">
                            {belt.reigns}
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                            {belt.holders}
                          </td>
                          <td className="px-4 py-2 text-muted-foreground">
                            {belt.topHolder ? (
                              <>
                                <Link
                                  href={`/records/${encodeURIComponent(belt.topHolder)}`}
                                  className="text-brand-link underline-offset-4 hover:underline"
                                >
                                  {belt.topHolder}
                                </Link>
                                <span className="ml-1 tabular-nums">{belt.topHolderReigns}회</span>
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  원본의 획득 일자가 자유 텍스트(예: “Payback — June 16, 2013”)라 재위 기간은
                  계산하지 않습니다. 데이터 구조가 정리되면 최장 재위를 더합니다.
                </p>
              </section>
            </>
          )}
        </div>
      )}
    </DataCenterShell>
  );
}
