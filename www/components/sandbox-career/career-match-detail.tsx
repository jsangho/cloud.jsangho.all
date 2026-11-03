"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import {
  fetchCareerMatch,
  type CareerMatchDetail,
  type CareerMatchLookup,
  type CareerMatchParticipant,
} from "@/lib/career-api";
import {
  matchParamStatus,
  missingCopy,
  participantRoles,
  participantsBySide,
  signed,
  stateChanges,
} from "@/lib/career-match";
import { cn } from "@/lib/utils";

import { CARD_KIND_LABEL, SEVERITY_LABEL, labelOf } from "./career-labels";
import { ArenaDialog, Loading, Panel, Stat } from "./career-ui";

/**
 * 경기 상세 — **저장된 경기 기록 한 장을 그대로 펼친다.**
 *
 * 값은 전부 서버 기록이다(P1 `GET /{career}/matches/{id}`). 화면이 하는 계산은
 * 「after − before」 하나뿐이고 그것도 두 저장값의 차다.
 *
 * ## 열림 여부는 URL 이 정한다
 *
 * 이 컴포넌트는 `matchId` 를 받기만 한다. 열고 닫는 것은 페이지가 URL(`?match=`)로
 * 하고, 여기서는 URL 을 건드리지 않는다 — 상태가 두 곳에 있으면 서로를 고치다가
 * 무한 갱신이 난다.
 *
 * ## 요청
 *
 * - **같은 경기를 두 번 요청하지 않는다.** 진행 중인 요청은 키(`커리어:경기`)로 묶어
 *   두 번째 열기가 같은 약속을 기다리고, 받은 기록은 기억해 둔다(기록은 불변이다).
 *   「없음」·「실패」는 기억하지 않는다 — 다시 열면 다시 묻는다.
 * - **늦게 온 응답이 다른 경기 화면에 덮이지 않는다.** 응답은 자기 키로만 저장되고,
 *   화면은 지금 키의 결과만 읽는다.
 */
export function CareerMatchDetailDialog({
  careerId,
  matchId,
  onClose,
}: {
  careerId: number;
  /** URL 의 `match` 값 그대로. `null` 이면 닫혀 있다. */
  matchId: string | null;
  onClose: () => void;
}) {
  const result = useMatchLookup(careerId, matchId);
  if (matchId == null || result == null) return null;

  if (result.status === "loading") {
    return (
      <ArenaDialog title="경기 상세" onClose={onClose}>
        <Loading>경기 기록을 읽는 중…</Loading>
      </ArenaDialog>
    );
  }
  if (result.status === "invalid") {
    return (
      <ArenaDialog title="경기 상세" onClose={onClose}>
        <Notice tone="alert" title="잘못된 경기 링크">
          주소의 경기 ID 형식이 올바르지 않습니다. 경기 목록에서 다시 골라 주세요.
        </Notice>
      </ArenaDialog>
    );
  }
  if (result.status === "error") {
    return (
      <ArenaDialog title="경기 상세" onClose={onClose}>
        <Notice tone="alert" title="경기 기록을 불러오지 못했습니다">
          {result.message}
        </Notice>
        <button
          type="button"
          onClick={result.retry}
          className="arena-ghost justify-self-start px-3 py-1 text-xs font-semibold"
        >
          다시 시도
        </button>
      </ArenaDialog>
    );
  }
  if (result.status === "missing") {
    const copy = missingCopy(result.reason);
    return (
      <ArenaDialog title="경기 상세" onClose={onClose}>
        <Notice tone={copy.tone} title={copy.title}>
          {copy.body}
        </Notice>
      </ArenaDialog>
    );
  }
  return <MatchBody match={result.match} onClose={onClose} />;
}

// ── 요청 ─────────────────────────────────────────────────────────

type ViewResult =
  | { status: "loading" }
  | { status: "invalid" }
  | { status: "ok"; match: CareerMatchDetail }
  | { status: "missing"; reason: (CareerMatchLookup & { status: "missing" })["reason"] }
  | { status: "error"; message: string; retry: () => void };

