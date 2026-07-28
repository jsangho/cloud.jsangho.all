"use client";

import { ChatSubnav } from "@/components/chat-subnav";
import { LangchainChatPanel } from "@/components/langchain-chat-panel";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function LangchainChatPage() {
  return (
    <WweArenaShell>
      <div className="mx-auto flex h-[calc(100dvh-9rem)] max-h-[720px] w-full max-w-2xl flex-col px-4 py-6 sm:py-10">
        <ChatSubnav active="langchain" />
        <LangchainChatPanel className="min-h-0 flex-1" />
      </div>
    </WweArenaShell>
  );
}
