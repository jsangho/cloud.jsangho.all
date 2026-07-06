import type { Metadata } from "next";
import { Geist, Geist_Mono, Oswald } from "next/font/google";
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
        className={`${geist.variable} ${geistMono.variable} ${oswald.variable} min-h-full w-full overflow-x-hidden font-sans antialiased bg-white text-stone-900 dark:bg-[#0a0a0c] dark:text-stone-100`}
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
