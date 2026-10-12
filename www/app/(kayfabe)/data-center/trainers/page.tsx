"use client";

import { useState } from "react";
import { useEffect } from "react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import { RosterPanel } from "@/components/data-center/roster-panel";
import { fetchTrainers, type Trainers } from "@/lib/data-center-api";
import { cn } from "@/lib/utils";

/**
 * 누가 누구를 길렀나 (2026-10-12).
 *
 * **그래프로 그리지 않았다.** 트레이너 241명 중 200명(83%)이 제자 한 명뿐이고
 * 1위 WWE 퍼포먼스 센터가 77명을 쥔다 — 허브 하나에 잎이 매달린 모양이라
 * 노드-엣지로 그리면 덩어리 하나와 먼지만 보인다. 세계 전도를 포기한 것과 같은
 * 이유다(`/data-center/origins`). 순위 목록이 이 분포에서는 더 정확하다.
 *
 * 누르면 제자 명단이 열리는 동작은 출신 지도와 **같은 패널**을 쓴다.
 */
type PageState = { status: "loading" } | { status: "ready"; data: Trainers } | { status: "error" };

/** 이 수 미만은 "한 명만 기른 트레이너" 꼬리로 접는다. */
const TAIL_THRESHOLD = 2;

export default function DataCenterTrainersPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });
  const [selected, setSelected] = useState<string | null>(null);
  const [showTail, setShowTail] = useState(false);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchTrainers();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <DataCenterShell
      title="트레이너"
      description="선수를 길러 낸 사람과 학교입니다. 한 선수가 여러 명에게 배우므로 제자 수의 합은 선수 수보다 큽니다."
    >
      {state.status === "loading" ? (
        <LoadingBlock rows={6} />
      ) : state.status === "error" ? (
        <DataUnavailable what="트레이너 분포" />
      ) : (
        (() => {
          const { groups, institutions, known, total } = state.data;
          const institutionSet = new Set(institutions);
          const main = groups.filter((g) => g.count >= TAIL_THRESHOLD);
          const tail = groups.filter((g) => g.count < TAIL_THRESHOLD);
          const top = groups[0];
          const picked = selected ? groups.filter((g) => g.name === selected) : [];

          return (
            <div className="flex flex-col gap-5">
              <p className="text-sm text-muted-foreground">
                트레이너를 아는 선수 <span className="tabular-nums text-foreground">{known}</span>/
                {total}명 · 서로 다른 트레이너{" "}
                <span className="tabular-nums text-foreground">{groups.length}</span>명
                {top && (
                  <>
                    {" "}
                    · 가장 많이 기른 곳은 <span className="text-foreground">{top.name}</span>{" "}
                    <span className="tabular-nums text-foreground">{top.count}</span>명
                  </>
                )}
              </p>

              <ol className="flex flex-col gap-0.5">
                {main.map((row) => (
                  <TrainerRow
                    key={row.name}
                    row={row}
                    max={top?.count ?? 1}
                    isInstitution={institutionSet.has(row.name)}
                    selected={selected === row.name}
                    onSelect={() => setSelected(selected === row.name ? null : row.name)}
                  />
                ))}
              </ol>

              {picked.length > 0 && (
                <RosterPanel
                  groups={picked}
                  suffix="가 기른 선수"
                  onClose={() => setSelected(null)}
                />
              )}

              {/* **꼬리를 숨기되 숫자는 적는다.** 200명이 제자 한 명뿐이라 그대로
                  펼치면 목록이 그 꼬리가 된다. 없는 척하지는 않는다. */}
              {tail.length > 0 && (
                <div>
                  <button
                    type="button"
                    onClick={() => setShowTail(!showTail)}
                    className="text-sm font-semibold text-brand-link underline-offset-4 hover:underline"
                  >
                    제자가 한 명뿐인 트레이너 {tail.length}명 {showTail ? "접기" : "펼치기"}
                  </button>
                  {showTail && (
                    <ol className="mt-3 flex flex-col gap-0.5">
                      {tail.map((row) => (
                        <TrainerRow
                          key={row.name}
                          row={row}
                          max={top?.count ?? 1}
                          isInstitution={institutionSet.has(row.name)}
                          selected={selected === row.name}
                          onSelect={() => setSelected(selected === row.name ? null : row.name)}
                        />
                      ))}
                    </ol>
                  )}
                </div>
              )}

              <p className="text-xs text-muted-foreground">
                이름은 로스터 CSV에 적힌 그대로입니다. 같은 사람이 링네임과 본명으로 두 번 들어가는
                일이 있어 확인된 것만 합쳤습니다(Sara Amato → Sara Del Rey). 괄호 안에 사람이 적힌
                표기는 학교와 사람 둘로 나눠 셉니다.
              </p>
            </div>
          );
        })()
      )}
    </DataCenterShell>
  );
}

function TrainerRow({
  row,
  max,
  isInstitution,
  selected,
  onSelect,
}: {
  row: { name: string; count: number };
  max: number;
  isInstitution: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={cn(
          "flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-card-2",
          selected && "bg-card-2",
        )}
      >
        <span className="min-w-0 flex-1 truncate text-foreground">
          {row.name}
          {isInstitution && (
            <span className="ml-2 rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
              학교·센터
            </span>
          )}
        </span>
        <span className="h-1.5 w-24 shrink-0 overflow-hidden rounded-sm bg-surface-2 sm:w-40">
          <span
            className="block h-full rounded-sm bg-chart-1"
            style={{ width: `${Math.max(4, (row.count / max) * 100)}%` }}
          />
        </span>
        <span className="w-8 shrink-0 text-right tabular-nums text-muted-foreground">
          {row.count}
        </span>
      </button>
    </li>
  );
}
