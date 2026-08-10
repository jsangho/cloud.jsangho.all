"use client";

import { useCallback, useEffect, useState } from "react";
import { BeltList } from "@/components/career-belt";
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
  readNews,
  readPresets,
  retireRun,
  startGuestRun,
  startRun,
  type CareerAdvance,
  type CareerMode,
  type CareerModeCode,
  type CareerPreset,
  type CareerNewsItem,
  type CareerNewsPage,
  type CareerStats,
  type CareerWeek,
  type GuestRunState,
} from "@/lib/career-api";

const GUEST_SAVE_KEY = "kayfabe.career.guest";

/** 프리셋 없이 만들 때 골라야 하는 값들. **넷을 다 주지 않으면 도메인이 거절한다.** */
const GENDERS = [
  { value: "male", label: "남성부" },
  { value: "female", label: "여성부" },
] as const;

const COUNTRIES = [
  ["KR", "한국"],
  ["US", "미국"],
  ["CA", "캐나다"],
  ["MX", "멕시코"],
  ["GB", "영국"],
  ["IE", "아일랜드"],
  ["DE", "독일"],
  ["FR", "프랑스"],
  ["ES", "스페인"],
  ["IT", "이탈리아"],
  ["PL", "폴란드"],
  ["SE", "스웨덴"],
  ["RU", "러시아"],
  ["GR", "그리스"],
  ["JP", "일본"],
  ["BR", "브라질"],
  ["AR", "아르헨티나"],
  ["CL", "칠레"],
  ["CO", "콜롬비아"],
  ["PR", "푸에르토리코"],
  ["DO", "도미니카"],
  ["AU", "호주"],
  ["NZ", "뉴질랜드"],
  ["TO", "통가"],
  ["FJ", "피지"],
  ["OTHER", "기타"],
] as const;

/** 경기 유형 21종 — 백엔드 `play_styles.KOREAN_STYLE_NAMES`와 같은 표다. */
const PLAY_STYLES = [
  ["technician", "테크니션"],
  ["submissions", "서브미션"],
  ["shooter", "슈터"],
  ["uwf", "U계"],
  ["powerhouse", "파워하우스"],
  ["giant", "자이언트"],
  ["monster", "몬스터"],
  ["high_flyer", "하이 플라이어"],
  ["lucha_libre", "루차 리브레"],
  ["stuntman", "스턴트맨"],
  ["brawler", "브롤러"],
  ["hard_hitting", "하드 히팅"],
  ["strong_style", "스트롱 스타일"],
  ["kings_road", "왕도 스타일"],
  ["showman", "쇼맨"],
  ["heel_style", "힐 스타일"],
  ["old_school", "올드스쿨"],
  ["showgirl", "쇼걸"],
  ["hardcore", "하드코어"],
  ["all_rounder", "올라운더"],
  ["underdog", "언더독"],
] as const;

const RESULT_LABELS: Record<string, string> = {
  win: "승",
  loss: "패",
  draw: "무",
  none: "—",
};

/** 승패는 색으로 먼저 읽힌다. 레드는 LIVE 전용이라(§7) 패배에 쓰지 않는다. */
const RESULT_TONE: Record<string, string> = {
  win: "text-brand-link",
  loss: "text-muted-foreground",
  draw: "text-muted-foreground",
  none: "text-muted-foreground/50",
};

const WEEK_KINDS: Record<string, string> = {
  weekly_show: "주간 방송",
  promo: "프로모",
  ple: "대회",
  special: "특별 방송",
  off: "결장",
};

/** 좌측 메뉴 — FM의 사이드바 자리다. 화면을 나누는 것이 이 개정의 뼈대다. */
const PANELS = [
  { key: "profile", label: "프로필" },
  { key: "schedule", label: "일정" },
  { key: "rivalries", label: "대립" },
  { key: "belts", label: "벨트" },
  { key: "inbox", label: "인박스" },
] as const;

type PanelKey = (typeof PANELS)[number]["key"];

/** 뉴스 한 줄의 성격 → 화면 라벨. 백엔드 `news_feed.NewsKind`와 같은 표다. */
const NEWS_KINDS: Record<string, string> = {
  title_won: "대관",
  title_lost: "벨트 상실",
  injury: "부상",
  call_up: "콜업",
  big_win: "대회 승리",
  cursed: "저주",
  team: "팀",
};

