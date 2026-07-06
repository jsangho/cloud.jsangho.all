import type { PleSlug } from "@/lib/wwe-ple";

export type BracketSideStyle = {
  headerBg: string;
  headerText: string;
  border: string;
  nameText: string;
  selectedBg: string;
  voteBar: string;
};

export type PleBracketTheme = {
  sideA: BracketSideStyle;
  sideB: BracketSideStyle;
};

export const PLE_BRACKET_THEMES: Record<PleSlug, PleBracketTheme> = {
  "royal-rumble": {
    sideA: {
      headerBg: "bg-amber-600",
      headerText: "text-white",
      border: "border-amber-600",
      nameText: "text-amber-700",
      selectedBg: "bg-amber-50",
      voteBar: "bg-amber-500",
    },
    sideB: {
      headerBg: "bg-stone-700",
      headerText: "text-white",
      border: "border-stone-600",
      nameText: "text-stone-700",
      selectedBg: "bg-stone-100",
      voteBar: "bg-stone-500",
    },
  },
  "elimination-chamber": {
    sideA: {
      headerBg: "bg-zinc-500",
      headerText: "text-white",
      border: "border-zinc-500",
      nameText: "text-zinc-700",
      selectedBg: "bg-zinc-100",
      voteBar: "bg-zinc-500",
    },
    sideB: {
      headerBg: "bg-slate-800",
      headerText: "text-white",
      border: "border-slate-700",
      nameText: "text-slate-800",
      selectedBg: "bg-slate-100",
      voteBar: "bg-slate-600",
    },
  },
  "stand-and-deliver": {
    sideA: {
      headerBg: "bg-violet-600",
      headerText: "text-white",
      border: "border-violet-600",
      nameText: "text-violet-700",
      selectedBg: "bg-violet-50",
      voteBar: "bg-violet-500",
    },
    sideB: {
      headerBg: "bg-fuchsia-700",
      headerText: "text-white",
      border: "border-fuchsia-700",
      nameText: "text-fuchsia-800",
      selectedBg: "bg-fuchsia-50",
      voteBar: "bg-fuchsia-600",
    },
  },
  wrestlemania: {
    sideA: {
      headerBg: "bg-fuchsia-600",
      headerText: "text-white",
      border: "border-fuchsia-600",
      nameText: "text-fuchsia-700",
      selectedBg: "bg-fuchsia-50",
      voteBar: "bg-fuchsia-500",
    },
    sideB: {
      headerBg: "bg-violet-700",
      headerText: "text-white",
      border: "border-violet-700",
      nameText: "text-violet-800",
      selectedBg: "bg-violet-50",
      voteBar: "bg-violet-600",
    },
  },
  backlash: {
    sideA: {
      headerBg: "bg-red-600",
      headerText: "text-white",
      border: "border-red-600",
      nameText: "text-red-700",
      selectedBg: "bg-red-50",
      voteBar: "bg-red-500",
    },
    sideB: {
      headerBg: "bg-orange-600",
      headerText: "text-white",
      border: "border-orange-600",
      nameText: "text-orange-800",
      selectedBg: "bg-orange-50",
      voteBar: "bg-orange-500",
    },
  },
  "night-of-champions": {
    sideA: {
      headerBg: "bg-amber-600",
      headerText: "text-white",
      border: "border-amber-600",
      nameText: "text-amber-800",
      selectedBg: "bg-amber-50",
      voteBar: "bg-amber-500",
    },
    sideB: {
      headerBg: "bg-yellow-700",
      headerText: "text-white",
      border: "border-yellow-700",
      nameText: "text-yellow-900",
      selectedBg: "bg-yellow-50",
      voteBar: "bg-yellow-600",
    },
  },
  "money-in-the-bank": {
    sideA: {
      headerBg: "bg-emerald-600",
      headerText: "text-white",
      border: "border-emerald-600",
      nameText: "text-emerald-800",
      selectedBg: "bg-emerald-50",
      voteBar: "bg-emerald-500",
    },
    sideB: {
      headerBg: "bg-teal-700",
      headerText: "text-white",
      border: "border-teal-700",
      nameText: "text-teal-800",
      selectedBg: "bg-teal-50",
      voteBar: "bg-teal-600",
    },
  },
  "king-queen-of-the-ring": {
    sideA: {
      headerBg: "bg-yellow-600",
      headerText: "text-white",
      border: "border-yellow-600",
      nameText: "text-yellow-800",
      selectedBg: "bg-yellow-50",
      voteBar: "bg-yellow-500",
    },
    sideB: {
      headerBg: "bg-amber-700",
      headerText: "text-white",
      border: "border-amber-700",
      nameText: "text-amber-900",
      selectedBg: "bg-amber-50",
      voteBar: "bg-amber-600",
    },
  },
  summerslam: {
    sideA: {
      headerBg: "bg-orange-500",
      headerText: "text-white",
      border: "border-orange-500",
      nameText: "text-orange-700",
      selectedBg: "bg-orange-50",
      voteBar: "bg-orange-500",
    },
    sideB: {
      headerBg: "bg-red-600",
      headerText: "text-white",
      border: "border-red-600",
      nameText: "text-red-700",
      selectedBg: "bg-red-50",
      voteBar: "bg-red-500",
    },
  },
  "clash-in-italy": {
    sideA: {
      headerBg: "bg-sky-600",
      headerText: "text-white",
      border: "border-sky-600",
      nameText: "text-sky-800",
      selectedBg: "bg-sky-50",
      voteBar: "bg-sky-500",
    },
    sideB: {
      headerBg: "bg-emerald-700",
      headerText: "text-white",
      border: "border-emerald-700",
      nameText: "text-emerald-800",
      selectedBg: "bg-emerald-50",
      voteBar: "bg-emerald-600",
    },
  },
  "bad-blood": {
    sideA: {
      headerBg: "bg-red-700",
      headerText: "text-white",
      border: "border-red-700",
      nameText: "text-red-800",
      selectedBg: "bg-red-50",
      voteBar: "bg-red-600",
    },
    sideB: {
      headerBg: "bg-stone-900",
      headerText: "text-white",
      border: "border-stone-800",
      nameText: "text-stone-900",
      selectedBg: "bg-stone-100",
      voteBar: "bg-stone-700",
    },
  },
  "survivor-series": {
    sideA: {
      headerBg: "bg-blue-600",
      headerText: "text-white",
      border: "border-blue-600",
      nameText: "text-blue-700",
      selectedBg: "bg-blue-50",
      voteBar: "bg-blue-500",
    },
    sideB: {
      headerBg: "bg-red-600",
      headerText: "text-white",
      border: "border-red-600",
      nameText: "text-red-700",
      selectedBg: "bg-red-50",
      voteBar: "bg-red-500",
    },
  },
};

export function getBracketTheme(slug: PleSlug): PleBracketTheme {
  return PLE_BRACKET_THEMES[slug];
}
