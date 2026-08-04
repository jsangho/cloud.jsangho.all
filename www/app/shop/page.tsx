"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, ShoppingBag } from "lucide-react";
import { useAuth } from "@/context/auth-context";
import { cn } from "@/lib/utils";
import { WweArenaShell } from "@/components/wwe-arena-shell";
import {
  fetchInventory,
  fetchShopItems,
  fetchWallet,
  purchaseShopItem,
  setItemEquipped,
  type InventoryItem,
  type ShopItem,
  type Wallet,
} from "@/lib/shop-api";

type Notice = { kind: "ok" | "error"; message: string };

type ShopPageState = {
  loading: boolean;
  unavailable: boolean;
  items: ShopItem[];
  wallet: Wallet | null;
  inventory: InventoryItem[];
  /** 구매·장착 요청이 진행 중인 대상. 버튼 중복 클릭을 막는다. */
  pending: string | null;
  notice: Notice | null;
};

const initialState: ShopPageState = {
  loading: true,
  unavailable: false,
  items: [],
  wallet: null,
  inventory: [],
  pending: null,
  notice: null,
};

const CATEGORY_LABELS: Readonly<Record<string, string>> = {
  title: "칭호",
  nickname_color: "닉네임 색상",
  badge: "뱃지",
  report: "여론 리포트",
  hof: "명예의 전당",
};

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

function formatPoints(value: number): string {
  return value.toLocaleString("ko-KR");
}

function WalletStrip({ wallet }: { wallet: Wallet }) {
  const cells = [
    { label: "획득", value: wallet.earned },
    { label: "사용", value: wallet.spent },
    { label: "보유", value: wallet.balance, highlight: true },
  ];

  return (
    <div className="rankings-panel mb-6 grid grid-cols-3 gap-2 rounded-2xl px-4 py-4 sm:rounded-3xl sm:px-6">
      {cells.map((cell) => (
        <div key={cell.label} className="text-center">
          <p className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
            {cell.label}
          </p>
          <p
            className={cn(
              "mt-1 text-lg font-bold tabular-nums sm:text-xl",
              cell.highlight
                ? "text-brand-600 dark:text-brand-300"
                : "text-stone-700 dark:text-stone-200",
            )}
          >
            {formatPoints(cell.value)}
            <span className="ml-0.5 text-xs font-semibold">P</span>
          </p>
        </div>
      ))}
    </div>
  );
}

