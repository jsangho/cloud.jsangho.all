"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/context/auth-context";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import { CareerDashboard } from "@/components/sandbox-career/career-dashboard";
import { CareerLogPanel } from "@/components/sandbox-career/career-log-panel";
import { CareerMatchesPanel } from "@/components/sandbox-career/career-matches-panel";
import { CareerTabs, type CareerTab } from "@/components/sandbox-career/career-tabs";
import { CareerTitlesPanel } from "@/components/sandbox-career/career-titles-panel";
import { CareerWeekPanel } from "@/components/sandbox-career/career-week-panel";
import { CareerWorldPanel } from "@/components/sandbox-career/career-world-panel";
import { CareerWrestlerDetail } from "@/components/sandbox-career/career-wrestler-detail";
import { PHASE_LABEL, labelOf } from "@/components/sandbox-career/career-labels";
import { Loading } from "@/components/sandbox-career/career-ui";
import {
  advanceCareerWeek,
  CareerWriteError,
  createCareer,
  fetchCareer,
  fetchCareerLog,
  fetchCareers,
  newCareerRequestId,
  performCareerAction,
  resolveCareerEvent,
  settleCareerSeason,
  startNextCareerSeason,
  type CareerAction,
  type CareerLogEntry,
  type CareerSummary,
  type CareerTrainable,
  type CareerView,
} from "@/lib/career-api";
import {
  actionScope,
  beginAttempt,
  endAttempt,
  eventScope,
  type PendingRequestKey,
} from "@/lib/career-request-keys";

/**
 * 커리어 — **저장되는 쪽이다.**
 *
 * `/sandbox/career`(무상태 장난감)와 갈라 둔 화면이다. 그쪽은 런을
 * `localStorage`에 들고 다니고 서버가 아무것도 모른다. 이쪽은 세이브가 서버에
 * 있어서 재접속하면 같은 세계가 이어진다 — 그래서 로그인이 필요하다.
 *
 * ## 이 파일이 맡는 것
 *
 * 세이브 목록·생성, 상태 한 덩어리, 여섯 탭 사이의 이동, 그리고 **읽기 한 번으로
 * 복구되는 흐름**(`fetchCareer`)이다. 각 탭의 화면은 `components/sandbox-career/`
 * 아래로 나가 있다 — 여섯 화면을 한 파일에 두면 이전 커리어 시뮬레이터가 불어난
 * 길을 다시 걷게 된다.
 *
 * ## 상태를 이 화면이 계산하지 않는다
 *
 * 능력치·승패·인기도·위험도·재위 주차는 전부 서버가 정하고, 화면은 받은 값을
 * 그리고 다음 요청에 행동 코드만 담는다. 그 경계가 이전 판본(38,326줄)이 불어난
 * 길 하나를 막는다.
 *
 * ## 재시도는 **같은 요청 키**로 간다
 *
 * 쓰기 하나마다 `Idempotency-Key`를 붙인다. 키는 한 번의 사용자 의도에 하나이고,
 * 결론이 나지 않은 실패(타임아웃·네트워크 오류·5xx) 뒤에는 **그 키를 그대로 둔다**
 * — 사용자가 다시 눌렀을 때 서버가 같은 요청으로 알아보고 두 번 적용하지 않는다.
 * 서버가 4xx로 답했으면 결론이 난 것이므로 키를 버린다(입력을 고쳐 보낼 때 같은
 * 키를 쓰면 서버가 409로 막는다).
 *
 * 여전히 **자동으로는 다시 보내지 않는다.** 재전송은 사용자가 버튼을 다시 누르는
 * 것이고, 버튼 비활성화(`busy`)도 그대로 남는다 — 화면의 중복 클릭 방지가 서버
 * 멱등성을 대신하지 않고, 둘이 서로를 대신하지도 않는다.
 */
const STYLES = ["파워", "테크니션", "하이플라이어"] as const;
const STYLE_NOTE: Readonly<Record<string, string>> = {
  파워: "잘 이긴다 · 부상 보통",
  테크니션: "안전하다 · 상승 느림",
  하이플라이어: "빨리 뜬다 · 자주 다친다",
};

