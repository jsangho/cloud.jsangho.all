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
  readGuestReport,
  readLog,
  readReport,
  readModes,
  readNews,
  readGuestNews,
  readPresets,
  resumeGuestRun,
  retireRun,
  startGuestRun,
  startRun,
  type CareerAdvance,
  type CareerMode,
  type CareerModeCode,
  type CareerBeat,
  type CareerCardMatch,
  type CareerPreset,
  type CareerShowReport,
  type CareerNewsItem,
  type CareerNewsPage,
  type CareerStats,
  type CareerWeek,
  type GuestRunState,
} from "@/lib/career-api";

const GUEST_SAVE_KEY = "kayfabe.career.guest";

/** 체험판 일정. 세이브에 로그가 없어(§3-D8) 브라우저가 따로 들고 있어야 한다. */
const GUEST_LOG_KEY = "kayfabe.career.guest.log";

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
  crown: "왕관",
  turn: "턴",
  team: "팀",
  scene: "세계",
  debut: "데뷔",
  call_up_scene: "콜업",
  retire: "은퇴",
  moved: "이적",
  renamed: "개명",
  title_scene: "세계 벨트",
};

/**
 * 인박스에서 접을 수 있는 배경 소식 (§3-D61).
 *
 * 명부의 들고 남까지 흘리면 30년에 백 줄이 넘는다. **규칙으로 숨기지 않고 사용자가
 * 접게 한다** — 세계가 도는 것을 보고 싶은 사람과 내 커리어만 보고 싶은 사람이 다르다.
 */
const BACKGROUND_KINDS = [
  "title_scene",
  "scene",
  "team",
  "debut",
  "call_up_scene",
  "moved",
  "renamed",
  "retire",
] as const;

type BackgroundKind = (typeof BACKGROUND_KINDS)[number];

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

/**
 * 대립 단계 → 화면 이름. **백엔드 `RivalryStage`와 같은 표여야 한다.**
 *
 * 예전 표는 `taunt/feud/betrayal/revenge/blowoff` 다섯이었는데 도메인은 셋이다 —
 * 하나도 안 맞아서 화면에 `heated` 같은 영문 코드가 그대로 찍히고 있었다.
 */
const RIVALRY_STAGES: Record<string, string> = {
  indifferent: "신경전",
  heated: "과열",
  nemesis: "숙적",
};

/** 모드 코드 → 화면 이름. 백엔드는 코드를 그대로 label로 준다. */
const MODE_LABELS: Record<CareerModeCode, string> = {
  yearly: "연 단위",
  quarterly: "분기",
  monthly: "월 단위",
  weekly: "주 단위",
};

const DISCLAIMER_INTRO = "이 게임의 선수명은 실존하지만, 모든 전개·경기·대사는 허구입니다.";

/**
 * 타이틀전 배지 — **어떻게 그 자리에 섰는지** (§3-D36).
 *
 * 같은 "타이틀전"이라도 럼블을 이겨서 선 자리와 어쩌다 걸린 자리는 다른 사건이다.
 * 골드는 이미 타이틀전의 색이므로 셋이 같은 색을 쓴다 — 늘리는 것은 뜻이지 색이 아니다.
 */
const SHOT_LABELS: Record<string, string> = {
  gate: "타이틀전",
  earned: "도전권 · 타이틀전",
  briefcase: "가방 · 타이틀전",
};

/** 킹 앤 퀸 오브 더 링의 회전 이름 (§3-D33). 백엔드 `TOURNAMENT_ROUNDS`와 같은 수다. */
const TOURNAMENT_ROUNDS: Record<number, string> = {
  1: "토너먼트 1회전",
  2: "토너먼트 준결승",
  3: "토너먼트 결승",
};

/** 재개했을 때 되읽는 주차 수. 30년이면 1560줄이라 전부 받지 않는다. */
const HISTORY_WEEKS = 60;

/**
 * 화면이 들고 있는 일정의 상한 — 한 해가 52주니 10년치다.
 *
 * '다음'을 누를 때마다 진행분이 쌓이므로 상한이 없으면 30년 커리어가 1560줄이 되어
 * 브라우저가 먼저 무너진다. 오래된 쪽부터 버린다.
 */
const TIMELINE_WEEKS = 520;

/** 빈 일정의 고정 참조. 렌더마다 `[]`를 새로 만들면 effect가 끝없이 다시 돈다. */
const NO_WEEKS: CareerWeek[] = [];

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

