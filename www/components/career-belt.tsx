import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * 벨트 표시 — 코드 → 한글 이름 + 계층별 색.
 *
 * **아이콘은 SVG다.** 실제 벨트 사진은 저작권이 있어 저장소에 넣지 않는다. 사진을
 * 쓰려면 `public/belts/<코드>.png`를 두면 되고, 아래 `hasPhoto`가 자동으로 그쪽을
 * 집는다 — 파일을 넣는 것 말고 코드는 손댈 게 없다.
 */

type Tier = "world" | "secondary" | "tag";

const TITLES: Record<string, [name: string, tier: Tier]> = {
  undisputed_wwe_championship: ["언디스퓨티드 WWE", "world"],
  world_heavyweight_championship: ["월드 헤비웨이트", "world"],
  united_states_championship: ["US", "secondary"],
  intercontinental_championship: ["인터컨티넨탈", "secondary"],
  wwe_tag_team_championship: ["WWE 태그팀", "tag"],
  world_tag_team_championship: ["월드 태그팀", "tag"],
  nxt_championship: ["NXT", "world"],
  nxt_north_american_championship: ["NXT 노스 아메리칸", "secondary"],
  nxt_tag_team_championship: ["NXT 태그팀", "tag"],
  wwe_womens_championship: ["WWE 위민스", "world"],
  womens_world_championship: ["위민스 월드", "world"],
  wwe_womens_united_states_championship: ["위민스 US", "secondary"],
  wwe_womens_intercontinental_championship: ["위민스 인터컨티넨탈", "secondary"],
  wwe_womens_tag_team_championship: ["위민스 태그팀", "tag"],
  nxt_womens_championship: ["NXT 위민스", "world"],
  nxt_womens_north_american_championship: ["NXT 위민스 노스 아메리칸", "secondary"],
  nxt_womens_tag_team_championship: ["NXT 위민스 태그팀", "tag"],
};

/** 계층이 색을 정한다 — 월드가 가장 금빛이고 태그가 가장 차분하다. */
const PLATE: Record<Tier, { face: string; edge: string }> = {
  world: { face: "#fcbb00", edge: "#b75000" },
  secondary: { face: "#d4af37", edge: "#7b3306" },
  // 태그는 골드 램프 밖이다 — DESIGN.md의 Body/Muted Stone을 쓴다.
  tag: { face: "#d6d3d1", edge: "#78716c" },
};

/** 사진을 넣어 둔 벨트. `public/belts/<코드>.png`를 두면 여기에 코드를 더한다. */
const PHOTOS = new Set<string>();

export function BeltIcon({ tier, size = 18 }: { tier: Tier; size?: number }) {
  const { face, edge } = PLATE[tier];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden
      className="shrink-0"
      focusable="false"
    >
      {/* 스트랩 */}
      <rect x="0" y="9" width="24" height="6" rx="1" fill={edge} />
      {/* 센터 플레이트 */}
      <path
        d="M12 3.5 19 8v6.5c0 2.4-3.1 4.6-7 6-3.9-1.4-7-3.6-7-6V8z"
        fill={face}
        stroke={edge}
        strokeWidth="1"
      />
      <circle cx="12" cy="11" r="2.2" fill={edge} opacity="0.55" />
    </svg>
  );
}

export function BeltChip({ code, held = false }: { code: string; held?: boolean }) {
  const entry = TITLES[code];
  // 모르는 코드는 원문 그대로 보여 준다 — 조용히 숨기면 벨트를 잃은 것처럼 읽힌다.
  const [name, tier] = entry ?? [code, "secondary" as Tier];
  return (
    <span
      title={name}
      className={cn(
        // 배지는 4px (DESIGN.md §5 Radius Scale — Small).
        "inline-flex items-center gap-1.5 rounded-[4px] px-2 py-1 text-xs",
        held ? "bg-card ring-1 ring-brand-400/60 ring-inset" : "bg-card text-muted-foreground",
      )}
    >
      {PHOTOS.has(code) ? (
        <Image src={`/belts/${code}.png`} alt="" width={18} height={18} className="shrink-0" />
      ) : (
        <BeltIcon tier={tier} />
      )}
      {name}
    </span>
  );
}

/** 같은 벨트를 여러 번 감았으면 `×N`으로 접는다 — 30년이면 목록이 길어진다. */
export function BeltList({ codes, held }: { codes: string[]; held: string[] }) {
  const counts = new Map<string, number>();
  for (const code of codes) counts.set(code, (counts.get(code) ?? 0) + 1);
  const heldSet = new Set(held);
  return (
    <div className="flex flex-wrap gap-1.5">
      {[...counts.entries()].map(([code, times]) => (
        <span key={code} className="inline-flex items-center gap-1">
          <BeltChip code={code} held={heldSet.has(code)} />
          {times > 1 && <span className="text-xs text-muted-foreground">×{times}</span>}
        </span>
      ))}
    </div>
  );
}
