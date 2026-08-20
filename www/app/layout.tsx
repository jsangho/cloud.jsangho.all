import type { Metadata } from "next";
import { Geist, Geist_Mono, Oswald, Black_Han_Sans } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Analytics } from "@vercel/analytics/next";
import { Navbar } from "@/components/navbar";
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

export const metadata: Metadata = {
  title: "KayFabe",
  description: "WWE PLE 예측 게임",
  icons: {
    icon: [
      { url: "/kayfabe-mark.svg", type: "image/svg+xml" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: "/kayfabe-mark.svg",
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
            defaultTheme="dark"
            enableSystem
            disableTransitionOnChange
          >
            <AuthProvider>
              <Navbar />
              {children}
            </AuthProvider>
          </ThemeProvider>
        </GoogleSessionProvider>
        {process.env.NODE_ENV === "production" && <Analytics />}
      </body>
    </html>
  );
}
