import type { EvaluationStatus } from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

/**
 * 자격 판정 배지 (Phase 3-6·9).
 *
 * Synthesis 화면과 감사 화면이 **같은 배지를 쓴다.** 따로 두면 언젠가 한쪽만 바뀌어
 * 같은 판정이 두 화면에서 다른 이름으로 불린다 — 감사 도구에서 그것은 사소한
 * 불일치가 아니라 신뢰의 문제다.
 *
 * **색만으로 말하지 않는다.** 실격과 보류는 다른 사실이고, 색맹이거나 흑백으로
 * 인쇄한 사람에게도 그 차이가 남아야 한다.
 */

/** 일곱 상태의 한국어 이름. **여기가 유일한 출처다.** */
const STATUS_LABEL: Record<EvaluationStatus, string> = {
  eligible: "자격 있음",
  disqualified: "실격",
  held: "보류",
  // 실격이 아니다 — 누수가 확정된 것과 표본의 성격이 다른 것은 다른 사실이다.
  ex_post: "사후 재현",
  // 결과를 기다리는 것이 아니라 물음이 회수된 것이다 — pending과 다른 사실이다.
  withdrawn_match: "경기 사라짐",
  pending: "결과 없음",
  not_applicable: "평가 대상 아님",
};

export function statusLabel(status: EvaluationStatus): string {
  return STATUS_LABEL[status];
}

export function StatusBadge({
  status,
  className,
}: {
  status: EvaluationStatus;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-1.5 py-0.5 text-xs",
        status === "eligible"
          ? "border-data-500/50 bg-data-surface text-data"
          : status === "disqualified"
            ? "border-live/50 bg-live/10 text-live"
            : "border-border text-muted-foreground",
        className,
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

/** **보류를 실격으로 적지 않는다.** 색만으로 말하지 않고 글자를 함께 단다. */
export function SeverityBadge({ severity }: { severity: string }) {
  const label = severity === "disqualify" ? "실격" : severity === "hold" ? "보류" : "제외";
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-xs",
        severity === "disqualify"
          ? "border-live/50 bg-live/10 text-live"
          : "border-border text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}
