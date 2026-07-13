import {
  pleEventsBaseUrl,
  pleMatchesBaseUrl,
  pleMatchPicksBaseUrl,
  requestTimeoutMs,
} from "@/lib/api";
import type { PleMatchCard } from "@/lib/wwe-ple-matches";
import type { PleSlug } from "@/lib/wwe-ple";
import { getPleBySlug } from "@/lib/wwe-ple";

export type PleMatchResult = {
  winnerSide?: "left" | "right";
  winnerIndex?: number;
  winnerName?: string;
};

export type PleBoardMatch = {
  id: string;
  dbId: number;
  title: string;
  cardVariant: "sideA" | "sideB";
  format: "singles" | "multi";
  left?: { name: string; isChampion?: boolean };
  right?: { name: string; isChampion?: boolean };
  competitors?: { name: string; isChampion?: boolean }[];
  bookmakerDecimal?: PleMatchCard["bookmakerDecimal"] | number[];
  status: string;
  result?: PleMatchResult | null;
  siteVotes: { left: number; right: number; multi: number[] };
  locked: boolean;
  myPick?: string | null;
  aiPick?: string | null;
  aiPickName?: string | null;
  aiCorrect?: boolean | null;
};

export type { PleAiRecord, PleAiStats } from "@/lib/ple-ai-stats";
export { fetchPleAiStats } from "@/lib/ple-ai-stats";

export type PleBoard = {
  slug: string;
  label: string;
  month: number | null;
  year: number;
  status: "upcoming" | "live" | "finished";
  finishedAt?: string | null;
  matches: PleBoardMatch[];
  updatedAt: string;
};

function boardMatchToCard(m: PleBoardMatch): PleMatchCard {
  const base = {
    id: m.id,
    title: m.title,
    cardVariant: m.cardVariant,
  };
  if (m.format === "multi") {
    return {
      ...base,
      format: "multi",
      competitors: m.competitors ?? [],
      bookmakerDecimal: m.bookmakerDecimal as number[] | undefined,
    };
  }
  return {
    ...base,
    format: "singles",
    left: m.left!,
    right: m.right!,
    bookmakerDecimal: m.bookmakerDecimal as { left: number; right: number },
  };
}

export function boardMatchesToCards(matches: PleBoardMatch[]): PleMatchCard[] {
  return matches.map(boardMatchToCard);
}

export function buildSyncPayload(slug: PleSlug, cards: PleMatchCard[]) {
  const ple = getPleBySlug(slug);
  if (!ple) throw new Error(`Unknown PLE: ${slug}`);
  return {
    slug,
    label: ple.label,
    month: ple.month,
    year: 2026,
    matches: cards,
  };
}

export async function syncPleFromClient(
  slug: PleSlug,
  cards: PleMatchCard[],
): Promise<PleBoard> {
  const res = await fetch(`${pleEventsBaseUrl}/${slug}/sync-from-client`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildSyncPayload(slug, cards)),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json();
}

export type FetchPleBoardOptions = {
  clientId?: string;
  userId?: number;
};

export async function fetchPleBoard(
  slug: PleSlug,
  options?: FetchPleBoardOptions | string,
): Promise<PleBoard | null> {
  const opts: FetchPleBoardOptions =
    typeof options === "string" ? { clientId: options } : (options ?? {});
  const params = new URLSearchParams();
  if (opts.clientId) params.set("client_id", opts.clientId);
  if (opts.userId != null) params.set("user_id", String(opts.userId));
  const q = params.toString() ? `?${params.toString()}` : "";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  const res = await fetch(`${pleEventsBaseUrl}/${slug}${q}`, {
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function parseApiErrorDetail(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "detail" in err) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) =>
          typeof d === "object" && d && "msg" in d
            ? String((d as { msg: string }).msg)
            : String(d),
        )
        .join(", ");
    }
  }
  return fallback;
}

export type MatchResultPayload = {
  winnerSide?: "left" | "right";
  winnerIndex?: number;
  winnerName?: string;
  status?: "scheduled" | "live" | "finished";
};

export async function submitPleMatchResult(
  slug: PleSlug,
  matchKey: string,
  body: MatchResultPayload,
): Promise<PleBoard> {
  const res = await fetch(
    `${pleMatchesBaseUrl}/${slug}/matches/${matchKey}/result`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        winnerSide: body.winnerSide,
        winnerIndex: body.winnerIndex,
        winnerName: body.winnerName,
        status: body.status ?? "finished",
      }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(parseApiErrorDetail(err, res.statusText));
  }
  return res.json();
}

export async function linkPlePredictions(
  clientId: string,
  userId: number,
): Promise<number | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(`${pleMatchPicksBaseUrl}/link-predictions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clientId, userId }),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { linked?: number };
    return typeof data.linked === "number" ? data.linked : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export type BatchPredictionItem = {
  matchKey: string;
  pick: string;
};

export async function submitPlePredictionsBatch(
  slug: PleSlug,
  clientId: string,
  predictions: BatchPredictionItem[],
  userId: number,
): Promise<PleBoard> {
  const res = await fetch(`${pleMatchPicksBaseUrl}/${slug}/predictions/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      clientId,
      userId,
      predictions,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(parseApiErrorDetail(err, res.statusText));
  }
  return res.json();
}

export type BatchResultItem = {
  matchKey: string;
  winnerSide?: "left" | "right";
  winnerIndex?: number;
  winnerName?: string;
  status?: "scheduled" | "live" | "finished";
};

export async function submitPleResultsBatch(
  slug: PleSlug,
  results: BatchResultItem[],
): Promise<PleBoard> {
  const res = await fetch(`${pleMatchesBaseUrl}/${slug}/results/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ results }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(parseApiErrorDetail(err, res.statusText));
  }
  return res.json();
}

export async function submitPlePrediction(
  slug: PleSlug,
  matchKey: string,
  pick: string,
  clientId: string,
  userId: number,
): Promise<PleBoard> {
  const res = await fetch(
    `${pleMatchPicksBaseUrl}/${slug}/matches/${matchKey}/predict`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pick,
        clientId,
        userId,
      }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json();
}

export async function setPleMatchResult(
  slug: PleSlug,
  matchKey: string,
  payload: PleMatchResult,
): Promise<PleBoard> {
  const res = await fetch(
    `${pleMatchesBaseUrl}/${slug}/matches/${matchKey}/result`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json();
}

export function subscribePleLive(
  slug: PleSlug,
  clientId: string,
  onBoard: (board: PleBoard) => void,
  onError?: (err: unknown) => void,
  userId?: number,
): () => void {
  const params = new URLSearchParams({ client_id: clientId });
  if (userId != null) params.set("user_id", String(userId));
  const url = `${pleEventsBaseUrl}/${slug}/live?${params.toString()}`;
  const source = new EventSource(url);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as PleBoard & { error?: string };
      if (data.error) {
        onError?.(new Error(data.error));
        return;
      }
      onBoard(data);
    } catch (e) {
      onError?.(e);
    }
  };

  source.onerror = () => onError?.(new Error("SSE connection error"));

  return () => source.close();
}
