import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * 벨트 표시 — 코드 → 한글 이름 + 계층별 색.
 *
 * **사진이 기본이다** (2026-08-13). 사용자가 열여덟 장을 직접 가져와 `public/belts/`에
 * 넣었고, 원본이 1300px대라 640px WebP로 줄여 뒀다(22MB → 1.1MB). 아래 `PHOTOS`에
 * 없는 코드만 SVG 아이콘으로 떨어진다 — 새 벨트가 생겨도 화면이 비지 않는다.
 *
 * **사진이 가로로 길다**(약 2.2:1). 벨트는 스트랩까지가 한 벌이라 정사각형에 넣으면
 * 어느 벨트든 가운데 금색 판만 남아 서로 구별이 안 된다. 그래서 기록 목록도 칩이
 * 아니라 카드다 — 사용자 요청이 "내 벨트 기록을 최대한 구별이 가게"였다.
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
  // RAW·SD·NXT 공용이다 (2026-08-13 사용자 확인) — NXT 전용 위민스 태그 벨트는 없다.
  wwe_womens_tag_team_championship: ["위민스 태그팀", "tag"],
  nxt_womens_championship: ["NXT 위민스", "world"],
  nxt_womens_north_american_championship: ["NXT 위민스 노스 아메리칸", "secondary"],
  // 스피드는 3분 경기다 (§3-D72). 급이 아니라 선수의 급이 자리를 정하는 벨트다.
  wwe_speed_championship: ["WWE 스피드", "secondary"],
  wwe_womens_speed_championship: ["위민스 스피드", "secondary"],
};

/** 계층이 색을 정한다 — 월드가 가장 금빛이고 태그가 가장 차분하다. */
const PLATE: Record<Tier, { face: string; edge: string }> = {
  world: { face: "#fcbb00", edge: "#b75000" },
  secondary: { face: "#d4af37", edge: "#7b3306" },
  // 태그는 골드 램프 밖이다 — DESIGN.md의 Body/Muted Stone을 쓴다.
  tag: { face: "#d6d3d1", edge: "#78716c" },
};

/** 사진이 있는 벨트. `public/belts/<코드>.webp`를 두면 여기에 코드를 더한다. */
const PHOTOS = new Set(Object.keys(TITLES));

/** 사진의 가로:세로. 열여덟 장이 260~330 높이라 그 언저리로 잡았다. */
const PHOTO_RATIO = 2.2;

/**
 * 이 너비를 넘으면 큰 파일을 집는다 — `belts/hero/`.
 *
 * **화질을 깎는 것은 WebP가 아니라 축소다** (2026-08-13 실측). 같은 픽셀 수라면
 * q88과 q95의 차이가 0.6dB이고, 1280px을 384px로 줄이는 손실은 9dB다. 그래서
 * 압축률이 아니라 **어느 크기를 집느냐**로 나눈다.
 *
 * Next 이미지 최적화가 꺼져 있어(`next.config.mjs`의 `unoptimized: true`) 브라우저가
 * 파일을 그대로 받는다 — 크기를 코드가 아니라 파일로 나눠야 하는 이유다. 목록에
 * 큰 파일을 물리면 벨트 여덟 개짜리 커리어가 2MB를 받는다.
 *
 * 320은 3배 화면(모바일)에서 큰 파일이 필요해지는 경계다: 작은 쪽이 384px이므로
 * 128 CSS px까지는 3배로도 충분하고, 그 위는 큰 파일이 답이다.
 */
const HERO_FROM = 128;

function entryOf(code: string): [string, Tier] {
  // 모르는 코드는 원문 그대로 보여 준다 — 조용히 숨기면 벨트를 잃은 것처럼 읽힌다.
  return TITLES[code] ?? [code, "secondary"];
}

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

/** 벨트 사진 한 장. 사진이 없는 코드는 같은 자리에 SVG를 세운다. */
export function BeltPhoto({ code, width }: { code: string; width: number }) {
  const [name, tier] = entryOf(code);
  const height = Math.round(width / PHOTO_RATIO);
  if (!PHOTOS.has(code)) {
    return (
      <span className="flex shrink-0 items-center justify-center" style={{ width, height }}>
        <BeltIcon tier={tier} size={height} />
      </span>
    );
  }
  const folder = width >= HERO_FROM ? "/belts/hero" : "/belts";
  return (
    <Image
      src={`${folder}/${code}.webp`}
      alt={name}
      width={width}
      height={height}
      className="shrink-0 object-contain"
    />
  );
}

export function BeltChip({ code, held = false }: { code: string; held?: boolean }) {
  const [name] = entryOf(code);
  return (
    <span
      title={name}
      className={cn(
        // 배지는 4px (DESIGN.md §5 Radius Scale — Small).
        "inline-flex items-center gap-1.5 rounded-[4px] px-2 py-1 text-xs",
        held ? "bg-card ring-1 ring-brand-400/60 ring-inset" : "bg-card text-muted-foreground",
      )}
    >
      <BeltPhoto code={code} width={40} />
      {name}
    </span>
  );
}

