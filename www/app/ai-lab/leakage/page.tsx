"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { SeverityBadge, StatusBadge } from "@/components/ai-lab/eligibility-badges";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  fetchAiLabLeakage,
  type AiLabLeakage,
  type LeakageDocument,
  type LeakageEdge,
  type RuleDefinition,
} from "@/lib/ai-lab-api";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabLeakage }
  | { status: "error" };

/**
 * Leakage (Phase 10).
 *
 * **"실격 12건"은 이미 다른 화면이 말한다. 여기서 묻는 것은 무엇 때문인가다.**
 * 평가 화면은 예측 단위로 판정을 내고, 지식 화면은 문서가 쓰였는지를 센다. 그 둘을
 * 잇는 간선이 없어서, 코퍼스에서 무엇을 걷어내야 하는지는 매번 손으로 찾아야 했다.
 *
 * **판정을 다시 하지 않는다.** 줄에 붙은 상태는 평가 화면이 낸 것과 같은 계산에서
 * 나온다. 문서 기여는 규칙이 쓰는 것과 같은 함수로 읽고, "단독 원인"만 반사실이다.
 *
 * **문서를 지운다고 이미 만들어진 예측이 되살아나지는 않는다.** 그 예측은 그 글을
 * 실제로 읽었다. 이 화면이 쓰이는 자리는 과거가 아니라 **다음 수집**이다.
 */
export default function AiLabLeakagePage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabLeakage();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="근거 오염"
      description="성적에서 뺀 예측을 근거가 된 글까지 되짚습니다. 어느 글이 몇 건을 못 쓰게 만들었는지 봅니다."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="근거 오염 기록" />}
      {state.status === "ready" && <Leakage data={state.data} />}
    </AiLabShell>
  );
}

