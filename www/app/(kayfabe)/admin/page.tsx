"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession, signIn, signOut } from "next-auth/react";
import { useAuth } from "@/context/auth-context";
import {
  ChevronDown,
  Mail,
  Inbox,
  Medal,
  Send,
  Loader2,
  CheckCircle,
  AlertCircle,
  BookUser,
  Plus,
  SendHorizonal,
  MailOpen,
} from "lucide-react";
import { ContactsCsvUpload } from "@/components/contacts-csv-upload";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/**
 * 탭은 **실제로 있는 것만** 적는다.
 *
 * 예전에는 대시보드·CRM·물류·SaaS·크립토·채팅·캘린더·파일 관리까지 열 개가 서 있었는데,
 * 이메일과 결과를 뺀 나머지는 눌러도 아무 데도 가지 않는 장식이었다. 대시보드 탭이 그리던
 * 매출·회원·근무시간·리텐션 수치도 전부 하드코딩이었다 — 이 제품의 데이터가 아니라
 * 템플릿에 딸려 온 숫자다. 관리자만 보는 화면이라 노출 문제는 아니었지만, **화면이 자기
 * 데이터에 대해 거짓말을 하고 있었다** (DESIGN.md §7 "숫자를 지어내지 않는다").
 *
 * 그래서 가짜를 걷어내고 실제로 도는 도구만 남겼다. 다시 늘릴 때는 **그 탭이 가리키는
 * 화면이 먼저 있어야** 한다.
 */
const NAV_TABS: {
  label: string;
  icon: typeof Inbox;
  dropdown: boolean;
  href?: string;
}[] = [
  // `dropdown`은 열리는 메뉴가 **있을 때만** 켠다. 예전에는 켜 두고 꺾쇠만 그려서,
  // 눌러도 아무것도 안 열리는 화살표가 붙어 있었다.
  { label: "이메일", icon: Inbox, dropdown: false },
  { label: "결과", icon: Medal, dropdown: false, href: "/results" },
];

