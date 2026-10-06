import { RotateCcw } from "lucide-react";

import { Emphasis } from "@/components/portfolio/emphasis";
import { cn } from "@/lib/utils";

/**
 * 기술 흐름도 — 세로로 흐르는 단계 도면. 서버 컴포넌트다(상태도 fetch도 없다).
 *
 * **SVG 가 아니라 DOM 이다.** 좌표를 손으로 쥐지 않으므로 라이트/다크 토큰이
 * 그대로 먹고, 긴 한글 라벨이 칸을 넘기지 않고, 글자가 선택·검색된다. 대가는
 * 자유로운 분기선을 못 그리는 것이다 — 그래서 모델이 세로 한 줄이고, 병렬은
 * 한 단계에 칸을 나란히 두는 것으로, 빠지는 길은 단계 아래 갈라진 칸으로 적는다.
 *
 * **흐름은 레일 하나로 말한다** (2026-10-06). 전에는 단계마다 가운데 정렬된
 * 화살표를 두고 칸은 전폭, 빠지는 길은 또 다른 들여쓰기에 뒀다 — 왼쪽 끝이
 * 세 군데라 눈이 매 단계 좌우로 튀었고, 그것이 화면을 난잡하게 만든 원인이다.
 * 지금은 **왼쪽 세로선 하나가 모든 줄의 기준**이고, 화살표 글리프는 없앴다.
 * 순서는 `<ol>` 과 그 선이 말하고, 화살표에 적혀 있던 말은 칸 위로 올라갔다.
 *
 * **색은 둘만 쓴다** (DESIGN.md §2): 모델이 서는 자리에 블루, 빠지는 길에 레드.
 * 나머지 종류는 전부 중립 표면이고 칸마다 붙는 작은 머리말이 종류를 말한다 —
 * 색만으로 종류를 말하면 색각 이상에서 읽히지 않고, 네 번째 색을 만들게 된다.
 */

/** 칸의 종류. 색이 아니라 **머리말**로 갈린다. */
export type FlowNodeKind = "code" | "model" | "store" | "external" | "gate" | "output";

const KIND_LABEL: Record<FlowNodeKind, string> = {
  code: "코드",
  model: "모델",
  store: "저장",
  external: "외부",
  gate: "관문",
  output: "산출",
};

/** 모델 칸만 블루다 — 이 시스템에서 블루는 AI·데이터의 색이다. */
const KIND_STYLE: Record<FlowNodeKind, string> = {
  code: "border-border bg-card",
  model: "border-data/40 bg-data/10",
  store: "border-border bg-surface-2",
  external: "border-dashed border-border bg-surface-2",
  gate: "border-border bg-card-2",
  output: "border-border bg-card-2",
};

export type FlowNode = {
  label: string;
  kind: FlowNodeKind;
  /** 이 칸이 실제로 하는 일. 한 줄에 하나. */
  detail?: readonly string[];
  /** 실측값·근거. **실제로 재 본 값만 적는다.** */
  measured?: string;
};

export type FlowStep = {
  nodes: readonly FlowNode[];
  /** 칸이 둘 이상일 때 왜 나란한지 — "동시 호출" · "둘 중 하나". */
  parallel?: string;
  /** 이 단계로 들어오는 화살표에 붙는 말. 첫 단계는 비운다. */
  edge?: string;
  /** 여기서 빠져나가는 길 — 반려·보류·폴백. 레드는 이 자리에만 선다. */
  exit?: { label: string; detail: string };
  /** 되돌아가는 루프. 상한을 함께 적는다. */
  loop?: string;
};

export type Flow = {
  /** 도면 번호 — "01". 본문에서 "도 01" 로 가리킬 수 있게 둔다. */
  no: string;
  title: string;
  /** 한 줄 요약. 도면을 안 보고도 무슨 흐름인지 알 수 있게. */
  summary: string;
  steps: readonly FlowStep[];
  /** 도면 아래 각주 — 실측 환경, 감수한 트레이드오프, 안 하기로 한 것. */
  notes?: readonly string[];
};

