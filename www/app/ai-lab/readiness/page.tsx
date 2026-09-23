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
      title="Readiness"
      description="지금 코퍼스로 다음 대회를 예측하면 무엇이 막히는지를 봅니다. 판정이 아니라 위험입니다."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="코퍼스 준비도" />}
      {state.status === "ready" && <Readiness data={state.data} />}
    </AiLabShell>
  );
}

const RISK_LABEL: Record<ReadinessRisk, string> = {
  clear: "지뢰 없음",
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
          label="Upcoming"
          note={
            totals.undatedEvents > 0
              ? `날짜 없는 대회 ${totals.undatedEvents}건은 판정 불가`
              : "날짜가 오늘 이후인 대회"
          }
        />
        <StatTile
          value={totals.disqualifyRisk}
          label="Disqualify risk"
          note="대회 문서가 코퍼스에 있음"
        />
        <StatTile value={totals.holdRisk} label="Hold risk" note="계보를 모르는 문서만 있음" />
        <StatTile
          value={totals.clear}
          label="Clear"
          note={`지뢰 문서 ${totals.mineDocuments}건`}
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
          <h2
            id="events-heading"
            className="font-sport text-base tracking-wide text-foreground"
          >
            Upcoming events
          </h2>
          <ul className="flex flex-col gap-2">
            {events.map((item) => (
              <EventCard key={item.slug} event={item} />
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        지뢰는 <strong className="font-semibold">검색되면 막는다</strong>는 뜻이지 반드시
        검색된다는 뜻이 아닙니다 — 이 화면은 검색을 돌리지 않으므로 어떤 청크가 실제로 뽑힐지
        모릅니다. 그래서 위험을 과하게 세는 쪽으로 틀립니다. 못 본 지뢰는 자격을 앗아가지만,
        헛본 지뢰는 문서 하나를 덜 수집하게 할 뿐입니다.
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
        미리 볼 수 있는 규칙
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
        나머지 규칙은 예측이 생긴 뒤에야 물을 수 있습니다 — 특히 &ldquo;증거가 예측보다 나중에
        생긴 글인가&rdquo;는 개정본과 <strong className="font-semibold">예측 생성 시각</strong>을
        견주는데, 견줄 시각이 아직 없습니다. 여기서 깨끗하다고 자격이 보장되지는 않습니다.
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
        코퍼스 전역
      </h2>
      <dl className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-muted-foreground">문서</dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">{corpus.documents}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
            계보 불완전
          </dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">
            {corpus.incompleteLineage}
          </dd>
          <p className="mt-0.5 text-xs text-muted-foreground">
            어느 대회를 예측하든 인용되면 보류를 만듭니다.
          </p>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
            임베딩 없음
          </dt>
          <dd className="text-lg font-bold tabular-nums text-foreground">
            {corpus.unembeddedDocuments}
          </dd>
          {/* **지뢰가 아니라 없는 것이다.** 검색에 안 잡히므로 근거도 못 된다. */}
          <p className="mt-0.5 text-xs text-muted-foreground">
            검색에 잡히지 않습니다 — 코퍼스가 보이는 것보다 작습니다.
          </p>
        </div>
      </dl>
    </section>
  );
}

function EventCard({ event }: { event: ReadinessEvent }) {
  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3.5 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{event.label}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {event.startDate} · D-{event.daysUntil} · 경기 {event.matches}건 중 예측{" "}
            {event.predicted}건
            {/* 날짜가 앞인데 상태가 닫혀 있으면 사람이 아직 안 돌린 것이다. */}
            {event.status !== "upcoming" && (
              <span className="text-muted-foreground"> · 상태 {event.status}</span>
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
          이 대회 날짜 기준으로 시간을 확인할 수 없는 문서{" "}
          <strong className="font-semibold">{event.unverifiableDocuments}건</strong> — 인용되면
          보류가 됩니다. 목록은 위의 코퍼스 칸에 있습니다.
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
        대회 문서
      </span>
      <a
        href={mine.sourceUrl}
        target="_blank"
        rel="noreferrer noopener"
        className="min-w-0 flex-1 truncate text-foreground hover:text-data"
      >
        {mine.title ?? mine.sourceUrl}
      </a>
      <span className="shrink-0 tabular-nums text-muted-foreground">청크 {mine.chunks}</span>
    </li>
  );
}
