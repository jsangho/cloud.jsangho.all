"use client";

const TICKER_ITEMS = [
  "🔥 실시간 대세 예측 · Royal Rumble 우승자 58% Cody Rhodes",
  "👑 WWE Undisputed · Roman Reigns 127일 방어 중",
  "⚡ Elimination Chamber · 팬 픽 1위 Seth Rollins",
  "🏆 WrestleMania 42 · 라스베이거스 메인 이벤트 D-Day 카운트다운",
  "📊 KayFabe 순위표 · 이번 주 Head of the Table 경쟁 치열",
  "🎯 SummerSlam 2 Nights · 미니애폴리스 아레나 예매 오픈 예정",
] as const;

export function WweTicker() {
  const track = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div
      className="wwe-ticker border-t border-stone-200 dark:border-white/5 bg-stone-100/80 dark:bg-black/40"
      aria-label="실시간 WWE 정보"
    >
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-1.5">
        <span className="shrink-0 rounded border border-red-500/40 bg-red-100 dark:bg-red-950/50 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-widest text-red-600 dark:text-red-400">
          Live
        </span>
        <div className="relative min-w-0 flex-1 overflow-hidden">
          <div className="wwe-ticker-track flex w-max gap-10 whitespace-nowrap">
            {track.map((item, i) => (
              <span
                key={`${item}-${i}`}
                className="text-xs font-semibold tracking-wide text-stone-500 dark:text-stone-400"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
