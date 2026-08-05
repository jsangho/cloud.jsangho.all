"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  agentLabel,
  isBookmakerFallback,
  opponentShare,
  resolvePickName,
  toPercent,
  type AiAgentReport,
  type AiPrediction,
} from "@/lib/ple-ai-predictions";

type AiReportDialogProps = {
  slug: string;
  matchTitle: string;
  prediction: AiPrediction;
};

function AgentRow({
  report,
  slug,
  matchKey,
}: {
  report: AiAgentReport;
  slug: string;
  matchKey: string;
}) {
  const hasOpinion = report.pick !== null;

  return (
    <li className="rounded-lg border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-900/40 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-stone-200 dark:bg-stone-800 px-2 py-0.5 text-xs font-semibold text-stone-700 dark:text-stone-200">
          {agentLabel(report.agent)}
        </span>
        {hasOpinion ? (
          <span className="text-sm font-medium text-violet-700 dark:text-violet-200">
            {resolvePickName(slug, matchKey, report.pick ?? "")}
          </span>
        ) : (
          /* 의견 없음은 실패가 아니다 — 판단할 근거가 없었다는 뜻이다. */
          <span className="text-sm text-stone-500">의견 없음</span>
        )}
        {hasOpinion && (
          <span className="text-xs tabular-nums text-stone-500">
            확신 {toPercent(report.weight)}%
          </span>
        )}
      </div>
      {report.summary && (
        <p className="mt-1.5 text-sm leading-relaxed text-stone-600 dark:text-stone-300">
          {report.summary}
        </p>
      )}
      {report.sources.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {report.sources.map((url) => (
            <li key={url} className="truncate text-xs">
              <a
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="text-stone-500 underline underline-offset-2 hover:text-stone-700 dark:hover:text-stone-200"
              >
                {url}
              </a>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function AiReportDialog({
  slug,
  matchTitle,
  prediction,
}: AiReportDialogProps) {
  const [open, setOpen] = useState(false);
  const fallback = isBookmakerFallback(prediction);
  const opponent = opponentShare(slug, prediction);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          type="button"
          className="rounded-md border border-stone-300/70 dark:border-stone-600/70 px-2 py-0.5 text-[11px] font-medium text-stone-600 dark:text-stone-300 transition-colors hover:bg-stone-200/70 dark:hover:bg-stone-800"
          aria-expanded={open}
        >
          근거
        </button>
      </DialogTrigger>
      <DialogContent
        className="max-h-[min(85dvh,760px)] overflow-y-auto border-stone-300 dark:border-stone-700 bg-stone-50 dark:bg-stone-900 text-stone-900 dark:text-stone-100 sm:max-w-lg"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="text-base sm:text-lg">
            {matchTitle}
          </DialogTitle>
          <DialogDescription className="text-sm text-stone-500">
            {fallback
              ? "분석 근거를 모으지 못해 북메이커 배당으로 대체한 예측입니다."
              : "각 분석의 의견을 합쳐 만든 예측입니다."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/60 dark:bg-stone-800/40 px-4 py-3">
          <span className="text-base font-bold text-violet-700 dark:text-violet-200">
            {prediction.pickName}
          </span>
          <span className="text-sm tabular-nums text-stone-600 dark:text-stone-300">
            승률 {toPercent(prediction.winProbability)}%
          </span>
          {opponent && (
            /* 상대가 가진 몫. 승률이 한쪽만 적히면 나머지가 어디 갔는지 알 수 없다. */
            <span className="text-sm tabular-nums text-stone-500">
              vs {opponent.name} {toPercent(opponent.probability)}%
            </span>
          )}
          <span
            className={cn(
              "text-sm tabular-nums",
              prediction.confidence > 0
                ? "text-stone-600 dark:text-stone-300"
                : "text-stone-500",
            )}
          >
            확신 {toPercent(prediction.confidence)}%
          </span>
        </div>

        {prediction.rationale && (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-700 dark:text-stone-200">
            {prediction.rationale}
          </p>
        )}

        {prediction.reports.length > 0 ? (
          <ul className="space-y-2">
            {prediction.reports.map((report) => (
              <AgentRow
                key={report.agent}
                report={report}
                slug={slug}
                matchKey={prediction.matchKey}
              />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-stone-500">
            분석 리포트가 없는 예측입니다.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
