"use client";

import { useEffect, useState } from "react";
import { AiLabShell } from "@/components/ai-lab/ai-lab-shell";
import { IntegrityBanner } from "@/components/ai-lab/integrity-banner";
// 대시보드 공통 조각은 데이터 센터(Phase 2)의 것을 그대로 쓴다.
import {
  DataUnavailable,
  LoadingBlock,
  StatTile,
} from "@/components/data-center/data-center-shell";
import {
  agentLabel,
  fetchAiLabKnowledge,
  formatRatio,
  type AiLabKnowledge,
  type KnowledgeDocument,
} from "@/lib/ai-lab-api";
import { cn } from "@/lib/utils";

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: AiLabKnowledge }
  | { status: "error" };

/**
 * Knowledge (Phase 3-4).
 *
 * 이 화면이 답하는 질문은 "코퍼스에 무엇이 있는가"가 아니라 **"그중 무엇이 실제로
 * 쓰였는가"** 다. 문서를 모아 두는 것과 그 문서가 프롬프트에 들어가는 것은 다르고,
 * 갈리는 자리가 이 화면의 존재 이유다.
 *
 * **검색을 돌리지 않는다.** 저장된 리포트의 출처와 문서 목록을 URL로 맞춰 볼 뿐이라
 * 화면 진입이 임베딩·LLM 비용을 만들지 않는다 — 다른 AI LAB 화면과 같은 규칙이다.
 */
