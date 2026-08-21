import { formatRatio, type Integrity, type PredictionTotals } from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

/**
 * Evaluation Integrity (Phase 3-0) — Overview와 Predictions가 **같은 것을 쓴다.**
 *
 * 사용자 결정: 100%를 숨기지 않되 "신뢰 가능한 AI 성능"처럼 표현하지 않는다.
 * 모든 값은 서버가 센 것이고, 화면이 만들어 낸 문장은 없다.
 *
 * 적중률을 여기 함께 세우는 이유는 **떼어 놓으면 자랑이 되기 때문**이다. 표본·커버리지·
 * 자기 참조 출처가 같은 상자 안에 있어야 100%가 무슨 뜻인지 읽힌다.
 */
export function IntegrityBanner({
  integrity,
  totals,
}: {
  integrity: Integrity;
  totals: PredictionTotals;
}) {
  const leakageSuspected =
    integrity.selfReferencingPredictions > 0 || !integrity.temporalVerifiable;

  return (
    <section
      aria-labelledby="integrity-heading"
      className="rounded-xl border border-live/40 bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2
          id="integrity-heading"
          className="font-sport text-base tracking-wide text-foreground"
        >
          Evaluation Integrity
        </h2>
        {!integrity.generalizable && (
          <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs font-medium text-live">
            일반화 지표 아님
          </span>
        )}
      </div>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        <IntegrityFact
          label="Hit rate"
          value={
            totals.hitRate === null
              ? "채점된 예측 없음"
              : `${formatRatio(totals.hitRate)} · ${totals.correct}/${totals.graded} · 95% CI ${formatRatio(totals.hitRateLow)}–${formatRatio(totals.hitRateHigh)}`
          }
        />
        <IntegrityFact label="Sample" value={`${integrity.sampleSize} predictions`} />
        <IntegrityFact
          label="Coverage"
          value={`${integrity.eventsCovered} of ${integrity.eventsTotal} PLE`}
        />
        <IntegrityFact
          label="Self-referencing sources"
          value={`${integrity.selfReferencingPredictions} / ${integrity.predictionsWithSources} predictions`}
          tone={integrity.selfReferencingPredictions > 0 ? "warn" : "default"}
        />
        <IntegrityFact
          label="Temporal verification"
          value={
            integrity.temporalVerifiable
              ? `가능 (발행일 ${integrity.chunksWithPublishedAt}/${integrity.chunksTotal})`
              : `불가 (발행일 0/${integrity.chunksTotal})`
          }
          tone={integrity.temporalVerifiable ? "default" : "warn"}
        />
        <IntegrityFact
          label="Generalizable"
          value={integrity.generalizable ? "Yes" : "No"}
          tone={integrity.generalizable ? "default" : "warn"}
        />
      </dl>

      {leakageSuspected && (
        <p className="mt-3 text-sm font-medium text-live">
          Potential data leakage detected.
        </p>
      )}
      {!integrity.generalizable && totals.hitRate !== null && (
        <p className="mt-1 text-sm text-foreground">
          현재 적중률 {formatRatio(totals.hitRate)}는{" "}
          <strong className="font-semibold">일반화 성능 지표가 아닙니다.</strong>
        </p>
      )}

      {integrity.reasons.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {integrity.reasons.map((reason) => (
            <li key={reason} className="flex gap-2 text-xs text-muted-foreground">
              <span aria-hidden className="select-none">
                ·
              </span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-xs text-muted-foreground">
        누수 없는 평가 표본을 따로 만드는 작업은 Phase 3-6으로 분리했습니다. 발행일이
        없는 문서를 임의로 과거 문서로 간주하지 않습니다.
      </p>
    </section>
  );
}

function IntegrityFact({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warn";
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </dt>
      <dd
        className={cn(
          "text-sm tabular-nums",
          tone === "warn" ? "text-live" : "text-foreground",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
