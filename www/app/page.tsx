import { Github, Mail } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProjectBanner, type PortfolioProject } from "@/components/portfolio/project-banner";

/**
 * 개인 포트폴리오 — `www.jsangho.cloud` 의 첫 화면 (2026-09-30).
 *
 * 이 경로에는 **제품 내비게이션이 붙지 않는다**. KAYFABE 의 크롬은
 * `app/(kayfabe)/layout.tsx` 로 내려갔고, 호스트 분기는 `middleware.ts` 가 한다.
 *
 * 서버 컴포넌트로 둔다 — 상태도 fetch 도 없고, 적힌 값은 전부 고정된 사실이다.
 */

const GITHUB_URL = "https://github.com/jsangho";
const EMAIL = "leicestercity12968@gmail.com";

/** 이 저장소에서 실제로 쓰는 것만 적는다 — 이력서용 나열을 만들지 않는다. */
const STACK: { group: string; items: string[] }[] = [
  { group: "언어", items: ["Python 3.13", "TypeScript", "Dart", "SQL"] },
  {
    group: "백엔드",
    items: ["FastAPI", "SQLAlchemy 2.0 async", "SQLModel", "Alembic", "Pydantic", "pytest"],
  },
  {
    group: "프론트엔드",
    items: ["Next.js 16", "React 19", "Tailwind CSS", "Radix UI", "Recharts", "Flutter"],
  },
  { group: "데이터", items: ["PostgreSQL", "pgvector", "Neo4j", "Redis", "Supabase"] },
  { group: "AI", items: ["Google Gemini", "RAG", "BAAI/bge-m3", "Kiwi 형태소"] },
  {
    group: "인프라",
    items: ["Docker", "k3s", "AWS EC2", "Vercel", "Cloudflare Tunnel", "GitHub Actions"],
  },
];

const PROJECTS: PortfolioProject[] = [
  {
    name: "KAYFABE",
    tagline: "WWE 경기 예측 · 데이터 분석 플랫폼",
    description:
      "세 개의 AI 에이전트가 각본 · 배당 · 소식을 근거로 경기 결과를 예측하고, 그 예측이 무엇을 읽고 나온 것인지를 함께 남깁니다. 적중률을 자랑하는 대신 그 숫자를 성적에 세도 되는지를 시스템이 스스로 판정합니다.",
    href: "https://kayfabe.jsangho.cloud",
    hrefLabel: "kayfabe.jsangho.cloud",
    image: "/projects/kayfabe-home.jpg",
    imageAlt: "KAYFABE 메인 화면 — WWE DATA & PREDICTION PLATFORM 히어로와 AI 예측 카드",
    facts: ["화면 19개", "테스트 1,182건", "아키텍처 계약 4", "커밋 369"],
  },
];

export default function PortfolioPage() {
  return (
    <main className="min-h-dvh bg-background">
      <header className="mx-auto flex w-full max-w-4xl items-center justify-between px-4 py-5">
        <span className="font-sport text-lg tracking-wide text-foreground">SANGHO JEONG</span>
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

      {/* ── 소개 ────────────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-4xl px-4 pt-10 pb-14 sm:pt-16">
        <p className="font-sport text-sm tracking-[0.3em] text-brand-link">PORTFOLIO</p>
        <h1 className="mt-4 text-3xl font-bold leading-[1.25] text-foreground sm:text-4xl">
          만든 것을
          <br />
          데이터로 검증합니다
        </h1>
        <div className="mt-6 flex max-w-2xl flex-col gap-3 text-base leading-relaxed text-muted-foreground">
          <p>
            백엔드와 프론트엔드를 함께 만듭니다. 최근 석 달은 WWE 경기 결과를 예측하는 플랫폼 하나에
            붙어 있었고, 적중률을 올리는 것보다{" "}
            <strong className="font-semibold text-foreground">
              그 숫자를 믿어도 되는지를 시스템이 스스로 판정하게
            </strong>{" "}
            만드는 데 대부분의 시간을 썼습니다.
          </p>
          <p>
            규칙은 문서가 아니라 게이트로 지킵니다. 앱 사이의 의존 방향과 레이어 순서를 CI가
            계약으로 검사하고, 어기면 커밋이 막힙니다. 표본이 모자란 지표는 0%로 채우지 않고 무엇이
            모자란지를 화면에 적습니다.
          </p>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <a
            href={PROJECTS[0].href}
            className="inline-flex h-10 items-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-brand-hover"
          >
            KAYFABE 보러 가기
          </a>
          <a
            href={GITHUB_URL}
            className="inline-flex h-10 items-center gap-2 rounded-full border border-border px-5 text-sm font-semibold text-foreground transition-colors hover:bg-card-2"
          >
            <Github className="size-4" />
            GitHub
          </a>
        </div>
      </section>

      {/* ── 기술 스택 ───────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-4xl px-4 pb-14" aria-labelledby="stack">
        <h2 id="stack" className="font-sport text-xl text-foreground">
          쓰는 기술
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          아래 프로젝트에서 실제로 돌아가는 것만 적었습니다.
        </p>

        <dl className="mt-5 flex flex-col gap-4">
          {STACK.map(({ group, items }) => (
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

      {/* ── 프로젝트 ────────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-4xl px-4 pb-16" aria-labelledby="projects">
        <h2 id="projects" className="font-sport text-xl text-foreground">
          만든 것
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">카드를 누르면 서비스로 이동합니다.</p>

        <div className="mt-5 flex flex-col gap-4">
          {PROJECTS.map((project) => (
            <ProjectBanner key={project.name} project={project} />
          ))}
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground">
          <span>정상호 · 2026</span>
          <div className="flex items-center gap-4">
            <a
              href={GITHUB_URL}
              className="underline-offset-4 hover:text-foreground hover:underline"
            >
              github.com/jsangho
            </a>
            <a
              href={`mailto:${EMAIL}`}
              className="underline-offset-4 hover:text-foreground hover:underline"
            >
              {EMAIL}
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
