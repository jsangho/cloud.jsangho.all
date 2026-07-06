"use client";

import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { resolveCompetitorInfo } from "@/lib/wrestler-info";
import type {
  CompetitorProfile,
  CompetitorMatchRecord,
} from "@/lib/records-api";
import type { TitleAcquisition } from "@/lib/title-history-api";

type FilterResult = "all" | CompetitorMatchRecord["result"];
type FilterFormat = "all" | "singles" | "multi";

type CompetitorRecordViewState = {
  q: string;
  result: FilterResult;
  format: FilterFormat;
  titleHistoryOpen: boolean;
};

const initialState: CompetitorRecordViewState = {
  q: "",
  result: "all",
  format: "all",
  titleHistoryOpen: false,
};

function pct(n: number): string {
  const v = Math.round(n * 100);
  return `${v}%`;
}

function winRate(wins: number, losses: number): string {
  const denom = wins + losses;
  if (denom <= 0) return "-";
  return pct(wins / denom);
}

function badgeClass(result: CompetitorMatchRecord["result"]) {
  switch (result) {
    case "win":
      return "border-emerald-700/60 bg-emerald-950/30 text-emerald-200";
    case "loss":
      return "border-rose-700/60 bg-rose-950/30 text-rose-200";
    case "pending":
      return "border-stone-700/70 bg-stone-950/30 text-stone-200";
    case "no-contest":
      return "border-amber-700/60 bg-amber-950/30 text-amber-200";
  }
}

function accentClass(result: CompetitorMatchRecord["result"]) {
  switch (result) {
    case "win":
      return "border-l-emerald-500";
    case "loss":
      return "border-l-rose-500";
    case "pending":
      return "border-l-stone-500";
    case "no-contest":
      return "border-l-amber-500";
  }
}

function labelFor(result: CompetitorMatchRecord["result"]) {
  switch (result) {
    case "win":
      return "승";
    case "loss":
      return "패";
    case "pending":
      return "대기";
    case "no-contest":
      return "무효";
  }
}

function groupByPle(matches: CompetitorMatchRecord[]) {
  const map = new Map<string, CompetitorMatchRecord[]>();
  for (const m of matches) {
    const key = `${m.slug}::${m.pleLabel}`;
    const cur = map.get(key) ?? [];
    cur.push(m);
    map.set(key, cur);
  }
  return Array.from(map.entries()).map(([key, items]) => {
    const [slug, pleLabel] = key.split("::") as [string, string];
    return { slug, pleLabel, items };
  });
}

function participantIncludesCompetitor(
  participantName: string,
  competitorName: string,
): boolean {
  const info = resolveCompetitorInfo(participantName);
  if (info.members.length > 0) {
    return info.members.some((m) => m.ringName === competitorName);
  }
  return participantName === competitorName;
}

function isTitleMatchTitle(title: string): boolean {
  const t = title.toLowerCase();
  if (t.includes("money in the bank") && t.includes("ladder")) return false;
  return /championship|챔피언십/i.test(title);
}

