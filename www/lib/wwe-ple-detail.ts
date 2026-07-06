import type { PleSlug } from "@/lib/wwe-ple";

export type PleLayoutVariant =
  | "rumble"
  | "chamber"
  | "nxt"
  | "mania"
  | "fallout"
  | "ladder"
  | "tournament"
  | "summer"
  | "international"
  | "cell"
  | "teams";

export type PleTheme = {
  pageBg: string;
  heroGradient: string;
  accent: string;
  accentMuted: string;
  border: string;
  badge: string;
  glow: string;
};

export type PleHighlight = {
  title: string;
  detail: string;
};

export type PleEventDetail = {
  slug: PleSlug;
  tagline: string;
  layout: PleLayoutVariant;
  theme: PleTheme;
  signatureLabel: string;
  highlights: PleHighlight[];
  predictionFocus: string[];
};

export const PLE_EVENT_DETAILS: Record<PleSlug, PleEventDetail> = {
  "royal-rumble": {
    slug: "royal-rumble",
    tagline: "넘어지면 탈락, 마지막까지 남은 자가 WrestleMania로",
    layout: "rumble",
    signatureLabel: "로열 럼블 매치",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-blue-950/15 via-transparent to-transparent",
      accent: "text-amber-300",
      accentMuted: "text-amber-200/70",
      border: "border-amber-700/50",
      badge: "bg-amber-900/40 text-amber-200 ring-amber-600/40",
      glow: "shadow-[0_0_80px_-20px_rgba(251,191,36,0.35)]",
    },
    highlights: [
      { title: "30인 룰렛", detail: "2분 간격 입장, 로프 밖 탈락" },
      { title: "WM 출전권", detail: "남·여 각 1명이 Mania 메인 이벤트 진출" },
      { title: "서프라이즈 입장", detail: "복귀·데뷔가 시즌 내러티브를 바꿈" },
    ],
    predictionFocus: ["우승자", "최후 4인", "서프라이즈 입장", "탈락 순서"],
  },
  "elimination-chamber": {
    slug: "elimination-chamber",
    tagline: "철창 안에서 챔피언이 방어하거나 새 챔피언이 탄생",
    layout: "chamber",
    signatureLabel: "엘리미네이션 챔버",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-zinc-500/10 via-transparent to-transparent",
      accent: "text-zinc-200",
      accentMuted: "text-zinc-400",
      border: "border-zinc-500/50",
      badge: "bg-zinc-800/60 text-zinc-100 ring-zinc-500/40",
      glow: "shadow-[0_0_70px_-18px_rgba(161,161,170,0.4)]",
    },
    highlights: [
      { title: "4개의 포드", detail: "4분마다 한 명씩 입장하는 6인 구조" },
      { title: "핀·서브", detail: "탈락은 핀폴 또는 초크아웃" },
      {
        title: "듀얼 챔버",
        detail: "남·여 단일·태그 타이틀 방어가 동시 진행되기도 함",
      },
    ],
    predictionFocus: [
      "챔피언 방어 여부",
      "탈락 순서",
      "마지막 2인",
      "핀/sub 승리 방식",
    ],
  },
  "stand-and-deliver": {
    slug: "stand-and-deliver",
    tagline: "NXT의 가장 큰 밤, 다음 세대가 메인 이벤트를 채운다",
    layout: "nxt",
    signatureLabel: "NXT 타이틀 매치",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-violet-950/15 via-transparent to-transparent",
      accent: "text-violet-300",
      accentMuted: "text-violet-200/70",
      border: "border-violet-600/45",
      badge: "bg-violet-900/35 text-violet-100 ring-violet-500/35",
      glow: "shadow-[0_0_75px_-20px_rgba(139,92,246,0.45)]",
    },
    highlights: [
      { title: "NXT 챔피언십", detail: "브랜드의 최고 타이틀 방어" },
      { title: "스테이블 클래시", detail: "팀 대 팀 스토리라인 정리" },
      { title: "메인 로스터 이동", detail: "승진·콜업 서사의 분기점" },
    ],
    predictionFocus: ["NXT 챔피언 방어", "태그/여성 타이틀", "콜업 각성"],
  },
  wrestlemania: {
    slug: "wrestlemania",
    tagline: "스포츠 엔터테인먼트의 슈퍼볼",
    layout: "mania",
    signatureLabel: "WrestleMania 카드",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-amber-950/15 via-transparent to-transparent",
      accent: "text-fuchsia-200",
      accentMuted: "text-violet-200/75",
      border: "border-fuchsia-500/40",
      badge: "bg-fuchsia-950/50 text-fuchsia-100 ring-fuchsia-500/35",
      glow: "shadow-[0_0_100px_-15px_rgba(217,70,239,0.4)]",
    },
    highlights: [
      { title: "2박 구성", detail: "Night 1·2로 나뉘는 대형 카드" },
      { title: "최고 대접", detail: "입장·세트·스토리텔링이 시즌 최고조" },
      { title: "레전드 복귀", detail: "깜짝 등장과 스토리 마무리의 무대" },
    ],
    predictionFocus: [
      "메인 이벤트 승자",
      "스틸 케이지/노 DQ",
      "서프라이즈 등장",
      "챔피언십 변동",
    ],
  },
  backlash: {
    slug: "backlash",
    tagline: "WrestleMania 여파, 즉각적인 리벤지와 새 라이벌",
    layout: "fallout",
    signatureLabel: "백래시 카드",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-red-950/15 via-transparent to-transparent",
      accent: "text-red-300",
      accentMuted: "text-red-200/65",
      border: "border-red-700/45",
      badge: "bg-red-950/45 text-red-100 ring-red-600/35",
      glow: "shadow-[0_0_70px_-22px_rgba(239,68,68,0.35)]",
    },
    highlights: [
      { title: "리매치", detail: "Mania 직후 챔피언·도전자 재대결" },
      { title: "분노의 연장", detail: "노 DQ·스틸 케이지로 격화" },
      { title: "새 각", detail: "다음 PLE로 이어질 페우드 시드" },
    ],
    predictionFocus: ["리매치 승자", "DQ/개입 여부", "다음 PLE 주선"],
  },
  "money-in-the-bank": {
    slug: "money-in-the-bank",
    tagline: "서류가방 하나가 시즌 전체를 뒤흔든다",
    layout: "ladder",
    signatureLabel: "머니 인 더 뱅크 래더",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-emerald-950/15 via-transparent to-transparent",
      accent: "text-emerald-300",
      accentMuted: "text-emerald-200/70",
      border: "border-emerald-600/45",
      badge: "bg-emerald-950/45 text-emerald-100 ring-emerald-500/35",
      glow: "shadow-[0_0_75px_-18px_rgba(52,211,153,0.35)]",
    },
    highlights: [
      { title: "남·여 래더", detail: "서류가방을 걸고 다인 래더 매치" },
      { title: "언제든 도전", detail: "12개월 내 원하는 PLE·쇼에서 캐시 인" },
      { title: "캐시 인 타이밍", detail: "스토리의 최대 반전 카드" },
    ],
    predictionFocus: ["MITB 우승자", "캐시 인 시점 예상", "성공·실패"],
  },
  "king-queen-of-the-ring": {
    slug: "king-queen-of-the-ring",
    tagline: "왕관을 쓴 자는 한 시즌 내내 스포트라이트",
    layout: "tournament",
    signatureLabel: "킹 & 퀸 토너먼트",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-yellow-950/15 via-transparent to-transparent",
      accent: "text-yellow-200",
      accentMuted: "text-amber-200/65",
      border: "border-yellow-700/40",
      badge: "bg-yellow-950/40 text-yellow-100 ring-yellow-600/30",
      glow: "shadow-[0_0_70px_-20px_rgba(234,179,8,0.3)]",
    },
    highlights: [
      { title: "싱글 토너먼트", detail: "남·여 각각 브래킷으로 우승자 결정" },
      { title: "왕·여왕 각", detail: "의상·입장·스토리 권한이 부여됨" },
      { title: "중세 테마", detail: "대관식 연출과 특별 매치" },
    ],
    predictionFocus: ["킹 우승", "퀸 우승", "결승 조합", "준결승 이변"],
  },
  summerslam: {
    slug: "summerslam",
    tagline: "여름의 Big 4, 라이벌의 정면 충돌",
    layout: "summer",
    signatureLabel: "SummerSlam 메인 카드",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-orange-950/15 via-transparent to-transparent",
      accent: "text-orange-300",
      accentMuted: "text-orange-200/70",
      border: "border-orange-600/45",
      badge: "bg-orange-950/45 text-orange-100 ring-orange-500/35",
      glow: "shadow-[0_0_80px_-18px_rgba(251,146,60,0.38)]",
    },
    highlights: [
      { title: "여름 최대 PLE", detail: "챔피언십·라이벌 정리의 중간 결산" },
      { title: "2박 가능", detail: "대형 로스터 전원 투입 카드" },
      { title: "WM 복선", detail: "다음 WrestleMania 각을 심기도 함" },
    ],
    predictionFocus: ["메인 이벤트", "챔피언 방어", "서프라이즈 결과"],
  },
  "clash-in-italy": {
    slug: "clash-in-italy",
    tagline: "이탈리아의 밤, 유럽 팬과 함께하는 스펙터클",
    layout: "international",
    signatureLabel: "Clash in Italy",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-emerald-950/15 via-transparent to-transparent",
      accent: "text-emerald-300",
      accentMuted: "text-emerald-200/70",
      border: "border-emerald-600/40",
      badge: "bg-emerald-950/40 text-emerald-100 ring-emerald-500/35",
      glow: "shadow-[0_0_70px_-20px_rgba(52,211,153,0.32)]",
    },
    highlights: [
      {
        title: "Undisputed WWE Championship",
        detail: "Cody Rhodes (c) vs Gunther",
      },
      {
        title: "WHC Tribal Combat",
        detail: "Roman Reigns (c) vs Jacob Fatu",
      },
      {
        title: "WWE Women's Championship",
        detail: "Rhea Ripley (c) vs Jade Cargill",
      },
      {
        title: "Women's Intercontinental Championship",
        detail: "Becky Lynch (c) vs Sol Ruca — SNME XLIV에서 성사",
      },
      {
        title: "WrestleMania 42 리매치",
        detail: "Brock Lesnar vs Oba Femi",
      },
    ],
    predictionFocus: [
      "Undisputed·WHC 방어",
      "여자 챔피언십 2장",
      "레스너·페미 리매치",
    ],
  },
  "night-of-champions": {
    slug: "night-of-champions",
    tagline: "모든 챔피언이 한 밤에 타이틀을 건다",
    layout: "fallout",
    signatureLabel: "Night of Champions",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-amber-950/15 via-transparent to-transparent",
      accent: "text-amber-300",
      accentMuted: "text-amber-200/70",
      border: "border-amber-600/45",
      badge: "bg-amber-950/45 text-amber-100 ring-amber-500/35",
      glow: "shadow-[0_0_75px_-18px_rgba(251,191,36,0.35)]",
    },
    highlights: [
      {
        title: "Undisputed 트리플 스렛",
        detail: "Cody Rhodes (c) vs Gunther vs Sami Zayn",
      },
      {
        title: "킹 & 퀸 결승",
        detail: "Jey Uso vs Oba Femi / IYO SKY vs Liv Morgan",
      },
      { title: "스틸 케이지", detail: "Seth Rollins vs Bron Breakker" },
    ],
    predictionFocus: [
      "Undisputed 챔피언 방어",
      "킹·퀸 우승자",
      "여자 US 타이틀 변동",
      "케이지 매치 승자",
    ],
  },
  "bad-blood": {
    slug: "bad-blood",
    tagline: "헬 인 어 셀만이 남길 수 있는 결말",
    layout: "cell",
    signatureLabel: "Hell in a Cell",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-red-950/15 via-transparent to-transparent",
      accent: "text-red-400",
      accentMuted: "text-red-300/60",
      border: "border-red-800/50",
      badge: "bg-red-950/55 text-red-100 ring-red-700/40",
      glow: "shadow-[0_0_90px_-15px_rgba(185,28,28,0.45)]",
    },
    highlights: [
      { title: "철장 구조", detail: "천장·벽·바닥이 닫힌 셀 매치" },
      { title: "무기 사용", detail: "테이블·사다리·체인 등 규칙 완화" },
      { title: "페우드 종결", detail: "오랜 라이벌의 클라이맥스용" },
    ],
    predictionFocus: ["셀 매치 승자", "테이블/체인 사용", "개입·DQ"],
  },
  "survivor-series": {
    slug: "survivor-series",
    tagline: "팀 대 팀, 생존과 브랜드 우위가 걸린 11월",
    layout: "teams",
    signatureLabel: "서바이버 시리즈",
    theme: {
      pageBg: "bg-[#0a0a0c]",
      heroGradient: "from-blue-950/15 via-transparent to-transparent",
      accent: "text-blue-300",
      accentMuted: "text-red-200/65",
      border: "border-blue-600/35",
      badge:
        "bg-gradient-to-r from-blue-950/50 to-red-950/50 text-stone-100 ring-stone-500/30",
      glow: "shadow-[0_0_80px_-20px_rgba(59,130,246,0.3)]",
    },
    highlights: [
      { title: "5 vs 5", detail: "태그 제거 방식 서바이버 매치" },
      { title: "브랜드 대전", detail: "Raw·SmackDown 우위가 갈림" },
      { title: "시즌 마무리", detail: "연말 스토리와 WM 시드" },
    ],
    predictionFocus: [
      "서바이버 승리 팀",
      "최후 1인",
      "브랜드 우위",
      "챔피언 방어",
    ],
  },
};

export function getPleDetailBySlug(slug: string): PleEventDetail | undefined {
  return PLE_EVENT_DETAILS[slug as PleSlug];
}
