"use client";

import { useEffect, useState } from "react";
import {
  DataCenterShell,
  DataUnavailable,
  LoadingBlock,
} from "@/components/data-center/data-center-shell";
import { fetchStaff, type StaffDirectory } from "@/lib/data-center-api";
import { cn } from "@/lib/utils";

/**
 * 관계자 명부 (2026-10-12).
 *
 * 선수 표(`wrestlers`)와 **다른 표**(`wwe_staff`)다 — 경영진·해설·링아나운서·
 * 심판·프로듀서. 그동안 생일 보드에서만 보였다.
 *
 * **머리 숫자는 "전직 선수"다.** 66명 중 24명이 링에 섰던 사람이고(Triple H ·
 * Shawn Michaels · William Regal · Booker T · Haku · Finlay …), 이 명부에서
 * 그게 제일 읽을 만한 사실이다. 판정은 `wrestling_experience`에 낱말
 * `wrestler`가 있는지로만 한다 — 「ECW Promoter | Commentator」(폴 헤이먼)처럼
 * 업계 사람이지만 선수는 아닌 경우를 끌어들이지 않는다.
 *
 * **구역을 인원순으로 재정렬하지 않는다.** CSV가 적어 둔 순서가 조직도다.
 */
type PageState =
  | { status: "loading" }
  | { status: "ready"; data: StaffDirectory }
  | { status: "error" };

export default function DataCenterStaffPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });
  const [group, setGroup] = useState("");
  const [onlyFormer, setOnlyFormer] = useState(false);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchStaff();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <DataCenterShell
      title="관계자"
      description="링 밖에서 일하는 사람들입니다. 경영진·해설·링아나운서·심판·프로듀서를 담았고, 선수 명부와는 다른 표입니다."
    >
      {state.status === "loading" ? (
        <LoadingBlock rows={6} />
      ) : state.status === "error" ? (
        <DataUnavailable what="관계자 명부" />
      ) : (
        (() => {
          const { members, groups, formerWrestlers, total } = state.data;
          const shown = members.filter(
            (m) => (!group || (m.group ?? "미지정") === group) && (!onlyFormer || m.formerWrestler),
          );
          return (
            <div className="flex flex-col gap-5">
              <p className="text-sm text-muted-foreground">
                관계자 <span className="tabular-nums text-foreground">{total}</span>명 ·{" "}
                <span className="tabular-nums text-foreground">{formerWrestlers}</span>명이 링에
                섰던 사람입니다
              </p>

              <div className="flex flex-col gap-2">
                <div className="-mx-4 overflow-x-auto px-4 pb-1">
                  <ul className="flex min-w-max items-center gap-1.5" aria-label="구역 필터">
                    <li>
                      <Chip active={group === ""} onClick={() => setGroup("")}>
                        전체 {total}
                      </Chip>
                    </li>
                    {groups.map((g) => (
                      <li key={g.name}>
                        <Chip active={group === g.name} onClick={() => setGroup(g.name)}>
                          {g.name} {g.count}
                        </Chip>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <Chip active={onlyFormer} onClick={() => setOnlyFormer(!onlyFormer)}>
                    전직 선수만 {formerWrestlers}명
                  </Chip>
                </div>
              </div>

              {shown.length === 0 ? (
                <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  조건에 맞는 사람이 없습니다.
                </p>
              ) : (
                <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {shown.map((m) => (
                    <li
                      key={m.name}
                      className="flex h-full flex-col gap-1 rounded-xl border border-border bg-card p-4"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="min-w-0 truncate font-sport text-base text-foreground">
                          {m.name}
                        </span>
                        {m.formerWrestler && (
                          <span className="shrink-0 rounded-md bg-brand-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-brand-600 dark:text-brand-300/90">
                            전직 선수
                          </span>
                        )}
                      </div>
                      {m.koreanName && m.koreanName !== m.name && (
                        <span className="text-xs text-muted-foreground">{m.koreanName}</span>
                      )}
                      {/* 역할이 비어 있는 행이 17건이다 — 없는 말을 지어내지 않는다. */}
                      {m.role && <span className="text-sm text-foreground">{m.role}</span>}
                      <span className="mt-auto pt-1 text-xs text-muted-foreground">
                        {m.group ?? "미지정"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })()
      )}
    </DataCenterShell>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "whitespace-nowrap rounded-md border px-2.5 py-1 text-xs transition-colors",
        active
          ? "border-brand-500/40 bg-brand-500/10 text-foreground"
          : "border-border text-muted-foreground hover:bg-card-2",
      )}
    >
      {children}
    </button>
  );
}
