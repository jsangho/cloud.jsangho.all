import { Github, Mail } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProjectBanner, type PortfolioProject } from "@/components/portfolio/project-banner";
import { TechStack, type StackGroup } from "@/components/portfolio/tech-stack";

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

/**
 * 실제로 쓰는 것만 적는다 — 이력서용 나열을 만들지 않는다.
 *
 * `where` 는 칩에 마우스를 올렸을 때 뜨는 문장이고, `project: "supersub"` 는
 * 팀 프로젝트(SUPER-SUB) 의 AI 영상 분석 에이전트에서 쓴 것이라는 표시다.
 * 색이 갈리는 이유가 그거다 — 혼자 만든 것과 팀에서 맡은 몫을 섞지 않는다.
 *
 * **`where` 는 비개발자가 읽는 문장이다.** 이 페이지를 보는 사람 중 다수는
 * 기술 이름을 모른다 — 이름을 풀어 쓰는 대신 *그게 무슨 일을 하는지*를 적는다.
 * 용어를 남기려면 그 자리에서 뜻을 함께 풀어 준다.
 */
const STACK: StackGroup[] = [
  {
    group: "언어",
    items: [
      {
        name: "Python 3.13",
        where: "서버 쪽 코드를 쓰는 언어입니다. 백엔드 전체가 이걸로 돕니다.",
      },
      {
        name: "Python 3.12",
        where:
          "영상 분석 쪽만 한 버전 낮게 맞췄습니다. 쓰는 AI 도구들이 아직 최신 버전을 지원하지 않아서입니다.",
        project: "supersub",
      },
      {
        name: "TypeScript",
        where:
          "화면 쪽 코드를 쓰는 언어입니다. 실행하기 전에 미리 검사해서 오타 같은 실수를 잡아 줍니다.",
      },
      { name: "Dart", where: "모바일 앱을 만드는 언어입니다." },
      { name: "SQL", where: "저장해 둔 기록 중 필요한 것만 찾아오는 언어입니다." },
    ],
  },
  {
    group: "백엔드",
    items: [
      {
        name: "FastAPI",
        where:
          "화면이 서버에 자료를 요청할 때 그 요청을 받는 창구입니다. KAYFABE와 SUPER-SUB 영상 분석 모두 이걸로 만들었습니다.",
      },
      {
        name: "SQLAlchemy 2.0 async",
        where: "코드에서 데이터베이스를 다루는 도구입니다. 여러 요청이 서로 기다리지 않게 합니다.",
      },
      {
        name: "SQLModel",
        where: "저장할 자료의 모양과 화면에 내보낼 자료의 모양을 한 번에 정의합니다.",
      },
      {
        name: "Alembic",
        where: "저장 구조를 바꿀 때 그 변경을 기록해 두고, 필요하면 되돌릴 수 있게 합니다.",
      },
      {
        name: "Pydantic",
        where: "오가는 자료가 약속한 형식이 맞는지 검사합니다. 이상한 값은 여기서 걸립니다.",
      },
      {
        name: "pytest",
        where: "코드가 망가졌는지 자동으로 확인하는 검사 도구입니다. 1,182건이 매번 돌아갑니다.",
      },
      { name: "Uvicorn", where: "만든 서버를 실제로 띄워 두고 요청을 받게 하는 프로그램입니다." },
      { name: "uv", where: "프로젝트에 필요한 외부 코드들을 받아서 관리합니다." },
    ],
  },
  {
    group: "프론트엔드",
    items: [
      {
        name: "Next.js 16",
        where: "지금 보고 계신 이 페이지를 포함해, 웹 화면 전체를 만드는 틀입니다.",
      },
      { name: "React 19", where: "화면을 버튼·카드 같은 조각으로 나눠 만들고 조립합니다." },
      {
        name: "Tailwind CSS",
        where:
          "색과 여백, 글자 크기를 정해진 규칙 안에서만 쓰게 해서 화면이 제각각 되는 걸 막습니다.",
      },
      {
        name: "Radix UI",
        where:
          "마우스 없이 키보드만으로도 쓸 수 있게 만들어진 화면 부품 모음입니다. 지금 보고 계신 이 설명창도 그중 하나입니다.",
      },
      { name: "Recharts", where: "기록과 순위를 그래프로 그립니다." },
      { name: "Flutter", where: "코드 한 벌로 안드로이드와 아이폰 앱을 함께 만듭니다." },
    ],
  },
  {
    group: "데이터",
    items: [
      { name: "PostgreSQL", where: "경기와 예측, 채점 결과를 담아 두는 저장소입니다." },
      {
        name: "pgvector",
        where: "글의 뜻을 숫자로 바꿔 저장해 두고, 말이 달라도 뜻이 비슷한 글을 찾아옵니다.",
      },
      {
        name: "Neo4j",
        where: "선수·단체·사건처럼 서로 얽힌 관계를 그물 모양 그대로 저장합니다.",
      },
      {
        name: "Redis",
        where:
          "자주 쓰는 값을 잠깐 올려 두는 빠른 임시 저장소입니다. 로그인 상태와 수집 대기열이 여기 있습니다.",
      },
      { name: "Supabase", where: "저장소를 직접 운영하지 않고 맡겨 두는 서비스입니다." },
      {
        name: "S3",
        where: "분석할 경기 영상과 결과 보고서를 올려 두는 아마존 저장 공간입니다.",
        project: "supersub",
      },
    ],
  },
  {
    group: "AI · 비전",
    items: [
      {
        name: "RT-DETR",
        where:
          "영상 한 장면에서 사람이 어디에 있는지 찾아냅니다. 상업적으로 써도 되는 공개 모델이라 골랐습니다.",
        project: "supersub",
      },
      {
        name: "ViTPose",
        where:
          "찾아낸 사람의 어깨·팔꿈치·무릎 등 17곳을 짚어 자세를 읽습니다. 그걸 관절이 꺾인 각도로 바꿔 실력을 재는 재료로 씁니다.",
        project: "supersub",
      },
      {
        name: "OpenCV",
        where:
          "영상을 사진 여러 장으로 쪼갭니다. 전부 똑같이 보면 비용이 커서, 먼저 띄엄띄엄 훑어 중요한 구간만 고른 뒤 그 부분만 자세히 다시 봅니다.",
        project: "supersub",
      },
      {
        name: "NumPy",
        where: "자세에서 뽑아낸 숫자 더미를 빠르게 계산합니다.",
        project: "supersub",
      },
      {
        name: "SciPy",
        where: "시간에 따라 흔들리는 자세 값을 다듬고 통계를 냅니다.",
        project: "supersub",
      },
    ],
  },
  {
    group: "AI · 언어모델",
    items: [
      {
        name: "Google Gemini",
        where: "경기 결과를 예측하고, 끝난 경기의 승자를 찾아 정리하는 AI입니다.",
      },
      {
        name: "RAG",
        where:
          "AI가 기억으로 지어내지 않도록, 먼저 관련 자료를 찾아 읽히고 그 자료를 근거로만 답하게 하는 방식입니다.",
      },
      {
        name: "BAAI/bge-m3",
        where: "문장을 숫자로 바꿔 줍니다. 이 숫자가 있어야 뜻이 비슷한 글을 찾을 수 있습니다.",
      },
      {
        name: "Kiwi 형태소",
        where: "한국어 문장을 단어 단위로 끊어 줍니다. 띄어쓰기만으로는 제대로 갈리지 않습니다.",
      },
      {
        name: "EXAONE 4.0 1.2B",
        where:
          "등급 자체는 정하지 않습니다. 이미 정해진 등급을 사람이 읽을 설명으로 옮기는 일만 합니다 — 숫자 비교를 틀리는 일이 있어서 판정은 AI에게 맡기지 않았습니다.",
        project: "supersub",
      },
      {
        name: "Hugging Face Transformers",
        where: "공개된 AI 모델을 내려받아 돌려 주는 도구입니다.",
        project: "supersub",
      },
      {
        name: "PyTorch (CUDA)",
        where: "AI 모델을 그래픽카드로 돌려 속도를 올립니다.",
        project: "supersub",
      },
      {
        name: "vLLM",
        where:
          "언어 모델을 여러 요청이 나눠 쓸 수 있게 띄워 둡니다. 자세 분석 모델과 그래픽카드 한 장을 나눠 써야 해서, 메모리를 35%만 쓰도록 묶어 뒀습니다.",
        project: "supersub",
      },
      {
        name: "Outlines",
        where:
          "AI가 제멋대로 된 문장 대신 정해진 형식으로만 답하게 강제합니다. 그래야 프로그램이 그 답을 바로 쓸 수 있습니다.",
        project: "supersub",
      },
    ],
  },
  {
    group: "인프라",
    items: [
      {
        name: "Docker",
        where: "서버에서 돌릴 프로그램을 통째로 포장해, 어느 컴퓨터에서나 똑같이 실행되게 합니다.",
      },
      {
        name: "k3s",
        where: "여러 프로그램을 한 대에서 묶어 돌리는 가벼운 운영 도구입니다. 개발용으로 씁니다.",
      },
      { name: "AWS EC2", where: "서비스가 실제로 돌아가고 있는 아마존 서버입니다." },
      {
        name: "AWS EC2 g4dn.xlarge (T4)",
        where: "그래픽카드가 달린 아마존 서버입니다. 영상 분석 모델들이 이 한 장을 나눠 씁니다.",
        project: "supersub",
      },
      {
        name: "systemd",
        where:
          "분석할 영상이 들어왔는지 계속 확인하고 처리하는 프로그램을, 서버가 알아서 켜 두고 꺼지면 다시 살립니다.",
        project: "supersub",
      },
      {
        name: "Vercel",
        where: "화면 쪽을 올려 두는 서비스입니다. 코드를 올리면 그대로 배포됩니다.",
      },
      {
        name: "Cloudflare Tunnel",
        where: "서버 문을 바깥에 직접 열지 않고도 인터넷에서 접속할 수 있게 연결해 줍니다.",
      },
      {
        name: "GitHub Actions",
        where:
          "코드를 올릴 때마다 검사와 테스트를 자동으로 돌립니다. 통과 못 하면 올라가지 않습니다.",
      },
    ],
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
    facts: ["화면 19개", "테스트 1,235건", "아키텍처 계약 4", "커밋 385"],
  },
  {
    name: "SUPER-SUB",
    tagline: "멀티모달 용병 스카우팅 · RAG 검증 플랫폼",
    role: { team: "팀 프로젝트 · 4명", mine: "AI 영상 분석 에이전트" },
    description:
      "생활체육 경기 영상을 분석해 선수의 실력을 재고, 그 근거로 팀이 빈 자리에 맞는 용병을 찾는 플랫폼입니다. 저는 영상에서 플레이 이벤트를 뽑아 색인하는 영상 분석 에이전트를 맡았습니다 — 프레임 추출 간격이 비용과 정확도를 동시에 정하는 자리라, 전 구간을 같은 간격으로 훑는 대신 거칠게 훑어 구간을 추리고 그 구간만 다시 봅니다.",
    /* 🔴 **팀 운영 도메인(`supersub-ai.com`)이 아니라 목업 데모로 보낸다**
       (2026-10-06). 그쪽은 백엔드가 살아 있어야 보이고 사이트 전체가 로그인
       뒤에 있어서, 처음 오는 사람이 눌러도 볼 것이 없다. 이쪽은 AWS 없이
       끝까지 도는 사본이고 데모 계정이 로그인 화면에 적혀 있다
       (`www/supersub/README.md`). **목업이라는 것을 누르기 전에 알린다** —
       레이블에 적어 두지 않으면 운영 중인 서비스로 읽는다. */
    href: "https://supersub.jsangho.cloud",
    hrefLabel: "supersub.jsangho.cloud · 목업 데모",
    image: "/projects/supersub-home.jpg",
    imageAlt: "SUPER-SUB 서비스 첫 화면 — 초록 배경 위의 SUPERSUB 워드마크",
    facts: ["에이전트 3종", "보고서 9장", "2026.08 – 10 진행 중"],
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
            AI를 실제 서비스에 붙이는 일을 합니다. 모델을 고르는 일보다{" "}
            <strong className="font-semibold text-foreground">
              그 출력을 믿어도 되는지를 시스템이 스스로 판정하게
            </strong>{" "}
            만드는 데 시간을 더 씁니다. 모델은 자신 있게 틀리기 때문입니다.
          </p>
          <p>
            혼자 만든 WWE 경기 예측 플랫폼은 백엔드부터 프론트, 배포까지 직접 만들었습니다. 여기서는
            언어 모델에게 데이터를 쓸 권한을 주지 않았습니다 — 모델은 결론과 근거 구절만 주장하고,
            반영할지는 서버가 그 인용을 원문과 대조해 판정합니다.
          </p>
          <p>
            네 명이 함께한 영상 분석 프로젝트에서는 모델을 부르기 전에 입력을 검증했습니다. 전신이
            잘리거나 가린 영상에서 뽑은 자세 좌표는 쓸 수 없는 값이기 때문입니다.
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
          아래 프로젝트에서 실제로 돌아가는 것만 적었습니다. 칩에 마우스를 올리면 어디에 쓰이는지
          보입니다.
        </p>

        <TechStack groups={STACK} />
      </section>

      {/* ── 프로젝트 ────────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-4xl px-4 pb-16" aria-labelledby="projects">
        <h2 id="projects" className="font-sport text-xl text-foreground">
          만든 것
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          카드를 누르면 해당 사이트로 이동합니다.
        </p>

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
