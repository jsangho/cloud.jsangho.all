"use client";

import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { SeverityBadge } from "@/components/ai-lab/eligibility-badges";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  fetchAiLabReadiness,
  type AiLabReadiness,
  type ReadinessEvent,
  type ReadinessMine,
  type ReadinessRisk,
  type RuleDefinition,
} from "@/lib/ai-lab-api";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabReadiness }
  | { status: "error" };

/**
 * Readiness (Phase 8).
 *
 * **AI LAB의 다른 화면은 전부 뒤를 본다.** 무엇을 예측했고, 누가 맞혔고, 무엇이
 * 막혔고, 어느 문서가 막았는가. 그런데 그 화면들이 모두 같은 결론에 닿는다 —
 * 예측을 만들기 전에 코퍼스를 손봤어야 했다. **누수는 판정에서 생기지 않고
 * 수집에서 생긴다.**
 *
 * 그 손보는 일이 지금까지 화면 없이 돌아갔다. MITB 대회 문서를 손으로 찾아
 * 걷어낸 것이 그 일이고, 아무도 그것을 다시 확인할 수 없었다.
 *
 * **판정하지 않는다.** 여기 나오는 것은 상태가 아니라 위험이다 — 아직 예측이
 * 없으므로 자격을 말할 대상 자체가 없다. 검색도 돌리지 않으므로 지뢰가 실제로
 * 뽑힐지는 모르고, 그래서 이 화면은 **과대평가 쪽으로 틀린다.**
 */
export default function AiLabReadinessPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabReadiness();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="예측 가능성"
      description="지금 가진 문서로 다음 대회를 예측하면 무엇이 걸리는지 미리 봅니다. 판정이 아니라 위험 예보입니다."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="예측 가능성 점검" />}
      {state.status === "ready" && <Readiness data={state.data} />}
    </AiLabShell>
  );
}

const RISK_LABEL: Record<ReadinessRisk, string> = {
  clear: "걸릴 글 없음",
  hold_risk: "보류 위험",
  disqualify_risk: "실격 위험",
};