/**
 * **그 경기에 걸린 벨트** (2026-08-13 사용자 요청 1).
 *
 * "챔피언십 기회를 가져 경기가 열린다면 이 벨트가 처음에 나오게" — 그래서 문장보다
 * 위에, 그 주차 줄의 맨 앞에 선다. 30년에 몇 번 없는 밤이라 이만한 자리를 준다.
 *
 * **크게 세운다** (사용자: "챔피언십 경기나 PLE 이럴 때는 화면에 크게 보여야 하는데").
 * 벨트가 칸의 주인공이고 문구는 그 아래 받침이다 — 목록의 104px 카드와 같은 크기면
 * "이 밤은 다르다"가 화면에서 안 읽힌다.
 */
export function BeltBanner({ code, won }: { code: string; won?: boolean }) {
  const [name] = entryOf(code);
  return (
    <div
      className={cn(
        "mb-2 flex flex-col items-center gap-1.5 rounded-[6px] px-3 py-3",
        won
          ? "bg-brand-400/10 ring-1 ring-brand-400/60 ring-inset"
          : "bg-card ring-1 ring-stone-300/60 ring-inset dark:ring-stone-700/60",
      )}
    >
      {/* 큰 파일(`belts/hero/`)을 집는 크기다 — 320px는 3배 화면에서도 또렷하다. */}
      <BeltPhoto code={code} width={320} />
      <span className="text-center">
        <span className="block font-sport text-base leading-tight">{name} 챔피언십</span>
        <span className="block text-xs text-muted-foreground">
          {won ? "이 밤에 감았다" : "이 밤에 걸렸다"}
        </span>
      </span>
    </div>
  );
}

/**
 * 브랜드 로고 (2026-08-13 사용자가 가져왔다). 없으면 대문자 텍스트로 떨어진다.
 *
 * 파일명은 백엔드 `Brand` 열거값 그대로다 — `raw` · `smackdown` · `nxt`.
 */
const BRANDS = new Set(["raw", "smackdown", "nxt"]);

export function BrandLogo({ brand, width = 96 }: { brand: string; width?: number }) {
  const code = brand.toLowerCase();
  if (!BRANDS.has(code)) return <>{brand.toUpperCase()}</>;
  const folder = width >= HERO_FROM ? "/brands/hero" : "/brands";
  return (
    // **어두운 칩 위에 얹는다.** 셋의 색이 제각각이라(RAW 밝은 적색 · SmackDown 짙은
    // 청색 · NXT 무채색) 일괄 반전은 어느 하나를 반드시 망가뜨린다. 방송 로고는
    // 어두운 바탕을 전제로 그려진 것이라, 배경을 고정하는 쪽이 맞다.
    <span className="inline-flex items-center rounded-[4px] bg-stone-900 px-2 py-1">
      <Image
        src={`${folder}/${code}.webp`}
        alt={brand.toUpperCase()}
        width={width}
        height={Math.round(width / 2.4)}
        className="object-contain"
      />
    </span>
  );
}

/**
 * 감아 본 벨트 목록. 같은 벨트를 여러 번 감았으면 `×N`으로 접는다 — 30년이면 길어진다.
 *
 * **칩이 아니라 카드다** (2026-08-13 사용자 요청 2). 18px 아이콘으로는 열여덟 벨트가
 * 전부 "금색 판"으로 보였다. 사진을 넣은 이유가 구별인데 그 크기로는 넣으나 마나다.
 */
export function BeltList({ codes, held }: { codes: string[]; held: string[] }) {
  const counts = new Map<string, number>();
  for (const code of codes) counts.set(code, (counts.get(code) ?? 0) + 1);
  const heldSet = new Set(held);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {[...counts.entries()].map(([code, times]) => {
        const [name] = entryOf(code);
        const holding = heldSet.has(code);
        return (
          <div
            key={code}
            title={name}
            className={cn(
              "flex flex-col items-center gap-1 rounded-[6px] px-2 py-2 text-center",
              holding
                ? "bg-brand-400/10 ring-1 ring-brand-400/60 ring-inset"
                : "bg-card ring-1 ring-stone-300/50 ring-inset dark:ring-stone-700/50",
            )}
          >
            <BeltPhoto code={code} width={104} />
            <span className="flex items-baseline gap-1">
              <span className="text-xs leading-tight">{name}</span>
              {times > 1 && <span className="text-xs text-muted-foreground">×{times}</span>}
            </span>
            {/* 지금 들고 있는 벨트는 감아 본 벨트와 다른 사실이다 — 색만으로는 안 읽힌다. */}
            {holding && <span className="text-[10px] text-brand-link">보유 중</span>}
          </div>
        );
      })}
    </div>
  );
}
