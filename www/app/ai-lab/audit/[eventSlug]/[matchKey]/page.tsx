"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { SeverityBadge, StatusBadge } from "@/components/ai-lab/eligibility-badges";
import { DataUnavailable, LoadingBlock } from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchPredictionAudit,
  formatRatio,
  type AuditReport,
  type Evidence,
  type EvidenceTemporal,
  type PredictionAudit,
  type RuleDefinition,
  type RuleVerdict,
} from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: PredictionAudit }
  | { status: "missing" };

/**
 * Prediction Audit (Phase 9).
 *
 * **이 화면은 예측이 맞았는지를 묻지 않는다.** 그 예측이 생성될 당시 실제로 알 수
 * 있었던 정보만 썼는지를, 사후에 증거로 재구성할 수 있는지를 묻는다.
 *
 * 그래서 화면의 순서가 곧 논증의 순서다 — 무엇을 예측했나 → 왜 이 판정인가 →
 * 무엇을 읽었길래 → 그 글은 언제 것인가.
 *
 * **판정 문구를 화면이 지어내지 않는다.** 사유도 규칙 설명도 서버가 낸 문장을 그대로
 * 쓴다. LLM에게 "왜 실격인지 설명해"라고 시킨 것이 아니라, 결정적 규칙 엔진이 실제로
 * 본 값을 그대로 펼친 것이다 — 그 구분이 이 화면의 존재 이유다.
 *
 * **Replay 칸이 없다.** Phase 5가 아직이고, 보장할 수 없는 것을 빈칸으로 세워 두면
 * 그 빈칸이 "재현 가능한데 안 했다"로 읽힌다.
 */
export default function PredictionAuditPage({
  params,
}: {
  params: Promise<{ eventSlug: string; matchKey: string }>;
}) {
  const { eventSlug, matchKey } = use(params);
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchPredictionAudit(eventSlug, matchKey);
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "missing" });
    })();
    return () => {
      alive = false;
    };
  }, [eventSlug, matchKey]);

  return (
    <AiLabShell
      title="Prediction Audit"
      description="이 예측이 생성될 당시 실제로 알 수 있었던 정보만 썼는지, 그 사실을 사후에 증거로 재구성할 수 있는지를 봅니다."
    >
      <p className="mb-4 text-xs text-muted-foreground">
        <Link href="/ai-lab/performance" className="hover:text-foreground">
          ← Synthesis
        </Link>
      </p>

      {state.status === "loading" && <LoadingBlock rows={5} />}
      {/* **오류가 아니라 없음이다.** 404를 장애처럼 보이게 하지 않는다. */}
      {state.status === "missing" && <DataUnavailable what="이 경기의 예측" />}
      {state.status === "ready" && <Audit data={state.data} />}
    </AiLabShell>
  );
}

function Audit({ data }: { data: PredictionAudit }) {
  return (
    <div className="flex flex-col gap-6">
      <Header data={data} />
      <Verdict data={data} />
      <Agents reports={data.reports} />
      <EvidenceList evidence={data.evidence} eventStartDate={data.eventStartDate} />
    </div>
  );
}

/* ── 1. 무엇을 예측했나 ─────────────────────────────────────────── */

function Header({ data }: { data: PredictionAudit }) {
  return (
    <section className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5">
      <p className="text-xs text-muted-foreground">
        {data.eventLabel} · {data.matchKey}
      </p>
      <h2 className="mt-1 font-sport text-lg tracking-wide text-foreground">{data.matchTitle}</h2>

      <p className="mt-3 text-sm text-foreground">
        <span className="text-muted-foreground">예측 </span>
        <span className="font-medium">{data.pickName}</span>{" "}
        <span className="tabular-nums text-muted-foreground">
          (승률 {formatRatio(data.winProbability)} · 확신 {formatRatio(data.confidence)})
        </span>
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{data.rationale}</p>

      <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
        <Fact label="생성 시각" value={formatMoment(data.generatedAt)} />
        {/* **경기가 끝난 시각이 아니다.** 시간 규칙이 보는 것이 이쪽이라 이름을 정확히 쓴다. */}
        <Fact
          label="결과가 시스템에 기록된 시각"
          value={data.resultRecordedAt ? formatMoment(data.resultRecordedAt) : "기록 없음"}
        />
        <Fact label="대회 날짜" value={data.eventStartDate ?? "모름"} />
        <Fact
          label="결과"
          value={
            data.winnerName === null
              ? "아직 없음"
              : `${data.winnerName}${data.correct === null ? "" : data.correct ? " · 적중" : " · 실패"}`
          }
        />
      </dl>

      {data.source !== "agents" && (
        <p className="mt-3 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
          이 예측은 에이전트가 아니라 북메이커 배당으로 만들어졌습니다.
        </p>
      )}
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-border/60 pb-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right tabular-nums text-foreground">{value}</dd>
    </div>
  );
}

