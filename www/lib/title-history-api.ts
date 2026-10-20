import { titleAcquisitionsBaseUrl, requestTimeoutMs } from "@/lib/api";

export type TitleAcquisition = {
  beltName: string;
  wonAt: string;
  wonAtSlug?: string | null;
  matchKey?: string | null;
  /** `wonAt`에서 가른 대회명. 못 읽으면 null — 그때는 `wonAt` 원문이 유일한 정보다. */
  eventLabel?: string | null;
  /** ISO 날짜(`2009-04-05`). null은 "날짜 미상"이고 정상이다. */
  wonOn?: string | null;
};

export type CompetitorTitleHistory = {
  name: string;
  acquisitions: TitleAcquisition[];
  total: number;
};

export async function fetchCompetitorTitleHistory(
  name: string,
): Promise<CompetitorTitleHistory | null> {
  const url = `${titleAcquisitionsBaseUrl}/competitors/${encodeURIComponent(name)}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (res.status === 404) {
      return { name, acquisitions: [], total: 0 };
    }
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
