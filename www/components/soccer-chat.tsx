"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Plus, RefreshCw, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseApiError } from "@/lib/api";

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  ts: string;
};

type ChatState = {
  messages: ChatMessage[];
  isLoading: boolean;
  errorMessage: string | null;
  lastPayload: ChatMessage[] | null;
};

const INITIAL_ASSISTANT_TEXT =
  "안녕하세요, 축구 스카우트 soccer입니다. " +
  "경기장, 구단, 경기 일정, 선수 정보까지 무엇이든 물어보세요.";

const CHAT_REQUEST_FAILED = "메시지를 전송하지 못했습니다.";

export function SoccerChat({ className }: { className?: string }) {
  const [state, setState] = useState<ChatState>(() => ({
    messages: [{ role: "assistant", text: INITIAL_ASSISTANT_TEXT, ts: new Date().toISOString() }],
    isLoading: false,
    errorMessage: null,
    lastPayload: null,
  }));
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const patchState = useCallback(
    (patch: Partial<ChatState>) => setState((prev) => ({ ...prev, ...patch })),
    [],
  );

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [state.messages, state.isLoading]);

  const sendWithHistory = async (history: ChatMessage[]) => {
    const last = history[history.length - 1];
    if (!last || last.role !== "user" || !last.text.trim()) return;

    const assistantTs = new Date().toISOString();
    const draftAssistant: ChatMessage = {
      role: "assistant",
      text: "",
      ts: assistantTs,
    };

    patchState({
      isLoading: true,
      errorMessage: null,
      lastPayload: history,
      messages: [...history, draftAssistant],
    });

    try {
      const response = await fetch("/api/soccer/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        patchState({
          messages: history,
          errorMessage: parseApiError(data, response.status) || CHAT_REQUEST_FAILED,
        });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        patchState({ messages: history, errorMessage: CHAT_REQUEST_FAILED });
        return;
      }

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

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (state.isLoading) return;

    const text = String(new FormData(e.currentTarget).get("message") ?? "").trim();
    if (!text) return;

    const userMessage: ChatMessage = {
      role: "user",
      text,
      ts: new Date().toISOString(),
    };
    const next = [...state.messages, userMessage];
    patchState({ messages: next });
    e.currentTarget.reset();
    void sendWithHistory(next);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  };

  const formatTime = (ts: string) =>
    new Date(ts).toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col overflow-hidden", className)}>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-1 pb-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {state.messages.map((msg, idx) => {
            const isStreamingDraft =
              state.isLoading &&
              idx === state.messages.length - 1 &&
              msg.role === "assistant" &&
              !msg.text.trim();

            if (isStreamingDraft) {
              return (
                <div key={`${msg.ts}-${idx}`} className="flex justify-start">
                  <div className="rounded-3xl border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-950/50 px-4 py-3">
                    <Loader2 className="size-5 animate-spin text-stone-400" />
                  </div>
                </div>
              );
            }

            if (!msg.text.trim()) return null;

            return (
              <div
                key={`${msg.ts}-${idx}`}
                className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[88%] rounded-3xl px-4 py-3 text-sm leading-relaxed shadow-sm",
                    msg.role === "user"
                      ? "bg-stone-200 dark:bg-stone-100 text-stone-900"
                      : "border border-stone-300/60 dark:border-stone-700/60 bg-stone-100/50 dark:bg-stone-950/50 text-stone-800 dark:text-stone-100",
                  )}
                >
                  {msg.role === "assistant" && (
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-stone-400">
                      Soccer
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                  <p className="mt-1.5 text-[11px] text-stone-500" suppressHydrationWarning>
                    {formatTime(msg.ts)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {state.errorMessage && (
        <div className="mx-auto mb-3 w-full max-w-3xl rounded-xl border border-red-400/40 dark:border-red-900/40 bg-red-50/80 dark:bg-red-950/30 px-4 py-3">
          <p className="text-sm text-red-700 dark:text-red-200">{state.errorMessage}</p>
          {state.lastPayload && (
            <button
              type="button"
              onClick={() => {
                patchState({ errorMessage: null });
                void sendWithHistory(state.lastPayload!);
              }}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-red-700 dark:text-red-100 hover:underline"
            >
              <RefreshCw className="size-3.5" />
              재시도
            </button>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mx-auto w-full max-w-3xl shrink-0">
        <div className="rounded-[1.75rem] border border-stone-300/70 dark:border-stone-600/70 bg-stone-100/70 dark:bg-stone-950/70 px-3 py-2 shadow-lg shadow-black/20 backdrop-blur-sm">
          <label htmlFor="soccer-chat-input" className="sr-only">
            soccer에게 메시지 보내기
          </label>
          <textarea
            ref={textareaRef}
            id="soccer-chat-input"
            name="message"
            rows={1}
            maxLength={4000}
            disabled={state.isLoading}
            onKeyDown={handleKeyDown}
            placeholder="선수, 구단, 경기 정보를 물어보세요"
            className="w-full resize-none border-0 bg-transparent px-2 py-2 text-sm text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-500 focus:outline-none disabled:opacity-50"
          />
          <div className="flex items-center justify-between gap-2 border-t border-stone-200/80 dark:border-stone-800/80 pt-2">
            <button
              type="button"
              title="준비 중입니다"
              aria-label="첨부"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-stone-500 dark:text-stone-400 hover:bg-stone-200/80 dark:hover:bg-stone-800/80 hover:text-stone-700 dark:hover:text-stone-200"
            >
              <Plus className="size-5" strokeWidth={1.75} />
            </button>

            <div className="flex items-center gap-1">
              <button
                type="submit"
                disabled={state.isLoading}
                aria-label="전송"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-stone-100 text-stone-900 hover:bg-white disabled:opacity-40"
              >
                {state.isLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" strokeWidth={1.75} />
                )}
              </button>
            </div>
          </div>
        </div>
        <p className="mt-2 text-center text-[11px] text-stone-500">
          Enter로 전송 · Shift+Enter로 줄바꿈
        </p>
      </form>
    </div>
  );
}