function Readiness({ data }: { data: AiLabReadiness }) {
  const { totals, corpus, integrity, events, rules } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          value={totals.events}
          label="다가오는 대회"
          note={
            totals.undatedEvents > 0
              ? `날짜 없는 대회 ${totals.undatedEvents}건은 볼 수 없음`
              : "날짜가 오늘 이후인 대회"
          }
        />
        <StatTile
          value={totals.disqualifyRisk}
          label="실격 위험"
          note="그 대회를 다룬 글을 이미 갖고 있음"
        />
        <StatTile value={totals.holdRisk} label="보류 위험" note="출처를 모르는 글만 있음" />
        <StatTile
          value={totals.clear}
          label="걸릴 글 없음"
          note={`걸릴 만한 글 ${totals.mineDocuments}건`}
          tone="data"
        />
      </div>

      <IntegrityBanner integrity={integrity} />

      <Legend rules={rules} />

      <CorpusCard corpus={corpus} />

      {events.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
          {totals.undatedEvents > 0
            ? `날짜가 있는 다가오는 대회가 없습니다 — 날짜 없는 대회 ${totals.undatedEvents}건은 앞에 있는지조차 알 수 없어 세지 않았습니다.`
            : "다가오는 대회가 없습니다."}
        </p>
      ) : (
        <section aria-labelledby="events-heading" className="flex flex-col gap-3">
          <h2 id="events-heading" className="font-sport text-base tracking-wide text-foreground">
            다가오는 대회
          </h2>
          <ul className="flex flex-col gap-2">
            {events.map((item) => (
              <EventCard key={item.slug} event={item} />
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        &ldquo;걸릴 만한 글&rdquo;은 <strong className="font-semibold">읽히면 막힌다</strong>는
        뜻이지 반드시 읽힌다는 뜻이 아닙니다 — 이 화면은 실제 검색을 돌리지 않아서 어느 글이 뽑힐지
        모릅니다. 그래서 위험을 실제보다 많이 세는 쪽으로 틀립니다. 놓친 글은 예측 하나를 통째로 못
        쓰게 만들지만, 괜히 센 글은 문서 하나를 덜 모으게 할 뿐입니다.
      </p>
    </div>
  );
}

/**
 * 이 화면이 **무엇을 물을 수 없는지**를 먼저 적는다.
 *
 * 규칙 여덟 중 앞서 볼 수 있는 것은 둘뿐이다. 적지 않으면 화면이 "여기서 깨끗하면
 * 자격을 얻는다"고 말하는 셈이 된다.
 */
function Legend({ rules }: { rules: RuleDefinition[] }) {
  return (
    <section
      aria-labelledby="legend-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="legend-heading" className="font-sport text-base tracking-wide text-foreground">
        미리 볼 수 있는 경우
      </h2>
      <ul className="mt-3 flex flex-col gap-2.5">
        {rules.map((rule) => (
          <li key={rule.code} className="text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-foreground">{rule.label}</span>
              <span className="text-muted-foreground">({rule.code})</span>
              <SeverityBadge severity={rule.severity} />
            </div>
            <p className="mt-1 text-muted-foreground">{rule.description}</p>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-border/60 pt-3 text-xs text-muted-foreground">
        나머지는 예측이 실제로 만들어진 뒤에야 확인할 수 있습니다 — 특히 &ldquo;읽은 글이 예측보다
        나중에 고쳐진 것인가&rdquo;는 글의 판본과{" "}
        <strong className="font-semibold">예측을 만든 시각</strong>을 견주는데, 견줄 시각이 아직
        없습니다. 여기서 깨끗하다고 통과가 보장되지는 않습니다.
      </p>
    </section>
  );
}

/**
 * 대회와 무관한 코퍼스 자체의 상태.
 *
 * 계보 불완전 문서를 대회마다 반복해 싣지 않는 이유가 여기 있다 — 그것은 대회가
 * 아니라 **문서의 성질**이라 어느 대회를 예측하든 같은 문서가 같은 보류를 만든다.
 */
function CorpusCard({ corpus }: { corpus: AiLabReadiness["corpus"] }) {
  return (
    <section
      aria-labelledby="corpus-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="corpus-heading" className="font-sport text-base tracking-wide text-foreground">
        대회와 상관없는 문제
      </h2>
      <dl className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">모아 둔 문서</dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">{corpus.documents}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">출처를 되짚을 수 없는 글</dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">
            {corpus.incompleteLineage}
          </dd>
          <p className="mt-0.5 text-xs text-muted-foreground">
            어느 대회를 예측하든 이 글이 읽히면 보류가 됩니다.
          </p>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">검색에 안 걸리는 글</dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">
            {corpus.unembeddedDocuments}
          </dd>
          {/* **지뢰가 아니라 없는 것이다.** 검색에 안 잡히므로 근거도 못 된다. */}
          <p className="mt-0.5 text-xs text-muted-foreground">
            뽑히지 않으므로 근거도 못 됩니다 — 실제로 쓸 수 있는 문서는 보이는 수보다 적습니다.
          </p>
        </div>
      </dl>
    </section>
  );
}

/**
 * 대회 상태 코드 → 한국어.
 *
 * **모르는 값은 그대로 내보낸다.** 서버가 상태를 늘렸는데 화면이 임의로 다른 말로
 * 옮기면, 사람이 보는 것과 DB에 적힌 것이 조용히 갈린다 (`scoringExclusionLabel`과
 * 같은 규칙). 타입이 `string`이라 유니온으로 좁힐 수도 없다.
 */
const EVENT_STATUS_LABEL: Record<string, string> = {
  upcoming: "예정",
  live: "진행 중",
  finished: "종료",
};

function eventStatusLabel(status: string): string {
  return EVENT_STATUS_LABEL[status] ?? status;
}

function EventCard({ event }: { event: ReadinessEvent }) {
  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3.5 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{event.label}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {event.startDate} · D-{event.daysUntil} · 경기 {event.matches}건 중 예측{" "}
            {event.predicted}건{/* 날짜가 앞인데 상태가 닫혀 있으면 사람이 아직 안 돌린 것이다. */}
            {event.status !== "upcoming" && (
              <span className="text-muted-foreground">
                {" "}
                · 상태 {eventStatusLabel(event.status)}
              </span>
            )}
          </p>
        </div>
        <RiskBadge risk={event.risk} />
      </div>

      {event.mines.length > 0 && (
        <ul className="mt-2.5 flex flex-col gap-1.5 border-t border-border/60 pt-2.5">
          {event.mines.map((mine) => (
            <MineRow key={mine.sourceUrl} mine={mine} />
          ))}
        </ul>
      )}

      {/* 0이면 적지 않는다 — "0건"은 화면에서 배경이 된다. */}
      {event.unverifiableDocuments > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          이 대회 날짜보다 먼저 쓰인 글인지 확인할 수 없는 문서{" "}
          <strong className="font-semibold">{event.unverifiableDocuments}건</strong> — 읽히면 보류가
          됩니다. 수는 위의 &ldquo;대회와 상관없는 문제&rdquo; 칸에 함께 있습니다.
        </p>
      )}
    </li>
  );
}

/** **색만으로 말하지 않는다.** 실격 위험과 보류 위험은 다른 사실이다. */
function RiskBadge({ risk }: { risk: ReadinessRisk }) {
  return (
    <span
      className={
        risk === "disqualify_risk"
          ? "shrink-0 rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs text-live"
          : risk === "hold_risk"
            ? "shrink-0 rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground"
            : "shrink-0 rounded border border-data-500/50 bg-data-surface px-1.5 py-0.5 text-xs text-data"
      }
    >
      {RISK_LABEL[risk]}
    </span>
  );
}

function MineRow({ mine }: { mine: ReadinessMine }) {
  return (
    <li className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs">
      <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-live">
        그 대회를 다룬 글
      </span>
      <a
        href={mine.sourceUrl}
        target="_blank"
        rel="noreferrer noopener"
        className="min-w-0 flex-1 truncate text-foreground hover:text-data"
      >
        {mine.title ?? mine.sourceUrl}
      </a>
      <span className="shrink-0 tabular-nums text-muted-foreground">글 조각 {mine.chunks}</span>
    </li>
  );
}
