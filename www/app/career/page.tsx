"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";
import {
  CareerApiError,
  advanceGuestRun,
  advanceRun,
  chooseEvent,
  chooseGuestEvent,
  readCurrentRun,
  readModes,
  readPresets,
  retireRun,
  startGuestRun,
  startRun,
  type CareerAdvance,
  type CareerMode,
  type CareerModeCode,
  type CareerPreset,
  type GuestRunState,
} from "@/lib/career-api";

const GUEST_SAVE_KEY = "kayfabe.career.guest";

/** 모드 코드 → 화면 이름. 백엔드는 코드를 그대로 label로 준다. */
const MODE_LABELS: Record<CareerModeCode, string> = {
  yearly: "연 단위",
  quarterly: "분기",
  monthly: "월 단위",
  weekly: "주 단위",
};

const DISCLAIMER_INTRO = "이 게임의 선수명은 실존하지만, 모든 전개·경기·대사는 허구입니다.";

/** 화면이 가질 수 있는 상태. 불가능한 조합을 타입에서 지운다. */
type Screen =
  | { phase: "loading" }
  | { phase: "create"; error?: string }
  | { phase: "play"; advance: CareerAdvance; state: GuestRunState | null; busy: boolean };

/** 내 선수를 만들 두 갈래 (2026-08-10 사용자 요청). */
type Origin = "custom" | "real";

type Draft = { origin: Origin; name: string; mode: CareerModeCode; basedOn: string };

function readGuestSave(): GuestRunState | null {
  try {
    const raw = window.localStorage.getItem(GUEST_SAVE_KEY);
    return raw ? (JSON.parse(raw) as GuestRunState) : null;
  } catch {
    return null;
  }
}

function writeGuestSave(state: GuestRunState | null): void {
  try {
    if (state) window.localStorage.setItem(GUEST_SAVE_KEY, JSON.stringify(state));
    else window.localStorage.removeItem(GUEST_SAVE_KEY);
  } catch {
    // 사파리 프라이빗 모드 등에서 막힌다. 진행 자체는 계속할 수 있다.
  }
}

