"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { Loader2, RefreshCw, Send } from "lucide-react";
import { KayfabeMark } from "@/components/kayfabe-logo";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  ts: string;
}

type WrestlerChatPanelState = {
  messages: ChatMessage[];
  isLoading: boolean;
  errorMessage: string | null;
  lastPayload: ChatMessage[] | null;
};

const initialState: WrestlerChatPanelState = {
  messages: [],
  isLoading: false,
  errorMessage: null,
  lastPayload: null,
};

const CHAT_REQUEST_FAILED = "메시지를 전송하지 못했습니다.";

const SUGGESTIONS = [
  "로만 레인즈는 어디 출신이야?",
  "코디 로즈 피니셔가 뭐야?",
  "가장 최근에 데뷔한 선수는?",
];

export function WrestlerChatPanel({ className }: { className?: string }) {
  const [state, setState] = useState<WrestlerChatPanelState>(initialState);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const patchState = useCallback(
    (patch: Partial<WrestlerChatPanelState>) =>
      setState((prev) => ({ ...prev, ...patch })),
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

    const assistantTs = new Date().toISOString();
    patchState({
      isLoading: true,
      errorMessage: null,
      lastPayload: history,
      messages: [...history, { role: "assistant", text: "", ts: assistantTs }],
    });

    try {
      const response = await fetch("/api/kayfabe/wwe-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (!response.ok || !response.body) {
        patchState({ messages: history, errorMessage: CHAT_REQUEST_FAILED });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let reply = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        reply += decoder.decode(value, { stream: true });
        patchState({
          messages: [...history, { role: "assistant", text: reply, ts: assistantTs }],
        });
      }

      reply = reply.trim();
      if (!reply) {
        patchState({ messages: history, errorMessage: CHAT_REQUEST_FAILED });
        return;
      }
      patchState({
        messages: [...history, { role: "assistant", text: reply, ts: assistantTs }],
        lastPayload: null,
      });
    } catch {
      patchState({ messages: history, errorMessage: CHAT_REQUEST_FAILED });
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
              <KayfabeMark className="h-8 w-8" />
            </div>
            <div>
              <h2 className="font-sport text-2xl text-head-of-table sm:text-3xl">
                고릴라 포지션
              </h2>
              <p className="mt-1.5 text-sm text-stone-500 dark:text-stone-400">
                선수 정보라면 뭐든 물어보세요
              </p>
              <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-500">
                WWE 로스터 정보로 24시간 대기 중입니다
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => submitText(s)}
                  className="rounded-full border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/40 dark:bg-stone-900/40 px-3 py-1.5 text-xs text-stone-600 dark:text-stone-300 transition-colors hover:bg-stone-200/60 dark:hover:bg-stone-800/60"
                >
                  {s}
                </button>
              ))}
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
                  {msg.text ? (
                    <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                  ) : (
                    <Loader2
                      size={16}
                      className="animate-spin text-stone-400 dark:text-stone-500"
                    />
                  )}
                </div>
              </div>
            ))}
            <div aria-hidden className="h-px shrink-0" />
          </div>
        )}
      </div>

      {state.errorMessage && (
        <div className="mb-3 rounded-lg border border-red-300/60 dark:border-red-800/60 bg-red-50/60 dark:bg-red-900/20 p-3">
          <p className="mb-2 text-sm text-red-700 dark:text-red-400">
            {state.errorMessage}
          </p>
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
          <label htmlFor="wrestler-chat-input" className="sr-only">
            선수 정보 물어보기
          </label>
          <input
            ref={inputRef}
            id="wrestler-chat-input"
            name="message"
            type="text"
            onKeyDown={handleKeyDown}
            placeholder="선수 정보를 물어보세요"
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
