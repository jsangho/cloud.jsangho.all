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
      title="Agents"
      description="세 에이전트가 각각 얼마나 답했고, 그 의견이 실제 결과와 얼마나 맞았는지."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="에이전트 분석" />}
      {state.status === "ready" && <Agents data={state.data} />}
    </AiLabShell>
  );
}

function Agents({ data }: { data: AiLabAgents }) {
  const { totals, integrity, agents } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value={totals.agentCount} label="Agents" note="실제 코드의 이름" />
        <StatTile
          value={totals.totalReports}
          label="Reports"
          note={`예측 ${totals.totalPredictions}건에 대해`}
          tone="data"
        />
        <StatTile
          value={formatRatio(totals.overallOpinionRate)}
          label="Opinion rate"
          note={`${totals.opinionated}/${totals.totalReports} · 의견 없음 ${totals.noOpinion}`}
        />
        <StatTile
          value={totals.gradableReports}
          label="Gradable"
          note="의견 + 결과가 있는 리포트"
        />
      </div>

      {/* 전체 적중률은 이 화면의 문맥이 아니다 — 여기서는 에이전트별 정확도를 말한다. */}
      <IntegrityBanner integrity={integrity} />

      {agents.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
          리포트를 낸 에이전트가 없습니다.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {agents.map((agent) => (
            <AgentRow key={agent.agent} agent={agent} totals={totals} />
          ))}
        </ul>
      )}

      <p className="text-xs text-muted-foreground">
        정확도는 최종 예측이 아니라 <strong className="font-semibold">그 에이전트의
        의견</strong>을 실제 승자와 대조한 값입니다. 의견 없음은 오답이 아니며 분모에
        들어가지 않습니다 — 근거가 없을 때 판단하지 않는 것은 설계된 동작입니다.
      </p>
    </div>
  );
}

function AgentRow({
  agent,
  totals,
}: {
  agent: AgentAnalysis;
  totals: AiLabAgents["totals"];
}) {
  const lowResponse =
    agent.responseRate !== null && agent.reports < totals.totalPredictions;

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
          label="Response"
          value={`${agent.reports}/${totals.totalPredictions}`}
          note={formatRatio(agent.responseRate)}
        />
        <Metric
          label="Opinion"
          value={`${agent.withPick}/${agent.reports}`}
          note={`의견 없음 ${agent.noOpinion}`}
        />
        <Metric
          label="Accuracy"
          value={
            agent.accuracy === null
              ? "—"
              : `${formatRatio(agent.accuracy)} (${agent.correct}/${agent.gradable})`
          }
          note={
            agent.accuracy === null
              ? "채점 대상 없음"
              : `95% CI ${formatRatio(agent.accuracyLow)}–${formatRatio(agent.accuracyHigh)}`
          }
        />
        <Metric
          label="Avg weight"
          value={formatRatio(agent.avgWeightOpinionated)}
          note={`전체 ${formatRatio(agent.avgWeight)}`}
        />
      </dl>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {!agent.usesKnowledge && (
          <Note tone="neutral">
            코퍼스 미사용 — 이 에이전트는 RAG 지식을 사용하지 않습니다.
          </Note>
        )}
        {agent.selfReferencingReports > 0 && (
          <Note tone="warn">
            자기 대회 문서 {agent.selfReferencingReports}/{agent.reports} 인용
          </Note>
        )}
        {lowResponse && (
          <Note tone="neutral">
            현재 데이터에서는 {agent.reports}/{totals.totalPredictions} 응답만 확인됩니다
            — 기존 생성 로그상 Gemini 무료 등급 분당 호출 제한의 영향입니다.
          </Note>
        )}
      </div>
    </li>
  );
}

function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums text-foreground">
        {value}
      </dd>
      {note && <p className="text-xs tabular-nums text-muted-foreground">{note}</p>}
    </div>
  );
}

/** 사실만 적는다 — "어느 쪽이 더 믿을 만하다" 같은 해석은 화면이 하지 않는다. */
function Note({
  tone,
  children,
}: {
  tone: "neutral" | "warn";
  children: React.ReactNode;
}) {
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