function useMatchLookup(careerId: number, matchId: string | null): ViewResult | null {
  // 받은 기록(불변) — 키별로. 다시 열면 요청하지 않는다.
  const [found, setFound] = useState<Record<string, CareerMatchDetail>>({});
  // 마지막으로 끝난 요청 하나. **키를 함께 들고 있다** — 지금 키와 다르면 버린다.
  const [settled, setSettled] = useState<{ key: string; lookup: CareerMatchLookup } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const inflight = useRef(new Map<string, Promise<CareerMatchLookup>>());

  const status = matchParamStatus(matchId);
  const key = status === "valid" ? `${careerId}:${matchId}` : null;
  const known = key != null && key in found;

  useEffect(() => {
    if (key == null || known || matchId == null) return;
    let current = true;
    // 같은 경기의 지난 「실패·없음」을 지운다 — 다시 열면 다시 묻고, 그동안은 로딩이다.
    setSettled((s) => (s?.key === key ? null : s));
    let promise = inflight.current.get(key);
    if (!promise) {
      promise = fetchCareerMatch(careerId, matchId).finally(() => {
        inflight.current.delete(key);
      });
      inflight.current.set(key, promise);
    }
    void promise.then((lookup) => {
      if (lookup.status === "ok") setFound((f) => ({ ...f, [key]: lookup.match }));
      // 닫혔거나 다른 경기로 넘어갔으면 화면 상태를 건드리지 않는다.
      if (current) setSettled({ key, lookup });
    });
    return () => {
      // 요청 자체는 끊지 않는다 — 같은 경기를 곧 다시 열면 그 약속을 이어 받는다.
      current = false;
    };
  }, [careerId, matchId, key, known, attempt]);

  if (status === "none") return null;
  if (status === "invalid" || key == null) return { status: "invalid" };
  if (known) return { status: "ok", match: found[key] };
  if (settled == null || settled.key !== key) return { status: "loading" };
  const lookup = settled.lookup;
  if (lookup.status === "ok") return { status: "ok", match: lookup.match };
  if (lookup.status === "missing") return { status: "missing", reason: lookup.reason };
  return {
    status: "error",
    message: lookup.message,
    retry: () => {
      setSettled(null);
      setAttempt((n) => n + 1);
    },
  };
}

// ── 본문 ─────────────────────────────────────────────────────────

function MatchBody({ match, onClose }: { match: CareerMatchDetail; onClose: () => void }) {
  const [mine, theirs] = participantsBySide(match.participants);
  const won = match.winnerSide === 0;
  const isTag = match.kind === "tag";

  return (
    <ArenaDialog
      title={`S${match.season} · W${match.week} — ${labelOf(CARD_KIND_LABEL, match.kind)}`}
      description={`${match.brand} · ${match.reason}`}
      onClose={onClose}
    >
      <div className="space-y-3">
        <section aria-label="경기 개요" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            label="결과"
            value={won ? "승리" : "패배"}
            tone={won ? undefined : "warn"}
            sub={won ? "내 팀 승리" : "상대 팀 승리"}
          />
          <Stat label="피니시" value={match.finish} />
          <Stat label="평점" value={`${match.rating}`} />
          <Stat
            label="경기 전 승률"
            value={`${Math.round(match.probability * 100)}%`}
            sub="내 팀 기준"
          />
        </section>

        {match.title ? (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-brand-700/50 bg-brand-500/10 px-3 py-2">
            <span className="text-xs font-bold text-stone-400">타이틀</span>
            <span className="text-sm font-semibold text-brand-300">{match.title}</span>
            <span
              className={cn(
                "rounded-md border px-1.5 text-[11px] font-bold",
                match.titleChanged
                  ? "border-brand-400/70 text-brand-300"
                  : "border-white/10 text-stone-400",
              )}
            >
              {match.titleChanged ? "타이틀 이동" : "타이틀 유지"}
            </span>
          </div>
        ) : null}

        <section aria-label="참가자" className="grid gap-2 sm:grid-cols-2">
          <TeamCard label="내 팀" winner={won} members={mine} match={match} />
          <TeamCard label="상대 팀" winner={!won} members={theirs} match={match} />
        </section>

        <Panel
          title="경기 전후"
          hint={
            isTag
              ? "태그 경기의 개인 전적은 엔진이 실제로 반영한 값 그대로입니다. 팀의 승패는 위 「결과」가 기준입니다."
              : undefined
          }
        >
          <div className="space-y-3">
            {match.participants.map((p, index) => (
              // 동명이인이 있어도 줄이 겹치지 않게 순서를 키에 넣는다.
              <StateTable key={`${index}:${p.name}`} participant={p} />
            ))}
          </div>
        </Panel>

        <Extras match={match} />
      </div>
    </ArenaDialog>
  );
}