export default function CareerPage() {
  const { user, isReady } = useAuth();
  const [screen, setScreen] = useState<Screen>({ phase: "loading" });
  const [modes, setModes] = useState<CareerMode[]>([]);
  const [presets, setPresets] = useState<CareerPreset[]>([]);
  const [metaFailed, setMetaFailed] = useState(false);
  const [draft, setDraft] = useState<Draft>({
    origin: "custom",
    name: "",
    mode: "quarterly",
    basedOn: "",
  });

  useEffect(() => {
    let alive = true;
    Promise.all([readModes(), readPresets()])
      .then(([m, p]) => {
        if (!alive) return;
        setModes(m);
        setPresets(p);
      })
      .catch(() => alive && setMetaFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  // 로그인 여부가 정해진 뒤에 세이브를 찾는다 — 로그인은 서버, 체험판은 브라우저다.
  useEffect(() => {
    if (!isReady) return;
    let alive = true;
    if (user) {
      readCurrentRun()
        .then((found) => {
          if (!alive) return;
          setScreen(
            found
              ? { phase: "play", advance: found, state: null, busy: false }
              : { phase: "create" },
          );
        })
        .catch(() => alive && setScreen({ phase: "create" }));
      return () => {
        alive = false;
      };
    }
    const saved = readGuestSave();
    if (!saved) {
      setScreen({ phase: "create" });
      return;
    }
    advanceGuestRun(saved, "tick")
      .then((next) => {
        if (!alive) return;
        writeGuestSave(next.state);
        setScreen({ phase: "play", advance: next, state: next.state, busy: false });
      })
      .catch(() => {
        // 읽을 수 없는 세이브(포맷 변경·조작)는 버리고 새로 시작하게 둔다.
        writeGuestSave(null);
        if (alive) setScreen({ phase: "create" });
      });
    return () => {
      alive = false;
    };
  }, [isReady, user]);

  const allowedModes = user ? modes : modes.filter((m) => m.guestAllowed);

  const handleStart = useCallback(async () => {
    setScreen({ phase: "create" });
    try {
      const input = {
        name: draft.name.trim(),
        mode: draft.mode,
        ...(draft.basedOn ? { basedOn: draft.basedOn } : {}),
      };
      if (user) {
        const started = await startRun(input);
        setScreen({ phase: "play", advance: started, state: null, busy: false });
      } else {
        const started = await startGuestRun(input);
        writeGuestSave(started.state);
        setScreen({ phase: "play", advance: started, state: started.state, busy: false });
      }
    } catch (error) {
      const message =
        error instanceof CareerApiError ? error.message : "커리어를 시작하지 못했습니다.";
      setScreen({ phase: "create", error: message });
    }
  }, [draft, user]);

  const run = screen.phase === "play" ? screen.advance : null;

  const act = useCallback(
    async (work: () => Promise<CareerAdvance | (CareerAdvance & { state: GuestRunState })>) => {
      setScreen((s) => (s.phase === "play" ? { ...s, busy: true } : s));
      try {
        const next = await work();
        const state = "state" in next ? next.state : null;
        if (state) writeGuestSave(state);
        setScreen({ phase: "play", advance: next, state, busy: false });
      } catch {
        setScreen((s) => (s.phase === "play" ? { ...s, busy: false } : s));
      }
    },
    [],
  );

  function handleNext() {
    if (!run) return;
    const state = screen.phase === "play" ? screen.state : null;
    void act(() =>
      state ? advanceGuestRun(state, "auto") : advanceRun(run.run.id as number, "auto"),
    );
  }

  function handleChoose(code: string) {
    if (!run) return;
    const state = screen.phase === "play" ? screen.state : null;
    void act(() =>
      state ? chooseGuestEvent(state, code) : chooseEvent(run.run.id as number, code),
    );
  }

  function handleRetire() {
    if (!run?.run.id) {
      writeGuestSave(null);
      setScreen({ phase: "create" });
      return;
    }
    void act(() => retireRun(run.run.id as number));
  }

  if (screen.phase === "loading") {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-10 text-muted-foreground">
        불러오는 중…
      </main>
    );
  }

  if (screen.phase === "create") {
    const trimmed = draft.name.trim();
    const nameOk = trimmed.length >= 2 && trimmed.length <= 20;
    const ready = nameOk && (draft.origin === "custom" || draft.basedOn !== "");

    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-10">
        <p className="font-sport text-xs tracking-[0.3em] text-brand-link">CAREER MODE</p>
        <h1 className="font-sport mt-1 text-4xl leading-none font-semibold sm:text-5xl">
          커리어 시뮬레이터
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          스무 살에 데뷔해 서른 해. 멈추는 건 사건이 생겼을 때뿐이다.
        </p>

        {metaFailed && (
          <p className="mt-6 rounded-lg bg-card p-3 text-sm text-live">
            선수 목록과 진행 단위를 불러오지 못했습니다. 백엔드가 켜져 있는지 확인해 주세요.
          </p>
        )}

        {/* ① 두 갈래 — 실존 선수를 반드시 골라야 하는 것처럼 보이지 않게 나눈다. */}
        <div className="mt-8 grid grid-cols-2 gap-2">
          {(
            [
              { key: "custom", title: "나만의 선수", desc: "이름부터 새로 짓는다" },
              { key: "real", title: "실존 선수", desc: "그 선수의 커리어를 다시 쓴다" },
            ] as const
          ).map((option) => {
            const on = draft.origin === option.key;
            return (
              <button
                key={option.key}
                type="button"
                aria-pressed={on}
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    origin: option.key,
                    basedOn: option.key === "custom" ? "" : d.basedOn,
                    name: option.key === "custom" ? "" : d.name,
                  }))
                }
                className={cn(
                  "rounded-lg bg-card p-4 text-left transition-colors duration-[120ms]",
                  "ring-1 ring-inset ring-stone-300/70 dark:ring-stone-700/70",
                  on
                    ? "ring-2 ring-brand-400 dark:ring-brand-400"
                    : "hover:ring-stone-400 dark:hover:ring-stone-500",
                )}
              >
                <span className="font-sport block text-lg">{option.title}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{option.desc}</span>
              </button>
            );
          })}
        </div>

        {draft.origin === "real" && (
          <section className="mt-4 space-y-2">
            <label htmlFor="based-on" className="text-sm">
              누가 될까요
            </label>
            <select
              id="based-on"
              value={draft.basedOn}
              onChange={(e) => {
                const source = e.target.value;
                // 고른 순간 이름까지 그 선수의 것이 된다 (§3-D10-1 개정).
                setDraft((d) => ({ ...d, basedOn: source, name: source }));
              }}
              className="h-10 w-full rounded-lg bg-card px-3 text-sm ring-1 ring-stone-300/70 ring-inset outline-none dark:ring-stone-700/70"
            >
              <option value="">선수를 고르세요</option>
              {presets.map((preset) => (
                <option key={preset.source} value={preset.source}>
                  {preset.source} · {preset.playStyleLabel}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              성별·국적·경기 유형을 그대로 씁니다. 스무 살 데뷔 시점부터 다시 시작합니다.
            </p>
          </section>
        )}

        <section className="mt-4 space-y-2">
          <label htmlFor="ring-name" className="text-sm">
            링 네임
            {draft.origin === "real" && (
              <span className="text-muted-foreground"> (고쳐도 됩니다)</span>
            )}
          </label>
          <input
            id="ring-name"
            value={draft.name}
            onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
            maxLength={20}
            placeholder="2~20자"
            className="h-10 w-full rounded-lg bg-card px-3 text-sm ring-1 ring-stone-300/70 ring-inset outline-none focus:ring-brand-400 dark:ring-stone-700/70"
          />
        </section>

        {/* ② 모드는 갈래 선택 아래로 (사용자 요청). */}
        <section className="mt-6 space-y-2">
          <p className="text-sm">진행 단위</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {allowedModes.map((mode) => {
              const on = draft.mode === mode.code;
              return (
                <button
                  key={mode.code}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setDraft((d) => ({ ...d, mode: mode.code }))}
                  className={cn(
                    "rounded-lg bg-card px-3 py-2 text-center transition-colors duration-[120ms]",
                    "ring-1 ring-inset ring-stone-300/70 dark:ring-stone-700/70",
                    on
                      ? "ring-2 ring-brand-400 dark:ring-brand-400"
                      : "hover:ring-stone-400 dark:hover:ring-stone-500",
                  )}
                >
                  <span className="font-sport block text-base">{MODE_LABELS[mode.code]}</span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {mode.ticks}턴
                  </span>
                </button>
              );
            })}
          </div>
          {!user && (
            <p className="text-xs text-muted-foreground">
              긴 모드는 로그인 후 플레이할 수 있습니다. 체험판 진행은 이 브라우저에 저장됩니다.
            </p>
          )}
        </section>

        {screen.error && <p className="mt-6 text-sm text-live">{screen.error}</p>}

        {/* 이 화면의 유일한 액션이라 골드를 쓴다 (DESIGN.md §7). */}
        <Button
          type="button"
          disabled={!ready}
          onClick={() => void handleStart()}
          className="mt-8 h-11 w-full rounded-full text-base font-semibold sm:w-auto sm:px-10"
        >
          커리어 시작
        </Button>

        <p className="mt-10 text-xs text-muted-foreground">{DISCLAIMER_INTRO}</p>
      </main>
    );
  }

  const { advance, busy } = screen;
  const { run: view, weeks, pendingEvent } = advance;
  const ended = advance.stopReason === "ended";

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="font-sport text-2xl font-semibold">
          {view.year}년차 · {view.age}세
        </h1>
        <p className="text-sm text-muted-foreground">
          {view.brand.toUpperCase()}
          {view.team && ` · ${view.team.label}`}
        </p>
      </header>

      <section className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        <Stat label="인기도" value={view.stats.popularity} />
        <details className="group">
          <summary className="flex cursor-pointer list-none justify-between">
            <span className="text-muted-foreground">경기력</span>
            <span>{view.stats.inRing}</span>
          </summary>
          <ul className="mt-1 space-y-0.5 border-l border-stone-300/70 pl-2 text-xs text-muted-foreground dark:border-stone-600/70">
            {view.stats.skills.map((skill) => (
              <li key={skill.name} className="flex justify-between">
                <span>{skill.name}</span>
                <span>{skill.value}</span>
              </li>
            ))}
          </ul>
        </details>
        <Stat label="마이크웍" value={view.stats.micWork} />
        <Stat label="평판" value={view.stats.backstage} />
        <Stat label="성향" value={view.stats.alignment} />
        <Stat label="마모" value={view.stats.wear} />
      </section>

      {pendingEvent ? (
        <section className="mt-8 rounded-lg bg-card p-4">
          <h2 className="font-sport text-lg">{pendingEvent.title}</h2>
          <p className="mt-2 text-sm leading-relaxed">{pendingEvent.body}</p>
          <div className="mt-4 flex flex-col gap-1.5">
            {pendingEvent.choices.map((choice) => (
              <Button
                key={choice.code}
                type="button"
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => handleChoose(choice.code)}
                className="justify-start"
              >
                {choice.label}
              </Button>
            ))}
          </div>
        </section>
      ) : (
        <div className="mt-8 flex flex-wrap items-center gap-2">
          {/* '다음'에 골드를 쓰지 않는다 — 가장 많이 눌리는 버튼에 브랜드 액션 색을
              주면 그 색의 의미가 사라진다 (DESIGN.md §7). */}
          <Button type="button" variant="outline" disabled={busy || ended} onClick={handleNext}>
            {busy ? "진행 중…" : "다음"}
          </Button>
          {view.id !== null && (
            <Link href="/career/news" className="text-sm text-brand-link hover:underline">
              뉴스
            </Link>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={handleRetire}
          >
            {ended ? "새 커리어" : "은퇴"}
          </Button>
        </div>
      )}

      {ended && (
        <p className="mt-4 text-sm">
          커리어가 끝났습니다{view.endReason ? ` · ${view.endReason}` : ""}.
        </p>
      )}

      <section className="mt-8 space-y-2">
        {weeks.map((week) => (
          <p
            key={week.week}
            className={cn("text-sm leading-relaxed", week.cursed && "text-muted-foreground")}
          >
            <span className="mr-2 text-xs text-muted-foreground">{week.week}주</span>
            {week.narration}
          </p>
        ))}
      </section>

      {/* 실존 이름이 실제로 박히는 곳이 로그다. 캡처·공유되므로 상시 노출한다 (§3-D13). */}
      <p className="mt-10 text-xs text-muted-foreground">이 게임의 전개는 가상입니다.</p>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <p className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </p>
  );
}
