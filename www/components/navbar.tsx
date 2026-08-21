"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BarChart3, Brain, LogIn, Menu, Trophy, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { KayfabeLogo } from "@/components/kayfabe-logo";
import { MORE_GROUPS, MoreMenu, isMorePath } from "@/components/more-menu";
import { WeatherWidget } from "@/components/weather-widget";
import { WweTicker } from "@/components/wwe-ticker";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserNavBadge } from "@/components/user-nav-badge";
import { useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";

function navLinkClass(active: boolean, champion = false) {
  return cn(
    champion
      ? "btn-champion"
      : "border-stone-300/70 dark:border-stone-600/70 bg-stone-200/45 dark:bg-stone-800/45 text-stone-700 dark:text-stone-200 shadow-none hover:bg-stone-200/65 dark:hover:bg-stone-700/65 hover:text-stone-950 dark:hover:text-stone-50 hover:border-stone-400 dark:hover:border-stone-500 focus-visible:ring-stone-500/40",
    !champion &&
      active &&
      "border-stone-400 bg-stone-300 dark:bg-stone-600 text-stone-900 dark:text-stone-50 hover:bg-stone-300 dark:hover:bg-stone-600 hover:border-stone-400 hover:text-stone-900 dark:hover:text-stone-50",
    champion && active && "border-brand-400/80 !text-brand-50",
  );
}

function NavLink({
  href,
  active,
  champion = false,
  icon,
  children,
  fullWidth = false,
}: {
  href: string;
  active: boolean;
  champion?: boolean;
  icon?: ReactNode;
  children: ReactNode;
  fullWidth?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        buttonVariants({ variant: "outline", size: "sm" }),
        "gap-1.5",
        fullWidth && "w-full justify-start",
        navLinkClass(active, champion),
      )}
      {...(active ? { "aria-current": "page" as const } : {})}
    >
      {icon}
      {children}
    </Link>
  );
}

export function Navbar() {
  const router = useRouter();
  const { user, logout, isReady } = useAuth();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const isHome = mounted && pathname === "/";
  const isPle = mounted && (pathname === "/ple" || pathname.startsWith("/ple/"));
  const isDataCenter = mounted && pathname.startsWith("/data-center");
  const isAiLab = mounted && pathname.startsWith("/ai-lab");
  const isRankings = mounted && pathname === "/rankings";
  const isRecords = mounted && (pathname === "/records" || pathname.startsWith("/records/"));
  const isMore = mounted && isMorePath(pathname);
  const isAdmin = mounted && pathname === "/admin";
  const isLogin = mounted && pathname === "/login";
  const isMyInfo = mounted && pathname === "/my-info";
  const showAuth = mounted && isReady;
  const isUserAdmin = mounted && isReady && user?.role === "admin";

  function handleLogout() {
    logout();
    router.push("/");
    setMobileOpen(false);
  }

  const authControls = !showAuth ? (
    <div
      className="h-8 w-[7.5rem] animate-pulse rounded-md border border-stone-300/50 dark:border-stone-700/50 bg-stone-200/60 dark:bg-stone-800/60"
      aria-hidden
    />
  ) : user ? (
    <>
      <NavLink href="/my-info" active={isMyInfo} fullWidth={mobileOpen}>
        내 정보
      </NavLink>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className={cn(navLinkClass(false), mobileOpen && "w-full justify-start")}
        onClick={handleLogout}
      >
        로그아웃
      </Button>
      <UserNavBadge user={user} />
    </>
  ) : (
    <NavLink
      href="/login"
      active={isLogin}
      champion
      fullWidth={mobileOpen}
      icon={<LogIn className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden />}
    >
      로그인
    </NavLink>
  );

  /** 메인 여섯 자리 (KAYFABE 2.0). 데스크톱·모바일이 같은 목록을 그린다. */
  const mainNav = (fullWidth: boolean) => (
    <>
      <NavLink href="/" active={isHome} fullWidth={fullWidth}>
        홈
      </NavLink>
      <NavLink href="/ple" active={isPle} fullWidth={fullWidth}>
        PLE 예측
      </NavLink>
      <NavLink
        href="/data-center"
        active={isDataCenter}
        fullWidth={fullWidth}
        icon={<BarChart3 className="h-3.5 w-3.5 shrink-0" aria-hidden />}
      >
        데이터 센터
      </NavLink>
      <NavLink
        href="/ai-lab"
        active={isAiLab}
        fullWidth={fullWidth}
        icon={<Brain className="h-3.5 w-3.5 shrink-0 text-data" aria-hidden />}
      >
        AI LAB
      </NavLink>
      <NavLink
        href="/rankings"
        active={isRankings}
        champion
        fullWidth={fullWidth}
        icon={<Trophy className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden />}
      >
        랭킹
      </NavLink>
      <NavLink href="/records" active={isRecords} fullWidth={fullWidth}>
        기록
      </NavLink>
    </>
  );

  return (
    <header className="sticky top-0 z-50 w-full min-w-0 border-b border-border bg-background/85 backdrop-blur-[12px] supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex w-full max-w-6xl min-w-0 items-center justify-between gap-2 px-4 py-3">
        <div className="flex min-w-0 shrink-0 items-center gap-2">
          <KayfabeLogo />
        </div>

        <nav className="hidden items-center gap-1.5 lg:flex" aria-label="주요 메뉴">
          {mainNav(false)}
        </nav>

        <div className="hidden shrink-0 items-center gap-1.5 lg:flex">
          <MoreMenu active={isMore} triggerClassName={navLinkClass(isMore)} />
          <WeatherWidget />
          {isUserAdmin && (
            <NavLink href="/admin" active={isAdmin}>
              관리자
            </NavLink>
          )}
          {authControls}
          <ThemeToggle />
        </div>

        <div className="flex shrink-0 items-center gap-1.5 lg:hidden">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-foreground hover:bg-card-2"
          >
            {mobileOpen ? (
              <X className="size-5" aria-hidden />
            ) : (
              <Menu className="size-5" aria-hidden />
            )}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="border-t border-border px-4 py-3 lg:hidden">
          <nav className="mx-auto flex w-full max-w-6xl flex-col gap-2" aria-label="모바일 메뉴">
            {mainNav(true)}

            {/* 더보기 — 데스크톱의 드롭다운과 같은 목록을 펼쳐 둔다. */}
            {MORE_GROUPS.map((group, index) => (
              <div key={group.title ?? `group-${index}`} className="flex flex-col gap-2">
                <p className="px-1 pt-1 text-xs text-muted-foreground">{group.title ?? "더보기"}</p>
                {group.items.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    active={mounted && pathname.startsWith(item.href)}
                    fullWidth
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ))}

            {isUserAdmin && (
              <NavLink href="/admin" active={isAdmin} fullWidth>
                관리자
              </NavLink>
            )}
            {authControls}
            <div className="pt-1">
              <WeatherWidget />
            </div>
          </nav>
        </div>
      )}

      <WweTicker />
    </header>
  );
}
