"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ChevronDown } from "lucide-react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import { fetchBeltDetail, type BeltDetail } from "@/lib/data-center-api";
import { fetchChampionshipBoard } from "@/lib/championship-api";
import type { BrandRoster, ChampionshipBoard, TitleReign } from "@/lib/championship-api";
import { formatChampionshipDate, TIER_LABELS } from "@/lib/wwe-current-champions";

/**
 * 벨트 하나 (2026-10-07).
 *
 * **두 곳에서 받아 겹친다.** 현 챔피언은 이미 있던 `/api/title-acquisitions/` 보드가
 * 주고, 획득 이력은 데이터 센터가 준다 — 같은 것을 두 곳에서 만들지 않는다.
 *
 * **이력을 시간순으로 늘어놓지 않는다.** `wonAt`이 `"Payback — June 16, 2013"` 같은
 * 자유 텍스트라 정렬하면 틀린 순서가 된다. 보유자를 획득 횟수 순으로 세운다.
 */

type BeltPageState = {
  loading: boolean;
  detail: BeltDetail | null;
  /** 보드에서 찾은 현 챔피언 + 그 브랜드. 보드를 못 받으면 `null`. */
  current: { brand: BrandRoster; reign: TitleReign } | null;
  /** 보드는 받았는데 그 안에 이 벨트가 없었다 = 현존하지 않는 이름이다. */
  notABelt: boolean;
};

const initialState: BeltPageState = {
  loading: true,
  detail: null,
  current: null,
  notABelt: false,
};

function findOnBoard(board: ChampionshipBoard, beltName: string) {
  for (const brand of board.brands) {
    const reign = brand.titles.find((title) => title.beltName === beltName);
    if (reign) return { brand, reign };
  }
  return null;
}