/**
 * 체험판이 되읽는 일정. **세이브와 다른 칸에 둔다** — 세이브는 서버가 준 것을 그대로
 * 돌려보내는 불투명한 값이라(§3-D8) 화면이 안에 무엇을 끼워 넣을 수 없다.
 *
 * 로그인 쪽에는 서버 로그가 있지만 체험판에는 없다. 이걸 저장하지 않으면 새로고침
 * 한 번에 지나온 해가 전부 사라진다 — 커리어가 지워진 것처럼 보인다.
 */
function readGuestLog(uptoWeek: number): CareerWeek[] {
  try {
    const raw = window.localStorage.getItem(GUEST_LOG_KEY);
    if (!raw) return [];
    const rows: unknown = JSON.parse(raw);
    if (!Array.isArray(rows)) return [];
    // 세이브보다 앞선 주차는 짝이 맞지 않는 잔재다 — 앞 커리어의 줄을 물려받지 않는다.
    return (rows as CareerWeek[]).filter(
      (row) => typeof row?.week === "number" && row.week <= uptoWeek,
    );
  } catch {
    return [];
  }
}

/**
 * `beats`는 버리고 저장한다. 로그인 쪽도 다시 연 로그에는 입장·탈락을 싣지 않으므로
 * (§3-D34) 여기서만 남기면 두 갈래가 다르게 굴고, 럼블 30인의 비트가 브라우저에 쌓인다.
 */
function writeGuestLog(weeks: CareerWeek[]): void {
  try {
    if (weeks.length === 0) {
      window.localStorage.removeItem(GUEST_LOG_KEY);
      return;
    }
    const rows = weeks.map((week) => ({ ...week, beats: null }));
    window.localStorage.setItem(GUEST_LOG_KEY, JSON.stringify(rows));
  } catch {
    // 용량 초과·프라이빗 모드. 일정을 못 남길 뿐 진행 자체는 계속할 수 있다.
  }
}

/**
 * 진행분을 타임라인에 **얹는다** — 갈아끼우지 않는다.
 *
 * 한 번의 '다음'은 그 요청이 흘려보낸 주차만 돌려주므로(§3-D17) 그대로 세우면 지난
 * 해가 화면에서 사라진다. 같은 주차가 겹치면 `beats`를 든 쪽을 남긴다: 되읽은 로그에는
 * 입장·탈락이 실리지 않아(§3-D34) 그걸로 덮으면 펼칠 수 있던 줄이 닫힌다.
 */
function mergeWeeks(prev: CareerWeek[], incoming: CareerWeek[]): CareerWeek[] {
  if (incoming.length === 0) return prev;
  const byWeek = new Map(prev.map((week) => [week.week, week]));
  for (const week of incoming) {
    const had = byWeek.get(week.week);
    byWeek.set(week.week, week.beats === null && had?.beats ? had : week);
  }
  return [...byWeek.values()].sort((a, b) => a.week - b.week).slice(-TIMELINE_WEEKS);
}

