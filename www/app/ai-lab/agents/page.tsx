"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다.
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchAiLabAgents,
  formatRatio,
  type AgentAnalysis,
  type AiLabAgents,
} from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabAgents }
  | { status: "error" };

/**
 * Agent Analysis (Phase 3-3).
 *
 * **최종 예측이 맞았는지가 아니라 각 에이전트의 의견이 맞았는지**를 본다. 둘은 다르고,
 * 갈리는 자리가 이 화면의 존재 이유다.
 *
 * 차트를 만들지 않았다. 에이전트별 표본이 5~10건이라 어떤 그림을 그려도 장식이 된다 —
 * 그 자리에 분모와 신뢰구간을 적는 편이 훨씬 많은 것을 말한다.
 */
export default function AiLabAgentsPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabAgents();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="분석기 활동"
      description="분석기 셋이 각각 얼마나 답했고, 그 의견이 실제 결과와 얼마나 맞았는지."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="분석기 기록" />}
      {state.status === "ready" && <Agents data={state.data} />}
    </AiLabShell>
  );
}

function Agents({ data }: { data: AiLabAgents }) {
  const { totals, integrity, agents } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value={totals.agentCount} label="분석기" note="서로 다른 각도로 본다" />
        <StatTile
          value={totals.totalReports}
          label="내놓은 분석"
          note={`예측 ${totals.totalPredictions}건에 대해`}
          tone="data"
        />
        <StatTile
          value={formatRatio(totals.overallOpinionRate)}
          label="의견을 낸 비율"
          note={`${totals.opinionated}/${totals.totalReports} · 의견 없음 ${totals.noOpinion}`}
        />
        <StatTile
          value={totals.gradableReports}
          label="채점할 수 있는 분석"
          note="의견을 냈고 결과도 나온 것"
        />
      </div>

      {/* 전체 적중률은 이 화면의 문맥이 아니다 — 여기서는 에이전트별 정확도를 말한다. */}
      <IntegrityBanner integrity={integrity} />

      {agents.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
          아직 의견을 낸 분석기가 없습니다.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {agents.map((agent) => (
            <AgentRow key={agent.agent} agent={agent} totals={totals} />
          ))}
        </ul>
      )}

      <p className="text-xs text-muted-foreground">
        적중률은 최종 예측이 아니라 <strong className="font-semibold">그 분석기가 낸 의견</strong>을
        실제 승자와 맞춰 본 값입니다. 의견 없음은 틀린 것으로 치지 않고 아예 세지 않습니다 — 근거가
        없을 때 답하지 않는 것은 설계된 동작입니다.
      </p>
    </div>
  );
}

function AgentRow({ agent, totals }: { agent: AgentAnalysis; totals: AiLabAgents["totals"] }) {
  const lowResponse = agent.responseRate !== null && agent.reports < totals.totalPredictions;

  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3 sm:px-5 sm:py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="font-sport text-base text-data">{agentLabel(agent.agent)}</h3>
        <Link
          href={`/ai-lab/predictions?agent=${agent.agent}`}
          className="text-xs text-brand-link underline underline-offset-2 hover:text-brand-hover"
        >
          예측 보기
        </Link>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        <Metric
          label="답한 횟수"
          value={`${agent.reports}/${totals.totalPredictions}`}
          note={formatRatio(agent.responseRate)}
        />
        <Metric
          label="의견을 낸 횟수"
          value={`${agent.withPick}/${agent.reports}`}
          note={`의견 없음 ${agent.noOpinion}`}
        />
        <Metric
          label="적중률"
          value={
            agent.accuracy === null
              ? "—"
              : `${formatRatio(agent.accuracy)} (${agent.correct}/${agent.gradable})`
          }
          note={
            agent.accuracy === null
              ? "채점할 것이 없음"
              : `실제로는 ${formatRatio(agent.accuracyLow)}–${formatRatio(agent.accuracyHigh)} 사이`
          }
        />
        <Metric
          label="반영 비중"
          value={formatRatio(agent.avgWeightOpinionated)}
          note={`의견 없음까지 넣으면 ${formatRatio(agent.avgWeight)}`}
        />
      </dl>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {!agent.usesKnowledge && (
          <Note tone="neutral">모아 둔 문서를 읽지 않고 숫자만 보는 분석기입니다.</Note>
        )}
        {agent.selfReferencingReports > 0 && (
          <Note tone="warn">
            그 경기 결과가 적힌 글을 근거로 씀 {agent.selfReferencingReports}/{agent.reports}
          </Note>
        )}
        {lowResponse && (
          <Note tone="neutral">
            {totals.totalPredictions}번 중 {agent.reports}번만 답했습니다 — 무료 사용량의 분당 호출
            제한에 걸린 것으로 기록에 남아 있습니다.
          </Note>
        )}
      </div>
    </li>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums text-foreground">{value}</dd>
      {note && <p className="text-xs tabular-nums text-muted-foreground">{note}</p>}
    </div>
  );
}

/** 사실만 적는다 — "어느 쪽이 더 믿을 만하다" 같은 해석은 화면이 하지 않는다. */
function Note({ tone, children }: { tone: "neutral" | "warn"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-xs",
        tone === "warn"
          ? "border-live/50 bg-live/10 text-live"
          : "border-border text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}
