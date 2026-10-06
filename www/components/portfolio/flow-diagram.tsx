import { ChevronDown, CornerDownRight, RotateCcw } from "lucide-react";

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
    <figure className="rounded-xl border border-border bg-background">
      <figcaption className="border-b border-border px-4 py-3 sm:px-5">
        <p className="font-sport text-xs tracking-[0.2em] text-muted-foreground">도 {flow.no}</p>
        <h3 className="mt-1 text-base font-semibold text-foreground">{flow.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{flow.summary}</p>
      </figcaption>

      <div className="px-4 py-5 sm:px-5">
        <ol className="flex flex-col">
          {flow.steps.map((step, index) => (
            <li key={step.nodes.map((n) => n.label).join("|")}>
              {index > 0 && <Connector label={step.edge} />}
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

/**
 * 단계 사이의 화살표. `aria-hidden` 인 이유: 순서는 `<ol>` 이 이미 말하고,
 * 화살표 글리프를 읽어 주면 단계마다 "아래쪽 꺾쇠"가 끼어든다. 화살표에 적힌
 * **말**(`label`)은 정보라 남긴다.
 */
function Connector({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-1.5">
      <div className="flex flex-col items-center" aria-hidden>
        <span className="h-3 w-px bg-border" />
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </div>
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  );
}

function StepBlock({ step }: { step: FlowStep }) {
  const isParallel = step.nodes.length > 1;

  return (
    <div className="flex flex-col gap-2">
      {isParallel && step.parallel && (
        <p className="text-center text-xs text-muted-foreground">{step.parallel}</p>
      )}

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
        <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
          <RotateCcw aria-hidden className="size-3.5" />
          {step.loop}
        </p>
      )}

      {/* 빠져나가는 길. **본 흐름보다 좁게 둔다** — 같은 폭이면 다음 단계로
          이어지는 칸처럼 읽히고, 그러면 반려가 흐름의 일부가 된다. 들여쓰기와
          꺾인 화살표, 좁은 폭 셋이 "여기서 끝난다"를 말하는 장치다. */}
      {step.exit && (
        <div className="flex gap-2 pl-4 sm:pl-10">
          <CornerDownRight aria-hidden className="mt-2 size-4 shrink-0 text-live" />
          <div className="min-w-0 rounded-lg border border-live/40 bg-live/5 px-3 py-2 sm:max-w-lg">
            <p className="text-xs font-semibold text-live">{step.exit.label}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              {step.exit.detail}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function NodeCard({ node }: { node: FlowNode }) {
  return (
    <div className={cn("rounded-xl border px-3 py-2.5", KIND_STYLE[node.kind])}>
      <p
        className={cn(
          "text-[0.6875rem] tracking-[0.12em]",
          node.kind === "model" ? "text-data" : "text-muted-foreground",
        )}
      >
        {KIND_LABEL[node.kind]}
      </p>
      <p className="mt-0.5 text-sm font-semibold leading-snug text-foreground">{node.label}</p>

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
    <dl className="flex flex-wrap gap-x-4 gap-y-2 text-xs">
      {items.map((kind) => (
        <div key={kind} className="flex items-center gap-1.5">
          <dt
            className={cn(
              "rounded-md border px-1.5 py-0.5 tracking-[0.12em]",
              KIND_STYLE[kind],
              kind === "model" ? "text-data" : "text-muted-foreground",
            )}
          >
            {KIND_LABEL[kind]}
          </dt>
          <dd className="text-muted-foreground">{WHAT[kind]}</dd>
        </div>
      ))}
    </dl>
  );
}
