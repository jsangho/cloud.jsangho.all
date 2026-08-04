import {
  getRequestTimeoutMessage,
  isAbortError,
  parseApiError,
  receiptsBaseUrl,
  requestTimeoutMs,
} from "@/lib/api";

/** 목록 한 건. `thumbnailUrl`은 서버가 발급한 단명 presigned URL이고 버킷 이름은 담기지 않는다. */
export type ReceiptSummary = {
  key: string;
  thumbnailUrl: string;
  /** 촬영 시각 ISO 문자열. 서버가 모르면 null */
  capturedAt: string | null;
};

export type ReceiptLineItem = {
  name: string;
  quantity: number;
  /** KRW 정수. 영수증에 단가가 없으면 null */
  unitPrice: number | null;
  amount: number;
};

/**
 * 판독 초안. 확정 내역이 아니다 — `needsReview`가 true면 화면에서 확인이 필요함을 드러낸다.
 * 미판독(`null`)과 0원은 다르므로 null 자리를 0으로 채우지 않는다.
 */
export type ReceiptDraft = {
  merchantName: string | null;
  businessNo: string | null;
  /** ISO 문자열. Date 변환은 표시 직전에만 */
  transactedAt: string | null;
  /** KRW 정수 */
  totalAmount: number | null;
  vatAmount: number | null;
  currency: "KRW";
  lineItems: ReceiptLineItem[];
  confidence: number;
  needsReview: boolean;
};

export type ReceiptListResult =
  | { ok: true; items: ReceiptSummary[] }
  | { ok: false; status: number | null; message: string };

export type ReceiptOcrResult =
  | { ok: true; draft: ReceiptDraft }
  | { ok: false; status: number | null; message: string; canRetry: boolean };

/**
 * OCR은 S3에서 이미지를 내려받은 뒤 판독 엔진까지 왕복하므로 일반 조회보다 오래 걸린다.
 * 공용 `requestTimeoutMs`를 키우면 다른 화면 전체의 응답 기준이 함께 늘어나 여기만 따로 둔다.
 */
export const ocrTimeoutMs = 60000;

/** 목록 조회 실패 문구. 상태 코드·백엔드 원문은 화면에 노출하지 않는다. */
const LIST_FALLBACK_MESSAGE: Record<number, string> = {
  401: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
};

/** 판독 실패 문구. 백엔드 예외 매핑(하네스 §8)과 같은 자리를 채운다. */
const OCR_FALLBACK_MESSAGE: Record<number, string> = {
  401: "로그인이 만료되었습니다. 다시 로그인해 주세요.",
  404: "영수증 이미지를 찾을 수 없습니다.",
  422: "영수증을 인식하지 못했습니다. 다시 촬영해 주세요.",
  503: "영수증 판독을 잠시 사용할 수 없습니다.",
};

const GENERIC_MESSAGE = "영수증 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
const NETWORK_MESSAGE = "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.";

/**
 * FastAPI가 라우트·메서드 부재 시 자동으로 넣는 영문 detail. 사용자에게 보여줄 문구가
 * 아니므로 걸러내고 한국어 문구로 대신한다.
 */
const FRAMEWORK_DETAILS = new Set(["Not Found", "Method Not Allowed", "Internal Server Error"]);

async function readErrorMessage(res: Response, fallbacks: Record<number, string>): Promise<string> {
  const body = (await res.json().catch(() => null)) as {
    detail?: string;
  } | null;
  if (body?.detail && !FRAMEWORK_DETAILS.has(body.detail)) {
    return parseApiError(body, res.status);
  }
  return fallbacks[res.status] ?? GENERIC_MESSAGE;
}

/** 타임아웃·네트워크 오류의 브라우저 원문을 그대로 띄우지 않는다. */
function toTransportMessage(error: unknown): string {
  if (isAbortError(error)) return getRequestTimeoutMessage();
  if (error instanceof TypeError) return NETWORK_MESSAGE;
  return GENERIC_MESSAGE;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toNullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function toNullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toReceiptSummary(value: unknown): ReceiptSummary | null {
  if (!isRecord(value)) return null;
  const key = value.key;
  const thumbnailUrl = value.thumbnailUrl;
  if (typeof key !== "string" || key.length === 0) return null;
  if (typeof thumbnailUrl !== "string" || thumbnailUrl.length === 0) return null;
  return { key, thumbnailUrl, capturedAt: toNullableString(value.capturedAt) };
}

function toLineItems(value: unknown): ReceiptLineItem[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((raw) => ({
    name: typeof raw.name === "string" ? raw.name : "",
    quantity: toNullableNumber(raw.quantity) ?? 1,
    unitPrice: toNullableNumber(raw.unitPrice),
    amount: toNullableNumber(raw.amount) ?? 0,
  }));
}

function toReceiptDraft(value: unknown): ReceiptDraft | null {
  if (!isRecord(value)) return null;
  return {
    merchantName: toNullableString(value.merchantName),
    businessNo: toNullableString(value.businessNo),
    transactedAt: toNullableString(value.transactedAt),
    totalAmount: toNullableNumber(value.totalAmount),
    vatAmount: toNullableNumber(value.vatAmount),
    currency: "KRW",
    lineItems: toLineItems(value.lineItems),
    confidence: toNullableNumber(value.confidence) ?? 0,
    // 서버가 값을 빠뜨리면 "확인 불필요"가 아니라 "확인 필요"로 기운다.
    needsReview: value.needsReview !== false,
  };
}

/** 화면 진입 시 1회. 판독은 사용자가 고른 한 장에만 돌린다. */
export async function fetchReceipts(): Promise<ReceiptListResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  try {
    const res = await fetch(receiptsBaseUrl, {
      credentials: "include",
      signal: controller.signal,
    });
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        message: await readErrorMessage(res, LIST_FALLBACK_MESSAGE),
      };
    }
    const body = (await res.json()) as { items?: unknown };
    const items = Array.isArray(body.items)
      ? body.items.map(toReceiptSummary).filter((item): item is ReceiptSummary => item !== null)
      : [];
    return { ok: true, items };
  } catch (error) {
    return { ok: false, status: null, message: toTransportMessage(error) };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 판독 요청. 이미지 바이트가 아니라 `key`만 보낸다 — S3 → 브라우저 → 서버로
 * 같은 이미지를 두 번 왕복시키지 않기 위해서다.
 */
export async function requestReceiptOcr(key: string): Promise<ReceiptOcrResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ocrTimeoutMs);
  try {
    const res = await fetch(`${receiptsBaseUrl}/ocr`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
      signal: controller.signal,
    });
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        message: await readErrorMessage(res, OCR_FALLBACK_MESSAGE),
        // 422는 "영수증이 아니다"라 같은 이미지로 다시 걸어도 결과가 같다.
        canRetry: res.status !== 422 && res.status !== 404,
      };
    }
    const draft = toReceiptDraft(await res.json());
    if (!draft) {
      return {
        ok: false,
        status: res.status,
        message: "판독 결과를 읽지 못했습니다. 잠시 후 다시 시도해 주세요.",
        canRetry: true,
      };
    }
    return { ok: true, draft };
  } catch (error) {
    return {
      ok: false,
      status: null,
      message: toTransportMessage(error),
      canRetry: true,
    };
  } finally {
    clearTimeout(timer);
  }
}
