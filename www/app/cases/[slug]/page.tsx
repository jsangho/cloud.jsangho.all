import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Github, Mail } from "lucide-react";

import { Emphasis } from "@/components/portfolio/emphasis";
import { FlowDiagram, FlowLegend } from "@/components/portfolio/flow-diagram";
import { ThemeToggle } from "@/components/theme-toggle";
import { CASES, findCase, type CaseStudy } from "@/lib/portfolio-cases";

/**
 * 프로젝트 상세 — `jsangho.cloud/cases/<slug>` (2026-10-06).
 *
 * 첫 화면의 카드는 바깥 사이트로 바로 나갔다. 그러면 **무엇을 어떻게 만들었는지**를
 * 적을 자리가 없어서, 카드가 이제 이 경로로 들어오고 실제 사이트 링크는 이 안에 둔다.
 *
 * `/cases/*` 는 `middleware.ts` 의 `PROJECT_PATHS` 에 없다 — 그래서 포트폴리오
 * 호스트에 그대로 머문다. 제품 경로 목록에 넣으면 제품 호스트로 307 된다.
 *
 * 서버 컴포넌트다. 상태도 fetch 도 없고, 적힌 값은 전부 측정해 고정한 사실이다.
 */

const GITHUB_URL = "https://github.com/jsangho";
const EMAIL = "leicestercity12968@gmail.com";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return CASES.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const study = findCase(slug);
  if (!study) return {};

  return {
    title: `${study.name} — ${study.tagline}`,
    /* `lede` 첫 단락에는 강조 표시(`**`)가 섞여 있다. 메타 설명은 평문이라야
       하므로 여기서 떼어 낸다 — 검색 결과에 별표가 그대로 나가는 것을 막는다. */
    description: study.lede[0]?.replaceAll("**", ""),
  };
}

export default async function CasePage({ params }: Props) {
  const { slug } = await params;
  const study = findCase(slug);
  if (!study) notFound();

  return (
    <main className="min-h-dvh bg-background">
      <header className="mx-auto flex w-full max-w-4xl items-center justify-between px-4 py-5">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft aria-hidden className="size-4" />
          <span className="font-sport tracking-wide">SANGHO JEONG</span>
        </Link>
        <div className="flex items-center gap-2">
          <a
            href={GITHUB_URL}
            aria-label="GitHub"
            className="inline-flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-card-2 hover:text-foreground"
          >
            <Github className="size-4" />
          </a>
          <a
            href={`mailto:${EMAIL}`}
            aria-label="이메일"
            className="inline-flex size-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-card-2 hover:text-foreground"
          >
            <Mail className="size-4" />
          </a>
          <ThemeToggle />
        </div>
      </header>

      <Hero study={study} />
      <Facts study={study} />
      <Why study={study} />
      <Flows study={study} />
      <Decisions study={study} />
      <Stack study={study} />
      <Limits study={study} />
      <OtherCases slug={study.slug} />

      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground">
          <span>정상호 · 2026</span>
          <Link href="/" className="underline-offset-4 hover:text-foreground hover:underline">
            포트폴리오로 돌아가기
          </Link>
        </div>
      </footer>
    </main>
  );
}

function Hero({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pt-6 pb-12 sm:pt-10">
      <p className="font-sport text-sm tracking-[0.3em] text-brand-link">CASE</p>
      <h1 className="mt-3 font-sport text-4xl leading-tight text-foreground sm:text-5xl">
        {study.name}
      </h1>
      <p className="mt-2 text-base text-muted-foreground">{study.tagline}</p>

      <dl className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <div className="flex gap-2">
          <dt className="text-muted-foreground">기간</dt>
          <dd className="tabular-nums text-foreground">{study.period}</dd>
        </div>
        {study.role && (
          <>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">규모</dt>
              <dd className="text-foreground">{study.role.team}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">담당</dt>
              <dd className="text-foreground">{study.role.mine}</dd>
            </div>
          </>
        )}
      </dl>

      <div className="relative mt-7 aspect-[16/9] w-full overflow-hidden rounded-2xl border border-border">
        <Image
          src={study.image}
          alt={study.imageAlt}
          fill
          sizes="(max-width: 896px) 100vw, 896px"
          className="object-cover object-top"
          priority
        />
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {study.links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="inline-flex max-w-full items-center gap-2 rounded-full border border-border px-4 py-2 text-sm text-foreground transition-colors hover:bg-card-2"
          >
            <span className="truncate font-mono text-xs">{link.label}</span>
            {link.note && (
              <span className="shrink-0 text-xs text-muted-foreground">· {link.note}</span>
            )}
            <ArrowUpRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          </a>
        ))}
      </div>
    </section>
  );
}

/**
 * 실측 수치 타일. **차트가 아니라 KPI 타일이다** — 숫자 하나가 결론인 자리에
 * 그래프를 그리지 않는다 (DESIGN.md §16). `note` 가 분모와 측정일을 싣는다.
 */
