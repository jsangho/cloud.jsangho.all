"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/records", label: "선수 기록" },
  { href: "/records/champions", label: "챔피언" },
] as const;

export function RecordsSubnav({ active }: { active: "players" | "champions" }) {
  return (
    <div className="mb-6 flex justify-center gap-2">
      {TABS.map((tab, idx) => {
        const isActive = (idx === 0 && active === "players") || (idx === 1 && active === "champions");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "rounded-full border px-4 py-1.5 text-xs font-medium transition-colors",
              isActive
                ? "border-brand-400/70 bg-brand-500/15 text-brand-600 dark:text-brand-300"
                : "border-stone-300/60 dark:border-stone-700/60 bg-stone-100/40 dark:bg-stone-900/40 text-stone-600 dark:text-stone-300 hover:bg-stone-200/60 dark:hover:bg-stone-800/60",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
