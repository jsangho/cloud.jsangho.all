"use client";

import Link from "next/link";

/**
 * 고른 묶음의 **전체 명단**. 이름은 그 선수의 기록 페이지로 간다.
 *
 * 출신 지도와 트레이너 목록이 같은 패널을 쓴다 — 둘 다 "이 칸을 누르면 누가
 * 있는지"가 질문이라, 모양이 다르면 같은 동작을 두 번 배워야 한다.
 */
export type RosterGroup = { name: string; count: number; members: string[] };

export function RosterPanel({
  groups,
  suffix = "출신",
  onClose,
}: {
  groups: RosterGroup[];
  /** 제목에 붙는 말 — "출신" · "가 기른 선수" 처럼 자리마다 다르다. */
  suffix?: string;
  onClose: () => void;
}) {
  const total = groups.reduce((sum, g) => sum + g.count, 0);
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">
          {groups.map((g) => g.name).join(" · ")} {suffix}{" "}
          <span className="tabular-nums text-muted-foreground">{total}명</span>
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          닫기
        </button>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {groups.flatMap((group) =>
          group.members.map((name) => (
            <li key={`${group.name}-${name}`}>
              <Link
                href={`/records/${encodeURIComponent(name)}`}
                className="inline-block rounded-md border border-border px-2 py-1 text-xs text-foreground transition-colors hover:bg-card-2"
              >
                {name}
              </Link>
            </li>
          )),
        )}
      </ul>
    </div>
  );
}