export default function BeltDetailPage() {
  const params = useParams();
  const rawBelt = typeof params.belt === "string" ? params.belt : "";
  const beltName = decodeURIComponent(rawBelt);

  const [state, setState] = useState<BeltPageState>(initialState);

  useEffect(() => {
    if (!beltName) {
      setState({ ...initialState, loading: false, notABelt: true });
      return;
    }

    let cancelled = false;
    setState(initialState);
    void (async () => {
      const [detail, board] = await Promise.all([
        fetchBeltDetail(beltName),
        fetchChampionshipBoard(),
      ]);
      if (cancelled) return;
      const found = board ? findOnBoard(board, beltName) : null;
      setState({
        loading: false,
        detail,
        current: found,
        notABelt: board !== null && found === null,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [beltName]);

  const { loading, detail, current, notABelt } = state;
  const topHolder = detail?.holders[0] ?? null;

  return (
    <DataCenterShell
      title={beltName || "벨트"}
      description={
        current
          ? `${current.brand.label} · ${TIER_LABELS[current.reign.tier]}`
          : "현 챔피언 보드에 올라 있는 벨트의 획득 기록입니다."
      }
    >
      {loading ? (
        <LoadingBlock rows={4} />
      ) : notABelt ? (
        <div className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center">
          <p className="text-sm text-foreground">현 챔피언 보드에 없는 벨트입니다.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            폐지됐거나 이름이 바뀐 벨트일 수 있습니다. 바뀐 이름은 벨트 목록에서 옛 이름과 함께
            표시됩니다.
          </p>
          <Link
            href="/data-center/championships"
            className="mt-3 inline-block text-sm text-brand-link underline-offset-4 hover:underline"
          >
            벨트 목록으로
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <section aria-labelledby="current-champion">
            <h2 id="current-champion" className="mb-3 font-sport text-lg text-foreground">
              현 챔피언
            </h2>
            {!current ? (
              <DataUnavailable what="현 챔피언 보드" />
            ) : (
              <div className="rounded-xl border border-border bg-card p-4">
                <p className="text-lg text-brand-link">
                  {current.reign.champions.map((name, index) => (
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
                </p>
                {current.reign.teamName && (
                  <p className="mt-1 text-sm text-muted-foreground">{current.reign.teamName}</p>
                )}
                <p className="mt-2 text-xs tabular-nums text-muted-foreground">
                  {formatChampionshipDate(current.reign.wonAt)}
                  {current.reign.wonEvent && ` · ${current.reign.wonEvent}`}
                </p>
              </div>
            )}
          </section>

          {!detail ? (
            <DataUnavailable what="획득 기록" />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                <StatTile
                  value={detail.reigns > 0 ? detail.reigns : null}
                  label="획득"
                  note={detail.reigns > 0 ? undefined : "이력 카탈로그에 기록 없음"}
                  tone="gold"
                />
                <StatTile
                  value={detail.holderCount > 0 ? detail.holderCount : null}
                  label="보유자"
                />
                <StatTile
                  value={topHolder?.name ?? null}
                  label="최다 보유"
                  note={topHolder ? `${topHolder.reigns}회` : undefined}
                />
              </div>

              {detail.formerNames.length > 0 && (
                <p className="rounded-xl border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
                  이 집계에는 옛 이름{" "}
                  <span className="text-foreground">{detail.formerNames.join(" · ")}</span> 시절의
                  획득이 함께 들어 있습니다. 각 기록은 그때 불리던 이름을 그대로 답니다.
                </p>
              )}

              <section aria-labelledby="holders">
                <h2 id="holders" className="mb-3 font-sport text-lg text-foreground">
                  보유자
                </h2>
                {detail.holders.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center">
                    <p className="text-sm text-muted-foreground">
                      획득 이력 카탈로그에 이 벨트의 기록이 아직 없습니다.
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      “0회 획득”이 아니라 데이터가 비어 있다는 뜻입니다 — 숫자를 지어내지 않습니다.
                    </p>
                  </div>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {detail.holders.map((holder, index) => (
                      <li key={holder.name} className="rounded-xl border border-border bg-card">
                        {/* **접어 둔다.** 13명 × 최대 14회를 한꺼번에 펴면 순위가 안 읽힌다 —
                            이 목록이 먼저 답하는 질문은 "누가 몇 번"이고, 언제인지는 그다음이다.
                            `<details>`를 쓰는 이유는 JS 없이도 열리고, 브라우저 안에서 찾기가
                            닫힌 내용까지 뒤지기 때문이다. */}
                        <details className="group">
                          <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
                            <span className="w-5 shrink-0 text-sm font-bold tabular-nums text-muted-foreground">
                              {index + 1}
                            </span>
                            <Link
                              href={`/records/${encodeURIComponent(holder.name)}`}
                              className="min-w-0 flex-1 truncate text-sm text-brand-link underline-offset-4 hover:underline"
                            >
                              {holder.name}
                            </Link>
                            <span className="shrink-0 text-sm font-bold tabular-nums text-foreground">
                              {holder.reigns}회
                            </span>
                            <ChevronDown
                              aria-hidden
                              className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                            />
                          </summary>
                          <ul className="mx-4 mb-3 flex flex-col gap-1 border-t border-border pt-2">
                            {holder.history.map((reign, reignIndex) => (
                              <li
                                key={`${reign.beltName}-${reign.wonAt}-${reignIndex}`}
                                className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground"
                              >
                                <span className="tabular-nums">{reign.wonAt}</span>
                                {reign.beltName !== detail.beltName && (
                                  <span className="text-muted-foreground/80">
                                    ({reign.beltName})
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </details>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="mt-2 text-xs text-muted-foreground">
                  획득 일자가 자유 텍스트라 시간순으로 세우지 않고 획득 횟수 순으로 세웁니다. 재위
                  기간도 같은 이유로 계산하지 않습니다.
                </p>
              </section>
            </>
          )}
        </div>
      )}
    </DataCenterShell>
  );
}