function ItemCard({
  item,
  owned,
  disabled,
  pending,
  onBuy,
}: {
  item: ShopItem;
  owned: boolean;
  disabled: boolean;
  pending: boolean;
  onBuy: () => void;
}) {
  return (
    <li className="rankings-panel flex flex-col gap-3 rounded-2xl px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
            {categoryLabel(item.category)}
          </p>
          <h3 className="mt-1 truncate text-base font-bold text-stone-900 dark:text-stone-50">
            {item.name}
          </h3>
        </div>
        <span className="shrink-0 rounded-full border border-brand-500/35 bg-brand-500/10 px-2 py-1 text-xs font-bold tabular-nums text-brand-700 dark:text-brand-200">
          {formatPoints(item.price)} P
        </span>
      </div>

      {item.description && (
        <p className="text-sm leading-relaxed text-stone-500 dark:text-stone-400">
          {item.description}
        </p>
      )}

      <button
        type="button"
        onClick={onBuy}
        disabled={owned || disabled || pending}
        className={cn(
          "mt-auto inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-4 text-sm font-semibold transition",
          owned || disabled
            ? "cursor-not-allowed border border-stone-300/70 dark:border-stone-700/70 text-stone-400"
            : "bg-brand-500 text-stone-950 hover:bg-brand-400",
        )}
      >
        {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
        {owned ? "보유 중" : "구매"}
      </button>

      {item.isConsumable && !owned && (
        <p className="text-xs text-stone-500">소모성 아이템은 사용할 경기를 고른 뒤 구매합니다.</p>
      )}
    </li>
  );
}

function InventoryRow({
  entry,
  pending,
  onToggle,
}: {
  entry: InventoryItem;
  pending: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-stone-200/35 dark:border-stone-800/35 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-stone-800 dark:text-stone-100">
          {entry.itemName}
        </p>
        <p className="text-xs text-stone-500">
          {categoryLabel(entry.category)}
          {entry.contextKey && ` · ${entry.contextKey}`}
        </p>
      </div>
      <button
        type="button"
        onClick={onToggle}
        disabled={pending}
        className={cn(
          "inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold transition",
          entry.isEquipped
            ? "border-brand-500/40 bg-brand-500/10 text-brand-700 dark:text-brand-200"
            : "border-stone-300/70 dark:border-stone-700/70 text-stone-500 hover:text-stone-800 dark:hover:text-stone-200",
        )}
      >
        {pending && <Loader2 className="h-3 w-3 animate-spin" aria-hidden />}
        {entry.isEquipped ? "장착 중" : "장착"}
      </button>
    </li>
  );
}

export default function ShopPage() {
  const { user, isReady } = useAuth();
  const [state, setState] = useState<ShopPageState>(initialState);
  const isSignedIn = user != null;

  useEffect(() => {
    if (!isReady) return;

    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, unavailable: false }));

    void (async () => {
      const [items, wallet, inventory] = await Promise.all([
        fetchShopItems(),
        isSignedIn ? fetchWallet() : Promise.resolve(null),
        isSignedIn ? fetchInventory() : Promise.resolve([]),
      ]);
      if (cancelled) return;
      setState((prev) => ({
        ...prev,
        loading: false,
        // 로그인 상태에서 지갑을 못 받아 오면 백엔드가 응답하지 않는 것으로 본다.
        unavailable: isSignedIn && wallet === null,
        items,
        wallet,
        inventory,
      }));
    })();

    return () => {
      cancelled = true;
    };
  }, [isReady, isSignedIn]);

  const handleBuy = useCallback(
    (item: ShopItem) => {
      if (!isSignedIn) return;
      setState((prev) => ({ ...prev, pending: item.code, notice: null }));

      void (async () => {
        try {
          const receipt = await purchaseShopItem(item.code);
          const [wallet, inventory] = await Promise.all([
            fetchWallet(),
            fetchInventory(),
          ]);
          setState((prev) => ({
            ...prev,
            pending: null,
            wallet: wallet ?? prev.wallet,
            inventory,
            notice: {
              kind: "ok",
              message: `${item.name} 구매 완료 — 남은 포인트 ${formatPoints(receipt.balanceAfter)}P`,
            },
          }));
        } catch (error) {
          setState((prev) => ({
            ...prev,
            pending: null,
            notice: {
              kind: "error",
              message:
                error instanceof Error
                  ? error.message
                  : "구매하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            },
          }));
        }
      })();
    },
    [isSignedIn],
  );

  const handleToggleEquip = useCallback(
    (entry: InventoryItem) => {
      if (!isSignedIn) return;
      const key = `inventory:${entry.id}`;
      setState((prev) => ({ ...prev, pending: key, notice: null }));

      void (async () => {
        const updated = await setItemEquipped(entry.id, !entry.isEquipped);
        // 장착하면 서버가 같은 카테고리의 다른 아이템을 함께 내린다. 응답 한 건만
        // 반영하면 내려간 아이템이 화면에 계속 "장착 중"으로 남으므로 다시 읽는다.
        const refreshed = updated ? await fetchInventory() : [];
        setState((prev) => ({
          ...prev,
          pending: null,
          // 방금 장착한 아이템이 있으니 빈 목록은 조회 실패다 — 직전 상태를 유지한다.
          inventory: refreshed.length > 0 ? refreshed : prev.inventory,
          notice: updated ? null : { kind: "error", message: "장착 상태를 바꾸지 못했습니다." },
        }));
      })();
    },
    [isSignedIn],
  );

  const { loading, unavailable, items, wallet, inventory, pending, notice } = state;
  const ownedCodes = new Set(inventory.filter((i) => !i.contextKey).map((i) => i.itemCode));

  return (
    <WweArenaShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-10">
        <header className="relative mb-8 text-center sm:mb-10">
          <div
            aria-hidden
            className="hero-title-backdrop mx-auto"
            style={{ height: "8rem", width: "min(100%, 22rem)" }}
          />
          <h1 className="font-kr-hero relative z-10 text-2xl text-stone-900 dark:text-white sm:text-3xl md:text-4xl">
            상점
          </h1>
          <p className="relative z-10 mx-auto mt-3 max-w-lg text-sm font-medium leading-relaxed text-stone-400 sm:text-base">
            예측으로 모은{" "}
            <span className="font-semibold text-stone-700 dark:text-stone-200">포인트</span>를
            아이템으로 교환하세요.
          </p>
        </header>

        {wallet && <WalletStrip wallet={wallet} />}

        {notice && (
          <p
            role="status"
            className={cn(
              "mb-6 rounded-xl px-4 py-3 text-sm font-medium",
              notice.kind === "ok"
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "bg-red-500/10 text-red-700 dark:text-red-300",
            )}
          >
            {notice.message}
          </p>
        )}

        {!isReady || loading ? (
          <div className="rankings-panel flex items-center justify-center gap-2 rounded-2xl px-4 py-16 text-sm text-stone-400 sm:rounded-3xl">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            불러오는 중…
          </div>
        ) : unavailable ? (
          <div className="rankings-panel rounded-2xl px-4 py-16 text-center text-sm text-stone-400 sm:rounded-3xl">
            상점 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </div>
        ) : items.length === 0 ? (
          <div className="rankings-panel ple-section-glow flex flex-col items-center gap-3 rounded-2xl px-4 py-16 text-center sm:rounded-3xl">
            <ShoppingBag className="h-8 w-8 text-brand-400/80" aria-hidden />
            <p className="text-sm font-medium text-stone-400">
              판매 중인 상품이 아직 없습니다. 준비되면 이곳에 표시됩니다.
            </p>
          </div>
        ) : (
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <ItemCard
                key={item.code}
                item={item}
                owned={ownedCodes.has(item.code)}
                // 소모성은 사용 대상이 필요해서 이 화면에서 바로 살 수 없다.
                disabled={!user || item.isConsumable}
                pending={pending === item.code}
                onBuy={() => handleBuy(item)}
              />
            ))}
          </ul>
        )}

        {!user && isReady && (
          <p className="mt-6 text-center text-sm text-stone-500">구매하려면 로그인이 필요합니다.</p>
        )}

        {user && inventory.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-2 text-sm font-bold tracking-tight text-stone-700 dark:text-stone-200">
              보유 아이템
            </h2>
            <ul className="rankings-panel rounded-2xl px-4 py-1 sm:rounded-3xl sm:px-6">
              {inventory.map((entry) => (
                <InventoryRow
                  key={entry.id}
                  entry={entry}
                  pending={pending === `inventory:${entry.id}`}
                  onToggle={() => handleToggleEquip(entry)}
                />
              ))}
            </ul>
          </section>
        )}
      </div>
    </WweArenaShell>
  );
}
