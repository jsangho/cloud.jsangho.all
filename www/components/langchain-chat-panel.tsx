"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  ts: string;
}

type LangchainChatPanelState = {
  messages: ChatMessage[];
  isLoading: boolean;
  errorMessage: string | null;
  lastPayload: ChatMessage[] | null;
};

const initialState: LangchainChatPanelState = {
  messages: [],
  isLoading: false,
  errorMessage: null,
  lastPayload: null,
};

const CHAT_REQUEST_FAILED = "메시지를 전송하지 못했습니다.";

export function LangchainChatPanel({ className }: { className?: string }) {
  const [state, setState] = useState<LangchainChatPanelState>(initialState);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const patchState = useCallback(
    (patch: Partial<LangchainChatPanelState>) => setState((prev) => ({ ...prev, ...patch })),
    [],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [state.messages]);

  const sendWithHistory = async (history: ChatMessage[]) => {
    const last = history[history.length - 1];
    if (!last || last.role !== "user" || !last.text.trim()) return;

    patchState({ isLoading: true, errorMessage: null, lastPayload: history });

    try {
      const response = await fetch("/api/kayfabe/langchain-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (!response.ok) {
        patchState({ errorMessage: CHAT_REQUEST_FAILED });
        return;
      }

      const data: { reply: string } = await response.json();
      patchState({
        messages: [
          ...history,
          { role: "assistant", text: data.reply, ts: new Date().toISOString() },
        ],
        lastPayload: null,
      });
    } catch {
      patchState({ errorMessage: CHAT_REQUEST_FAILED });
    } finally {
      patchState({ isLoading: false });
    }
  };

  const submitText = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || state.isLoading) return;
    const next = [
      ...state.messages,
      { role: "user" as const, text: trimmed, ts: new Date().toISOString() },
    ];
    patchState({ messages: next });
    void sendWithHistory(next);
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const value = inputRef.current?.value ?? "";
    submitText(value);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  };

  const handleRetry = () => {
    if (!state.lastPayload) return;
    patchState({ errorMessage: null });
    void sendWithHistory(state.lastPayload);
  };

  const isEmpty = state.messages.length === 0;

  return (
    <div className={cn("flex min-h-[420px] flex-col", className)}>
      <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {isEmpty ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
            <div className="hero-ring-glow flex h-14 w-14 items-center justify-center rounded-2xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/60 dark:bg-stone-900/60 backdrop-blur-sm">
              <Sparkles className="h-7 w-7 text-stone-500 dark:text-stone-400" />
            </div>
            <div>
              <h2 className="font-sport text-2xl text-head-of-table sm:text-3xl">
                LangChain 어시스턴트
              </h2>
              <p className="mt-1.5 text-sm text-stone-500 dark:text-stone-400">
                무엇이든 편하게 대화해 보세요
              </p>
            </div>
          </div>
        ) : (
          <div className="flex min-h-full flex-col justify-end gap-3 pb-4">
            {state.messages.map((msg, idx) => (
              <div
                key={`${msg.ts}-${idx}`}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl border px-4 py-2.5 text-sm leading-relaxed",
                    msg.role === "user"
                      ? "border-amber-400/30 bg-amber-500/10 text-stone-900 dark:text-stone-50"
                      : "border-stone-300/50 dark:border-stone-700/50 bg-stone-100/60 dark:bg-stone-800/60 text-stone-800 dark:text-stone-100",
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                </div>
              </div>
            ))}
            {state.isLoading && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-100/60 dark:bg-stone-800/60 px-4 py-2.5">
                  <Loader2 size={16} className="animate-spin text-stone-400 dark:text-stone-500" />
                </div>
              </div>
            )}
            <div aria-hidden className="h-px shrink-0" />
          </div>
        )}
      </div>

      {state.errorMessage && (
        <div className="mb-3 rounded-lg border border-red-300/60 dark:border-red-800/60 bg-red-50/60 dark:bg-red-900/20 p-3">
          <p className="mb-2 text-sm text-red-700 dark:text-red-400">{state.errorMessage}</p>
          {state.lastPayload && (
            <button
              type="button"
              onClick={handleRetry}
              className="inline-flex items-center gap-1 rounded-lg border border-red-300 dark:border-red-700 bg-white dark:bg-stone-900 px-3 py-1.5 text-xs font-medium text-red-700 dark:text-red-400 transition-colors hover:bg-red-50 dark:hover:bg-red-900/30"
            >
              <RefreshCw size={14} />
              재시도
            </button>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex items-center gap-2 rounded-full border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/50 dark:bg-stone-900/60 px-2 py-1.5 backdrop-blur-sm">
          <label htmlFor="langchain-chat-input" className="sr-only">
            메시지 보내기
          </label>
          <input
            ref={inputRef}
            id="langchain-chat-input"
            name="message"
            type="text"
            onKeyDown={handleKeyDown}
            placeholder="메시지를 입력하세요"
            maxLength={2000}
            disabled={state.isLoading}
            autoComplete="off"
            className="w-full border-0 bg-transparent px-2 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none focus:ring-0 disabled:opacity-50 dark:text-stone-100 dark:placeholder:text-stone-500"
          />
          <button
            type="submit"
            disabled={state.isLoading}
            aria-label="전송"
            className="btn-champion inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border disabled:opacity-40"
          >
            {state.isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={16} strokeWidth={1.75} />
            )}
          </button>
        </div>
        <p className="text-center text-[11px] leading-relaxed text-stone-400 dark:text-stone-500">
          AI가 생성한 답변이라 부정확할 수 있어요 · Enter로 전송
        </p>
      </form>
    </div>
  );
}