// ── 공통 카드 ─────────────────────────────────────────────────────────────────

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-stone-300/50 dark:border-stone-700/50 bg-stone-50/70 dark:bg-stone-950/70 ${className}`}
    >
      {children}
    </div>
  );
}

// ── 이메일 작성 ───────────────────────────────────────────────────────────────

type SendState = "idle" | "sending" | "success" | "error";
type Suggestion = { name: string; email: string };

function EmailComposeCard() {
  const { status } = useSession();
  const isGoogleLinked = status === "authenticated";

  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sendState, setSendState] = useState<SendState>("idle");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleToChange = (value: string) => {
    setTo(value);
    setSuggestions([]);
    clearTimeout(debounceRef.current);
    if (!value) return;
    debounceRef.current = setTimeout(async () => {
      const res = await fetch(`/api/contacts?q=${encodeURIComponent(value)}`, {});
      if (res.ok) setSuggestions(await res.json());
    }, 300);
  };

  const selectSuggestion = (s: Suggestion) => {
    setTo(s.email);
    setSuggestions([]);
  };

  const handleSend = async () => {
    if (!to || !subject || !body) return;
    setSendState("sending");
    try {
      const res = await fetch("/api/email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ to, subject, body }),
      });
      setSendState(res.ok ? "success" : "error");
      if (res.ok) {
        setTo("");
        setSubject("");
        setBody("");
      }
    } catch {
      setSendState("error");
    }
    setTimeout(() => setSendState("idle"), 3000);
  };

  const inputCls =
    "w-full rounded-lg border border-stone-700/60 bg-stone-900/60 px-3 py-2 text-sm text-stone-100 placeholder-stone-600 outline-none focus:border-stone-500 transition-colors";

  return (
    <Card className="w-full p-6">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-stone-400" />
          <h2 className="text-sm font-semibold text-stone-100">이메일 작성</h2>
        </div>

        {isGoogleLinked ? (
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[11px] text-emerald-400">
              <CheckCircle className="h-3 w-3" /> 주소록 연동됨
            </span>
            <button
              onClick={() => signOut({ redirect: false })}
              className="text-[11px] text-stone-500 underline hover:text-stone-300"
            >
              해제
            </button>
          </div>
        ) : (
          <button
            onClick={() => signIn("google")}
            className="flex items-center gap-1.5 rounded-lg border border-stone-600/70 bg-stone-800/60 px-3 py-1.5 text-[11px] text-stone-300 transition-colors hover:bg-stone-700/60"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Google 주소록 연동
          </button>
        )}
      </div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] text-stone-500">
            받는 사람
            <span className="ml-1 text-stone-600">— 이름으로 검색 가능</span>
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder={isGoogleLinked ? "이름 또는 이메일 입력" : "example@gmail.com"}
              value={to}
              onChange={(e) => handleToChange(e.target.value)}
              onBlur={() => setTimeout(() => setSuggestions([]), 150)}
              className={inputCls}
            />
            {suggestions.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-stone-700 bg-stone-900 shadow-xl">
                {suggestions.map((s) => (
                  <li
                    key={s.email}
                    onMouseDown={() => selectSuggestion(s)}
                    className="flex cursor-pointer flex-col px-3 py-2.5 hover:bg-stone-800"
                  >
                    <span className="text-xs font-medium text-stone-100">{s.name}</span>
                    <span className="text-[11px] text-stone-400">{s.email}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-[11px] text-stone-500">제목</label>
          <input
            type="text"
            placeholder="제목을 입력하세요"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="mb-1 block text-[11px] text-stone-500">내용</label>
          <textarea
            rows={8}
            placeholder="내용을 입력하세요"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className={`${inputCls} resize-none`}
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          {sendState === "success" && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5" /> 전송 완료
            </span>
          )}
          {sendState === "error" && (
            <span className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertCircle className="h-3.5 w-3.5" /> 전송 실패
            </span>
          )}
          {sendState === "idle" && <span />}

          <button
            onClick={handleSend}
            disabled={sendState === "sending" || !to || !subject || !body}
            className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sendState === "sending" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {sendState === "sending" ? "전송 중..." : "보내기"}
          </button>
        </div>
      </div>
    </Card>
  );
}

// ── 텔레그램 작성 ─────────────────────────────────────────────────────────────

function TelegramComposeCard() {
  const [chatId, setChatId] = useState("");
  const [message, setMessage] = useState("");
  const [sendState, setSendState] = useState<SendState>("idle");

  const inputCls =
    "w-full rounded-lg border border-stone-700/60 bg-stone-900/60 px-3 py-2 text-sm text-stone-100 placeholder-stone-600 outline-none focus:border-stone-500 transition-colors";

  const handleSend = async () => {
    if (!chatId || !message) return;
    setSendState("sending");
    try {
      const res = await fetch("/api/telegram", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ chatId, message }),
      });
      setSendState(res.ok ? "success" : "error");
      if (res.ok) {
        setChatId("");
        setMessage("");
      }
    } catch {
      setSendState("error");
    }
    setTimeout(() => setSendState("idle"), 3000);
  };

  return (
    <Card className="w-full p-6">
      <div className="mb-5 flex items-center gap-2">
        <SendHorizonal className="h-4 w-4 text-stone-400" />
        <h2 className="text-sm font-semibold text-stone-100">텔레그램 메시지</h2>
      </div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] text-stone-500">Chat ID</label>
          <input
            type="text"
            placeholder="@username 또는 숫자 Chat ID"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className={inputCls}
          />
        </div>

        <div>
          <label className="mb-1 block text-[11px] text-stone-500">메시지</label>
          <textarea
            rows={8}
            placeholder="전송할 메시지를 입력하세요 (HTML 태그 지원)"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className={`${inputCls} resize-none`}
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          {sendState === "success" && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle className="h-3.5 w-3.5" /> 전송 완료
            </span>
          )}
          {sendState === "error" && (
            <span className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertCircle className="h-3.5 w-3.5" /> 전송 실패
            </span>
          )}
          {sendState === "idle" && <span />}

          <button
            onClick={handleSend}
            disabled={sendState === "sending" || !chatId || !message}
            className="flex items-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sendState === "sending" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {sendState === "sending" ? "전송 중..." : "보내기"}
          </button>
        </div>
      </div>
    </Card>
  );
}

// ── 받은편지함 ────────────────────────────────────────────────────────────────

type ReceiverEmail = {
  id: number;
  from_email: string;
  from_name: string;
  subject: string;
  body: string;
  receiver_at: string;
  is_read: boolean;
};

function ReceiverPanel() {
  const [emails, setEmails] = useState<ReceiverEmail[]>([]);
  const [selected, setSelected] = useState<ReceiverEmail | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchEmails = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/receiver", {});
      if (res.ok) setEmails(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmails();
  }, []);

  const openEmail = async (email: ReceiverEmail) => {
    setSelected(email);
    if (!email.is_read) {
      const res = await fetch(`/api/receiver/${email.id}/read`, {
        method: "PATCH",
      });
      if (res.ok) {
        setEmails((prev) => prev.map((e) => (e.id === email.id ? { ...e, is_read: true } : e)));
      }
    }
  };

  const unreadCount = emails.filter((e) => !e.is_read).length;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      {/* 메일 목록 */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-stone-700/50 px-4 py-3">
          <div className="flex items-center gap-2">
            <Inbox className="h-4 w-4 text-stone-400" />
            <span className="text-sm font-semibold text-stone-100">받은편지함</span>
            {unreadCount > 0 && (
              <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {unreadCount}
              </span>
            )}
          </div>
          <button
            onClick={fetchEmails}
            className="text-[11px] text-stone-500 hover:text-stone-300 transition-colors"
          >
            새로고침
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-stone-500" />
          </div>
        ) : emails.length === 0 ? (
          <div className="py-12 text-center text-[11px] text-stone-600">받은 메일이 없습니다.</div>
        ) : (
          <ul className="divide-y divide-stone-800 overflow-y-auto max-h-[600px]">
            {emails.map((email) => (
              <li
                key={email.id}
                onClick={() => openEmail(email)}
                className={`cursor-pointer px-4 py-3 transition-colors hover:bg-stone-800/50 ${
                  selected?.id === email.id ? "bg-stone-800/70" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {!email.is_read && (
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500" />
                      )}
                      <span
                        className={`truncate text-xs ${email.is_read ? "text-stone-400" : "font-semibold text-stone-100"}`}
                      >
                        {email.from_name || email.from_email}
                      </span>
                    </div>
                    <p
                      className={`mt-0.5 truncate text-[11px] ${email.is_read ? "text-stone-600" : "text-stone-300"}`}
                    >
                      {email.subject || "(제목 없음)"}
                    </p>
                  </div>
                  <span className="shrink-0 text-[10px] text-stone-600">
                    {new Date(email.receiver_at).toLocaleDateString("ko-KR", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* 메일 본문 */}
      <Card className="p-5">
        {selected ? (
          <>
            <div className="mb-4 border-b border-stone-700/50 pb-4">
              <h3 className="mb-2 text-sm font-semibold text-stone-100">
                {selected.subject || "(제목 없음)"}
              </h3>
              <div className="flex items-center gap-2 text-[11px] text-stone-500">
                <MailOpen className="h-3.5 w-3.5" />
                <span>
                  {selected.from_name
                    ? `${selected.from_name} <${selected.from_email}>`
                    : selected.from_email}
                </span>
                <span>·</span>
                <span>{new Date(selected.receiver_at).toLocaleString("ko-KR")}</span>
              </div>
            </div>
            <div
              className="prose prose-sm prose-invert max-w-none text-stone-300"
              dangerouslySetInnerHTML={{ __html: selected.body || "" }}
            />
          </>
        ) : (
          <div className="flex h-full min-h-[200px] items-center justify-center text-[11px] text-stone-600">
            메일을 선택하면 내용이 표시됩니다.
          </div>
        )}
      </Card>
    </div>
  );
}

