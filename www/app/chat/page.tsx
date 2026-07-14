"use client";

import { GeminiChatPanel } from "@/components/gemini-chat-panel";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function ChatPage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:py-10">
        <div className="mb-4 text-center sm:mb-6">
          <h1 className="font-sport text-xl font-semibold tracking-[-0.04em] text-stone-900 dark:text-white sm:text-2xl">
            대화
          </h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">궁금한 걸 물어보세요</p>
        </div>
        <GeminiChatPanel className="min-h-[420px] h-[min(60dvh,640px)] max-h-[70dvh]" />
      </div>
    </WweArenaShell>
  );
}