/** 군중 반응 → 색. 환호·구호만 띄우고 나머지는 죽인다 (DESIGN.md §7). */
const MOOD_TONE: Record<string, string> = {
  roar: "text-brand-link",
  chant: "text-brand-link",
  jeer: "text-muted-foreground",
  split: "text-muted-foreground",
  hush: "text-muted-foreground/70",
};

const END_REASONS: Record<string, string> = {
  age_50: "50세 만기",
  player: "스스로 은퇴",
  injury: "중대 부상",
  released: "방출",
};

const RIVALRY_STAGES: Record<string, string> = {
  taunt: "도발",
  feud: "대립",
  betrayal: "배신",
  revenge: "복수",
  blowoff: "결착",
};

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
  | { phase: "detail"; error?: string }
  | { phase: "play"; advance: CareerAdvance; state: GuestRunState | null; busy: boolean };

/** 내 선수를 만들 두 갈래 (2026-08-10 사용자 요청). */
type Origin = "custom" | "real";

type Draft = {
  origin: Origin;
  name: string;
  mode: CareerModeCode;
  basedOn: string;
  gender: "male" | "female";
  country: string;
  playStyle: string;
};

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
  const [tab, setTab] = useState<PanelKey>("schedule");
  const [inbox, setInbox] = useState<CareerNewsPage | null>(null);
  const [draft, setDraft] = useState<Draft>({
    origin: "custom",
    name: "",
    mode: "quarterly",
    basedOn: "",
    gender: "male",
    country: "KR",
    playStyle: "all_rounder",
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

  // 인박스를 열 때만 읽는다. 30년치를 진행할 때마다 따라 받으면 낭비다.
  const runId = screen.phase === "play" ? screen.advance.run.id : null;
  useEffect(() => {
    if (tab !== "inbox" || runId === null) return;
    let alive = true;
    readNews(runId, 0, 200)
      .then((page) => alive && setInbox(page))
      .catch(() => alive && setInbox(null));
    return () => {
      alive = false;
    };
  }, [tab, runId, screen]);

  const handleStart = useCallback(async () => {
    setScreen({ phase: draft.basedOn ? "create" : "detail" });
    try {
      const input = {
        name: draft.name.trim(),
        mode: draft.mode,
        ...(draft.basedOn
          ? { basedOn: draft.basedOn }
          : {
              gender: draft.gender,
              country: draft.country,
              playStyle: draft.playStyle,
            }),
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
      setScreen({ phase: draft.basedOn ? "create" : "detail", error: message });
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
          onClick={() =>
            draft.origin === "custom" ? setScreen({ phase: "detail" }) : void handleStart()
          }
          className="mt-8 h-11 w-full rounded-full text-base font-semibold sm:w-auto sm:px-10"
        >
          {draft.origin === "custom" ? "다음" : "커리어 시작"}
        </Button>

        <p className="mt-10 text-xs text-muted-foreground">{DISCLAIMER_INTRO}</p>
      </main>
    );
  }

  if (screen.phase === "detail") {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 py-10">
        <p className="font-sport text-xs tracking-[0.3em] text-brand-link">STEP 2 / 2</p>
        <h1 className="font-sport mt-1 text-4xl leading-none font-semibold sm:text-5xl">
          {draft.name.trim()}
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          디비전과 국적, 경기 유형을 정합니다. 셋 다 게임에 영향을 줍니다 — 국적은 전용 사건을, 경기
          유형은 경기력의 구성과 부상 위험을 바꿉니다.
        </p>

        <section className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <label htmlFor="gender" className="text-sm">
              디비전
            </label>
            <select
              id="gender"
              value={draft.gender}
              onChange={(e) =>
                setDraft((d) => ({ ...d, gender: e.target.value as "male" | "female" }))
              }
              className="h-10 w-full rounded-lg bg-card px-3 text-sm ring-1 ring-stone-300/70 ring-inset outline-none dark:ring-stone-700/70"
            >
              {GENDERS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="country" className="text-sm">
              국적
            </label>
            <select
              id="country"
              value={draft.country}
              onChange={(e) => setDraft((d) => ({ ...d, country: e.target.value }))}
              className="h-10 w-full rounded-lg bg-card px-3 text-sm ring-1 ring-stone-300/70 ring-inset outline-none dark:ring-stone-700/70"
            >
              {COUNTRIES.map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="play-style" className="text-sm">
              경기 유형
            </label>
            <select
              id="play-style"
              value={draft.playStyle}
              onChange={(e) => setDraft((d) => ({ ...d, playStyle: e.target.value }))}
              className="h-10 w-full rounded-lg bg-card px-3 text-sm ring-1 ring-stone-300/70 ring-inset outline-none dark:ring-stone-700/70"
            >
              {PLAY_STYLES.map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </section>

        {screen.error && <p className="mt-6 text-sm text-live">{screen.error}</p>}

        <div className="mt-8 flex flex-wrap gap-2">
          <Button
            type="button"
            onClick={() => void handleStart()}
            className="h-11 rounded-full px-10 text-base font-semibold"
          >
            커리어 시작
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-11 rounded-full px-6"
            onClick={() => setScreen({ phase: "create" })}
          >
            뒤로
          </Button>
        </div>

        <p className="mt-10 text-xs text-muted-foreground">{DISCLAIMER_INTRO}</p>
      </main>
    );
  }

  const { advance, busy } = screen;
  const { run: view, weeks, pendingEvent } = advance;
  const ended = advance.stopReason === "ended";
  const blocked = pendingEvent !== null;

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-6">
      {/* Continue 바 — 화면이 무엇이든 '다음'은 늘 같은 자리에 있다. FM의 구조에서
          가장 먼저 가져올 것이 이것이다: 진행이 메뉴에 묻히지 않는다. */}
      <div className="sticky top-16 z-30 -mx-4 mb-4 border-b border-stone-200/70 bg-background/95 px-4 py-3 backdrop-blur dark:border-white/10">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="font-sport text-lg leading-none">
            {view.year}년차 <span className="text-muted-foreground">·</span> {view.age}세
          </span>
          <span className="text-xs text-muted-foreground">
            {view.brand.toUpperCase()}
            {view.team && ` · ${view.team.label}`}
            {view.condition !== "healthy" && " · 부상"}
          </span>
          <div className="ml-auto flex items-center gap-2">
            {blocked ? (
              <span className="text-xs text-brand-link">선택을 기다리는 중</span>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busy || ended}
                onClick={handleNext}
                className="min-w-24"
              >
                {busy ? "진행 중…" : ended ? "종료됨" : "다음"}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleRetire}
              className="text-muted-foreground"
            >
              {ended ? "새 커리어" : "은퇴"}
            </Button>
          </div>
        </div>
      </div>

      {/* 대기 이벤트는 어느 화면에 있든 위로 올라온다 — 답하기 전에는 진행이 막힌다. */}
      {pendingEvent && (
        <section className="mb-6 rounded-lg bg-card p-4 ring-1 ring-brand-400/40 ring-inset">
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
      )}

      <div className="grid gap-6 lg:grid-cols-[10rem_1fr]">
        <nav aria-label="커리어 메뉴" className="flex gap-1.5 overflow-x-auto lg:flex-col">
          {PANELS.map((panel) => (
            <button
              key={panel.key}
              type="button"
              aria-current={tab === panel.key ? "page" : undefined}
              onClick={() => setTab(panel.key)}
              className={cn(
                "shrink-0 rounded-[4px] px-3 py-2 text-left text-sm transition-colors duration-[120ms]",
                tab === panel.key
                  ? "bg-card text-foreground ring-1 ring-brand-400/60 ring-inset"
                  : "text-muted-foreground hover:bg-card hover:text-foreground",
              )}
            >
              {panel.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0">
          {tab === "profile" && (
            <section className="space-y-4">
              <StatGrid stats={view.stats} />
              {view.team && (
                <p className="text-sm">
                  <span className="text-muted-foreground">소속 팀 </span>
                  {view.team.label}
                  <span className="text-muted-foreground"> · {view.team.members.join(" · ")}</span>
                </p>
              )}
              {ended && (
                <p className="text-sm">
                  커리어가 끝났습니다
                  {view.endReason ? ` · ${END_REASONS[view.endReason] ?? view.endReason}` : ""}.
                </p>
              )}
            </section>
          )}

          {tab === "schedule" && (
            <section className="space-y-6">
              {weeks.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  아직 진행한 주차가 없습니다. 위의 &lsquo;다음&rsquo;을 누르세요.
                </p>
              ) : (
                groupByTick(weeks, view.year).map((chunk) => (
                  <div key={chunk.from}>
                    <div className="flex items-baseline gap-2 border-b border-stone-300/60 pb-1 dark:border-stone-700/60">
                      <span className="font-sport text-sm">{chunk.label}</span>
                      <span className="text-xs text-muted-foreground">{chunk.weeks.length}주</span>
                      {chunk.record && (
                        <span className="ml-auto text-xs text-muted-foreground">
                          {chunk.record}
                        </span>
                      )}
                    </div>
                    <div className="mt-2">
                      {chunk.weeks.map((week) => (
                        <div
                          key={week.week}
                          className="grid grid-cols-[4.5rem_2.5rem_1fr] items-baseline gap-x-2 gap-y-0.5 border-b border-stone-200/40 py-1.5 sm:grid-cols-[5rem_2.5rem_9rem_1fr] dark:border-stone-800/60"
                        >
                          <span className="text-xs text-muted-foreground">
                            {week.month}월 {week.weekOfMonth}주
                          </span>
                          <span
                            className={cn(
                              "text-xs font-semibold",
                              RESULT_TONE[week.result ?? "none"],
                            )}
                          >
                            {RESULT_LABELS[week.result ?? "none"]}
                          </span>
                          <span className="truncate text-sm">
                            {week.opponent && week.result ? (
                              <>
                                <span className="text-muted-foreground">vs </span>
                                {week.opponent}
                              </>
                            ) : (
                              <span className="text-muted-foreground">{WEEK_KINDS[week.kind]}</span>
                            )}
                          </span>
                          <p
                            className={cn(
                              "col-span-3 text-sm leading-relaxed sm:col-span-1",
                              week.cursed && "text-muted-foreground",
                            )}
                          >
                            {week.titleAtStake && (
                              <span className="mr-1.5 text-xs text-brand-link">타이틀전</span>
                            )}
                            {week.narration}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </section>
          )}

          {tab === "rivalries" && (
            <section>
              {view.rivalries.length === 0 ? (
                <p className="text-sm text-muted-foreground">진행 중인 대립이 없습니다.</p>
              ) : (
                <div className="space-y-2">
                  {view.rivalries.map((r) => (
                    <div
                      key={r.rival}
                      className="flex items-baseline gap-3 rounded-[4px] bg-card px-3 py-2"
                    >
                      <span className="text-sm">{r.rival}</span>
                      <span className="text-xs text-brand-link">
                        {RIVALRY_STAGES[r.stage] ?? r.stage}
                      </span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {Math.floor((r.startedWeek - 1) / 52) + 1}년차부터
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === "inbox" && (
            <section>
              {runId === null ? (
                <p className="text-sm text-muted-foreground">
                  체험판은 인박스를 남기지 않습니다. 로그인하면 세계선의 사건이 쌓입니다.
                </p>
              ) : inbox === null || inbox.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">아직 남을 만한 사건이 없습니다.</p>
              ) : (
                <div className="space-y-5">
                  {groupNewsByYear(inbox.items).map(([year, rows]) => (
                    <div key={year}>
                      <p className="font-sport border-b border-stone-300/60 pb-1 text-sm dark:border-stone-700/60">
                        {year}년차
                      </p>
                      <ul className="mt-2 space-y-2">
                        {rows.map((item) => (
                          <li
                            key={`${item.week}-${item.headline}`}
                            className="grid grid-cols-[4.5rem_1fr] gap-x-3 border-b border-stone-200/40 pb-2 dark:border-stone-800/60"
                          >
                            <span className="text-xs text-muted-foreground">
                              {item.month}월 {item.weekOfMonth}주
                            </span>
                            <div className="min-w-0">
                              <p className="text-sm">
                                <span className="mr-1.5 text-xs text-muted-foreground">
                                  {NEWS_KINDS[item.kind] ?? item.kind}
                                </span>
                                {item.headline}
                              </p>
                              <p className={cn("mt-0.5 text-xs", MOOD_TONE[item.mood])}>
                                {item.crowdLine}
                              </p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === "belts" && (
            <section>
              {view.titlesWon.length === 0 ? (
                <p className="text-sm text-muted-foreground">아직 감은 벨트가 없습니다.</p>
              ) : (
                <BeltList codes={view.titlesWon} held={view.titlesHeld} />
              )}
            </section>
          )}
        </div>
      </div>

      {/* 실존 이름이 실제로 박히는 곳이 로그다. 캡처·공유되므로 상시 노출한다 (§3-D13). */}
      <p className="mt-10 text-xs text-muted-foreground">이 게임의 전개는 가상입니다.</p>
    </main>
  );
}

/** 인박스도 해 단위로 묶는다 — 일정과 같은 눈금이라야 서로 대조가 된다. */
function groupNewsByYear(items: CareerNewsItem[]): [number, CareerNewsItem[]][] {
  const years = new Map<number, CareerNewsItem[]>();
  for (const item of items) {
    const bucket = years.get(item.year);
    if (bucket) bucket.push(item);
    else years.set(item.year, [item]);
  }
  return [...years.entries()].sort((a, b) => a[0] - b[0]);
}

type Chunk = {
  from: number;
  to: number;
  label: string;
  record: string;
  weeks: CareerWeek[];
};

/**
 * 주차 로그를 **해 단위로** 묶는다.
 *
 * 한 번의 '다음'이 이벤트를 만날 때까지 여러 주를 흘려보내므로(§3-D17), 평평하게
 * 늘어놓으면 어디까지가 이번 턴인지 알 수 없다. 틱 경계가 아니라 **연차**로 나누는
 * 이유: 틱 크기는 모드마다 1~52주로 달라 `weekly`에서는 묶음이 한 줄짜리가 되고,
 * 사람이 커리어를 기억하는 단위는 어차피 해다.
 */
function groupByTick(weeks: CareerWeek[], _year: number): Chunk[] {
  const chunks = new Map<number, CareerWeek[]>();
  for (const week of weeks) {
    const year = Math.floor((week.week - 1) / 52) + 1;
    const bucket = chunks.get(year);
    if (bucket) bucket.push(week);
    else chunks.set(year, [week]);
  }
  return [...chunks.entries()].map(([year, rows]) => {
    const wins = rows.filter((w) => w.result === "win").length;
    const losses = rows.filter((w) => w.result === "loss").length;
    const draws = rows.filter((w) => w.result === "draw").length;
    const played = wins + losses + draws;
    return {
      from: rows[0].week,
      to: rows[rows.length - 1].week,
      label: `${year}년차`,
      record: played > 0 ? `${wins}승 ${losses}패${draws > 0 ? ` ${draws}무` : ""}` : "",
      weeks: rows,
    };
  });
}

/** FM의 속성 격자. 값이 아니라 **관계**가 읽혀야 해서 라벨과 숫자를 붙여 둔다. */
function StatGrid({ stats }: { stats: CareerStats }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        <Stat label="인기도" value={stats.popularity} />
        <Stat label="마이크웍" value={stats.micWork} />
        <Stat label="평판" value={stats.backstage} />
        <Stat label="성향" value={stats.alignment} />
        <Stat label="마모" value={stats.wear} />
      </div>
      <div>
        <div className="flex items-baseline justify-between border-b border-stone-300/60 pb-1 text-sm dark:border-stone-700/60">
          <span>
            경기력
            <span className="ml-2 text-xs text-muted-foreground">{stats.playStyleLabel}</span>
          </span>
          <span className="font-sport text-lg leading-none">{stats.inRing}</span>
        </div>
        <div className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
          {stats.skills.map((skill) => (
            <Stat key={skill.name} label={skill.name} value={skill.value} />
          ))}
        </div>
      </div>
    </div>
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