function Leakage({ data }: { data: AiLabLeakage }) {
  const { totals, integrity, documents, rules } = data;
  const ruleByCode = new Map(rules.map((rule) => [rule.code, rule]));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          value={totals.blockedPredictions}
          label="못 쓰게 된 예측"
          note="성적에서 뺀 것과 보류한 것"
        />
        <StatTile
          value={totals.attributed}
          label="원인이 된 글을 찾은 것"
          note="어느 글 때문인지 짚을 수 있음"
          tone="data"
        />
        {/* **감추지 않는다.** 문서로 못 돌리는 이유가 있고, 그 수가 곧 그래프의 한계다. */}
        <StatTile
          value={totals.unattributed}
          label="글 탓이 아닌 것"
          note="순서가 뒤집혔다거나, 글과 무관한 이유"
        />
        <StatTile
          value={totals.documents}
          label="문제가 된 글"
          note={`혼자서 막은 경우 ${totals.soleCausePredictions}건`}
        />
      </div>

      <IntegrityBanner integrity={integrity} />

      <Legend rules={rules} unattributed={totals.unattributed} />

      {documents.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
          {totals.blockedPredictions === 0
            ? "성적에서 뺀 예측이 없습니다."
            : "못 쓰게 된 예측은 있지만, 특정 글 때문인 것은 없습니다 — 전부 다른 이유입니다."}
        </p>
      ) : (
        <section aria-labelledby="documents-heading" className="flex flex-col gap-3">
          <h2 id="documents-heading" className="font-sport text-base tracking-wide text-foreground">
            문제가 된 글
          </h2>
          <ul className="flex flex-col gap-2">
            {documents.map((document) => (
              <DocumentCard key={document.sourceUrl} doc={document} rules={ruleByCode} />
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        그 글을 지금 지워도{" "}
        <strong className="font-semibold">이미 만들어진 예측은 되살아나지 않습니다</strong> — 그
        예측은 그 글을 실제로 읽고 나왔기 때문입니다. &ldquo;혼자서 막았다&rdquo;는 말은 지우면
        된다는 뜻이 아니라, 그 글 하나만으로 그 판단이 결정됐다는 사실입니다.
      </p>
    </div>
  );
}

/**
 * 이 화면이 **무엇을 말하지 않는지**를 먼저 적는다.
 *
 * 규칙 여덟 중 셋만 문서에 돌릴 수 있다. 그 사실을 적지 않으면 화면이 "실격은 전부
 * 문서 탓"이라고 말하는 셈이 된다.
 */
function Legend({ rules, unattributed }: { rules: RuleDefinition[]; unattributed: number }) {
  return (
    <section
      aria-labelledby="legend-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <h2 id="legend-heading" className="font-sport text-base tracking-wide text-foreground">
        글 탓으로 볼 수 있는 경우
      </h2>
      <ul className="mt-3 flex flex-col gap-2.5">
        {rules.map((rule) => (
          <li key={rule.code} className="text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-foreground">{rule.label}</span>
              <span className="text-muted-foreground">({rule.code})</span>
              <SeverityBadge severity={rule.severity} />
            </div>
            <p className="mt-1 text-muted-foreground">{rule.description}</p>
          </li>
        ))}
      </ul>
      {unattributed > 0 && (
        <p className="mt-3 border-t border-border/60 pt-3 text-xs text-muted-foreground">
          나머지는 읽은 글과 상관없이 예측 자체에 문제가 있던 경우입니다 — 결과가 나온 뒤에 만들어진
          예측, 대진표에서 빠진 경기 같은 것들입니다. 지금{" "}
          <strong className="font-semibold">{unattributed}건</strong>이 그런 이유로 빠져 있고, 아래
          목록에는 나오지 않습니다.
        </p>
      )}
    </section>
  );
}

function DocumentCard({
  doc,
  rules,
}: {
  doc: LeakageDocument;
  rules: Map<string, RuleDefinition>;
}) {
  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3.5 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
        <a
          href={doc.sourceUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="min-w-0 flex-1 truncate text-sm text-foreground hover:text-data"
        >
          {doc.sourceUrl}
        </a>
        <p className="shrink-0 text-sm tabular-nums text-muted-foreground">
          {doc.blocked}건 막음
          {/* 0이면 적지 않는다 — "단독 원인 0"은 화면에서 배경이 된다. */}
          {doc.soleCause > 0 && <span className="text-live"> · 단독 원인 {doc.soleCause}</span>}
        </p>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {doc.codes.map((code) => (
          <span
            key={code}
            className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-xs text-live"
          >
            {rules.get(code)?.label ?? code}
          </span>
        ))}
      </div>

      <ul className="mt-2.5 flex flex-col gap-1.5 border-t border-border/60 pt-2.5">
        {doc.predictions.map((edge) => (
          <EdgeRow key={`${edge.eventSlug}/${edge.matchKey}`} edge={edge} />
        ))}
      </ul>
    </li>
  );
}

function EdgeRow({ edge }: { edge: LeakageEdge }) {
  return (
    <li className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs">
      <StatusBadge status={edge.status} />
      {/* 한 건의 계보로 바로 갈 수 있어야 한다 — 그래프에서 증거까지가 한 걸음이다. */}
      <Link
        href={`/ai-lab/audit/${encodeURIComponent(edge.eventSlug)}/${encodeURIComponent(edge.matchKey)}`}
        className="min-w-0 truncate text-foreground hover:text-data"
      >
        {edge.eventLabel} · {edge.matchTitle}
      </Link>
      {edge.soleCause && (
        <span className="rounded border border-live/50 bg-live/10 px-1.5 py-0.5 text-live">
          이 문서가 혼자 막음
        </span>
      )}
      {/* **근거가 사라져서 통과하는 경우와 구분한다.** 둘을 같은 배지로 칠하면
          화면이 "이 문서를 지우면 된다"고 권하는 꼴이 된다. */}
      {edge.soleEvidence && (
        <span className="rounded border border-border px-1.5 py-0.5 text-muted-foreground">
          이 예측의 유일한 근거
        </span>
      )}
    </li>
  );
}
