"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/context/auth-context";
import { CareerDashboard } from "@/components/sandbox-career/career-dashboard";
import { CareerLogPanel } from "@/components/sandbox-career/career-log-panel";
import { CareerMatchDetailDialog } from "@/components/sandbox-career/career-match-detail";
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
  fetchCareerMatches,
  fetchCareers,
  newCareerRequestId,
  performCareerAction,
  resolveCareerEvent,
  settleCareerSeason,
  startNextCareerSeason,
  CAREER_DIVISIONS,
  type CareerAction,
  type CareerDivision,
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
import { recordForWeek } from "@/lib/career-match";

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
const DIVISION_LABEL: Readonly<Record<CareerDivision, string>> = {
  men: "남자부",
  women: "여자부",
};

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
/**
 * 열어 둔 경기 상세(`?tab=matches&match=s1w52:p`). **경기 탭에서만 뜻이 있다** —
 * 다른 탭으로 가면 지운다. 다이얼로그가 열려 있는지는 이 값 하나가 정한다(React
 * 상태에 따로 두지 않는다 — 두 곳에 있으면 서로를 고치다 무한 갱신이 난다).
 */
const MATCH_PARAM = "match";

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
  const [division, setDivision] = useState<CareerDivision>("men");

  const isSignedIn = user != null;
  const paramTab = params.get(TAB_PARAM);
  const tab: CareerTab = isTab(paramTab) ? paramTab : "dashboard";
  const paramCareer = Number(params.get(CAREER_PARAM));
  const wantedCareer = Number.isInteger(paramCareer) && paramCareer > 0 ? paramCareer : null;
  const openMatchId = tab === "matches" ? params.get(MATCH_PARAM) : null;

  /**
   * URL 한 줄에 커리어와 탭(과 경기)을 적는다 — 새로고침 복구가 이 값들로 끝난다.
   *
   * **탭·커리어 이동은 `replace`** 다(기존 정책 그대로). **경기 열기만 `push`** 다 —
   * 뒤로 가기가 다이얼로그를 닫아야 하기 때문이다. 경기 값은 탭을 옮기거나
   * 커리어를 바꾸면 지운다.
   */
  const writeUrl = useCallback(
    (
      next: { career?: number | null; tab?: CareerTab; match?: string | null },
      mode: "replace" | "push" = "replace",
    ) => {
      const search = new URLSearchParams(params.toString());
      if (next.career !== undefined) {
        if (next.career == null) search.delete(CAREER_PARAM);
        else search.set(CAREER_PARAM, String(next.career));
        search.delete(MATCH_PARAM);
      }
      if (next.tab !== undefined) {
        search.set(TAB_PARAM, next.tab);
        // 탭 이동은 경기를 들고 가지 않는다 — 경기 탭으로 가더라도. 다른 탭 URL 에
        // 남은 `match` 가 경기 탭에 들어서는 순간 다이얼로그로 되살아났다(브라우저
        // 실측). 경기를 열 때는 `match` 를 함께 넘긴다(`openMatch`).
        if (next.match === undefined) search.delete(MATCH_PARAM);
      }
      if (next.match !== undefined) {
        if (next.match == null) search.delete(MATCH_PARAM);
        else search.set(MATCH_PARAM, next.match);
      }
      const query = search.toString();
      const url = query ? `${pathname}?${query}` : pathname;
      if (mode === "push") router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [params, pathname, router],
  );

  /**
   * 이 화면이 `push` 로 연 경기. 닫을 때 **그 기록 항목이 지금 항목이면** 뒤로 가서
   * 닫는다 — 그래야 닫은 뒤 뒤로 가기가 같은 다이얼로그를 다시 열지 않는다. 딥링크로
   * 들어왔거나 앞으로 가기로 다시 열린 경우엔 `replace` 로 값만 지운다.
   */
  const pushedMatch = useRef<string | null>(null);
  const openMatch = useCallback(
    (matchId: string) => {
      pushedMatch.current = matchId;
      writeUrl({ tab: "matches", match: matchId }, "push");
    },
    [writeUrl],
  );
  const closeMatch = useCallback(() => {
    if (pushedMatch.current != null && pushedMatch.current === openMatchId) {
      pushedMatch.current = null;
      router.back();
      return;
    }
    pushedMatch.current = null;
    writeUrl({ match: null });
  }, [openMatchId, router, writeUrl]);

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

  /**
   * 지난 주 보고에 붙일 경기 기록 id. **서버가 준 id 만 쓴다** — 시즌·주차로 id 를
   * 지어내면 기록이 없는 경기(도입 전·잘림)에 죽은 링크가 생긴다. 최신 기록 하나를
   * 읽어 보고의 시즌·주차와 같을 때만 링크를 단다.
   */
  const [reportMatch, setReportMatch] = useState<{ key: string; id: string | null } | null>(null);

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
    // URL 에서 커리어가 빠졌다(목록으로 나갔다) — 다음에 같은 id 가 오면 다시 복구한다.
    if (wantedCareer == null) {
      restored.current = null;
      return;
    }
    if (state.view?.id === wantedCareer) return;
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

  // 지난 주 보고 → 경기 기록 id. 경기가 없던 주(휴식·결장)는 묻지 않는다.
  const reportCareer = state.view?.id ?? null;
  const lastReport = state.view?.lastReport ?? null;
  const reportSeason = lastReport?.opponent != null ? lastReport.season : null;
  const reportWeek = lastReport?.opponent != null ? lastReport.week : null;
  const reportKey =
    reportCareer != null && reportSeason != null && reportWeek != null
      ? `${reportCareer}:${reportSeason}:${reportWeek}`
      : null;
  useEffect(() => {
    if (reportKey == null || reportCareer == null || reportSeason == null || reportWeek == null)
      return;
    const controller = new AbortController();
    void fetchCareerMatches(
      reportCareer,
      { season: reportSeason, limit: 1, offset: 0 },
      controller.signal,
    ).then((result) => {
      if (controller.signal.aborted) return;
      // 실패하면 링크를 달지 않는다 — 보고 자체는 그대로 보인다.
      setReportMatch({
        key: reportKey,
        id: result.ok ? recordForWeek(result.rows, reportSeason, reportWeek) : null,
      });
    });
    return () => controller.abort();
  }, [reportKey, reportCareer, reportSeason, reportWeek]);
  const reportMatchId =
    reportMatch != null && reportMatch.key === reportKey ? reportMatch.id : null;

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
    // **지금 URL 의 커리어를 "이미 복구함" 으로 둔다.** `view` 를 비운 렌더가 URL 갱신
    // (`router.replace` — 비동기)보다 먼저 오므로, 그 사이 복구 효과가 낡은 `career`
    // 를 보고 방금 나온 커리어를 다시 읽어 들였다(2026-11-03 브라우저 실측 — 목록이
    // 안 열리고 대시보드로 돌아갔다). URL 이 따라오면 복구 효과가 이 값을 비운다.
    restored.current = wantedCareer;
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
  }, [wantedCareer, writeUrl]);

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
  // 단계 버튼 셋은 대시보드 히어로와 주간 진행 탭이 함께 쓴다 — 한 곳에서 정해야
  // 두 자리의 요청 범위(`advance` 등)가 갈라지지 않는다.
  const advance = () => {
    if (view)
      void run("advance", "advance", "한 주를 진행했습니다", (requestId) =>
        advanceCareerWeek(view.id, requestId),
      );
  };
  const settle = () => {
    if (view)
      void run("settle", "settle", "시즌을 결산했습니다", (requestId) =>
        settleCareerSeason(view.id, requestId),
      );
  };
  const nextSeason = () => {
    if (view)
      void run("next-season", "next-season", "다음 시즌을 시작했습니다", (requestId) =>
        startNextCareerSeason(view.id, requestId),
      );
  };
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
        <div className="mx-auto max-w-3xl">
          <section className="mb-8">
            <h2 className="font-sport text-2xl uppercase tracking-wide text-stone-50">내 커리어</h2>
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
                      className="arena-panel flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:border-brand-400/40 disabled:opacity-50"
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
            <h2 className="font-sport text-2xl uppercase tracking-wide text-stone-50">새 선수</h2>
            <div className="arena-panel mt-3 space-y-4 p-5">
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
                <span className="mb-1 block text-xs font-bold text-muted-foreground">디비전</span>
                <div className="grid grid-cols-2 gap-2 sm:max-w-sm">
                  {CAREER_DIVISIONS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setDivision(d)}
                      aria-pressed={division === d}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        division === d
                          ? "border-brand-400/70 bg-brand-400/10 text-stone-50"
                          : "border-white/10 bg-black/30 text-stone-400 hover:bg-white/[0.05]"
                      }`}
                    >
                      <span className="block font-bold">{DIVISION_LABEL[d]}</span>
                    </button>
                  ))}
                </div>
                <span className="mt-1 block text-[11px] text-muted-foreground">
                  세계에는 이 디비전의 실제 WWE 현역이 들어옵니다. 능력치·인기도는 실제 타이틀
                  이력과 나이로 낸 게임용 추정치이고, 전적은 모두 0승 0패에서 시작합니다.
                </span>
              </div>

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
                          ? "border-brand-400/70 bg-brand-400/10 text-stone-50"
                          : "border-white/10 bg-black/30 text-stone-400 hover:bg-white/[0.05]"
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
                    createCareer({ name: name.trim(), style, age, division }),
                  ).then((created) => {
                    if (created) writeUrl({ career: created.id, tab: "dashboard" });
                  })
                }
                disabled={state.busy != null || !name.trim()}
                className="arena-cta h-12 px-8 font-sport text-lg uppercase"
              >
                {state.busy === "create" ? "만드는 중…" : "▶ 데뷔"}
              </button>
            </div>
          </section>
        </div>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => void backToList()}
              disabled={state.busy != null}
              className="arena-ghost px-3 py-1 text-xs font-semibold disabled:opacity-50"
            >
              ← 커리어 목록
            </button>
            <span className="text-xs tabular-nums text-stone-400">
              세이브 #{view.id} · 서버 저장
            </span>
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
              reportMatchId={reportMatchId}
              onOpenMatch={openMatch}
              onAdvance={advance}
              onSettle={settle}
              onNextSeason={nextSeason}
            />
          ) : null}

          {tab === "week" ? (
            <CareerWeekPanel
              view={view}
              busy={state.busy}
              reportMatchId={reportMatchId}
              onOpenMatch={openMatch}
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
              onAdvance={advance}
              onSettle={settle}
              onNextSeason={nextSeason}
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
            <CareerMatchesPanel
              view={view}
              log={logEntries}
              logLoading={log.loading}
              onOpenMatch={openMatch}
            />
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

          <CareerMatchDetailDialog careerId={view.id} matchId={openMatchId} onClose={closeMatch} />
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
    // **다크 아레나는 이 페이지만이다** (DESIGN.md 예외 · 2026-11-02). `.dark` 가 토큰을
    // 이 트리 안에서만 다크로 바꾸고, `.career-arena` 가 경기장 조명을 깐다.
    <main className="dark career-arena relative min-h-screen w-full min-w-0 overflow-x-hidden text-foreground">
      <div className="relative mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="arena-eyebrow">Kayfabe · Career Mode</p>
            <h1 className="mt-1 font-sport text-3xl uppercase tracking-wide text-stone-50 sm:text-4xl">
              Wrestling Career
            </h1>
          </div>
          <details className="group max-w-xl text-xs text-stone-400">
            <summary className="cursor-pointer list-none text-right font-semibold uppercase tracking-wider text-stone-400 hover:text-stone-200">
              커리어 모드 안내{" "}
              <span className="inline-block transition-transform group-open:rotate-180">▾</span>
            </summary>
            <p className="mt-2 rounded-xl border border-dashed border-white/12 bg-black/40 px-3 py-2 text-xs leading-relaxed text-stone-400">
              한 시즌은 서버가 정한 주차만큼이고, 시즌이 끝나면 결산에서 나이가 한 살 오릅니다. 월드
              챔피언은 끝이 아니라 중간 목표이고, 커리어는{" "}
              <strong className="text-foreground">은퇴</strong>로 끝납니다. 은퇴해도 기록은
              남습니다. <strong className="text-foreground">세이브는 서버에 저장됩니다</strong> —
              저장 없이 돌려 보려면{" "}
              <Link href="/sandbox/career" className="text-brand-link underline">
                장난감
              </Link>
              을 쓰세요. 실제 예측은{" "}
              <Link href="/ai-lab" className="text-brand-link underline">
                AI Lab
              </Link>
              이 합니다.
            </p>
          </details>
        </header>
        {children}
      </div>
    </main>
  );
}
