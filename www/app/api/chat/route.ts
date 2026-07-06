import { GoogleGenerativeAI } from "@google/generative-ai";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const DEFAULT_MODEL = "gemini-2.5-flash";
const MODEL_FALLBACKS = ["gemini-2.5-flash", "gemini-2.0-flash"] as const;

function resolveApiKey(): string | undefined {
  return (
    process.env.GEMINI_API_KEY?.trim() ||
    process.env.GOOGLE_GENERATIVE_AI_API_KEY?.trim()
  );
}

function extractReplyText(
  result: Awaited<
    ReturnType<
      ReturnType<GoogleGenerativeAI["getGenerativeModel"]>["generateContent"]
    >
  >,
): string {
  try {
    return (result.response.text() || "").trim();
  } catch {
    const feedback = result.response.promptFeedback;
    throw new Error(
      feedback
        ? "응답이 차단되었거나 비어 있습니다."
        : "응답 텍스트를 읽을 수 없습니다.",
    );
  }
}

function toClientError(error: unknown): { message: string; status: number } {
  const msg = error instanceof Error ? error.message : String(error);
  const lower = msg.toLowerCase();

  if (lower.includes("api key") || lower.includes("api_key")) {
    return {
      message:
        "Gemini API 키가 없거나 유효하지 않습니다. Vercel에 GEMINI_API_KEY를 설정했는지 확인해 주세요.",
      status: 500,
    };
  }
  if (
    msg.includes("429") ||
    lower.includes("quota") ||
    lower.includes("resource exhausted") ||
    lower.includes("limit: 0")
  ) {
    return {
      message:
        "Gemini API 무료 할당량이 없거나 초과했습니다. Google AI Studio에서 키·빌링을 확인한 뒤 1~2분 후 다시 시도해 주세요.",
      status: 429,
    };
  }
  if (
    msg.includes("404") ||
    lower.includes("is not found") ||
    lower.includes("not supported for generatecontent")
  ) {
    return {
      message: "선택한 모델을 사용할 수 없습니다. 다른 모델을 선택해 주세요.",
      status: 502,
    };
  }
  return {
    message: "Gemini 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    status: 502,
  };
}

async function generateReply(
  prompt: string,
  preferredModel: string,
): Promise<string> {
  const apiKey = resolveApiKey();
  if (!apiKey) {
    throw new Error("API key not configured");
  }

  const genAI = new GoogleGenerativeAI(apiKey);
  const tryOrder = [
    preferredModel,
    ...MODEL_FALLBACKS.filter((m) => m !== preferredModel),
  ];

  let lastError: unknown;
  for (const modelName of tryOrder) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName });
      const result = await model.generateContent(prompt);
      const text = extractReplyText(result);
      if (!text) {
        throw new Error("Empty model response");
      }
      return text;
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError ?? new Error("Gemini generate failed");
}

async function streamReply(
  prompt: string,
  preferredModel: string,
): Promise<ReadableStream<Uint8Array>> {
  const apiKey = resolveApiKey();
  if (!apiKey) {
    throw new Error("API key not configured");
  }

  const genAI = new GoogleGenerativeAI(apiKey);
  const tryOrder = [
    preferredModel,
    ...MODEL_FALLBACKS.filter((m) => m !== preferredModel),
  ];

  let lastError: unknown;
  for (const modelName of tryOrder) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName });
      const result = await model.generateContentStream(prompt);
      const encoder = new TextEncoder();

      return new ReadableStream<Uint8Array>({
        async start(controller) {
          try {
            for await (const chunk of result.stream) {
              const text = chunk.text();
              if (text) {
                controller.enqueue(encoder.encode(text));
              }
            }
            controller.close();
          } catch (error) {
            controller.error(error);
          }
        },
      });
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError ?? new Error("Gemini generate failed");
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      prompt?: string;
      message?: string;
      model?: string;
      stream?: boolean;
    };
    const prompt = (body.prompt ?? body.message ?? "").trim();
    const modelName = body.model?.trim() || DEFAULT_MODEL;

    if (!prompt) {
      return NextResponse.json(
        { error: "메시지가 비어 있습니다." },
        { status: 400 },
      );
    }

    if (body.stream) {
      const stream = await streamReply(prompt, modelName);
      return new Response(stream, {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "no-cache",
        },
      });
    }

    const text = await generateReply(prompt, modelName);
    return NextResponse.json({ text, reply: text });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Gemini API Error:", error);
    const { message, status } = toClientError(error);
    return NextResponse.json({ error: message }, { status });
  }
}
