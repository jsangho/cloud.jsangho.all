"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { SeverityBadge, StatusBadge } from "@/components/ai-lab/eligibility-badges";
import { SynthesisVersion, synthesisVersionNote } from "@/components/ai-lab/synthesis-version";
import { DataUnavailable, LoadingBlock } from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchPredictionAudit,
  formatRatio,
  type AuditReport,
  type Evidence,
  type EvidenceTemporal,
  type PredictionAudit,
  type PredictionReplay,
  type ReplayStatus,
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
 * **Replay 칸은 재현된 것만 말한다** (Phase 5). 다섯 단계 중 실제로 다시 돌아가는
 * 것은 질의 조립과 리포트 합성 둘뿐이고, 나머지 셋은 왜 못 돌리는지를 문장으로
 * 세운다 — 보이지 않는 것은 "재현 가능한데 안 했다"로 읽히기 때문이다.
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
      title="예측 감사"
      description="이 예측을 만들 때 그 시점에 알 수 있던 정보만 썼는지, 그리고 그것을 나중에 증거로 다시 짚을 수 있는지를 봅니다."
    >
      <p className="mb-4 text-xs text-muted-foreground">
        <Link href="/ai-lab/performance" className="hover:text-foreground">
          ← 승률 합성
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
      <EvidenceList
        evidence={data.evidence}
        eventStartDate={data.eventStartDate}
        knowledgeQuery={data.knowledgeQuery}
      />
      <Replay replay={data.replay} synthesisVersion={data.synthesisVersion} />
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
          (승률 {formatRatio(data.winProbability)} · 확신 {formatRatio(data.confidence)} ·{" "}
          <SynthesisVersion version={data.synthesisVersion} />)
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
          이 예측은 분석기가 아니라 배당을 그대로 옮겨 만든 것입니다.
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
          채점 자격
        </h2>
        <StatusBadge status={data.evaluation.status} />
      </div>

      {blocking.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          걸린 것이 없습니다. 일곱 가지 점검을 모두 지났습니다.
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
          지난 점검: {passed.map((v) => rules.get(v.code)?.label ?? v.code).join(" · ")}
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
        누가 무엇이라고 했나
      </h2>

      {reports.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">저장된 의견이 없습니다.</p>
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
                    : `${report.pick} · 비중 ${report.weight.toFixed(2)}`}
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
        실행 조건 기록 없음 — 이 의견은 기록을 남기기 전에 만들어졌습니다.
      </p>
    );
  }
  return (
    <p className="mt-1.5 font-mono text-xs text-muted-foreground">
      {report.agentVersion ?? "판 미상"}
      {report.promptVersion && ` · 프롬프트 ${report.promptVersion}`}
    </p>
  );
}

/* ── 4. 무엇을 읽었나 ───────────────────────────────────────────── */

const TEMPORAL_LABEL: Record<EvidenceTemporal, string> = {
  before_event: "경기 전에 쓰인 글",
  not_before_event: "경기 당일 이후에 고쳐진 글",
  unknown_revision: "언제 쓰인 글인지 모름",
  unknown_event_date: "대회 날짜를 몰라 비교 불가",
};

