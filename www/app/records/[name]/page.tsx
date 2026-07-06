"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { CompetitorRecordView } from "@/components/records/competitor-record-view";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import {
  fetchCompetitorProfile,
  type CompetitorProfile,
} from "@/lib/records-api";
import { fetchCompetitorTitleHistory } from "@/lib/title-history-api";
import type { TitleAcquisition } from "@/lib/title-history-api";

type RecordDetailState = {
  loading: boolean;
  profile: CompetitorProfile | null;
  titleHistory: TitleAcquisition[];
  missing: boolean;
};

const initialState: RecordDetailState = {
  loading: true,
  profile: null,
  titleHistory: [],
  missing: false,
};

export default function RecordDetailPage() {
  const params = useParams();
  const rawName = typeof params.name === "string" ? params.name : "";
  const name = decodeURIComponent(rawName);

  const [state, setState] = useState<RecordDetailState>(initialState);
  const patchState = (patch: Partial<RecordDetailState>) =>
    setState((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    if (!name) {
      patchState({ loading: false, missing: true });
      return;
    }

    let cancelled = false;
    patchState({
      loading: true,
      missing: false,
      profile: null,
      titleHistory: [],
    });

    void (async () => {
      const [profile, titleHistory] = await Promise.all([
        fetchCompetitorProfile(name),
        fetchCompetitorTitleHistory(name),
      ]);
      if (cancelled) return;
      if (!profile) {
        patchState({ loading: false, missing: true });
        return;
      }
      patchState({
        loading: false,
        profile,
        titleHistory: titleHistory?.acquisitions ?? [],
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [name]);

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
        <header className="mb-6">
          <Link
            href="/records"
            className="text-sm font-semibold text-stone-400 transition-colors hover:text-amber-200/90"
          >
            ← 선수 목록
          </Link>
        </header>

        {state.loading ? (
          <div className="flex items-center justify-center gap-2 rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-100/50 dark:bg-stone-950/50 px-4 py-10 text-sm text-stone-500 dark:text-stone-400">
            <Loader2 className="h-4 w-4 animate-spin text-amber-400/80" />
            불러오는 중…
          </div>
        ) : state.missing || !state.profile ? (
          <div className="rounded-2xl border border-dashed border-stone-300/50 dark:border-stone-700/50 bg-stone-100/40 dark:bg-stone-950/40 px-4 py-10 text-center text-sm text-stone-500 dark:text-stone-400">
            <p>선수 정보를 찾을 수 없습니다.</p>
            <Link
              href="/records"
              className="mt-4 inline-block text-sm font-semibold text-amber-200/90 hover:text-amber-100"
            >
              선수 목록으로 돌아가기
            </Link>
          </div>
        ) : (
          <CompetitorRecordView
            profile={state.profile}
            titleHistory={state.titleHistory}
          />
        )}
      </div>
    </WweArenaShell>
  );
}