function CompetitorProfileHeader({ name }: { name: string }) {
  const info = resolveCompetitorInfo(name);
  const members = info.members.map((m) => m.ringName).filter(Boolean);

  return (
    <section className="rounded-2xl border border-stone-300/70 dark:border-stone-700/70 bg-gradient-to-br from-stone-100/80 dark:from-stone-950/80 to-stone-50/40 dark:to-stone-900/40 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-stone-900 dark:text-stone-50 sm:text-3xl">
              {info.ringName}
            </h1>
            <span className="rounded-full border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/50 dark:bg-stone-950/50 px-2.5 py-0.5 text-[11px] font-bold text-stone-600 dark:text-stone-300">
              {info.kindLabel}
            </span>
          </div>

          {members.length > 1 ? (
            <p className="mt-1.5 text-xs font-medium leading-relaxed text-stone-400">
              멤버 {members.join(" · ")}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function NameChip({ name, highlight }: { name: string; highlight?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-lg border px-2 py-0.5 text-[11px] font-semibold",
        highlight
          ? "border-amber-600/50 bg-amber-950/30 text-amber-100"
          : "border-stone-300/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-950/40 text-stone-700 dark:text-stone-200",
      )}
    >
      {name}
    </span>
  );
}

function MatchRecordCard({
  match,
  competitorName,
}: {
  match: CompetitorMatchRecord;
  competitorName: string;
}) {
  const opponents = match.opponents ?? [];
  const showParticipants =
    match.format === "multi" && (match.participants?.length ?? 0) > 0;
  const isTitle = isTitleMatchTitle(match.title);

  return (
    <li
      className={cn(
        "rounded-xl border border-stone-200/80 dark:border-stone-800/80 border-l-4 bg-stone-100/30 dark:bg-stone-950/30 p-4",
        accentClass(match.result),
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md border border-stone-200/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-900/50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-stone-400">
              {match.format}
            </span>
            {isTitle ? (
              <span className="rounded-md border border-amber-700/60 bg-amber-950/30 px-2 py-0.5 text-[10px] font-extrabold text-amber-200">
                타이틀
              </span>
            ) : null}
            {match.wasChampion ? (
              <span className="rounded-md border border-amber-700/50 bg-amber-950/30 px-2 py-0.5 text-[10px] font-extrabold text-amber-200">
                챔피언
              </span>
            ) : null}
          </div>

          <h3 className="text-base font-bold leading-snug text-stone-900 dark:text-stone-50">
            {match.title}
          </h3>

          {opponents.length > 0 ? (
            <div>
              <p className="mb-1.5 text-[11px] font-bold text-stone-500">
                상대
              </p>
              <div className="flex flex-wrap gap-1.5">
                {opponents.map((name) => (
                  <NameChip key={name} name={name} />
                ))}
              </div>
            </div>
          ) : null}

          {showParticipants ? (
            <div>
              <p className="mb-1.5 text-[11px] font-bold text-stone-500">
                참가자
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(match.participants ?? []).map((name) => (
                  <NameChip
                    key={name}
                    name={name}
                    highlight={participantIncludesCompetitor(
                      name,
                      competitorName,
                    )}
                  />
                ))}
              </div>
            </div>
          ) : null}

          {match.winnerName ? (
            <p className="text-xs font-medium text-stone-400">
              승자{" "}
              <span className="font-semibold text-emerald-200">
                {match.winnerName}
              </span>
            </p>
          ) : null}
        </div>

        <span
          className={cn(
            "shrink-0 rounded-full border px-3 py-1 text-xs font-extrabold",
            badgeClass(match.result),
          )}
        >
          {labelFor(match.result)}
        </span>
      </div>
    </li>
  );
}

export function CompetitorRecordView({
  profile,
  titleHistory = [],
}: {
  profile: CompetitorProfile;
  titleHistory?: TitleAcquisition[];
}) {
  const [state, setState] = useState<CompetitorRecordViewState>(initialState);
  const patchState = (patch: Partial<CompetitorRecordViewState>) =>
    setState((prev) => ({ ...prev, ...patch }));
  const titleBeltCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const h of titleHistory) {
      map.set(h.beltName, (map.get(h.beltName) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [titleHistory]);

  const filtered = useMemo(() => {
    const q = state.q.trim().toLowerCase();
    return profile.matches.filter((m) => {
      if (state.result !== "all" && m.result !== state.result) return false;
      if (state.format !== "all" && m.format !== state.format) return false;
      if (!q) return true;
      const hay = [
        m.pleLabel,
        m.slug,
        m.title,
        m.matchKey,
        ...(m.opponents ?? []),
        ...(m.participants ?? []),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [profile.matches, state.format, state.q, state.result]);

  const singles = useMemo(
    () => filtered.filter((m) => m.format === "singles"),
    [filtered],
  );
  const multi = useMemo(
    () => filtered.filter((m) => m.format === "multi"),
    [filtered],
  );

  const grouped = useMemo(() => groupByPle(filtered), [filtered]);

  return (
    <div className="space-y-4">
      <CompetitorProfileHeader name={profile.name} />

      <section className="rounded-2xl border border-amber-700/40 bg-amber-950/10 p-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-sm font-extrabold text-stone-900 dark:text-stone-50">
              역대 벨트 획득
            </h2>
            <p className="mt-0.5 text-xs font-medium text-stone-400">
              실제 WWE 챔피언십 획득 {titleHistory.length}회
            </p>
          </div>
        </div>

        {titleHistory.length === 0 ? (
          <div className="mt-3 rounded-xl border border-dashed border-amber-800/40 px-4 py-6 text-sm text-stone-300">
            벨트 획득 기록이 없습니다.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border border-amber-800/40 bg-stone-950/20 p-3">
              <p className="text-xs font-bold text-stone-400">벨트별 획득</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {titleBeltCounts.map(([belt, count]) => (
                  <span
                    key={belt}
                    className="inline-flex items-center gap-2 rounded-lg border border-amber-800/40 bg-amber-950/20 px-2.5 py-1 text-xs font-semibold text-amber-100"
                  >
                    <span className="text-amber-100">{belt}</span>
                    <span className="rounded-md bg-amber-900/30 px-1.5 py-0.5 text-[11px] font-extrabold text-amber-200">
                      {count}
                    </span>
                  </span>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-amber-800/40 bg-stone-950/20 p-3">
              <button
                type="button"
                onClick={() =>
                  patchState({ titleHistoryOpen: !state.titleHistoryOpen })
                }
                aria-expanded={state.titleHistoryOpen}
                aria-controls="title-acquisition-history"
                className="flex w-full items-center justify-between gap-2 rounded-lg text-left transition-colors hover:bg-stone-950/30"
              >
                <span className="text-xs font-bold text-stone-400">
                  획득 이력
                  <span className="ml-1.5 font-semibold text-stone-500">
                    ({titleHistory.length})
                  </span>
                </span>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-amber-200/70 transition-transform duration-200",
                    state.titleHistoryOpen && "rotate-180",
                  )}
                  aria-hidden
                />
              </button>
              {state.titleHistoryOpen ? (
                <ul id="title-acquisition-history" className="mt-2 space-y-2">
                  {titleHistory.map((h, idx) => (
                    <li
                      key={`${h.beltName}:${h.wonAt}:${h.matchKey ?? idx}`}
                      className="rounded-lg border border-stone-200/70 dark:border-stone-800/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-stone-800 dark:text-stone-100">
                          {h.beltName}
                        </span>
                        <span className="text-xs font-medium text-stone-400">
                          {h.wonAt}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-50/40 dark:bg-stone-950/40 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-sm font-extrabold text-stone-900 dark:text-stone-50">
              요약
            </h2>
            <p className="mt-0.5 text-xs font-medium text-stone-400">
              승률은 (승 / (승+패)) 기준입니다. (무효/대기는 제외)
            </p>
          </div>

          <div className="text-xs font-semibold text-stone-600 dark:text-stone-200">
            승률{" "}
            <span className="text-stone-800 dark:text-stone-50">
              {winRate(profile.summary.wins, profile.summary.losses)}
            </span>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-6">
          <div className="rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2">
            <div className="text-[11px] font-bold text-stone-400">총</div>
            <div className="text-sm font-extrabold text-stone-800 dark:text-stone-50">
              {profile.summary.total}
            </div>
          </div>
          <div className="rounded-xl border border-emerald-700/60 bg-emerald-950/20 px-3 py-2">
            <div className="text-[11px] font-bold text-emerald-200/80">승</div>
            <div className="text-sm font-extrabold text-emerald-200">
              {profile.summary.wins}
            </div>
          </div>
          <div className="rounded-xl border border-rose-700/60 bg-rose-950/20 px-3 py-2">
            <div className="text-[11px] font-bold text-rose-200/80">패</div>
            <div className="text-sm font-extrabold text-rose-200">
              {profile.summary.losses}
            </div>
          </div>
          <div className="rounded-xl border border-amber-700/60 bg-amber-950/20 px-3 py-2">
            <div className="text-[11px] font-bold text-amber-200/80">무효</div>
            <div className="text-sm font-extrabold text-amber-200">
              {profile.summary.noContest}
            </div>
          </div>
          <div className="rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2">
            <div className="text-[11px] font-bold text-stone-400">대기</div>
            <div className="text-sm font-extrabold text-stone-800 dark:text-stone-50">
              {profile.summary.pending}
            </div>
          </div>
          <div className="rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2">
            <div className="text-[11px] font-bold text-stone-400">
              챔피언 출전
            </div>
            <div className="text-sm font-extrabold text-stone-800 dark:text-stone-50">
              {profile.summary.championAppearances}
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2">
            <div className="text-[11px] font-bold text-stone-400">Singles</div>
            <div className="text-sm font-extrabold text-stone-800 dark:text-stone-50">
              {profile.summary.singlesTotal}{" "}
              <span className="text-xs font-semibold text-stone-400">
                (필터 결과: {singles.length})
              </span>
            </div>
          </div>
          <div className="rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/30 dark:bg-stone-950/30 px-3 py-2">
            <div className="text-[11px] font-bold text-stone-400">Multi</div>
            <div className="text-sm font-extrabold text-stone-800 dark:text-stone-50">
              {profile.summary.multiTotal}{" "}
              <span className="text-xs font-semibold text-stone-400">
                (필터 결과: {multi.length})
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-50/40 dark:bg-stone-950/40 p-4">
        <h2 className="text-sm font-extrabold text-stone-50">필터</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <input
            type="search"
            value={state.q}
            onChange={(e) => patchState({ q: e.target.value })}
            placeholder="검색 (PLE/경기/상대/키워드)"
            className={cn(
              "h-10 w-full rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-950/40 px-3 text-sm text-stone-900 dark:text-stone-100",
              "placeholder:text-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-500/40",
            )}
          />
          <select
            value={state.result}
            onChange={(e) =>
              patchState({ result: e.target.value as FilterResult })
            }
            className="h-10 w-full rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-950/40 px-3 text-sm text-stone-900 dark:text-stone-100"
          >
            <option value="all">결과: 전체</option>
            <option value="win">승</option>
            <option value="loss">패</option>
            <option value="no-contest">무효</option>
            <option value="pending">대기</option>
          </select>
          <select
            value={state.format}
            onChange={(e) =>
              patchState({ format: e.target.value as FilterFormat })
            }
            className="h-10 w-full rounded-xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-950/40 px-3 text-sm text-stone-900 dark:text-stone-100"
          >
            <option value="all">타입: 전체</option>
            <option value="singles">Singles</option>
            <option value="multi">Multi</option>
          </select>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-200/70 dark:border-stone-700/70 bg-stone-50/40 dark:bg-stone-950/40 p-4">
        <div className="mb-4">
          <h2 className="text-sm font-extrabold text-stone-50">경기 기록</h2>
          <p className="mt-0.5 text-xs font-medium text-stone-400">
            필터 결과 {filtered.length}건
          </p>
        </div>

        {filtered.length === 0 ? (
          <div className="rounded-xl border border-dashed border-stone-300/70 dark:border-stone-700/70 px-4 py-8 text-center text-sm text-stone-500 dark:text-stone-300">
            표시할 기록이 없습니다.
          </div>
        ) : (
          <div className="space-y-6">
            {grouped.map((g) => (
              <div key={`${g.slug}:${g.pleLabel}`}>
                <div className="mb-3 flex items-center gap-2">
                  <span className="text-sm font-extrabold text-stone-800 dark:text-stone-100">
                    {g.pleLabel}
                  </span>
                  <span className="rounded-md border border-stone-200/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-900/50 px-2 py-0.5 text-[10px] font-bold text-stone-400">
                    {g.slug}
                  </span>
                  <span className="text-xs font-medium text-stone-500">
                    {g.items.length}경기
                  </span>
                </div>
                <ul className="space-y-3">
                  {g.items.map((m) => (
                    <MatchRecordCard
                      key={`${m.slug}:${m.matchKey}`}
                      match={m}
                      competitorName={profile.name}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
