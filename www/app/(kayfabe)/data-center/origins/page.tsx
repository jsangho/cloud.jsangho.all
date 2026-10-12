"use client";

import { useEffect, useState } from "react";
import { Choropleth } from "@/components/data-center/choropleth";
import { RosterPanel } from "@/components/data-center/roster-panel";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import { fetchOrigins, type OriginCount, type Origins } from "@/lib/data-center-api";
import { shapeNameOf } from "@/lib/geo/shape-aliases";
import { US_STATES, US_STATES_VIEWBOX } from "@/lib/geo/us-states-paths";
import { WORLD_COUNTRIES, WORLD_COUNTRIES_VIEWBOX } from "@/lib/geo/world-countries-paths";
import { cn } from "@/lib/utils";

/**
 * 출신 분포 (2026-10-12).
 *
 * **지도가 둘인 이유.** 세계 전도 하나로는 아무것도 안 보인다 — 178명 중 118명이
 * 미국이라 램프가 미국 한 칸에 몰리고, 2위 England(11명)는 세계 지도에서 점만 하다.
 * 그래서 미국 **안**은 주 단위로, 미국 **밖**은 세계 지도로 나눠 그린다.
 *
 * **목록을 지도 옆에 함께 둔다.** 지도는 어디인지를 보여 주지만 몇 명인지는
 * 순위로 읽는 게 정확하다 (DESIGN.md §16 — 항목 간 크기 비교는 막대·목록의 일).
 * 지도와 목록은 **같은 선택 상태**를 공유한다: 어느 쪽을 눌러도 아래에 명단이 선다.
 */
type PageState = { status: "loading" } | { status: "ready"; data: Origins } | { status: "error" };

export default function DataCenterOriginsPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchOrigins();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <DataCenterShell
      title="출신"
      description="선수가 실제로 태어난 곳입니다. 지도나 옆 목록에서 지역을 누르면 그곳 출신이 누구인지 볼 수 있습니다."
    >
      {state.status === "loading" ? (
        <LoadingBlock rows={6} />
      ) : state.status === "error" ? (
        <DataUnavailable what="출신 분포" />
      ) : (
        <OriginsBody data={state.data} />
      )}
    </DataCenterShell>
  );
}

function OriginsBody({ data }: { data: Origins }) {
  const usTotal = data.countries.find((c) => c.name === "United States")?.count ?? 0;
  const abroad = data.countries.filter((c) => c.name !== "United States");
  const abroadTotal = abroad.reduce((sum, c) => sum + c.count, 0);

  const unmapped = abroad.filter(
    (row) => !WORLD_COUNTRIES.some((s) => s.id === shapeNameOf(row.name)),
  );

  return (
    <div className="flex flex-col gap-10">
      <p className="text-sm text-muted-foreground">
        출신을 아는 선수 <span className="tabular-nums text-foreground">{data.located}</span>/
        {data.total}명 · {data.countries.length}개 나라 ·{" "}
        <span className="tabular-nums text-foreground">{usTotal}</span>명이 미국,{" "}
        <span className="tabular-nums text-foreground">{abroadTotal}</span>명이 그 밖
      </p>

      <OriginSection
        id="us-map"
        heading="미국 어느 주에서 왔나"
        note={`미국 출신 ${usTotal}명 · ${data.usStates.length}개 주${
          data.usStateUnknown > 0 ? ` · 주를 모르는 ${data.usStateUnknown}명은 빼고 칠했습니다` : ""
        }`}
        rows={data.usStates}
        shapes={US_STATES}
        viewBox={US_STATES_VIEWBOX}
        /* 주 이름은 지도 도형 이름과 그대로 같다 — 별칭이 필요 없다. */
        toShape={(name) => name}
      />

      <OriginSection
        id="world-map"
        heading={`미국 밖에서 온 ${abroadTotal}명`}
        note={`${abroad.length}개 나라. 미국은 이 지도에서 뺐습니다 — 함께 칠하면 나머지가 전부 가장 옅은 한 단계로 몰립니다.`}
        rows={abroad}
        shapes={WORLD_COUNTRIES}
        viewBox={WORLD_COUNTRIES_VIEWBOX}
        toShape={shapeNameOf}
        footnote={
          <>
            지도는 잉글랜드·스코틀랜드를 영국 한 칸으로 칠합니다 — 경계 데이터에 그 둘이 따로
            없습니다.
            {unmapped.length > 0 &&
              ` 지도에 도형이 없어 칠하지 못한 곳: ${unmapped.map((r) => r.name).join(" · ")}.`}
          </>
        }
      />
    </div>
  );
}

/**
 * 지도 + 순위 목록 + 명단 한 묶음.
 *
 * **선택은 도형 이름으로 쥔다.** 잉글랜드와 스코틀랜드가 같은 영국 도형을 쓰므로
 * 데이터 이름으로 쥐면 지도에서 어느 쪽을 칠해야 할지 알 수 없다. 반대로 명단은
 * 그 도형에 묶인 데이터 행을 **모두** 모아 보여 준다 — 영국을 누르면 잉글랜드와
 * 스코틀랜드가 함께 나온다.
 */
function OriginSection({
  id,
  heading,
  note,
  rows,
  shapes,
  viewBox,
  toShape,
  footnote,
}: {
  id: string;
  heading: string;
  note: string;
  rows: OriginCount[];
  shapes: { id: string; name: string; d: string }[];
  viewBox: string;
  toShape: (name: string) => string;
  footnote?: React.ReactNode;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const values = new Map<string, number>();
  const members = new Map<string, string[]>();
  for (const row of rows) {
    const shape = toShape(row.name);
    values.set(shape, (values.get(shape) ?? 0) + row.count);
    members.set(shape, [...(members.get(shape) ?? []), ...row.members]);
  }

  const picked = selected ? rows.filter((row) => toShape(row.name) === selected) : [];

  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <div>
        <h2 id={id} className="font-sport text-lg text-foreground">
          {heading}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">{note}</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_14rem]">
        <Choropleth
          shapes={shapes}
          viewBox={viewBox}
          values={values}
          members={members}
          selected={selected}
          onSelect={setSelected}
          className="min-w-0"
        />
        <ol className="flex max-h-[28rem] flex-col gap-0.5 overflow-y-auto pr-1">
          {rows.map((row) => {
            const shape = toShape(row.name);
            const isSelected = selected === shape;
            const max = rows[0]?.count ?? 1;
            return (
              <li key={row.name}>
                <button
                  type="button"
                  onClick={() => setSelected(isSelected ? null : shape)}
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-sm transition-colors hover:bg-card-2",
                    isSelected && "bg-card-2",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate text-foreground">{row.name}</span>
                  {/* 막대는 목록 안에서 비율을 보여 주는 보조선이다 — 숫자가 먼저다. */}
                  <span className="h-1.5 w-14 shrink-0 overflow-hidden rounded-sm bg-surface-2">
                    <span
                      className="block h-full rounded-sm bg-chart-1"
                      style={{ width: `${Math.max(6, (row.count / max) * 100)}%` }}
                    />
                  </span>
                  <span className="w-6 shrink-0 text-right tabular-nums text-muted-foreground">
                    {row.count}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      {picked.length > 0 && <RosterPanel groups={picked} onClose={() => setSelected(null)} />}
      {footnote && <p className="text-xs text-muted-foreground">{footnote}</p>}
    </section>
  );
}
