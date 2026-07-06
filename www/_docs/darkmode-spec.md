# JSangho — 다크모드 구현 지시어

## 기본 방침

- **기본값: 화이트 모드**
- **다크 모드: 사용자 토글 제공** (OS 설정 감지 후 오버라이드 가능)
- Tailwind CSS `dark:` 클래스 방식 사용 (Next.js App Router 기준)

---

## 1. next-themes 설정

```bash
npm install next-themes
```

```tsx
// app/layout.tsx
import { ThemeProvider } from "next-themes";

export default function RootLayout({ children }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="light" // 기본값 화이트
          enableSystem={true} // OS 다크모드 감지
          disableTransitionOnChange // 전환 시 깜빡임 방지
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

---

## 2. Tailwind 다크모드 설정

```js
// tailwind.config.js
module.exports = {
  darkMode: "class", // 'media' 아닌 'class' — 토글 제어 가능하게
  // ...
};
```

---

## 3. 테마 토글 버튼 컴포넌트

상단 Topbar 우측에 배치. 해/달 아이콘 토글.

```tsx
// components/ThemeToggle.tsx
"use client";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null; // hydration 불일치 방지

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label="테마 전환"
      className="p-2 rounded-md text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
    >
      {theme === "dark" ? (
        <SunIcon className="w-4 h-4" />
      ) : (
        <MoonIcon className="w-4 h-4" />
      )}
    </button>
  );
}
```

---

## 4. CSS 변수 기반 색상 체계

Tailwind `dark:` 클래스와 병행해서 CSS 변수로 시맨틱 토큰 관리.

```css
/* app/globals.css */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-surface: #f3f4f6;

  --text-primary: #111827;
  --text-secondary: #6b7280;
  --text-muted: #9ca3af;

  --border: #e5e7eb;
  --border-strong: #d1d5db;

  --accent: #2563eb; /* RAGWATSON 브랜드 블루 */
  --accent-hover: #1d4ed8;
}

[class~="dark"] {
  --bg-primary: #0a0a0a;
  --bg-secondary: #111111;
  --bg-surface: #1a1a1a;

  --text-primary: #ededed;
  --text-secondary: #a1a1aa;
  --text-muted: #71717a;

  --border: #27272a;
  --border-strong: #3f3f46;

  --accent: #3b82f6;
  --accent-hover: #60a5fa;
}
```

---

## 5. 컴포넌트 적용 패턴

```tsx
// 모든 컴포넌트에서 이 패턴으로 통일

// 배경
<div className="bg-white dark:bg-[#0a0a0a]">
<div className="bg-gray-50 dark:bg-[#111111]">  {/* 사이드바, 패널 */}

// 텍스트
<p className="text-gray-900 dark:text-gray-100">         {/* 주요 텍스트 */}
<p className="text-gray-500 dark:text-gray-400">         {/* 보조 텍스트 */}
<p className="text-gray-400 dark:text-gray-500">         {/* 힌트 텍스트 */}

// 보더
<div className="border border-gray-200 dark:border-gray-800">
<div className="border-b border-gray-100 dark:border-gray-900">  {/* 얇은 구분선 */}

// 코드 블록 (다크모드에서 더 진하게)
<pre className="bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-200">

// accent (브랜드 컬러)
<a className="text-blue-600 dark:text-blue-400">
<button className="bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-400">
```

---

## 6. 우측 패널 다크모드

```tsx
// components/RightPanel.tsx
<aside
  className="
  w-[200px] shrink-0
  border-l border-gray-100 dark:border-gray-800
  bg-gray-50 dark:bg-[#111111]
  px-4 py-6
  hidden lg:block
"
>
  {/* TOC or FilterPanel or RelatedPanel */}
</aside>
```

---

## 7. 좌측 사이드바 다크모드

```tsx
// components/LeftSidebar.tsx
<nav
  className="
  w-[160px] shrink-0
  border-r border-gray-100 dark:border-gray-800
  bg-gray-50 dark:bg-[#111111]
  px-3 py-4
  hidden md:block
"
>
  {/* active 항목 */}
  <span className="text-blue-600 dark:text-blue-400 font-medium">
    데이터 수집
  </span>
  {/* 일반 항목 */}
  <span className="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
    탐승자 목록
  </span>
</nav>
```

---

## 8. Topbar에 토글 배치

```tsx
// components/Topbar.tsx
<header
  className="
  border-b border-gray-100 dark:border-gray-800
  bg-white dark:bg-[#0a0a0a]
  sticky top-0 z-50
"
>
  <div className="flex items-center px-6 h-12">
    <Logo />
    <NavLinks />
    <div className="ml-auto flex items-center gap-4">
      <ThemeToggle /> {/* 해/달 아이콘 */}
      <AuthButton /> {/* 로그인 */}
    </div>
  </div>
</header>
```

---

## 9. 이미지 처리

다크모드에서 밝은 이미지가 너무 튀는 경우 처리.

```tsx
// 로고, 다이어그램 이미지 등
<img
  className="dark:opacity-80 dark:brightness-90"
  src="/diagram.png"
/>

// 완전히 다른 이미지 사용 시
<img
  src={theme === 'dark' ? '/logo-dark.svg' : '/logo-light.svg'}
/>
```

---

## 10. 요약 — 한 줄 지시

> "next-themes로 `defaultTheme='light'`, `attribute='class'` 설정. Tailwind `darkMode: 'class'`. Topbar 우측에 ThemeToggle 컴포넌트 배치. 모든 색상은 `bg-white dark:bg-[#0a0a0a]` 패턴으로 적용. 사이드바·우측패널·본문·코드블록 전부 dark: 클래스 대응."
