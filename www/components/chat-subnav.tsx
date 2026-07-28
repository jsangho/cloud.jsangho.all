"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/chat", label: "WWE" },
  { href: "/chat/langchain", label: "LangChain" },
] as const;

export function ChatSubnav({ active }: { active: "wwe" | "langchain" }) {
  return (
    <div className="mb-4 flex justify-center gap-2">
      {TABS.map((tab, idx) => {
        const isActive = (idx === 0 && active === "wwe") || (idx === 1 && active === "langchain");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "rounded-full border px-4 py-1.5 text-xs font-medium transition-colors",
              isActive
                ? "border-amber-400/70 bg-amber-500/15 text-amber-600 dark:text-amber-300"
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