// ── 주소록 패널 ───────────────────────────────────────────────────────────────

type ContactItem = {
  id: number;
  name: string;
  email: string;
  phone: string;
  org_name: string;
};

function AddressBookPanel() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [resetting, setResetting] = useState(false);

  const fetchContacts = async () => {
    try {
      const res = await fetch("/api/contacts/list", {});
      if (res.ok) setContacts(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchContacts();
  }, []);

  const handleUploadClose = (open: boolean) => {
    setUploadOpen(open);
    if (!open) fetchContacts();
  };

  const handleReset = async () => {
    if (!window.confirm("연락처를 모두 삭제하시겠습니까?")) return;
    setResetting(true);
    try {
      await fetch("/api/contacts/list", {
        method: "DELETE",
      });
      setContacts([]);
    } finally {
      setResetting(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookUser className="h-4 w-4 text-stone-400" />
          <h3 className="text-sm font-semibold text-stone-100">주소록</h3>
          {contacts.length > 0 && (
            <span className="rounded-full bg-stone-700 px-1.5 py-0.5 text-[10px] text-stone-300">
              {contacts.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {contacts.length > 0 && (
            <button
              onClick={handleReset}
              disabled={resetting}
              className="flex items-center gap-1 rounded-lg border border-red-800/60 bg-red-900/30 px-2.5 py-1 text-[11px] font-medium text-red-400 transition-colors hover:bg-red-900/50 disabled:opacity-50"
            >
              {resetting ? "삭제 중..." : "리셋"}
            </button>
          )}
          <button
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-1 rounded-lg border border-stone-600/70 bg-stone-800/45 px-2.5 py-1 text-[11px] font-medium text-stone-200 transition-colors hover:bg-stone-700/65"
          >
            <Plus className="h-3 w-3" />
            등록
          </button>
        </div>
      </div>

      {contacts.length === 0 ? (
        <div className="py-8 text-center text-[11px] text-stone-600">
          등록된 연락처가 없습니다.
          <br />
          CSV 파일을 업로드해 주세요.
        </div>
      ) : (
        <ul className="max-h-[360px] divide-y divide-stone-800 overflow-y-auto">
          {contacts.map((c) => (
            <li key={c.id} className="flex flex-col gap-0.5 py-2.5">
              <span className="text-[12px] font-medium text-stone-100">{c.name}</span>
              {c.org_name && <span className="text-[10px] text-stone-400">{c.org_name}</span>}
              {c.email && <span className="text-[10px] text-stone-500">{c.email}</span>}
              {c.phone && <span className="text-[10px] text-stone-500">{c.phone}</span>}
            </li>
          ))}
        </ul>
      )}

      <Dialog open={uploadOpen} onOpenChange={handleUploadClose}>
        <DialogContent className="max-w-2xl border-stone-700/60 bg-stone-950">
          <DialogHeader>
            <DialogTitle className="text-stone-100">주소록 CSV 업로드</DialogTitle>
          </DialogHeader>
          <ContactsCsvUpload />
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ── 페이지 ────────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const router = useRouter();
  const { user, isReady } = useAuth();
  const isAdmin = isReady && user?.role === "admin";

  const [activeTab, setActiveTab] = useState("이메일");
  const [emailSubTab, setEmailSubTab] = useState<"이메일" | "텔레그램" | "받은편지함">("이메일");
  const [showAddressBook, setShowAddressBook] = useState(false);

  useEffect(() => {
    if (isReady && !isAdmin) {
      router.replace("/");
    }
  }, [isReady, isAdmin, router]);

  if (!isReady || !isAdmin) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-white text-stone-500 dark:bg-[#0a0a0c] dark:text-stone-400">
        불러오는 중...
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-white dark:bg-[#0a0a0c] text-stone-900 dark:text-stone-100">
      {/* 서브 내비게이션 */}
      <div className="border-b border-stone-200/80 dark:border-white/10 bg-white dark:bg-[#0a0a0c]">
        <div className="mx-auto max-w-7xl px-3">
          <div className="flex gap-0.5 overflow-x-auto py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {NAV_TABS.map(({ label, icon: Icon, dropdown, href }) => {
              const tabClassName = `flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors ${
                activeTab === label
                  ? "border border-stone-400 bg-stone-600 text-stone-50"
                  : "border border-transparent text-stone-500 dark:text-stone-400 hover:bg-stone-100/60 dark:hover:bg-stone-800/60 hover:text-stone-800 dark:hover:text-stone-200"
              }`;

              if (href) {
                return (
                  <Link key={label} href={href} className={tabClassName}>
                    <Icon className="h-3.5 w-3.5" />
                    <span>{label}</span>
                  </Link>
                );
              }

              return (
                <button key={label} onClick={() => setActiveTab(label)} className={tabClassName}>
                  <Icon className="h-3.5 w-3.5" />
                  <span>{label}</span>
                  {dropdown && <ChevronDown className="h-2.5 w-2.5 opacity-60" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <main className="mx-auto max-w-7xl px-3 py-4 sm:px-5 sm:py-5 lg:px-6 lg:py-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex gap-1">
            {(["이메일", "텔레그램", "받은편지함"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setEmailSubTab(t)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  emailSubTab === t
                    ? "border border-stone-400 bg-stone-600 text-stone-50"
                    : "border border-transparent text-stone-400 hover:bg-stone-800/60 hover:text-stone-200"
                }`}
              >
                {t === "이메일" ? (
                  <Mail className="h-3.5 w-3.5" />
                ) : t === "텔레그램" ? (
                  <SendHorizonal className="h-3.5 w-3.5" />
                ) : (
                  <Inbox className="h-3.5 w-3.5" />
                )}
                {t}
              </button>
            ))}
          </div>
          {emailSubTab === "이메일" && (
            <button
              onClick={() => setShowAddressBook((v) => !v)}
              className={[
                "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[11px] font-medium transition-colors",
                showAddressBook
                  ? "border-stone-400 bg-stone-600 text-stone-50"
                  : "border-stone-600/70 bg-stone-800/45 text-stone-300 hover:bg-stone-700/65",
              ].join(" ")}
            >
              <BookUser className="h-3.5 w-3.5" />
              주소록
            </button>
          )}
        </div>
        {emailSubTab === "이메일" ? (
          <div
            className={
              showAddressBook ? "grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_300px]" : ""
            }
          >
            <EmailComposeCard />
            {showAddressBook && <AddressBookPanel />}
          </div>
        ) : emailSubTab === "텔레그램" ? (
          <TelegramComposeCard />
        ) : (
          <ReceiverPanel />
        )}
      </main>
    </div>
  );
}
