"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <button
      type="button"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label="테마 전환"
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-stone-300/70 dark:border-stone-600/70 bg-stone-200/45 dark:bg-stone-800/45 text-stone-600 dark:text-stone-300 transition-colors hover:bg-stone-200/65 dark:hover:bg-stone-700/65 hover:text-stone-950 dark:hover:text-stone-50"
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </button>
  );
}