/* ── 2. 왜 이 판정인가 ──────────────────────────────────────────── */

function Verdict({ data }: { data: PredictionAudit }) {
  const rules = new Map(data.rules.map((rule) => [rule.code, rule]));
  /* **막은 것만 세운다.** `applicable=false`도 막은 것이다 — 잴 수 없으면 통과가 아니다. */
  const blocking = data.evaluation.verdicts.filter((v) => v.failed || !v.applicable);
  const passed = data.evaluation.verdicts.filter((v) => !v.failed && v.applicable);

  return (
    <section
      aria-labelledby="verdict-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="verdict-heading" className="font-sport text-base tracking-wide text-foreground">
          Eligibility
        </h2>
        <StatusBadge status={data.evaluation.status} />
      </div>

      {blocking.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          막은 규칙이 없습니다. 일곱 규칙을 모두 지났습니다.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {blocking.map((verdict) => (
            <VerdictRow key={verdict.code} verdict={verdict} rule={rules.get(verdict.code)} />
          ))}
        </ul>
      )}

      {passed.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          지난 규칙: {passed.map((v) => rules.get(v.code)?.label ?? v.code).join(" · ")}
        </p>
      )}
    </section>
  );
}

function VerdictRow({ verdict, rule }: { verdict: RuleVerdict; rule: RuleDefinition | undefined }) {
  return (
    <li className="rounded-lg border border-border px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-foreground">{rule?.label ?? verdict.code}</span>
        <span className="text-xs text-muted-foreground">({verdict.code})</span>
        {rule && <SeverityBadge severity={rule.severity} />}
        {/* **잴 수 없었던 것과 어긴 것은 다르다.** 같은 색으로 칠하면 그 차이가 사라진다. */}
        {!verdict.applicable && (
          <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
            판정 불가
          </span>
        )}
      </div>
      {/* 사유는 서버가 낸 문장 그대로다 — 화면이 지어내지 않는다. */}
      <p className="mt-1.5 text-xs text-foreground">{verdict.detail}</p>
      {rule && <p className="mt-1 text-xs text-muted-foreground">{rule.description}</p>}
    </li>
  );
}

/* ── 3. 누가 무엇이라고 했나 ────────────────────────────────────── */

