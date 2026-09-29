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
  /**
   * 없으면 적중률 줄을 아예 세우지 않는다. **0으로 채우지 않는다** — 에이전트 화면처럼
   * 전체 적중률이 문맥에 없는 자리가 있고, 거기에 0을 넣으면 "다 틀렸다"가 된다.
   */
  totals?: PredictionTotals;
}) {
  const leakageSuspected =
    integrity.selfReferencingPredictions > 0 || !integrity.temporalVerifiable;

  return (
    <section
      aria-labelledby="integrity-heading"
      className="rounded-xl border border-live/40 bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {/* 예전 제목은 `Evaluation Integrity`였다. 이 상자는 화면에서 **가장 먼저
            읽혀야 하는 블록**인데 제목부터 읽히지 않으면 그냥 넘어간다. */}
        <h2 id="integrity-heading" className="font-sport text-base tracking-wide text-foreground">
          이 숫자를 믿어도 되나
        </h2>
        {!integrity.generalizable && (
          <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs font-medium text-live">
            일반화 지표 아님
          </span>
        )}
      </div>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        {totals && (
          <IntegrityFact
            label="적중률"
            value={
              totals.hitRate === null
                ? "채점된 예측 없음"
                : `${formatRatio(totals.hitRate)} · ${totals.correct}/${totals.graded} · 실제로는 ${formatRatio(totals.hitRateLow)}–${formatRatio(totals.hitRateHigh)} 사이`
            }
          />
        )}
        <IntegrityFact label="표본" value={`예측 ${integrity.sampleSize}건`} />
        <IntegrityFact
          label="대회 범위"
          value={`대회 ${integrity.eventsTotal}개 중 ${integrity.eventsCovered}개`}
        />
        <IntegrityFact
          label="결과가 적힌 글을 근거로 쓴 예측"
          value={`${integrity.predictionsWithSources}건 중 ${integrity.selfReferencingPredictions}건`}
          tone={integrity.selfReferencingPredictions > 0 ? "warn" : "default"}
        />
        <IntegrityFact
          label="예측 시점 확인"
          value={
            integrity.temporalVerifiable
              ? `가능 (출처를 되짚을 수 있는 글 ${integrity.chunksWithRevision}/${integrity.chunksTotal})`
              : `불가 (출처를 모르는 글 ${integrity.chunksTotal - integrity.chunksWithRevision}/${integrity.chunksTotal})`
          }
          tone={integrity.temporalVerifiable ? "default" : "warn"}
        />
        <IntegrityFact
          label="다른 대회에도 통하는 숫자인가"
          value={integrity.generalizable ? "예" : "아니오"}
          tone={integrity.generalizable ? "default" : "warn"}
        />
      </dl>

      {leakageSuspected && (
        <p className="mt-3 text-sm font-medium text-live">
          경기 결과가 예측에 미리 새어 들어왔을 수 있습니다.
        </p>
      )}
      {!integrity.generalizable && totals && totals.hitRate !== null && (
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
        결과가 새지 않은 평가용 표본을 따로 모으는 일은 아직 남아 있습니다. 예측 시점 확인이 보는
        것은 글의 작성 날짜가 아니라{" "}
        <strong className="font-semibold">그 글이 어느 판본에서 온 것인가</strong>이고, 출처를
        모르는 글을 임의로 &ldquo;예전 글&rdquo;로 치지 않습니다.
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
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm tabular-nums", tone === "warn" ? "text-live" : "text-foreground")}>
        {value}
      </dd>
    </div>
  );
}
