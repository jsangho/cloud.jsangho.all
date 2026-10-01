import type { ReactNode } from "react";

/**
 * 아레나 배경 — **다크 전용 장치다.**
 *
 * 글로우 네 겹은 전부 근흑색(`#08090b`) 위에서 고른 레드인데, 라이트
 * 표면(`#f4f1ec`)에 그대로 얹히니 알파가 섞여 분홍 얼룩이 됐다. 색상만
 * 골드로 바꿔 봐도 이번엔 누렇게 떴다 — **밝은 표면 위의 저알파 워시는 어떤
 * 색이든 얼룩으로 읽힌다.** 알파를 낮추면 색이 없어지고 올리면 얼룩이 커져서
 * 빠져나갈 길이 없는 자리다. 게다가 레드는 LIVE·WWE 를 가리키는 뜻색이라
 * (DESIGN.md §색의 역할) 페이지 절반을 덮는 장식으로 쓰면 그 뜻이 닳는다.
 *
 * 그래서 라이트에서는 워시를 아예 걷었다. 라이트에 색을 주는 일은 `.arena-band`
 * 처럼 **경계가 또렷한 면**이 맡는다. 다크 값은 한 픽셀도 바뀌지 않았다.
 */
export function WweArenaShell({ children }: { children: ReactNode }) {
  return (
    // 표면은 토큰이 정한다 (KAYFABE 2.0) — 하드코딩된 `dark:bg-[#0a0a0c]`가
    // `--background`를 덮고 있어서 여기만 옛 값에 남아 있었다.
    <main className="relative min-h-screen w-full min-w-0 overflow-x-hidden bg-background text-foreground">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-[radial-gradient(ellipse_55%_45%_at_50%_-8%,rgba(224,32,32,0.22),transparent_68%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-[radial-gradient(ellipse_40%_35%_at_50%_12%,rgba(224,32,32,0.1),transparent_62%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-[radial-gradient(ellipse_70%_55%_at_0%_100%,rgba(120,20,20,0.12),transparent_58%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-[radial-gradient(ellipse_65%_50%_at_100%_0%,rgba(87,30,30,0.1),transparent_52%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:opacity-[0.03] dark:bg-[repeating-linear-gradient(118deg,#fafaf9_0px,#fafaf9_1px,transparent_1px,transparent_24px)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 dark:bg-gradient-to-b dark:from-black/40 dark:via-transparent dark:to-black/80"
      />
      <div className="relative z-10">{children}</div>
    </main>
  );
}