export default function CareerPage() {
  const { user, isReady } = useAuth();
  const [screen, setScreen] = useState<Screen>({ phase: "loading" });
  const [modes, setModes] = useState<CareerMode[]>([]);
  const [presets, setPresets] = useState<CareerPreset[]>([]);
  const [metaFailed, setMetaFailed] = useState(false);
  const [tab, setTab] = useState<PanelKey>("schedule");
  const [inbox, setInbox] = useState<CareerNewsPage | null>(null);
  const [history, setHistory] = useState<CareerWeek[]>([]);
  const [hidden, setHidden] = useState<readonly BackgroundKind[]>([]);
  const [openWeek, setOpenWeek] = useState<number | null>(null);
  const [report, setReport] = useState<CareerShowReport | null>(null);
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
    // **진행시키지 않고 읽기만 한다.** 예전에는 `advance(tick)`으로 재개했는데,
    // 그 한 번이 실제로 한 틱(분기 모드면 12주)을 태웠고 대기 이벤트가 있으면
    // 409로 막혀 아래 catch가 세이브를 지웠다 — 이벤트 중 새로고침이 곧 커리어 소멸이었다.
    resumeGuestRun(saved)
      .then((next) => {
        if (!alive) return;
        writeGuestSave(next.state);
        // 재개는 진행하지 않으므로 `weeks`가 비어서 온다 — 지나온 해는 여기서만 돌아온다.
        setHistory(readGuestLog(next.run.week));
        setScreen({ phase: "play", advance: next, state: next.state, busy: false });
      })
      .catch(() => {
        // 읽을 수 없는 세이브(포맷 변경·조작)는 버리고 새로 시작하게 둔다.
        writeGuestSave(null);
        writeGuestLog([]);
        if (alive) setScreen({ phase: "create" });
      });
    return () => {
      alive = false;
    };
  }, [isReady, user]);

  const allowedModes = user ? modes : modes.filter((m) => m.guestAllowed);

  // 체험판이 서버에 되돌려 보내는 세이브 — 리포트·인박스가 이걸 싣고 묻는다 (§3-D8).
  const guestState = screen.phase === "play" ? screen.state : null;

  // 인박스를 열 때만 읽는다. 30년치를 진행할 때마다 따라 받으면 낭비다.
  const runId = screen.phase === "play" ? screen.advance.run.id : null;
  useEffect(() => {
    if (tab !== "inbox") return;
    // 체험판은 배경 소식만 받는다 (§3-D67) — 내 로그가 서버에 없다.
    const asked =
      runId !== null
        ? readNews(runId, 0, 200)
        : guestState !== null
          ? readGuestNews(guestState)
          : null;
    if (asked === null) return;
    let alive = true;
    asked.then((page) => alive && setInbox(page)).catch(() => alive && setInbox(null));
    return () => {
      alive = false;
    };
  }, [tab, runId, guestState]);

  // 일정은 **누적된 타임라인**이 세운다 (§3-D51) — 방금 진행한 주차는 이미 그 안에
  // 얹혀 있다. 아직 한 번도 쌓이지 않은 첫 화면에서만 응답의 진행분을 그대로 쓴다.
  // 빈 배열을 여기서 만들면 렌더마다 새 참조가 되어 아래 effect가 계속 다시 돈다.
  const advanced = screen.phase === "play" ? screen.advance.weeks : NO_WEEKS;
  const timeline = history.length > 0 ? history : advanced;

  // 대회 주차를 펼치면 그 밤의 리포트를 받아 온다 (§3-D45). **열 때만 받는다** —
  // 인박스와 같은 방침이다: 30년치를 진행할 때마다 따라 받으면 낭비다.
  //
  // **두 갈래가 묻는 곳이 다르다** (§3-D51). 로그인은 `runId`로 서버 로그를 짚고,
  // 체험판은 세이브를 실어 보낸다 — 서버가 아는 커리어가 없기 때문이다.
  useEffect(() => {
    if (openWeek === null) {
      setReport(null);
      return;
    }
    // 체험판은 그 줄의 사실을 함께 보낸다 (§3-D52) — 서버에 로그가 없어, 안 보내면
    // 카드가 내 상대를 같은 밤에 두 번 세운다. 로그인 쪽은 서버가 로그에서 읽는다.
    const row = timeline.find((week) => week.week === openWeek) ?? null;
    const asked = guestState
      ? readGuestReport(guestState, openWeek, {
          opponent: row?.opponent ?? null,
          titleAtStake: row?.titleAtStake ?? null,
        })
      : runId !== null
        ? readReport(runId, openWeek)
        : null;
    if (asked === null) {
      setReport(null);
      return;
    }
    let alive = true;
    asked.then((found) => alive && setReport(found)).catch(() => alive && setReport(null));
    return () => {
      alive = false;
    };
  }, [openWeek, runId, guestState, timeline]);

  // 재개하면 응답의 `weeks`가 비어 있다 — 진행한 적이 없어서가 아니라 서버가 로그를
  // 세이브에 끌고 오지 않기 때문이다(§3-D6). 일정 탭을 열 때만 마지막 쪽을 받아 온다.
  // **받은 쪽도 얹는다** — 갈아끼우면 이번 판에 진행한 주차가 탭 전환 한 번에 날아간다.
  useEffect(() => {
    if (tab !== "schedule" || runId === null) return;
    let alive = true;
    readLog(runId, 0, 1)
      .then((head) => readLog(runId, Math.max(0, head.total - HISTORY_WEEKS), HISTORY_WEEKS))
      .then((page) => alive && setHistory((prev) => mergeWeeks(prev, page.entries)))
      // 못 받아 온 것은 "기록이 없다"가 아니다. 들고 있던 타임라인을 그대로 둔다.
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [tab, runId]);

  // 체험판은 일정도 브라우저가 남긴다. **로그인 플레이는 건드리지 않는다** — 그쪽은
  // 서버 로그가 원본이고, 여기서 덮으면 두 개의 진실이 생긴다.
  const guestPlaying = !user && screen.phase === "play";
  useEffect(() => {
    if (!guestPlaying) return;
    writeGuestLog(history);
  }, [guestPlaying, history]);

  const handleStart = useCallback(async () => {
    setScreen({ phase: draft.basedOn ? "create" : "detail" });
    // 새 커리어는 빈 일정에서 시작한다 — 앞 선수의 주차를 물려받으면 안 된다.
    setHistory([]);
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
        // **응답의 `weeks`는 "이번 요청이 진행시킨 주차"다.** 이벤트에 답하면 아무 주차도
        // 진행하지 않아 비어서 온다. 일정은 이 응답이 아니라 누적된 타임라인이 세운다.
        setHistory((prev) => mergeWeeks(prev, next.weeks));
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
      writeGuestLog([]);
      setHistory([]);
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
  const { run: view, pendingEvent } = advance;
  const shownWeeks = timeline;
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
          {/* 부상 구간은 통째로 흘러가고 복귀 주차에서 끊긴다 (§3-D37). 안 알리면
              방금 지나간 결장 열두 주가 로그 안에서만 조용히 흘러간다. */}
          {advance.stopReason === "recovered" && (
            <span className="text-xs text-brand-link">부상에서 복귀했습니다</span>
          )}
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
              {shownWeeks.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  아직 진행한 주차가 없습니다. 위의 &lsquo;다음&rsquo;을 누르세요.
                </p>
              ) : (
                groupByTick(shownWeeks, view.year).map((chunk) => (
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
                        <WeekRow
                          key={week.week}
                          week={week}
                          player={view.name}
                          open={openWeek === week.week}
                          report={openWeek === week.week ? report : null}
                          onToggle={() => setOpenWeek((w) => (w === week.week ? null : week.week))}
                        />
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
              {inbox === null || inbox.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">아직 남을 만한 사건이 없습니다.</p>
              ) : (
                <div className="space-y-5">
                  {runId === null && (
                    <p className="text-xs text-muted-foreground">
                      체험판은 <b>세계의 소식만</b> 받습니다 — 내 대관·부상 기록은 로그인 플레이에서
                      쌓입니다.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {BACKGROUND_KINDS.map((kind) => {
                      const off = hidden.includes(kind);
                      return (
                        <button
                          key={kind}
                          type="button"
                          aria-pressed={!off}
                          onClick={() =>
                            setHidden((now) =>
                              now.includes(kind) ? now.filter((k) => k !== kind) : [...now, kind],
                            )
                          }
                          className={cn(
                            "rounded-[4px] px-2 py-1 text-xs transition-colors duration-[120ms]",
                            off
                              ? "text-muted-foreground/60 line-through hover:text-muted-foreground"
                              : "bg-card text-foreground ring-1 ring-brand-400/40 ring-inset",
                          )}
                        >
                          {NEWS_KINDS[kind] ?? kind}
                        </button>
                      );
                    })}
                  </div>
                  {groupNewsByYear(
                    inbox.items.filter((item) => !hidden.includes(item.kind as BackgroundKind)),
                  ).map(([year, rows]) => (
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

/**
 * 주차 로그 한 줄.
 *
 * 럼블·챔버처럼 단계가 있는 밤은 **접힌 채로 요약 한 줄**을 보여주고, 누르면 입장과
 * 탈락이 순서대로 펼쳐진다 — 30인 럼블이 59줄이라 늘 펼쳐 두면 일정 탭이 그 한 밤으로
 * 가득 찬다 (2026-08-11 사용자 결정).
 */
function WeekRow({
  week,
  player,
  open,
  report,
  onToggle,
}: {
  week: CareerWeek;
  player: string;
  open: boolean;
  report: CareerShowReport | null;
  onToggle: () => void;
}) {
  const stagedNight = week.matchSummary !== null;
  // 경기가 선 밤은 펼칠 것이 하나 더 있다 — 그날의 리포트다 (§3-D45·D60).
  // 주간 방송도 연다: 밤이 작을 뿐 그날도 카드가 섰다. 프로모·결장은 링에 서지
  // 않은 주차라 열지 않는다.
  const showNight = week.kind === "ple" || week.kind === "special" || week.kind === "weekly_show";
  return (
    <div className="border-b border-stone-200/40 dark:border-stone-800/60">
      <div className="grid grid-cols-[4.5rem_2.5rem_1fr] items-baseline gap-x-2 gap-y-0.5 py-1.5 sm:grid-cols-[5rem_2.5rem_9rem_1fr]">
        <span className="text-xs text-muted-foreground">
          {week.month}월 {week.weekOfMonth}주
        </span>
        <span className={cn("text-xs font-semibold", RESULT_TONE[week.result ?? "none"])}>
          {RESULT_LABELS[week.result ?? "none"]}
        </span>
        <span className="truncate text-sm">
          <WeekOpponent week={week} />
        </span>
        <div className="col-span-3 sm:col-span-1">
          <p className={cn("text-sm leading-relaxed", week.cursed && "text-muted-foreground")}>
            {/* 토너먼트는 한 주에 안 끝난다 — 몇 회전인지가 그 밤의 뜻이다 (§3-D33). */}
            {week.tournamentRound > 0 && (
              <span className="mr-1.5 text-xs text-muted-foreground">
                {TOURNAMENT_ROUNDS[week.tournamentRound] ?? "토너먼트"}
              </span>
            )}
            {isStipulation(week) && (
              <span className="mr-1.5 text-xs text-muted-foreground">{week.matchLabel}</span>
            )}
            {week.titleAtStake && (
              <span className="mr-1.5 text-xs text-brand-link">
                {SHOT_LABELS[week.titleShotFrom ?? "gate"]}
              </span>
            )}
            {week.narration}
          </p>
          {week.stars > 0 && (
            <p className="mt-0.5 text-xs">
              <Stars value={week.stars} />
            </p>
          )}
          {stagedNight &&
            (week.beats && week.beats.length > 0 ? (
              <button
                type="button"
                onClick={onToggle}
                aria-expanded={open}
                className="mt-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                {week.matchSummary}
                <span className="ml-1">{open ? "▾" : "▸"}</span>
              </button>
            ) : (
              // 다시 연 로그에는 요약만 남아 있다 — 펼칠 것이 없으니 여는 시늉도 안 한다.
              <p className="mt-0.5 text-xs text-muted-foreground">{week.matchSummary}</p>
            ))}
          {showNight && !stagedNight && (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={open}
              className="mt-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              그날의 리포트<span className="ml-1">{open ? "▾" : "▸"}</span>
            </button>
          )}
          {open && week.beats && <BeatList beats={week.beats} player={player} />}
          {open && report && (
            <ShowCard
              report={report}
              mine={
                week.result === null
                  ? null
                  : {
                      player,
                      opponent: week.opponent,
                      matchLabel: isStipulation(week) ? week.matchLabel : null,
                      titleAtStake: week.titleAtStake,
                      stars: week.stars,
                    }
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 그날의 리포트 (§3-D45).
 *
 * **뉴스와 다른 것을 보여준다.** 뉴스가 "무슨 일이 있었더라"라면 이쪽은 "그날 카드가
 * 어땠지"다 — 그 밤 벨트를 누가 들고 있었고, 그 무렵 세계에 무슨 일이 있었는지.
 */
type MyMatch = {
  player: string;
  opponent: string | null;
  matchLabel: string | null;
  titleAtStake: string | null;
  stars: number;
};

function ShowCard({ report, mine }: { report: CareerShowReport; mine: MyMatch | null }) {
  return (
    <div className="mt-2 space-y-2 border-l border-stone-300/60 pl-3 dark:border-stone-700/60">
      <div className="flex items-start gap-2.5">
        {/* 그 밤의 로고 (§3-D71). 대회마다 얼굴이 다르다는 것이 카드보다 먼저 읽힌다.
            없는 밤(주간 방송)은 자리도 안 잡는다. */}
        {report.logo && (
          // eslint-disable-next-line @next/next/no-img-element -- public 정적 파일
          <img
            src={`/ple/${report.logo}.png`}
            alt=""
            className="mt-0.5 h-9 w-9 shrink-0 object-contain"
            loading="lazy"
          />
        )}
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-1.5 font-sport text-sm">
            {report.show}
            {report.nights > 1 && (
              <span className="text-xs text-brand-link">{report.nights}일차</span>
            )}
            {report.isMajor && <span className="text-xs text-brand-link">대형</span>}
            {report.stars > 0 && (
              <span className="ml-auto text-xs font-normal">
                <Stars value={report.stars} />
              </span>
            )}
          </p>
          {/* 그 밤이 어디서 열렸는지 (§3-D69). 서술이 쓰는 것과 같은 값이라, 로그 줄의
            문장과 이 머리가 같은 경기장을 말한다. */}
          {report.venue && <p className="text-xs text-muted-foreground">{report.venue}</p>}
        </div>
      </div>
      {report.card.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground">그날의 카드</p>
          <ul className="mt-0.5 space-y-0.5">
            {report.card.map((match, i) => (
              <li key={i} className="text-xs leading-relaxed">
                <CardLine match={match} />
              </li>
            ))}
            {/* **내 경기가 카드의 마지막에 선다** (§3-D68). 서버는 배경만 만들고
                (§3-D52) 내 기록은 이 줄이 이미 들고 있다 — 화면에서 이으면 그 밤이
                비로소 한 장이 된다. 체험판·로그인이 같은 자리에서 같은 모양이다. */}
            {mine && (
              <li className="text-xs leading-relaxed">
                <span className="font-semibold text-foreground">{mine.player}</span>
                {mine.opponent && (
                  <>
                    <span className="mx-1 text-muted-foreground/70">vs</span>
                    <span className="text-muted-foreground">{mine.opponent}</span>
                  </>
                )}
                {mine.matchLabel && (
                  <span className="ml-1.5 text-muted-foreground">{mine.matchLabel}</span>
                )}
                {mine.titleAtStake && (
                  <span className="ml-1.5 text-brand-link">{mine.titleAtStake}</span>
                )}
                <span className="ml-1.5 text-brand-link">내 경기</span>
                <span className="ml-1.5">
                  <Stars value={mine.stars} />
                </span>
              </li>
            )}
          </ul>
        </div>
      )}
      <div>
        <p className="text-xs text-muted-foreground">그날의 벨트</p>
        <ul className="mt-0.5 space-y-0.5">
          {report.champions.map((c) => (
            <li
              key={c.title}
              className={cn(
                "text-xs leading-relaxed",
                c.mine ? "font-semibold text-foreground" : "text-muted-foreground",
              )}
            >
              {c.title} — {c.holder}
              {c.mine && " (나)"}
            </li>
          ))}
        </ul>
      </div>
      {report.around.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground">그 무렵</p>
          <ul className="mt-0.5 space-y-0.5">
            {report.around.map((line, i) => (
              <li key={i} className="text-xs leading-relaxed text-muted-foreground">
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * 별점 (§3-D56) — **채운 별과 빈 별을 함께 그린다.**
 *
 * 숫자만 쓰면 "3.75"가 좋은 건지 나쁜 건지 한눈에 안 읽힌다. 다섯 칸을 늘 그려 두면
 * 그 밤이 어디쯤인지가 형태로 먼저 온다. 골드는 액션의 색이라(DESIGN.md §7) 별에는
 * 쓰지 않는다 — 별은 상태이지 누를 것이 아니다.
 */
function Stars({ value }: { value: number }) {
  if (value <= 0) return null;
  const full = Math.floor(value);
  const half = value - full >= 0.25;
  return (
    <span className="tabular-nums text-muted-foreground" title={`${value.toFixed(2)}점`}>
      {"★".repeat(full)}
      {half && "☆"}
      <span className="ml-1 text-[0.6875rem]">{value.toFixed(2)}</span>
    </span>
  );
}

/**
 * 카드 한 줄 — **이긴 쪽만 굵다** (§3-D52).
 *
 * "A def. B"를 쓰지 않는다. 승패는 굵기로 이미 읽히고, 여덟 줄이 같은 약어로 시작하면
 * 카드가 표가 된다. 벨트는 골드로 짚되 배지를 만들지 않는다 — 골드는 액션의 색이라
 * 배경 경기에까지 pill을 두르면 신호가 희석된다 (DESIGN.md §7).
 */
function CardLine({ match }: { match: CareerCardMatch }) {
  return (
    <>
      <Side name={match.left} won={match.winner === match.left} />
      <span className="mx-1 text-muted-foreground/70">vs</span>
      <Side name={match.right} won={match.winner === match.right} />
      {match.matchLabel && (
        <span className="ml-1.5 text-xs text-muted-foreground">{match.matchLabel}</span>
      )}
      {match.title && (
        <span className="ml-1.5 text-brand-link">
          {match.title}
          {match.vacant ? (
            <span className="ml-1">공석 결정전</span>
          ) : (
            match.changedHands && <span className="ml-1">타이틀 이동</span>
          )}
        </span>
      )}
      <span className="ml-1.5">
        <Stars value={match.stars} />
      </span>
    </>
  );
}

function Side({ name, won }: { name: string; won: boolean }) {
  return (
    <span className={won ? "font-semibold text-foreground" : "text-muted-foreground"}>{name}</span>
  );
}

/** 입장과 탈락을 순서대로. **내 줄만 굵다** — 서른 줄에서 나를 찾는 것이 이 화면의 일이다. */
function BeatList({ beats, player }: { beats: CareerBeat[]; player: string }) {
  return (
    <ol className="mt-1.5 space-y-0.5 border-l border-stone-300/60 pl-3 dark:border-stone-700/60">
      {beats.map((beat, i) => {
        const mine = beat.name === player || beat.by === player;
        return (
          <li
            key={i}
            className={cn(
              "text-xs leading-relaxed",
              mine ? "font-semibold text-foreground" : "text-muted-foreground",
            )}
          >
            {beatLine(beat)}
          </li>
        );
      })}
    </ol>
  );
}

/** 비트 한 마디를 문장으로. 백엔드는 구조만 보내고 말은 여기서 만든다 (§3-D34). */
function beatLine(beat: CareerBeat): string {
  if (beat.kind === "enter") {
    return `${beat.number}번 — ${beat.name} 입장`;
  }
  if (beat.kind === "win") {
    return `${beat.name} 우승`;
  }
  if (beat.by === null) {
    return `${beat.name} 탈락`;
  }
  return `${beat.by}${josa(beat.by, "이", "가")} ${beat.name}${josa(beat.name, "을", "를")} 탈락시켰다`;
}

/**
 * 받침이 있으면 앞엣것, 없으면 뒤엣것.
 *
 * 명부는 전부 한글 표기라(§3-D27) 마지막 글자의 종성만 보면 된다. "드류 맥킨타이어가"와
 * "브론 브레이커를"이 뒤집히면 문장이 바로 어색해진다.
 */
function josa(word: string, withFinal: string, withoutFinal: string): string {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  if (code < 0 || code > 11171) return withoutFinal;
  return code % 28 === 0 ? withoutFinal : withFinal;
}

/**
 * 서술 앞에 형식을 적어야 하는 경기인지 (§3-D32).
 *
 * **둘이 붙는 특수 경기만이다.** 여럿이 붙는 경기는 형식이 상대 칸에 이미 나가 있고
 * (`WeekOpponent`), 한 줄에 두 번 적으면 그게 노이즈다. 싱글은 기본값이라 적지 않는다 —
 * 매주 "싱글 매치"가 붙으면 헬 인 어 셀이 걸린 밤이 눈에 안 띈다.
 */
function isStipulation(week: CareerWeek): boolean {
  return week.matchLabel !== null && week.matchField === 2 && week.matchKind !== "singles";
}

/**
 * 그 주차에 누구와 붙었는가.
 *
 * **여럿이 붙는 경기는 상대 한 명을 말하지 않는다.** 백엔드는 30인 럼블에도 라이벌
 * 하나를 실어 보내지만(서술문의 `{rival}` 자리다), 그걸 그대로 "vs 세스 롤린스"로
 * 적으면 럼블이 싱글로 읽힌다. 그 자리는 형식이 대신한다.
 */
function WeekOpponent({ week }: { week: CareerWeek }) {
  if (week.result === null) {
    return <span className="text-muted-foreground">{WEEK_KINDS[week.kind]}</span>;
  }
  if (week.matchField > 2 && week.matchLabel !== null) {
    return <span className="text-muted-foreground">{week.matchLabel}</span>;
  }
  if (week.opponent === null) {
    return <span className="text-muted-foreground">{WEEK_KINDS[week.kind]}</span>;
  }
  return (
    <>
      <span className="text-muted-foreground">vs </span>
      {week.opponent}
    </>
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
