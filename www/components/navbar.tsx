"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { LogIn, Menu, Trophy, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { KayfabeLogo } from "@/components/kayfabe-logo";
import { PlePickerDialog } from "@/components/ple-picker-dialog";
import { WeatherWidget } from "@/components/weather-widget";
import { WweTicker } from "@/components/wwe-ticker";
import { ThemeToggle } from "@/components/theme-toggle";
import { authDisplayName, useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";

function navLinkClass(active: boolean, champion = false) {
  return cn(
    champion
      ? "btn-champion"
      : "border-stone-300/70 dark:border-stone-600/70 bg-stone-200/45 dark:bg-stone-800/45 text-stone-700 dark:text-stone-200 shadow-none hover:bg-stone-200/65 dark:hover:bg-stone-700/65 hover:text-stone-950 dark:hover:text-stone-50 hover:border-stone-400 dark:hover:border-stone-500 focus-visible:ring-stone-500/40",
    !champion &&
      active &&
      "border-stone-400 bg-stone-300 dark:bg-stone-600 text-stone-900 dark:text-stone-50 hover:bg-stone-300 dark:hover:bg-stone-600 hover:border-stone-400 hover:text-stone-900 dark:hover:text-stone-50",
    champion && active && "border-amber-400/80 !text-amber-50",
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

  const isPle =
    mounted && (pathname === "/ple" || pathname.startsWith("/ple/"));
  const isRankings = mounted && pathname === "/rankings";
  const isRecords =
    mounted && (pathname === "/records" || pathname.startsWith("/records/"));
  const isChampionship =
    mounted &&
    (pathname === "/championship" || pathname.startsWith("/championship/"));
  const isChat =
    mounted && (pathname === "/chat" || pathname.startsWith("/chat/"));
  const isLesson =
    mounted && (pathname === "/lesson" || pathname.startsWith("/lesson/"));
  const isAdmin = mounted && pathname === "/admin";
  const isLogin = mounted && pathname === "/login";
  const isMyInfo = mounted && pathname === "/my-info";
  const showAuth = mounted && isReady;

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
        className={cn(
          navLinkClass(false),
          mobileOpen && "w-full justify-start",
        )}
        onClick={handleLogout}
      >
        로그아웃
      </Button>
      <span
        className="max-w-[8rem] truncate px-1 text-sm font-semibold text-stone-900 dark:text-stone-100"
        title={authDisplayName(user)}
      >
        {authDisplayName(user)}
      </span>
    </>
  ) : (
    <NavLink
      href="/login"
      active={isLogin}
      champion
      fullWidth={mobileOpen}
      icon={
        <LogIn className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />
      }
    >
      로그인
    </NavLink>
  );

  return (
    <header className="sticky top-0 z-50 w-full min-w-0 border-b border-stone-200/80 dark:border-white/10 bg-white/90 dark:bg-[#0a0a0c]/85 backdrop-blur-[12px] supports-[backdrop-filter]:bg-white/70 dark:supports-[backdrop-filter]:bg-[#0a0a0c]/70">
      <div className="mx-auto flex w-full max-w-5xl min-w-0 items-center justify-between gap-2 px-4 py-3">
        <div className="flex min-w-0 shrink-0 items-center gap-2">
          <KayfabeLogo />
        </div>

        <div className="hidden items-center gap-1.5 md:flex">
          <PlePickerDialog triggerClassName={navLinkClass(isPle)} />
          <NavLink href="/records" active={isRecords}>
            기록
          </NavLink>
          <NavLink
            href="/rankings"
            active={isRankings}
            champion
            icon={
              <Trophy
                className="h-3.5 w-3.5 shrink-0 text-amber-400"
                aria-hidden
              />
            }
          >
            순위표
          </NavLink>
          <NavLink href="/championship" active={isChampionship}>
            챔피언십
          </NavLink>
          <NavLink href="/chat" active={isChat}>
            대화
          </NavLink>
        </div>

        <div className="hidden shrink-0 items-center gap-1.5 md:flex">
          <WeatherWidget />
          <NavLink href="/lesson" active={isLesson}>
            Lesson
          </NavLink>
          <NavLink href="/admin" active={isAdmin}>
            관리자
          </NavLink>
          {authControls}
          <ThemeToggle />
        </div>

        <div className="flex shrink-0 items-center gap-1.5 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "메뉴 닫기" : "메뉴 열기"}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-stone-300/70 dark:border-stone-700/70 bg-stone-100/40 dark:bg-stone-800/40 text-stone-700 dark:text-stone-100 hover:bg-stone-200/60 dark:hover:bg-stone-700/60"
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
        <div className="border-t border-stone-200/80 dark:border-white/10 px-4 py-3 md:hidden">
          <nav
            className="mx-auto flex w-full max-w-5xl flex-col gap-2"
            aria-label="모바일 메뉴"
          >
            <PlePickerDialog
              triggerClassName={cn(navLinkClass(isPle), "w-full justify-start")}
            />
            <NavLink href="/records" active={isRecords} fullWidth>
              기록
            </NavLink>
            <NavLink
              href="/rankings"
              active={isRankings}
              champion
              fullWidth
              icon={
                <Trophy
                  className="h-3.5 w-3.5 shrink-0 text-amber-400"
                  aria-hidden
                />
              }
            >
              순위표
            </NavLink>
            <NavLink href="/championship" active={isChampionship} fullWidth>
              챔피언십
            </NavLink>
            <NavLink href="/chat" active={isChat} fullWidth>
              대화
            </NavLink>
            <NavLink href="/lesson" active={isLesson} fullWidth>
              Lesson
            </NavLink>
            <NavLink href="/admin" active={isAdmin} fullWidth>
              관리자
            </NavLink>
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