/** 기록 한 번에 읽는 줄 수. 서버 `/log` 의 `limit` 상한이 200이다. */
const LOG_PAGE = 200;

/** 탭 ↔ URL 값. 새로고침해도 같은 탭으로 돌아온다. */
const TAB_PARAM = "tab";
const CAREER_PARAM = "career";

type Notice = { kind: "ok" | "error"; message: string };

/**
 * 읽어 둔 기록. **`careerId` 를 함께 들고 다닌다** — 커리어를 바꿨을 때 앞 세이브의
 * 기록이 새 화면에 섞이는 것을 막는 것이 이 칸이다(사용자 요구 §7).
 */
type LogState = {
  careerId: number | null;
  entries: CareerLogEntry[] | null;
  exhausted: boolean;
  loading: boolean;
};

type PageState = {
  loading: boolean;
  careers: CareerSummary[];
  view: CareerView | null;
  /** 진행 중인 요청 이름. 버튼 중복 클릭을 막는다. */
  busy: string | null;
  notice: Notice | null;
  log: LogState;
  /** 상세를 열어 둔 선수 이름. */
  detail: string | null;
  /** 주간 행동의 대상 선택. */
  targets: { stat: CareerTrainable; partner: string };
};

const emptyLog: LogState = { careerId: null, entries: null, exhausted: false, loading: false };

const initialState: PageState = {
  loading: true,
  careers: [],
  view: null,
  busy: null,
  notice: null,
  log: emptyLog,
  detail: null,
  targets: { stat: "in_ring", partner: "" },
};

/** 기록을 필요로 하는 탭. 열릴 때 읽어 온다. */
const LOG_TABS: readonly CareerTab[] = ["matches", "titles", "log"];
/** 세 수가 맞아야 하는 탭 — 끝까지 읽는다. 기록 탭은 「더 보기」로 사용자가 끊는다. */
const FULL_LOG_TABS: readonly CareerTab[] = ["matches", "titles"];

export default function CareersPage() {
  return (
    <Suspense
      fallback={
        <Shell>
          <Loading />
        </Shell>
      }
    >
      <CareersView />
    </Suspense>
  );
}

