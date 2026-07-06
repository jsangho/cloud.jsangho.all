"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type WeatherState =
  | { status: "loading" }
  | { status: "ok"; emoji: string; temp: number; label: string; place: string }
  | { status: "error" };

/** OpenWeatherMap condition id → emoji */
function emojiFromOwmId(id: number): string {
  if (id >= 200 && id < 300) return "⛈️";
  if (id >= 300 && id < 400) return "🌦️";
  if (id >= 500 && id < 600) return "🌧️";
  if (id >= 600 && id < 700) return "❄️";
  if (id >= 700 && id < 800) return "🌫️";
  if (id === 800) return "☀️";
  if (id === 801) return "🌤️";
  if (id === 802) return "⛅";
  if (id >= 803) return "☁️";
  return "🌡️";
}

async function fetchSeoulWeather() {
  const res = await fetch(`${apiBaseUrl}/weather/seoul`);
  const raw = await res.text();
  let data: {
    city?: string;
    temp_c?: number;
    description?: string;
    condition_id?: number;
    detail?: string;
  } = {};
  try {
    data = JSON.parse(raw) as typeof data;
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    throw new Error(
      typeof data.detail === "string" ? data.detail : `weather ${res.status}`,
    );
  }
  if (data.temp_c == null || data.condition_id == null) {
    throw new Error("invalid weather payload");
  }
  return {
    temp: data.temp_c,
    id: data.condition_id,
    label: data.description ?? "날씨",
    place: data.city ?? "서울",
  };
}

export function WeatherWidget({ className }: { className?: string }) {
  const [weather, setWeather] = useState<WeatherState>({ status: "loading" });

  const load = useCallback(async () => {
    setWeather({ status: "loading" });
    try {
      const result = await fetchSeoulWeather();
      setWeather({
        status: "ok",
        emoji: emojiFromOwmId(result.id),
        temp: Math.round(result.temp),
        label: result.label,
        place: result.place,
      });
    } catch {
      setWeather({ status: "error" });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pillClass =
    "inline-flex min-h-8 items-center gap-1.5 rounded-md border border-stone-300/70 dark:border-stone-600/70 bg-stone-200/45 dark:bg-stone-800/45 px-2.5 py-1 text-sm text-stone-700 dark:text-stone-200";

  if (weather.status === "loading") {
    return (
      <div
        className={cn(pillClass, "text-stone-400", className)}
        aria-label="서울 날씨 불러오는 중"
      >
        <span aria-hidden>🌡️</span>
        <span className="text-xs">…</span>
      </div>
    );
  }

  if (weather.status === "error") {
    return (
      <button
        type="button"
        onClick={load}
        className={cn(
          pillClass,
          "cursor-pointer transition-colors hover:bg-stone-200/65 dark:hover:bg-stone-700/65 hover:text-stone-950 dark:hover:text-stone-50",
          className,
        )}
        title="서울 날씨를 불러오지 못했습니다. backend/.env 의 OPENWEATHER_API_KEY와 서버 실행을 확인하세요."
        aria-label="서울 날씨 다시 불러오기"
      >
        <span aria-hidden>🌡️</span>
        <span className="text-xs">—</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={load}
      className={cn(
        pillClass,
        "cursor-pointer transition-colors hover:bg-stone-700/65 hover:text-stone-50",
        className,
      )}
      title={`${weather.place} · ${weather.label} · ${weather.temp}°C (클릭 시 새로고침)`}
      aria-label={`${weather.place} 날씨 ${weather.label}, 기온 ${weather.temp}도`}
    >
      <span className="text-base leading-none" aria-hidden>
        {weather.emoji}
      </span>
      <span className="font-medium tabular-nums">{weather.temp}°</span>
    </button>
  );
}