function Agents({ reports }: { reports: AuditReport[] }) {
  return (
    <section
      aria-labelledby="agents-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="agents-heading" className="font-sport text-base tracking-wide text-foreground">
        Agents
      </h2>

      {reports.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">저장된 리포트가 없습니다.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2.5">
          {reports.map((report) => (
            <li key={report.agent} className="rounded-lg border border-border px-3 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <span className="text-sm font-medium text-foreground">
                  {agentLabel(report.agent)}
                </span>
                <span className="text-sm tabular-nums text-muted-foreground">
                  {/* **의견 없음을 빈칸으로 두지 않는다.** 실패도 반반도 아닌 정상 상태다. */}
                  {report.pick === null
                    ? "의견 없음"
                    : `${report.pick} · weight ${report.weight.toFixed(2)}`}
                </span>
              </div>
              {report.summary && (
                <p className="mt-1.5 text-xs text-muted-foreground">{report.summary}</p>
              )}
              <RuntimeLine report={report} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * 이 의견을 만든 **판** (Phase 4).
 *
 * 모델 이름은 오지 않는다 — DB에는 있지만 응답에 싣지 않기로 했다(하네스 §11-6).
 * 여기 보이는 둘은 불투명한 식별자라 벤더를 드러내지 않으면서도 "같은 조건이었나"를
 * 가릴 수 있다.
 */
function RuntimeLine({ report }: { report: AuditReport }) {
  if (report.agentVersion === null && report.promptVersion === null) {
    /* **백필하지 않았다.** 없는 것을 없다고 적는다. */
    return (
      <p className="mt-1.5 text-xs text-muted-foreground">
        실행 조건 기록 없음 — 이 리포트는 기록을 남기기 전에 만들어졌습니다.
      </p>
    );
  }
  return (
    <p className="mt-1.5 font-mono text-xs text-muted-foreground">
      {report.agentVersion ?? "판 미상"}
      {report.promptVersion && ` · prompt ${report.promptVersion}`}
    </p>
  );
}

/* ── 4. 무엇을 읽었나 ───────────────────────────────────────────── */

const TEMPORAL_LABEL: Record<EvidenceTemporal, string> = {
  before_event: "경기 전 개정본",
  not_before_event: "경기 당일 이후 개정본",
  unknown_revision: "개정본 시각 모름",
  unknown_event_date: "대회 날짜를 몰라 비교 불가",
};

function EvidenceList({
  evidence,
  eventStartDate,
}: {
  evidence: Evidence[];
  eventStartDate: string | null;
}) {
  return (
    <section
      aria-labelledby="evidence-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="evidence-heading" className="font-sport text-base tracking-wide text-foreground">
        Evidence
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        예측을 만들 때 프롬프트에 **실제로 들어간** 청크입니다. 순서는 검색 순위가 아니라 읽은
        순서입니다.
      </p>

      {evidence.length === 0 ? (
        /* **빈 것이 정직한 상태다.** 지금 코퍼스에서 다시 검색해 채우면 "그때 읽은
           것"이 아니라 "지금 검색되는 것"을 적는 것이 된다. */
        <p className="mt-3 rounded-lg border border-border px-3 py-2.5 text-sm text-muted-foreground">
          이 예측에는 검색 기록이 없습니다. 기록을 남기기 전에 만들어진 예측이며, 지금 다시 검색해
          채우면 그때 읽은 것이 아니라 지금 검색되는 것을 적는 것이 됩니다.
        </p>
      ) : (
        <ol className="mt-3 flex flex-col gap-2">
          {evidence.map((item) => (
            <EvidenceRow key={item.rank} item={item} eventStartDate={eventStartDate} />
          ))}
        </ol>
      )}
    </section>
  );
}

function EvidenceRow({ item, eventStartDate }: { item: Evidence; eventStartDate: string | null }) {
  const leaks = item.selfReference || item.temporal === "not_before_event";
  /* **누수와 다른 고장이다** (Phase 2). 결과를 봤을 수 있다는 것이 아니라, 예측이
     읽을 수 없던 글이 증거에 있다는 뜻 — 기록 자체가 성립하지 않는다. 줄을 같은
     색으로 세우되 배지 문구로 둘을 구분한다. */
  const impossible = item.revisionVsPrediction === "after_prediction";

  return (
    <li
      className={cn(
        "rounded-lg border px-3 py-2.5",
        leaks || impossible ? "border-live/50 bg-live/5" : "border-border",
      )}
    >
      <div className="flex items-start gap-2.5">
        <span className="shrink-0 pt-0.5 font-mono text-xs tabular-nums text-muted-foreground">
          {item.rank}
        </span>
        <div className="min-w-0 flex-1">
          {item.sourceUrl ? (
            <a
              href={item.sourceUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="block truncate text-sm text-foreground hover:text-data"
            >
              {item.sourceUrl}
            </a>
          ) : (
            <p className="text-sm text-muted-foreground">출처 기록 없음</p>
          )}

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>
              개정본 {item.sourceRevisionId ?? "미상"}
              {item.sourceRevisedAt && ` · ${formatMoment(item.sourceRevisedAt)}`}
            </span>
            {/* 거리를 못 구했으면 비운다 — 0.0으로 채우지 않는다. */}
            {item.distance !== null && (
              <span className="tabular-nums">거리 {item.distance.toFixed(3)}</span>
            )}
          </div>

          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-xs",
                item.temporal === "before_event"
                  ? "border-data-500/50 bg-data-surface text-data"
                  : item.temporal === "not_before_event"
                    ? "border-live/50 bg-live/10 text-live"
                    : "border-border text-muted-foreground",
              )}
            >
              {TEMPORAL_LABEL[item.temporal]}
              {item.temporal === "not_before_event" &&
                eventStartDate &&
                ` (대회 ${eventStartDate})`}
            </span>
            {/* **정상일 때는 달지 않는다** (Phase 2). 모든 줄에 "예측 이전 개정본"을
                붙이면 그 배지가 배경이 되어, 정작 이상한 줄이 눈에 안 띈다. */}
            {impossible && (
              <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs text-live">
                예측보다 나중 개정본 ← 그때 없던 글
              </span>
            )}
            {item.selfReference && (
              <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs text-live">
                대회 자체 문서 ← 자기참조
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

/** 초 단위까지 적는다 — 시간 규칙이 같은 시각도 실격으로 보기 때문이다. */
function formatMoment(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "medium" });
}