function Facts({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="facts">
      <h2 id="facts" className="font-sport text-xl text-foreground">
        실측
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        측정한 값만 적었습니다. 측정하지 않은 칸은 비워 둡니다.
      </p>

      <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {study.facts.map((fact) => (
          <div key={fact.label} className="rounded-xl border border-border bg-card px-4 py-3">
            <dt className="text-xs text-muted-foreground">{fact.label}</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums leading-none text-foreground">
              {fact.value}
            </dd>
            {fact.note && (
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{fact.note}</p>
            )}
          </div>
        ))}
      </dl>
    </section>
  );
}

function Why({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="why">
      <h2 id="why" className="font-sport text-xl text-foreground">
        왜 만들었나
      </h2>
      <div className="mt-4 flex max-w-2xl flex-col gap-3 text-base leading-relaxed text-muted-foreground">
        {study.lede.map((paragraph) => (
          <p key={paragraph}>
            <Emphasis text={paragraph} />
          </p>
        ))}
      </div>

      {study.role && (
        <div className="mt-7 max-w-2xl rounded-xl border border-border bg-card p-4 sm:p-5">
          <h3 className="text-sm font-semibold text-foreground">업무 분담</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            팀 작업이라 적어 둡니다. 아래 도면에서 제 몫이 아닌 칸은 「팀원 담당」으로 표시했습니다.
          </p>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            {study.role.members.map((member) => (
              <div key={member.name} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
                <dt className="w-16 shrink-0 font-semibold text-foreground">{member.name}</dt>
                <dd className="text-muted-foreground">{member.part}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}

function Flows({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="flows">
      <h2 id="flows" className="font-sport text-xl text-foreground">
        기술 흐름
      </h2>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
        도면 {study.flows.length}장입니다. 위에서 아래로 흐르고, 나란한 칸은 동시에 일어나는
        일입니다. 빨간 칸은 그 자리에서{" "}
        <strong className="font-semibold text-foreground">빠져나가는 길</strong> —
        반려·보류·폴백입니다.
      </p>

      <div className="mt-4 rounded-xl border border-border bg-surface-2 px-4 py-3">
        <FlowLegend />
      </div>

      <div className="mt-5 flex flex-col gap-5">
        {study.flows.map((flow) => (
          <FlowDiagram key={flow.no} flow={flow} />
        ))}
      </div>
    </section>
  );
}

function Decisions({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="decisions">
      <h2 id="decisions" className="font-sport text-xl text-foreground">
        정한 것과 거부한 것
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
        만든 것보다 안 만든 것이 설계입니다. 왜 그렇게 정했는지를 함께 적었습니다.
      </p>

      <ol className="mt-5 flex flex-col gap-3">
        {study.decisions.map((decision, index) => (
          <li
            key={decision.title}
            className="rounded-xl border border-border bg-card p-4 sm:flex sm:gap-5 sm:p-5"
          >
            <span className="font-sport text-sm tabular-nums text-muted-foreground sm:w-8 sm:shrink-0">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0">
              <h3 className="mt-1 text-base font-semibold text-foreground sm:mt-0">
                {decision.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                <Emphasis text={decision.body} />
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Stack({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="stack">
      <h2 id="stack" className="font-sport text-xl text-foreground">
        이 프로젝트에서 쓴 것
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        실제로 돌아가는 것만 적었습니다. 각 기술이 어디에 쓰이는지는 위 도면이 말합니다.
      </p>

      <dl className="mt-5 flex flex-col gap-4">
        {study.stack.map(({ group, items }) => (
          <div
            key={group}
            className="grid grid-cols-1 gap-2 border-t border-border pt-4 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-4"
          >
            <dt className="text-sm font-semibold text-foreground">{group}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <span
                  key={item}
                  className="rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground"
                >
                  {item}
                </span>
              ))}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/**
 * 한계. **이 자리를 비워 두면 위의 전부가 과장이 된다** — 못 한 것을 적지 않은
 * 포트폴리오는 다 됐다고 말하는 것과 같다.
 */
function Limits({ study }: { study: CaseStudy }) {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="limits">
      <h2 id="limits" className="font-sport text-xl text-foreground">
        아직 못 한 것
      </h2>
      <ul className="mt-4 flex max-w-2xl flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
        {study.limits.map((limit) => (
          <li key={limit} className="border-l-2 border-border pl-4">
            <Emphasis text={limit} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function OtherCases({ slug }: { slug: string }) {
  const others = CASES.filter((item) => item.slug !== slug);
  if (others.length === 0) return null;

  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-16" aria-labelledby="others">
      <h2 id="others" className="font-sport text-xl text-foreground">
        다른 프로젝트
      </h2>
      <div className="mt-4 flex flex-col gap-3">
        {others.map((item) => (
          <Link
            key={item.slug}
            href={`/cases/${item.slug}`}
            className="group flex items-center justify-between gap-4 rounded-xl border border-border bg-card px-4 py-4 transition-colors hover:bg-card-2 sm:px-5"
          >
            <div className="min-w-0">
              <p className="font-sport text-xl leading-tight text-foreground">{item.name}</p>
              <p className="mt-0.5 truncate text-sm text-muted-foreground">{item.tagline}</p>
            </div>
            <ArrowUpRight
              aria-hidden
              className="size-5 shrink-0 text-muted-foreground transition-colors group-hover:text-brand-link"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}