export default function AiLabKnowledgePage() {
  const [state, setState] = useState<PageState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    void (async () => {
      const data = await fetchAiLabKnowledge();
      if (!alive) return;
      setState(data ? { status: "ready", data } : { status: "error" });
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AiLabShell
      title="Knowledge"
      description="에이전트가 근거로 쓰는 문서 코퍼스와, 그중 실제로 프롬프트에 들어간 문서."
    >
      {state.status === "loading" && <LoadingBlock rows={4} />}
      {state.status === "error" && <DataUnavailable what="지식 코퍼스" />}
      {state.status === "ready" && <Knowledge data={state.data} />}
    </AiLabShell>
  );
}

function Knowledge({ data }: { data: AiLabKnowledge }) {
  const { totals, integrity, documents, domains } = data;
  const missingEmbedding = totals.chunks - totals.chunksEmbedded;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile value={totals.documents} label="Documents" note="출처 URL 하나가 문서 하나" />
        <StatTile
          value={totals.chunks}
          label="Chunks"
          note={
            missingEmbedding > 0
              ? `임베딩 없음 ${missingEmbedding} — 검색되지 않음`
              : "전부 임베딩되어 검색 대상"
          }
          tone="data"
        />
        <StatTile value={totals.domains} label="Domains" note="허용 도메인 안에서만 수집" />
        <StatTile
          value={isoDate(totals.lastCollectedAt)}
          label="Last collected"
          note="가장 최근 수집 시각"
        />
      </div>

      <CorpusUsage totals={totals} />

      {/* 발행일 0건이라는 판정의 원인이 바로 이 코퍼스다 — 같은 상자를 여기에도 세운다. */}
      <IntegrityBanner integrity={integrity} />

      {domains.length > 0 && <Domains domains={domains} />}

      {documents.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border bg-card/50 px-4 py-8 text-center text-sm text-muted-foreground">
          적재된 지식이 없습니다 — 에이전트는 의견 없음만 냅니다.
        </p>
      ) : (
        <section aria-labelledby="documents-heading" className="flex flex-col gap-3">
          <h2 id="documents-heading" className="font-sport text-base tracking-wide text-foreground">
            Documents
          </h2>
          <ul className="flex flex-col gap-2">
            {documents.map((document) => (
              <DocumentRow key={document.sourceUrl} doc={document} />
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        &ldquo;사용됨&rdquo;은 인용 주장이 아니라{" "}
        <strong className="font-semibold">적재 기록</strong>입니다 — 저장된 출처가 실제로 프롬프트에
        넣은 청크의 주소이기 때문에 셀 수 있습니다. 다만 리포트당 상위 5청크·최대 5출처만 남으므로
        이 수치는 <strong className="font-semibold">하한</strong>입니다. 어떤 청크가 어떤 유사도로
        검색됐는지는 지금 구조가 기록하지 않습니다.
      </p>
    </div>
  );
}

/**
 * 코퍼스가 얼마나 쓰였는가 — **비율 하나라서 미터 바 하나다**(DESIGN.md §16).
 * 분모를 옆에 함께 적는다: 5/31과 5/6은 같은 비율이 아니다.
 */
function CorpusUsage({ totals }: { totals: AiLabKnowledge["totals"] }) {
  const percent = totals.usedDocumentRate === null ? 0 : totals.usedDocumentRate * 100;

  return (
    <section
      aria-labelledby="usage-heading"
      className="rounded-xl border border-border bg-card px-4 py-4 sm:px-5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="usage-heading" className="font-sport text-base tracking-wide text-foreground">
          Corpus usage
        </h2>
        <p className="text-sm tabular-nums text-foreground">
          {formatRatio(totals.usedDocumentRate)}{" "}
          <span className="text-muted-foreground">
            ({totals.usedDocuments}/{totals.documents} documents)
          </span>
        </p>
      </div>

      <div
        role="img"
        aria-label={`문서 ${totals.documents}건 중 ${totals.usedDocuments}건이 프롬프트에 들어갔습니다.`}
        className="mt-3 h-2 w-full overflow-hidden rounded bg-surface-2"
      >
        <div className="h-full rounded bg-data-400" style={{ width: `${percent}%` }} />
      </div>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        <Fact
          label="Reports with sources"
          value={`${totals.reportsWithSources} / ${totals.reportsTotal} reports`}
        />
        <Fact
          label="Sources outside corpus"
          value={`${totals.sourcesOutsideCorpus}`}
          tone={totals.sourcesOutsideCorpus > 0 ? "warn" : "default"}
        />
      </dl>

      {totals.usedDocuments < totals.documents && (
        <p className="mt-3 text-xs text-muted-foreground">
          문서 {totals.documents - totals.usedDocuments}건은 저장된 리포트의 출처에 한 번도 나오지
          않았습니다. 검색 상위에 못 들었거나, 그 경기와 무관한 문서입니다.
        </p>
      )}
      {totals.sourcesOutsideCorpus > 0 && (
        <p className="mt-1 text-xs text-live">
          출처 {totals.sourcesOutsideCorpus}건이 지금 코퍼스에 없습니다 — 그 문서가 재수집 과정에서
          지워졌거나 주소가 바뀌었습니다.
        </p>
      )}
    </section>
  );
}

function Domains({ domains }: { domains: AiLabKnowledge["domains"] }) {
  return (
    <section aria-labelledby="domains-heading" className="flex flex-col gap-3">
      <h2 id="domains-heading" className="font-sport text-base tracking-wide text-foreground">
        Domains
      </h2>
      <ul className="flex flex-col gap-2">
        {domains.map((domain) => (
          <li
            key={domain.domain}
            className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-xl border border-border bg-card px-4 py-3"
          >
            <span className="text-sm text-foreground">{domain.domain}</span>
            <span className="text-xs tabular-nums text-muted-foreground">
              문서 {domain.documents} · 청크 {domain.chunks} · 사용 {domain.usedDocuments}/
              {domain.documents}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** 문서 한 줄. 쓰인 문서와 안 쓰인 문서를 **글자로** 구분한다 — 색만으로 말하지 않는다. */
function DocumentRow({ doc }: { doc: KnowledgeDocument }) {
  const missingEmbedding = doc.chunks - doc.chunksEmbedded;
  const collected = isoDate(doc.lastCollectedAt);

  return (
    <li className="rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">
            {doc.title ?? doc.sourceUrl}
          </p>
          <a
            href={doc.sourceUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-0.5 block truncate text-xs text-brand-link underline underline-offset-2 hover:text-brand-hover"
          >
            {doc.sourceUrl}
          </a>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="text-xs tabular-nums text-muted-foreground">
            청크 {doc.chunks}
            {collected && ` · 수집 ${collected}`}
          </span>
          <UsageBadge doc={doc} />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {doc.usedByAgents.length > 0 && (
          <Note tone="neutral">{doc.usedByAgents.map(agentLabel).join(" · ")}</Note>
        )}
        {missingEmbedding > 0 && (
          <Note tone="warn">
            임베딩 없는 청크 {missingEmbedding}/{doc.chunks} — 검색되지 않습니다
          </Note>
        )}
        {doc.chunksWithPublishedAt === 0 && (
          <Note tone="neutral">발행일 없음 — 작성 시점을 알 수 없습니다</Note>
        )}
      </div>
    </li>
  );
}

/** 쓰였는지 여부. **0을 빈칸으로 두지 않는다** — 안 쓰였다는 것도 사실이다. */
function UsageBadge({ doc }: { doc: KnowledgeDocument }) {
  if (doc.usedByReports === 0) {
    return (
      <span className="rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
        미사용
      </span>
    );
  }
  return (
    <span className="rounded border border-data-500/50 bg-data-surface px-1.5 py-0.5 text-xs tabular-nums text-data">
      리포트 {doc.usedByReports}건에 사용
    </span>
  );
}

function Fact({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warn";
}) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm tabular-nums", tone === "warn" ? "text-live" : "text-foreground")}>
        {value}
      </dd>
    </div>
  );
}

/** 사실만 적는다 — "이 문서가 더 낫다" 같은 해석은 화면이 하지 않는다. */
function Note({ tone, children }: { tone: "neutral" | "warn"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-xs",
        tone === "warn"
          ? "border-live/50 bg-live/10 text-live"
          : "border-border text-muted-foreground",
      )}
    >
      {children}
    </span>
  );
}

/** 날짜만 적는다. 로캘에 따라 흔들리지 않게 ISO 그대로 쓴다. */
function isoDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}
