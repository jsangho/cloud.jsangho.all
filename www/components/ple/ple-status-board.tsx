"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarDays, CheckCircle2, Radio } from "lucide-react";
import { PleEventGrid } from "@/components/ple-event-grid";
import { fetchPleEvents, type PleEventRow } from "@/lib/ple-events-api";
import { formatPleSchedule, getPleBySlug, getPleCountdownDays } from "@/lib/wwe-ple";
import { cn } from "@/lib/utils";

/**
 * PLE 목록 — **서버가 아는 상태로 나눈다** (KAYFABE 2.0 §8).
 *
 * 예전에는 정적 상수와 날짜 계산만으로 상태를 그렸다. DB는 대회가 끝났는지
 * (`status`)와 몇 경기인지(`matchCount`)를 이미 알고 있는데 화면이 그걸 안 물었다.
 *
 * **API를 새로 만들지 않았다** — `GET /api/ple_events/events`가 원본이다.
 * 못 받으면 기존 `PleEventGrid`로 되돌아간다: 목록이 비어 보이는 것보다
 * 예전 화면이 그대로 뜨는 편이 낫다.
 */
type Group = {
  key: "live" | "upcoming" | "finished";
  title: string;
  blurb: string;
  rows: PleEventRow[];
};

/** 예측에 참여한 대회인지 — 기존 카드가 쓰던 로컬 표식과 같은 규약이다. */
function hasPredicted(slug: string): boolean {
  try {
    return localStorage.getItem(`ple-predicted-${slug}`) === "1";
  } catch {
    return false;
  }
}

function StatusChip({ status, days }: { status: Group["key"]; days: number | null }) {
  // **색만으로 상태를 말하지 않는다** (§13) — 아이콘과 글자를 함께 단다.
  if (status === "live") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-live px-2 py-0.5 text-xs font-semibold text-white">
        <Radio className="size-3" aria-hidden />
        LIVE
      </span>
    );
  }
  if (status === "finished") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs font-medium text-muted-foreground">
        <CheckCircle2 className="size-3" aria-hidden />
        종료
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-brand-400/40 px-2 py-0.5 text-xs font-semibold text-brand-link">
      <CalendarDays className="size-3" aria-hidden />
      {days != null && days >= 0 ? `D-${days}` : "예정"}
    </span>
  );
}

function EventCard({ row, group }: { row: PleEventRow; group: Group["key"] }) {
  const ple = getPleBySlug(row.slug);
  const days = ple ? getPleCountdownDays(ple) : null;
  const predicted = hasPredicted(row.slug);
  const href = group === "finished" ? `/results/${row.slug}` : `/ple/${row.slug}`;

  return (
    <Link
      href={href}
      className={cn(
        "group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-card-2",
        group === "live" && "border-live/50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-sport text-xl text-foreground">{row.label}</span>
        <StatusChip status={group} days={days} />
      </div>

      <span className="text-sm text-muted-foreground">
        {ple ? formatPleSchedule(ple) : `${row.year}년 ${row.month ?? "?"}월`}
      </span>

      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="tabular-nums">경기 {row.matchCount}</span>
        {predicted ? (
          <span className="inline-flex items-center gap-1 font-medium text-brand-link">
            <CheckCircle2 className="size-3" aria-hidden />
            예측 참여함
          </span>
        ) : group !== "finished" ? (
          <span>예측 가능</span>
        ) : null}
      </div>

      <span className="mt-2 text-xs font-semibold text-foreground group-hover:underline">
        {group === "finished" ? "결과 보기 →" : "예측하러 가기 →"}
      </span>
    </Link>
  );
}

export function PleStatusBoard() {
  const [rows, setRows] = useState<PleEventRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const data = await fetchPleEvents();
      if (cancelled) return;
      setRows(data);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl border border-border bg-card" />
        ))}
      </div>
    );
  }

  // 서버 목록을 못 받았을 때만 예전 그리드로 되돌아간다.
  if (!rows || rows.length === 0) {
    return <PleEventGrid variant="large" featured />;
  }

  const groups: Group[] = [
    {
      key: "live",
      title: "진행 중",
      blurb: "지금 열리고 있는 대회입니다.",
      rows: rows.filter((r) => r.status === "live"),
    },
    {
      key: "upcoming",
      title: "예정",
      blurb: "아직 예측할 수 있습니다.",
      rows: rows.filter((r) => r.status === "upcoming"),
    },
    {
      key: "finished",
      title: "종료",
      blurb: "결과와 AI 적중 여부를 확인할 수 있습니다.",
      rows: rows.filter((r) => r.status === "finished"),
    },
  ];

  return (
    <div className="flex flex-col gap-8">
      {groups.map((group) =>
        group.rows.length === 0 ? null : (
          <section key={group.key} aria-labelledby={`ple-group-${group.key}`}>
            <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 id={`ple-group-${group.key}`} className="font-sport text-lg text-foreground">
                {group.title}
              </h2>
              <span className="text-sm tabular-nums text-muted-foreground">
                {group.rows.length}개
              </span>
              <span className="text-sm text-muted-foreground">{group.blurb}</span>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {group.rows.map((row) => (
                <EventCard key={row.slug} row={row} group={group.key} />
              ))}
            </div>
          </section>
        ),
      )}
    </div>
  );
}
