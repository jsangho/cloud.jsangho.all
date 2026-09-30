import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";

/**
 * KAYFABE 제품 레이아웃.
 *
 * **내비게이션이 여기로 내려온 이유**: 루트 레이아웃에 있으면 포트폴리오 화면(`/`)
 * 위에도 PLE·랭킹·샵 메뉴가 선다. 그건 이 사이트의 크롬이 아니라 **프로젝트의
 * 크롬**이므로, 프로젝트 경로에만 붙인다.
 *
 * 라우트 그룹(괄호 이름)이라 **URL에는 나타나지 않는다** — `/ple`은 그대로 `/ple`이다.
 * 레이아웃 선택은 미들웨어가 다시 쓴 **내부 경로**로 정해지므로, `kayfabe.jsangho.cloud/`
 * 처럼 주소창이 `/`인 경우에도 이 레이아웃이 걸린다.
 */
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

export default function KayfabeLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Navbar />
      {children}
    </>
  );
}
