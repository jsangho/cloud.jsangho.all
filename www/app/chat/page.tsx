"use client";

import { WrestlerChatPanel } from "@/components/wrestler-chat-panel";
import { WweArenaShell } from "@/components/wwe-arena-shell";

export default function ChatPage() {
  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-2xl px-4 py-6 sm:py-10">
        <WrestlerChatPanel className="h-[calc(100dvh-9rem)] max-h-[720px]" />
      </div>
    </WweArenaShell>
  );
}
