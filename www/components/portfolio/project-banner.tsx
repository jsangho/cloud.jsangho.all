import Image from "next/image";
import { ArrowUpRight } from "lucide-react";

export type PortfolioProject = {
  name: string;
  tagline: string;
  /**
   * 혼자 만든 게 아닐 때 **어디까지가 내 몫인지** 적는다.
   * 없으면 개인 작업으로 읽힌다 — 팀 프로젝트는 반드시 채운다.
   */
  role?: { team: string; mine: string };
  description: string;
  href: string;
  /** 주소를 사람이 읽는 형태로 — 버튼이 어디로 가는지 눌러 보기 전에 보여 준다. */
  hrefLabel: string;
  /** 프로젝트 메인 화면 캡처. `public/projects/` 아래. */
  image: string;
  imageAlt: string;
  /** 카드 아래 한 줄짜리 사실들. **실측값만 적는다.** */
  facts: string[];
};

/**
 * 프로젝트 배너 버튼 — 카드 전체가 링크다.
 *
 * 화면 캡처를 쓰는 이유: 이름과 설명만 있는 카드는 어느 프로젝트나 비슷해 보인다.
 * **무엇을 만들었는지는 화면이 가장 빨리 말한다.**
 */
export function ProjectBanner({ project }: { project: PortfolioProject }) {
  return (
    <a
      href={project.href}
      className="group block overflow-hidden rounded-xl border border-border bg-card transition-colors hover:bg-card-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-link"
    >
      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        {/* 캡처는 카드 안에서 잘린다 — 화면 비율이 달라도 카드 높이가 흔들리지 않는다.
            원본은 첫 화면 위쪽만 잘라 뒀다: 카드 안에서 무엇도 반으로 끊기지 않게. */}
        <div className="relative aspect-[16/9] w-full overflow-hidden border-b border-border md:aspect-auto md:min-h-[19rem] md:border-b-0 md:border-r">
          <Image
            src={project.image}
            alt={project.imageAlt}
            fill
            sizes="(max-width: 768px) 100vw, 55vw"
            className="object-cover object-top"
            priority
          />
        </div>

        <div className="flex flex-col gap-3 p-5 sm:p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="font-sport text-2xl leading-tight text-foreground">{project.name}</h3>
              <p className="mt-1 text-sm text-brand-link">{project.tagline}</p>
            </div>
            <ArrowUpRight
              aria-hidden
              className="mt-1 size-5 shrink-0 text-muted-foreground transition-colors group-hover:text-brand-link"
            />
          </div>

          {project.role && (
            <p className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="rounded-md border border-border px-2 py-0.5 text-muted-foreground">
                {project.role.team}
              </span>
              <span className="text-muted-foreground">
                담당 <span className="text-foreground">{project.role.mine}</span>
              </span>
            </p>
          )}

          <p className="text-sm leading-relaxed text-muted-foreground">{project.description}</p>

          <ul className="mt-auto flex flex-wrap gap-x-3 gap-y-1 pt-2 text-xs text-muted-foreground">
            {project.facts.map((fact) => (
              <li key={fact} className="tabular-nums">
                {fact}
              </li>
            ))}
          </ul>

          <p className="font-mono text-xs text-muted-foreground">{project.hrefLabel}</p>
        </div>
      </div>
    </a>
  );
}
