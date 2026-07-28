"use client";

import { ChatSubnav } from "@/components/chat-subnav";
import { LangchainChatPanel } from "@/components/langchain-chat-panel";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function LangchainChatPage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:py-10">
        <ChatSubnav active="langchain" />
        <LangchainChatPanel className="h-[calc(100dvh-9rem)] max-h-[720px]" />
      </div>
    </WweArenaShell>
  );
}
