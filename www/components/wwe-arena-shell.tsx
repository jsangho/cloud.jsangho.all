import type { ReactNode } from "react";

/** 네온 톤 다크 아레나 배경 — 링 주변·상단 레드 글로우 */
export function WweArenaShell({ children }: { children: ReactNode }) {
  return (
    <main className="relative min-h-screen w-full min-w-0 overflow-x-hidden bg-white text-stone-900 dark:bg-[#0a0a0c] dark:text-stone-100">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_55%_45%_at_50%_-8%,rgba(224,32,32,0.22),transparent_68%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_40%_35%_at_50%_12%,rgba(224,32,32,0.1),transparent_62%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_0%_100%,rgba(120,20,20,0.12),transparent_58%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_65%_50%_at_100%_0%,rgba(87,30,30,0.1),transparent_52%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.03] bg-[repeating-linear-gradient(118deg,#fafaf9_0px,#fafaf9_1px,transparent_1px,transparent_24px)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-gradient-to-b dark:from-black/40 dark:via-transparent dark:to-black/80"
      />
      <div className="relative z-10">{children}</div>
    </main>
  );
}