export function FlowDiagram({ flow }: { flow: Flow }) {
  return (
    <figure
      id={flowAnchorId(flow.no)}
      className="scroll-mt-4 rounded-xl border border-border bg-background"
    >
      <figcaption className="border-b border-border px-4 py-3 sm:px-5">
        <p className="font-sport text-xs tracking-[0.2em] text-muted-foreground">도 {flow.no}</p>
        <h3 className="mt-1 text-base font-semibold text-foreground">{flow.title}</h3>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {flow.summary}
        </p>
      </figcaption>

      <div className="px-4 py-5 sm:px-5">
        {/* 레일은 `<li>` 의 왼쪽 테두리다. 마지막 단계만 선을 끊어 흐름이
            거기서 끝났음을 말한다 — 선이 허공으로 더 내려가지 않는다. */}
        <ol className="flex max-w-2xl flex-col">
          {flow.steps.map((step) => (
            <li
              key={step.nodes.map((n) => n.label).join("|")}
              className="relative border-l border-border pb-4 pl-5 last:border-transparent last:pb-0 sm:pl-6"
            >
              <span
                aria-hidden
                className="absolute -left-[3.5px] top-1.5 size-[7px] rounded-full bg-border"
              />
              <StepBlock step={step} />
            </li>
          ))}
        </ol>
      </div>

      {flow.notes && flow.notes.length > 0 && (
        <ul className="flex flex-col gap-1.5 border-t border-border px-4 py-3 text-xs leading-relaxed text-muted-foreground sm:px-5">
          {flow.notes.map((note) => (
            <li key={note} className="flex gap-1.5">
              <span aria-hidden>※</span>
              <span>
                <Emphasis text={note} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

/** 섹션 머리의 도면 목차가 가리키는 앵커. 도면과 목차가 같은 함수를 쓴다. */
export function flowAnchorId(no: string): string {
  return `flow-${no}`;
}

function StepBlock({ step }: { step: FlowStep }) {
  const isParallel = step.nodes.length > 1;
  /* 화살표에 적혀 있던 말과 병렬 사유는 같은 자리(칸 위 한 줄)에 선다.
     데이터에 `edge: ""` 가 섞여 있어 빈 문자열은 그냥 떨어져 나간다. */
  const lead = step.edge || (isParallel ? step.parallel : undefined);

  return (
    <div className="flex flex-col gap-2">
      {lead && <p className="text-xs leading-5 text-muted-foreground">{lead}</p>}

      <div
        className={cn(
          "grid gap-2",
          /* 병렬 칸은 폭을 나눠 쓰고, 모바일에서는 세로로 쌓인다. 셋까지만
             가로로 두는 이유는 넷이 되면 한 칸이 글자 두 자 폭이 된다. */
          isParallel && step.nodes.length === 2 && "sm:grid-cols-2",
          isParallel && step.nodes.length >= 3 && "sm:grid-cols-3",
        )}
      >
        {step.nodes.map((node) => (
          <NodeCard key={node.label} node={node} />
        ))}
      </div>

      {step.loop && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <RotateCcw aria-hidden className="size-3.5 shrink-0" />
          {step.loop}
        </p>
      )}

      {/* 빠져나가는 길. **칸이 아니라 주석으로 읽혀야 한다** — 테두리를 두른
          같은 모양이면 다음 단계로 이어지는 칸처럼 보이고, 그러면 반려가
          흐름의 일부가 된다. 그래서 들여쓰기 + 왼쪽 레드 막대만 남겼다. */}
      {step.exit && (
        <div className="ml-4 rounded-md border-l-2 border-live/60 bg-live/5 px-3 py-2">
          <p className="text-xs font-semibold text-live">{step.exit.label}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.exit.detail}</p>
        </div>
      )}
    </div>
  );
}

function NodeCard({ node }: { node: FlowNode }) {
  return (
    <div className={cn("rounded-xl border px-3 py-2.5", KIND_STYLE[node.kind])}>
      {/* 머리말과 이름이 **같은 줄**에 선다. 두 줄로 쌓으면 칸마다 높이가
          한 줄씩 늘고, 단계가 여덟이면 그것만으로 화면 한 장이 된다. */}
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span
          className={cn(
            "text-[0.6875rem] tracking-[0.12em]",
            node.kind === "model" ? "text-data" : "text-muted-foreground",
          )}
        >
          {KIND_LABEL[node.kind]}
        </span>
        <span className="text-sm font-semibold leading-snug text-foreground">{node.label}</span>
      </p>

      {node.detail && node.detail.length > 0 && (
        <ul className="mt-1.5 flex flex-col gap-0.5 text-xs leading-relaxed text-muted-foreground">
          {node.detail.map((line) => (
            <li key={line}>
              <Emphasis text={line} />
            </li>
          ))}
        </ul>
      )}

      {node.measured && (
        <p className="mt-1.5 border-t border-border pt-1.5 text-xs tabular-nums text-muted-foreground">
          {node.measured}
        </p>
      )}
    </div>
  );
}

/**
 * 칸 종류 범례. **도면마다 반복하지 않는다** — 페이지에 한 번 세워 두고,
 * 도면이 여럿이면 그 위에 한 번만 둔다.
 */
export function FlowLegend() {
  const items: readonly FlowNodeKind[] = ["code", "model", "store", "external", "gate", "output"];
  const WHAT: Record<FlowNodeKind, string> = {
    code: "결정론 코드 — 같은 입력이면 같은 출력",
    model: "언어·비전 모델",
    store: "저장소",
    external: "외부 서비스·공개 소스",
    gate: "관문 — 통과 못 하면 빠진다",
    output: "사람이 보는 산출물",
  };

  return (
    // 줄바꿈에 맡기면 여섯 항목의 왼쪽 끝이 전부 어긋난다 — 격자로 고정한다.
    <dl className="grid gap-x-5 gap-y-2 text-xs sm:grid-cols-2 lg:grid-cols-3">
      {items.map((kind) => (
        <div key={kind} className="flex items-baseline gap-2">
          <dt
            className={cn(
              "w-9 shrink-0 rounded-md border px-1.5 py-0.5 text-center tracking-[0.08em]",
              KIND_STYLE[kind],
              kind === "model" ? "text-data" : "text-muted-foreground",
            )}
          >
            {KIND_LABEL[kind]}
          </dt>
          <dd className="leading-5 text-muted-foreground">{WHAT[kind]}</dd>
        </div>
      ))}
    </dl>
  );
}