function CareersView() {
  const { user, isReady } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [state, setState] = useState<PageState>(initialState);
  const [name, setName] = useState("");
  const [style, setStyle] = useState<string>(STYLES[0]);
  const [age, setAge] = useState(24);

  const isSignedIn = user != null;
  const paramTab = params.get(TAB_PARAM);
  const tab: CareerTab = isTab(paramTab) ? paramTab : "dashboard";
  const paramCareer = Number(params.get(CAREER_PARAM));
  const wantedCareer = Number.isInteger(paramCareer) && paramCareer > 0 ? paramCareer : null;

  /** URL 한 줄에 커리어와 탭을 적는다 — 새로고침 복구가 이 두 값으로 끝난다. */
  const writeUrl = useCallback(
    (next: { career?: number | null; tab?: CareerTab }) => {
      const search = new URLSearchParams(params.toString());
      if (next.career !== undefined) {
        if (next.career == null) search.delete(CAREER_PARAM);
        else search.set(CAREER_PARAM, String(next.career));
      }
      if (next.tab !== undefined) search.set(TAB_PARAM, next.tab);
      const query = search.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  /** 복구를 한 번만 시도한다 — 실패한 id로 매 렌더마다 다시 부르지 않는다. */
  const restored = useRef<number | null>(null);

  /**
   * 결론이 나지 않은 쓰기 **하나**. **ref인 것은 의도다.**
   *
   * 화면에 그리지 않는 값이고, `useState`로 두면 `setState` 갱신 함수가 비동기라
   * 키를 만든 직후 읽을 수 없다 — 그 자리에서 빈 문자열을 보내게 된다.
   *
   * 전에는 `label` → 키 **맵**이었다. 라벨이 busy 표시와 키 범위를 겸해서 키가
   * 화면 버튼 단위로 묶였고(`action:훈련`), 서버가 payload로 내는 지문과 범위가
   * 어긋나 불필요한 409가 났다. 지금은 범위를 `career-request-keys`가 정하고 이
   * ref는 **미해결 시도 하나**만 든다 — 이유는 그 모듈 주석에 있다.
   */
  const pending = useRef<PendingRequestKey>(null);

  useEffect(() => {
    if (!isReady) return;
    if (!isSignedIn) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }
    let cancelled = false;
    void (async () => {
      const careers = await fetchCareers();
      if (cancelled) return;
      setState((s) => ({ ...s, loading: false, careers }));
    })();
    return () => {
      cancelled = true;
    };
  }, [isReady, isSignedIn]);

  // 새로고침 복구: URL에 커리어가 적혀 있으면 그 세이브를 읽어 온다.
  useEffect(() => {
    if (!isSignedIn || state.loading) return;
    if (wantedCareer == null || state.view?.id === wantedCareer) return;
    if (restored.current === wantedCareer) return;
    restored.current = wantedCareer;
    let cancelled = false;
    void (async () => {
      const view = await fetchCareer(wantedCareer);
      if (cancelled) return;
      setState((s) => ({
        ...s,
        view,
        log: { ...emptyLog, careerId: view ? view.id : null },
        detail: null,
        notice: view ? s.notice : { kind: "error", message: "커리어를 불러오지 못했습니다." },
      }));
      if (!view) writeUrl({ career: null });
    })();
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, state.loading, state.view?.id, wantedCareer, writeUrl]);

  /** 기록 한 페이지. **다른 커리어의 응답이 돌아오면 버린다.** */
  const loadLogPage = useCallback(async (careerId: number, offset: number) => {
    setState((s) => (s.log.careerId === careerId ? { ...s, log: { ...s.log, loading: true } } : s));
    const rows = await fetchCareerLog(careerId, { limit: LOG_PAGE, offset });
    setState((s) => {
      // 그 사이 커리어가 바뀌었거나 기록이 비워졌으면(쓰기 뒤) 이 응답은 낡았다.
      if (s.log.careerId !== careerId) return s;
      if ((s.log.entries?.length ?? 0) !== offset)
        return { ...s, log: { ...s.log, loading: false } };
      return {
        ...s,
        log: {
          careerId,
          entries: [...(s.log.entries ?? []), ...rows],
          exhausted: rows.length < LOG_PAGE,
          loading: false,
        },
      };
    });
  }, []);

  // 탭이 기록을 필요로 하면 읽는다. 경기·타이틀 탭은 수가 맞아야 해서 끝까지 읽는다.
  useEffect(() => {
    const view = state.view;
    if (!view || state.busy != null) return;
    const needs = LOG_TABS.includes(tab) || state.detail != null;
    if (!needs) return;
    const { entries, exhausted, loading, careerId } = state.log;
    if (loading || careerId !== view.id) return;
    if (entries == null) {
      void loadLogPage(view.id, 0);
      return;
    }
    const wantsAll = FULL_LOG_TABS.includes(tab) || state.detail != null;
    if (wantsAll && !exhausted) void loadLogPage(view.id, entries.length);
  }, [state.view, state.busy, state.log, state.detail, tab, loadLogPage]);

  /**
   * 쓰기 하나. **실패하면 화면 상태를 바꾸지 않는다** — 사유만 적는다.
   *
   * 성공하면 읽어 둔 기록을 버린다. 세이브가 바뀌어 앞쪽에 줄이 끼어들었으므로
   * 순번 기반 키가 밀리고, 이어 읽으면 같은 줄이 두 번 들어온다.
   *
   * **`busy`와 `scope`는 다른 개념이다.**
   *
   *     busy    화면 식별자 — 어느 버튼이 돌고 있나. 패널이 이 문자열을 비교한다.
   *     scope   요청 식별자 — 무엇을 보냈나. 서버가 지문을 내는 범위와 같아야 한다.
   *
   * 훈련이 그 차이를 만든다: 버튼은 하나(`action:훈련`)인데 대상이 다르면 다른
   * 요청이다(`action:훈련:in_ring`). 둘을 한 문자열로 쓰던 때는 대상을 바꿔 재전송
   * 하면 같은 키에 다른 payload가 실려 409가 났다.
   *
   * `scope`가 `null`이면 **멱등 키를 보내지 않는 쓰기**다(생성 — 키 범위가
   * `(사용자, 커리어, 키)`인데 커리어가 아직 없다). 그 경우 보관 슬롯을 건드리지
   * 않는다.
   */
  const run = useCallback(
    async (
      busy: string,
      scope: string | null,
      ok: string,
      request: (requestId: string) => Promise<CareerView>,
    ) => {
      // 같은 범위의 미해결 시도가 있으면 그 키를 재사용한다(재전송). 범위가 다르면
      // 새 키이고, 앞의 미해결 시도는 버려진다 — `career-request-keys` 참조.
      const attempt =
        scope == null ? null : beginAttempt(pending.current, scope, newCareerRequestId);
      if (attempt != null) pending.current = attempt;
      setState((s) => ({ ...s, busy, notice: null }));
      try {
        // 생성은 이 키를 보내지 않는다. 혹시 보내면 서버가 길이로 422를 내 조용히
        // 넘어가지 않는다.
        const view = await request(attempt?.requestId ?? "");
        // **슬롯을 아직 이 시도가 들고 있을 때만** 비운다. 화면이 `busy`로 버튼을
        // 막으므로 요청이 겹칠 일은 없지만, 겹쳤다면 뒤 시도의 슬롯을 덮어쓰는 쪽이
        // 더 나쁘다 — 재전송 기회를 잃는 것으로 끝나야 한다.
        if (attempt != null && pending.current === attempt) {
          pending.current = endAttempt(attempt, "applied");
        }
        setState((s) => ({
          ...s,
          busy: null,
          view,
          log: { ...emptyLog, careerId: view.id },
          notice: { kind: "ok", message: `${ok} — 시즌 ${view.season} · ${view.week}주차` },
        }));
        return view;
      } catch (error) {
        // **결론이 난 실패는 키를 버린다.** 서버가 4xx로 답했으면 상태는 그대로고,
        // 입력을 고쳐 보낼 때는 새 키가 맞다. 결론이 나지 않은 실패(타임아웃·
        // 네트워크·5xx)만 키를 남겨 **같은 payload의** 다음 클릭이 재전송이 되게 한다.
        const unresolved = error instanceof CareerWriteError && error.inconclusive;
        if (attempt != null && pending.current === attempt) {
          pending.current = endAttempt(attempt, unresolved ? "unresolved" : "rejected");
        }
        setState((s) => ({
          ...s,
          busy: null,
          notice: {
            kind: "error",
            message: error instanceof Error ? error.message : "요청에 실패했습니다.",
          },
        }));
        return null;
      }
    },
    [],
  );

  const open = useCallback(
    async (careerId: number) => {
      setState((s) => ({ ...s, busy: `open:${careerId}`, notice: null }));
      const view = await fetchCareer(careerId);
      restored.current = careerId;
      // 커리어를 옮기면 미해결 시도를 버린다. 서버가 커리어로 범위를 갈라 주므로
      // 남아도 안전하긴 하지만, 그 키가 가리키는 세이브는 더 이상 화면에 없다.
      pending.current = null;
      setState((s) => ({
        ...s,
        busy: null,
        view,
        log: { ...emptyLog, careerId: view ? view.id : null },
        detail: null,
        targets: { stat: "in_ring", partner: "" },
        notice: view ? null : { kind: "error", message: "커리어를 불러오지 못했습니다." },
      }));
      if (view) writeUrl({ career: view.id, tab: "dashboard" });
    },
    [writeUrl],
  );

  const backToList = useCallback(async () => {
    const careers = await fetchCareers();
    restored.current = null;
    pending.current = null;
    setState((s) => ({
      ...s,
      careers,
      view: null,
      log: emptyLog,
      detail: null,
      notice: null,
    }));
    writeUrl({ career: null, tab: "dashboard" });
  }, [writeUrl]);

  if (!isReady || state.loading) {
    return (
      <Shell>
        <Loading />
      </Shell>
    );
  }

  if (!isSignedIn) {
    return (
      <Shell>
        <div className="rounded-xl border border-border bg-card p-4 text-sm">
          <p className="text-foreground">세이브가 회원에게 묶여 있어 로그인이 필요합니다.</p>
          <p className="mt-2 text-muted-foreground">
            로그인 없이 돌려 보려면{" "}
            <Link href="/sandbox/career" className="text-brand-link underline">
              저장 없는 장난감
            </Link>
            을 쓰세요 — 그쪽은 런이 이 브라우저에만 남습니다.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-flex h-9 items-center rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground"
          >
            로그인
          </Link>
        </div>
      </Shell>
    );
  }

  const view = state.view;
  const notice = state.notice;
  // **세 칸을 함께 막는다.** 커리어가 바뀐 직후에는 `entries` 만 비우면 안 된다 —
  // 앞 세이브의 `exhausted: true` 가 남아 새 화면이 "끝까지 읽었다" 고 말한다.
  const log =
    state.log.careerId === view?.id ? state.log : { ...emptyLog, careerId: view?.id ?? null };
  const logEntries = log.entries;
  const detailWrestler =
    view && state.detail ? (view.roster.find((w) => w.name === state.detail) ?? null) : null;

  return (
    <Shell>
      {notice ? (
        <p
          role="status"
          className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
            notice.kind === "error"
              ? "border-live/40 bg-live/10 text-live"
              : "border-chart-win/40 bg-chart-win/10 text-chart-win"
          }`}
        >
          {notice.message}
        </p>
      ) : null}

      {!view ? (
        <>
          <section className="mb-8">
            <h2 className="font-sport text-lg text-foreground">내 커리어</h2>
            {state.careers.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                아직 없습니다. 아래에서 선수를 만들면 시즌 1의 1주차부터 시작합니다.
              </p>
            ) : (
              <ul className="mt-3 space-y-2">
                {state.careers.map((row) => (
                  <li key={row.id}>
                    <button
                      type="button"
                      onClick={() => void open(row.id)}
                      disabled={state.busy != null}
                      className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-card-2 disabled:opacity-50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-foreground">
                          {row.playerName}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {labelOf(PHASE_LABEL, row.phase)} · 갱신{" "}
                          {new Date(row.updatedAt).toLocaleDateString("ko-KR")}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground">
                        시즌 {row.season} · {row.week} / {row.seasonWeeks}주
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="font-sport text-lg text-foreground">새 선수</h2>
            <div className="mt-3 space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs font-bold text-muted-foreground">링네임</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={40}
                  placeholder="예: Ho"
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground"
                />
              </label>

              <div>
                <span className="mb-1 block text-xs font-bold text-muted-foreground">스타일</span>
                <div className="grid gap-2 sm:grid-cols-3">
                  {STYLES.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStyle(s)}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        style === s
                          ? "border-brand-500 bg-brand-500/10 text-foreground"
                          : "border-border bg-card text-muted-foreground hover:bg-card-2"
                      }`}
                    >
                      <span className="block font-bold">{s}</span>
                      <span className="block text-[11px]">{STYLE_NOTE[s]}</span>
                    </button>
                  ))}
                </div>
              </div>

              <label className="block">
                <span className="mb-1 block text-xs font-bold text-muted-foreground">
                  데뷔 나이 (18~40)
                </span>
                <input
                  type="number"
                  min={18}
                  max={40}
                  value={age}
                  onChange={(e) => setAge(Number(e.target.value))}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm tabular-nums text-foreground sm:w-32"
                />
                <span className="mt-1 block text-[11px] text-muted-foreground">
                  데뷔 나이는 이후 바뀌지 않습니다. 나이는 시즌 결산에서만 한 살 오릅니다.
                </span>
              </label>

              <button
                type="button"
                onClick={() =>
                  void run("create", null, "커리어를 만들었습니다", () =>
                    createCareer({ name: name.trim(), style, age }),
                  ).then((created) => {
                    if (created) writeUrl({ career: created.id, tab: "dashboard" });
                  })
                }
                disabled={state.busy != null || !name.trim()}
                className="h-9 rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              >
                {state.busy === "create" ? "만드는 중…" : "데뷔"}
              </button>
            </div>
          </section>
        </>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-sport text-xl text-foreground">{view.player.name}</h2>
            <button
              type="button"
              onClick={() => void backToList()}
              disabled={state.busy != null}
              className="text-xs text-brand-link underline disabled:opacity-50"
            >
              커리어 목록으로
            </button>
          </div>

          <CareerTabs
            active={tab}
            pending={view.pending.length}
            onSelect={(next) => writeUrl({ tab: next })}
          />

          {tab === "dashboard" ? (
            <CareerDashboard
              view={view}
              busy={state.busy}
              log={logEntries}
              onResolve={(eventId, choice) =>
                void run(
                  `event:${eventId}:${choice}`,
                  eventScope(eventId, choice),
                  "선택을 반영했습니다",
                  (requestId) => resolveCareerEvent(view.id, eventId, choice, requestId),
                )
              }
              onGoTo={(next) => writeUrl({ tab: next })}
            />
          ) : null}

          {tab === "week" ? (
            <CareerWeekPanel
              view={view}
              busy={state.busy}
              targets={state.targets}
              onTargets={(next) => setState((s) => ({ ...s, targets: { ...s.targets, ...next } }))}
              onAct={(action: CareerAction, target) =>
                // busy는 버튼 하나(`action:훈련`), 요청 범위는 대상까지 포함한다.
                void run(
                  `action:${action}`,
                  actionScope(action, target),
                  `${action}을 적용했습니다`,
                  (requestId) => performCareerAction(view.id, action, target, requestId),
                )
              }
              onAdvance={() =>
                void run("advance", "advance", "한 주를 진행했습니다", (requestId) =>
                  advanceCareerWeek(view.id, requestId),
                )
              }
              onSettle={() =>
                void run("settle", "settle", "시즌을 결산했습니다", (requestId) =>
                  settleCareerSeason(view.id, requestId),
                )
              }
              onNextSeason={() =>
                void run("next-season", "next-season", "다음 시즌을 시작했습니다", (requestId) =>
                  startNextCareerSeason(view.id, requestId),
                )
              }
              onResolve={(eventId, choice) =>
                void run(
                  `event:${eventId}:${choice}`,
                  eventScope(eventId, choice),
                  "선택을 반영했습니다",
                  (requestId) => resolveCareerEvent(view.id, eventId, choice, requestId),
                )
              }
            />
          ) : null}

          {tab === "world" ? (
            <CareerWorldPanel
              view={view}
              onOpenWrestler={(wrestler) => setState((s) => ({ ...s, detail: wrestler }))}
            />
          ) : null}

          {tab === "matches" ? (
            <CareerMatchesPanel view={view} log={logEntries} logLoading={log.loading} />
          ) : null}

          {tab === "titles" ? (
            <CareerTitlesPanel view={view} log={logEntries} logLoading={log.loading} />
          ) : null}

          {tab === "log" ? (
            <CareerLogPanel
              view={view}
              log={logEntries}
              logLoading={log.loading}
              exhausted={log.exhausted}
              onLoadMore={() => void loadLogPage(view.id, logEntries?.length ?? 0)}
            />
          ) : null}

          <CareerWrestlerDetail
            wrestler={detailWrestler}
            relationships={view.relationships}
            seasons={view.seasons}
            log={logEntries}
            onClose={() => setState((s) => ({ ...s, detail: null }))}
          />
        </>
      )}
    </Shell>
  );
}

function isTab(value: string | null): value is CareerTab {
  return (
    value === "dashboard" ||
    value === "week" ||
    value === "world" ||
    value === "matches" ||
    value === "titles" ||
    value === "log"
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:py-10">
        <header className="mb-6">
          <h1 className="font-sport text-2xl text-foreground sm:text-3xl">커리어</h1>
          <p className="mt-2 rounded-xl border border-dashed border-border px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            한 시즌은 서버가 정한 주차만큼이고, 시즌이 끝나면 결산에서 나이가 한 살 오릅니다. 월드
            챔피언은 끝이 아니라 중간 목표이고, 커리어는{" "}
            <strong className="text-foreground">은퇴</strong>로 끝납니다. 은퇴해도 기록은 남습니다.{" "}
            <strong className="text-foreground">세이브는 서버에 저장됩니다</strong> — 저장 없이 돌려
            보려면{" "}
            <Link href="/sandbox/career" className="text-brand-link underline">
              장난감
            </Link>
            을 쓰세요. 실제 예측은{" "}
            <Link href="/ai-lab" className="text-brand-link underline">
              AI Lab
            </Link>
            이 합니다.
          </p>
        </header>
        {children}
      </div>
    </WweArenaShell>
  );
}