function EvidenceList({
  evidence,
  eventStartDate,
  knowledgeQuery,
}: {
  evidence: Evidence[];
  eventStartDate: string | null;
  knowledgeQuery: string | null;
}) {
  return (
    <section
      aria-labelledby="evidence-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="evidence-heading" className="font-sport text-base tracking-wide text-foreground">
        무엇을 읽었나
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        예측을 만들 때 AI에게 실제로 건네진 글 조각입니다. 순서는 검색 순위가 아니라 건네진
        순서입니다.
      </p>

      {/* **무엇을 물었는가가 무엇이 나왔는가보다 앞선다** (Phase 3). 기록이 없으면
          칸을 세우지 않는다 — 빈칸은 "질의가 없었다"로 읽히는데 그건 거짓이다. */}
      {knowledgeQuery && (
        <div className="mt-3 rounded-lg border border-border bg-surface-2 px-3 py-2.5">
          <p className="text-xs text-muted-foreground">AI가 던진 검색어</p>
          <p className="mt-1 break-words font-mono text-sm text-foreground">{knowledgeQuery}</p>
        </div>
      )}

      {evidence.length === 0 ? (
        /* **빈 것이 정직한 상태다.** 지금 코퍼스에서 다시 검색해 채우면 "그때 읽은
           것"이 아니라 "지금 검색되는 것"을 적는 것이 된다. */
        <p className="mt-3 rounded-lg border border-border px-3 py-2.5 text-sm text-muted-foreground">
          이 예측에는 무엇을 읽었는지 기록이 없습니다. 기록을 남기기 전에 만들어진 예측이며, 지금
          다시 검색해 채우면 그때 읽은 것이 아니라 지금 검색되는 것을 적는 셈이 됩니다.
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
              판본 {item.sourceRevisionId ?? "미상"}
              {item.sourceRevisedAt && ` · ${formatMoment(item.sourceRevisedAt)}`}
            </span>
            {/* 거리를 못 구했으면 비운다 — 0.0으로 채우지 않는다. */}
            {item.distance !== null && (
              <span className="tabular-nums">질문과의 거리 {item.distance.toFixed(3)}</span>
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
                예측보다 나중에 고쳐진 글 ← 그때는 없던 내용
              </span>
            )}
            {item.selfReference && (
              <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs text-live">
                그 대회를 다룬 글 ← 결과가 적혀 있을 수 있음
              </span>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

/* ── 5. 다시 돌리면 같은 답이 나오나 (Phase 5) ──────────────────── */

/** 어긋난 칸의 이름. 서버가 내는 것은 식별자이고 화면 문구는 여기서 붙인다. */
const REPLAY_FIELD_LABEL: Record<string, string> = {
  pick: "선택",
  win_probability: "승률",
  confidence: "확신도",
  knowledge_query: "검색어",
};

/**
 * 저장된 재료로 합성을 **다시 돌린** 결과 (Phase 5).
 *
 * **예측이 맞았는지를 묻는 칸이 아니다.** 저장된 리포트만으로 저장된 결론이 다시
 * 나오는지, 즉 기록이 스스로를 설명하는지를 본다.
 *
 * 다섯 단계 중 둘만 실제로 돌아간다. 나머지 셋을 목록에서 빼지 않는 이유는 Phase 9가
 * 이 칸을 아예 만들지 않았던 이유와 같다 — 보이지 않는 것은 "재현됐다"로 읽힌다.
 */
function Replay({
  replay,
  synthesisVersion,
}: {
  replay: PredictionReplay;
  synthesisVersion: string;
}) {
  return (
    <section
      aria-labelledby="replay-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="replay-heading" className="font-sport text-base tracking-wide text-foreground">
          다시 돌려보기
        </h2>
        <ReplayBadge status={replay.status} />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        저장된 의견을 처음과 같은 계산에 다시 넣어 같은 결론이 나오는지 봅니다. 맞혔는지와는
        상관없습니다.
      </p>
      {/*
        **어느 판본으로 돌렸는지 적는다.** 지금 산식으로 옛 예측을 견주면 전부 값이
        달라지고, 화면은 우리가 함수를 바꾼 일을 "예측이 드리프트했다"로 읽는다.
      */}
      <p className="mt-1 text-xs text-muted-foreground">{synthesisVersionNote(synthesisVersion)}</p>

      <p className="mt-3 text-sm text-foreground">
        {replay.status === "reproduced" && "같은 재료에서 같은 결론이 다시 나왔습니다."}
        {replay.status === "diverged" &&
          "다시 돌렸더니 값이 달라졌습니다. 그 사이 계산 방식이 바뀌었거나 대진이 바뀌었다는 뜻입니다."}
        {/* **사유는 서버가 낸 문장 그대로다.** 화면이 "재현 실패"로 뭉뚱그리지 않는다. */}
        {replay.status === "unreplayable" && (replay.reason ?? "다시 돌릴 재료가 없습니다.")}
      </p>

      {replay.mismatches.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {replay.mismatches.map((item) => (
            <li key={item.field} className="rounded-lg border border-border px-3 py-2.5">
              <p className="text-xs text-muted-foreground">
                {REPLAY_FIELD_LABEL[item.field] ?? item.field}
              </p>
              {/* **두 값을 다 세운다.** "다르다"만으로는 아무것도 못 한다. */}
              <div className="mt-1 grid grid-cols-1 gap-1 font-mono text-xs sm:grid-cols-2">
                <p className="break-words text-muted-foreground">그때 저장된 값 {item.stored}</p>
                <p className="break-words text-foreground">다시 돌린 값 {item.replayed}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <CardDrift unchanged={replay.cardUnchanged} />

      <ul className="mt-4 flex flex-col gap-1.5 border-t border-border/60 pt-3">
        {replay.stages.map((stage) => (
          <li key={stage.stage} className="flex items-start gap-2 text-xs">
            <span
              className={cn(
                "mt-0.5 shrink-0 rounded border px-1.5 py-0.5",
                stage.replayable
                  ? "border-data-500/50 bg-data-surface text-data"
                  : "border-border text-muted-foreground",
              )}
            >
              {stage.replayable ? "다시 됨" : "안 됨"}
            </span>
            <span className="min-w-0">
              <span className="text-foreground">{stage.label}</span>
              <span className="text-muted-foreground"> — {stage.note}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * 카드가 그때와 같은가.
 *
 * 합성은 **지금 카드**의 선택지로 돌아간다. 카드가 바뀌었으면 결과가 달라진 이유를
 * 합성 규칙에 돌릴 수 없으므로, 그 사실을 같은 칸에 세운다.
 */
function CardDrift({ unchanged }: { unchanged: boolean | null }) {
  if (unchanged === null) {
    /* **`null`은 "같다"가 아니다.** 견줄 질의 기록이 없는 상태다. */
    return (
      <p className="mt-3 text-xs text-muted-foreground">
        대진이 그때와 같은지는 알 수 없습니다 — 견줄 검색어 기록이 없습니다.
      </p>
    );
  }
  if (unchanged) {
    return (
      <p className="mt-3 text-xs text-muted-foreground">
        저장된 검색어가 지금 대진으로 다시 만든 것과 같습니다 — 경기 제목과 선수 이름이 그때와
        같습니다.
      </p>
    );
  }
  return (
    <p className="mt-3 rounded-lg border border-live/50 bg-live/5 px-3 py-2 text-xs text-live">
      대진이 그때와 다릅니다. 다시 돌릴 때는 지금 대진을 썼으므로, 값이 달라졌더라도 그 원인을 계산
      방식 탓으로만 볼 수 없습니다.
    </p>
  );
}

function ReplayBadge({ status }: { status: ReplayStatus }) {
  const style =
    status === "reproduced"
      ? "border-data-500/50 bg-data-surface text-data"
      : status === "diverged"
        ? "border-live/50 bg-live/10 text-live"
        : "border-border text-muted-foreground";
  const label =
    status === "reproduced" ? "재현됨" : status === "diverged" ? "값이 달라짐" : "재현 불가";
  return <span className={cn("rounded border px-2 py-0.5 text-xs", style)}>{label}</span>;
}

/** 초 단위까지 적는다 — 시간 규칙이 같은 시각도 실격으로 보기 때문이다. */
function formatMoment(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString("ko-KR", { dateStyle: "short", timeStyle: "medium" });
}
