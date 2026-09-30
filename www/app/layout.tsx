import type { Metadata } from "next";
import { Geist, Geist_Mono, Oswald, Black_Han_Sans } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Analytics } from "@vercel/analytics/next";
import { AuthProvider } from "@/context/auth-context";
import { GoogleSessionProvider } from "@/components/google-session-provider";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});
const oswald = Oswald({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-sport",
});
const blackHanSans = Black_Han_Sans({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-kr-display",
});

/* 제품(KAYFABE) 메타데이터는 `app/(kayfabe)/layout.tsx`로 내려갔다 — 루트는 이제
   포트폴리오와 제품 양쪽의 껍데기라 어느 한쪽의 제목을 달고 있으면 안 된다. */
export const metadata: Metadata = {
  title: {
    default: "정상호 — 백엔드·데이터 중심 풀스택",
    template: "%s · 정상호",
  },
  description: "Wiki + LLM 개인 지식 시스템과 WWE 예측 플랫폼을 만듭니다.",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full" suppressHydrationWarning>
      <body
        /* 배경·글자색은 **토큰이 정한다** (KAYFABE 2.0). 하드코딩된
           `dark:bg-[#0a0a0c]`가 `--background`를 덮고 있어서, globals.css의
           표면 계단을 고쳐도 페이지 배경만 옛 값에 남아 있었다. */
        className={`${geist.variable} ${geistMono.variable} ${oswald.variable} ${blackHanSans.variable} min-h-full w-full overflow-x-hidden bg-background font-sans text-foreground antialiased`}
      >
        <GoogleSessionProvider>
          <ThemeProvider
            attribute="class"
            /* 라이트가 기본이다 (2026-09-29). `_docs/darkmode-spec.md`가 처음부터
               "기본값: 화이트 모드"로 정해 둔 것을 구현이 `dark`로 뒤집고 있었다.
               `enableSystem`이 남아 있으므로 OS가 다크면 다크로 뜬다 — 기본값은
               OS 설정이 없을 때만 쓰인다. */
            defaultTheme="light"
            enableSystem
            disableTransitionOnChange
          >
            <AuthProvider>{children}</AuthProvider>
          </ThemeProvider>
        </GoogleSessionProvider>
        {process.env.NODE_ENV === "production" && <Analytics />}
      </body>
    </html>
  );
}
