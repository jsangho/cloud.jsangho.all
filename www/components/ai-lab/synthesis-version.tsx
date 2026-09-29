import { cn } from "@/lib/utils";

/**
 * 승률을 만든 **합성 산식의 판본** (2026-09-28).
 *
 * 목록 화면과 감사 화면이 **같은 표기를 쓴다.** 따로 두면 언젠가 한쪽만 바뀌어 같은
 * 판본이 두 화면에서 다르게 불린다 — `EligibilityBadges`와 같은 이유다.
 *
 * **왜 이 값을 화면에 적는가.** v1은 기권한 에이전트를 분포에서 빼서 셋 중 하나만
 * 답해도 승률 1.0을 냈고, v2는 기권을 균등분포로 센다. 그래서 목록에 승률 1.00과
 * 0.44가 나란히 서는데, 판본을 안 적으면 **서로 비교할 수 없는 두 숫자가 같은 자로
 * 잰 값처럼** 읽힌다. 옛 예측을 새 산식으로 다시 계산하지 않는 이유는 그 예측의
 * 계보(생성 시각·검색 스냅샷)가 그때의 숫자에 묶여 있기 때문이다.
 *
 * 판정과 무관하다 — 산식은 자격이 아니라 **숫자의 출처**다.
 */

/** 판본별 설명. **여기가 유일한 출처다.** */
const VERSION_NOTE: Record<string, string> = {
  "1": "산식 v1 — 의견을 내지 않은 분석기를 승률 계산에서 뺐습니다. 한 명만 답하면 승률이 100%까지 오릅니다.",
  "2": "산식 v2 — 기권을 '모르겠다'로 세어 분포에 넣습니다. 답한 수가 적으면 승률이 균등 쪽으로 내려옵니다.",
};

/** 모르는 판본도 숨기지 않는다 — 빈칸이 "판본이 없다"로 읽히는 것이 더 나쁘다. */
export function synthesisVersionNote(version: string): string {
  return VERSION_NOTE[version] ?? `산식 v${version} — 이 화면이 모르는 판본입니다.`;
}

export function SynthesisVersion({ version, className }: { version: string; className?: string }) {
  return (
    <span className={cn("whitespace-nowrap", className)} title={synthesisVersionNote(version)}>
      산식 v{version}
    </span>
  );
}