function TeamCard({
  label,
  winner,
  members,
  match,
}: {
  label: string;
  winner: boolean;
  members: readonly CareerMatchParticipant[];
  match: CareerMatchDetail;
}) {
  return (
    <div
      className={cn(
        "arena-panel px-3 py-2.5",
        winner && "ring-1 ring-brand-400/60 bg-brand-400/[0.06]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">
          {label}
        </span>
        {winner ? (
          // 색만으로 말하지 않는다 — 글자가 함께 선다 (DESIGN.md §2).
          <span className="rounded-md border border-brand-400/70 px-1.5 text-[11px] font-bold text-brand-300">
            승리
          </span>
        ) : null}
      </div>
      <ul className="mt-1.5 space-y-1">
        {members.map((p, index) => (
          <li
            key={`${index}:${p.name}`}
            className="flex flex-wrap items-baseline gap-x-2 text-sm text-stone-100"
          >
            <span className="font-semibold">{p.name}</span>
            {participantRoles(match, p.name).map((role) => (
              <span
                key={role}
                className="rounded-md border border-white/10 px-1.5 text-[11px] text-stone-300"
              >
                {role}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StateTable({ participant }: { participant: CareerMatchParticipant }) {
  const rows = stateChanges(participant);
  return (
    <div>
      <p className="text-xs font-semibold text-stone-200">{participant.name}</p>
      <table className="mt-1 w-full text-xs tabular-nums">
        <caption className="sr-only">{participant.name} 경기 전후 상태</caption>
        <thead>
          <tr className="text-[11px] text-stone-500">
            <th scope="col" className="py-0.5 text-left font-normal">
              항목
            </th>
            <th scope="col" className="py-0.5 text-right font-normal">
              경기 전
            </th>
            <th scope="col" className="py-0.5 text-right font-normal">
              경기 후
            </th>
            <th scope="col" className="py-0.5 text-right font-normal">
              변화
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-t border-white/5">
              <th scope="row" className="py-1 text-left font-normal text-stone-400">
                {row.label}
              </th>
              <td className="py-1 text-right text-stone-300">{row.before}</td>
              <td className="py-1 text-right font-semibold text-stone-50">{row.after}</td>
              <td
                className={cn(
                  "py-1 text-right font-semibold",
                  row.good == null ? "text-stone-500" : row.good ? "text-chart-win" : "text-live",
                )}
              >
                {/* 화살표와 부호가 방향을 말한다 — 색은 좋고 나쁨만 덧붙인다. */}
                {row.delta > 0 ? "▲ " : row.delta < 0 ? "▼ " : ""}
                {signed(row.delta)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Extras({ match }: { match: CareerMatchDetail }) {
  const items: { key: string; node: ReactNode }[] = [];
  if (match.popularityDelta !== 0) {
    items.push({
      key: "pop",
      node: (
        <p className="text-sm text-stone-100">
          인기도 변화 <span className="font-semibold">{signed(match.popularityDelta)}</span>
          <span className="ml-1 text-[11px] text-stone-400">
            (엔진 계산값 · 상한·하한에 걸리면 실제 변화는 위 표가 더 작다)
          </span>
        </p>
      ),
    });
  }
  if (match.injury) {
    const injury = match.injury;
    items.push({
      key: "injury",
      node: (
        <p className="text-sm text-live">
          부상 — {injury.kind} · {labelOf(SEVERITY_LABEL, injury.severity)} · 결장 {injury.weeksOut}
          주{injury.recurrence ? " · 재발" : ""}
          {injury.permanent ? " · 영구 불가" : ""}
        </p>
      ),
    });
  }
  if (match.heat.length > 0) {
    items.push({
      key: "heat",
      node: (
        <div>
          <p className="text-xs font-semibold text-stone-400">관계 변화</p>
          <ul className="mt-1 space-y-0.5 text-sm tabular-nums text-stone-100">
            {match.heat.map((h, index) => (
              <li key={`${index}:${h.a}:${h.b}`}>
                {h.a} → {h.b}:{" "}
                {h.before == null ? (
                  <span>새 관계 {h.after}</span>
                ) : (
                  <span>
                    {h.before} → {h.after}{" "}
                    <span className="text-stone-400">({signed(h.after - h.before)})</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ),
    });
  }
  // 없는 정보는 칸째 뺀다 — 빈 상자나 「0」을 세우지 않는다.
  if (items.length === 0) return null;
  return (
    <Panel title="경기 부가 정보">
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.key}>{item.node}</div>
        ))}
      </div>
    </Panel>
  );
}

function Notice({
  tone,
  title,
  children,
}: {
  tone: "info" | "alert";
  title: string;
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "alert" ? "alert" : "status"}
      className={cn(
        "rounded-xl border p-3",
        tone === "alert" ? "border-live/50 bg-live/10" : "border-white/10 bg-white/[0.03]",
      )}
    >
      <p className={cn("text-sm font-semibold", tone === "alert" ? "text-live" : "text-stone-100")}>
        {title}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-stone-300">{children}</p>
    </div>
  );
}
