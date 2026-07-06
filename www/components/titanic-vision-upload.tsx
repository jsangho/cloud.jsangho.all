"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { parseApiError } from "@/lib/api";

type UploadState =
  | { kind: "empty" }
  | { kind: "ready"; fileName: string; previewUrl: string };

type UploadResult = {
  filename: string;
  contentType: string;
  sizeBytes: number;
  savedPath: string;
};

const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png"]);

export function TitanicVisionUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [state, setState] = useState<UploadState>({ kind: "empty" });

  const uploadFile = useCallback(async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch("/api/vision/upload", {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(parseApiError(data, res.status));
      }
      const body = data as Record<string, unknown>;
      setResult({
        filename: String(body.filename ?? file.name),
        contentType: String(body.content_type ?? file.type),
        sizeBytes: Number(body.size_bytes ?? file.size),
        savedPath: String(body.saved_path ?? ""),
      });
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "업로드 중 오류가 발생했습니다.",
      );
    } finally {
      setUploading(false);
    }
  }, []);

  const ingestFile = useCallback(
    (file: File | undefined) => {
      setError(null);
      setResult(null);
      if (!file) return;

      if (!ACCEPTED_TYPES.has(file.type)) {
        setError("jpg 또는 png 이미지 파일만 업로드할 수 있습니다.");
        return;
      }

      const previewUrl = URL.createObjectURL(file);
      setState({ kind: "ready", fileName: file.name, previewUrl });

      void uploadFile(file);
    },
    [uploadFile],
  );

  const openPicker = () => {
    inputRef.current?.click();
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    ingestFile(file);
    e.target.value = "";
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    ingestFile(file);
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="sr-only"
        aria-hidden
        tabIndex={-1}
        onChange={onInputChange}
      />

      <div className="space-y-8">
        <section aria-labelledby="upload-panel-title">
          <h2
            id="upload-panel-title"
            className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500"
          >
            방식 1 · 업로드 창
          </h2>
          <button
            type="button"
            onClick={openPicker}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            disabled={uploading}
            aria-label="이미지 파일을 여기에 놓거나 클릭하여 선택"
            className={[
              "flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
              uploading
                ? "cursor-wait border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800/60"
                : dragOver
                  ? "border-zinc-900 dark:border-zinc-400 bg-zinc-100 dark:bg-zinc-800/60"
                  : "border-zinc-300 dark:border-zinc-700 bg-zinc-50/50 dark:bg-zinc-900/50 hover:border-zinc-400 dark:hover:border-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-800/60",
            ].join(" ")}
          >
            <Upload
              className="mb-3 size-10 text-zinc-400"
              strokeWidth={1.25}
              aria-hidden
            />
            <p className="text-base font-medium text-zinc-800 dark:text-zinc-200">
              {uploading
                ? "서버로 전송 중..."
                : "이미지를 이 영역에 끌어다 놓기"}
            </p>
            <p className="mt-1 text-sm text-zinc-500">
              {uploading
                ? "잠시만 기다려 주세요."
                : "jpg, png 만 지원 · 또는 클릭해서 탐색기에서 선택 (선택 즉시 전송)"}
            </p>
          </button>
        </section>

        <div className="relative">
          <div className="absolute inset-0 flex items-center" aria-hidden>
            <div className="w-full border-t border-zinc-200" />
          </div>
          <div className="relative flex justify-center text-xs uppercase tracking-wide text-zinc-400">
            <span className="bg-white dark:bg-stone-900 px-3 dark:text-zinc-400">
              또는
            </span>
          </div>
        </div>

        <section aria-labelledby="upload-button-title">
          <h2
            id="upload-button-title"
            className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500"
          >
            방식 2 · 업로드 버튼
          </h2>
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <button
              type="button"
              onClick={openPicker}
              disabled={uploading}
              className={[
                "inline-flex min-w-[200px] items-center justify-center gap-2 rounded-xl border px-8 py-3.5 text-sm font-semibold shadow-sm transition-colors",
                uploading
                  ? "cursor-wait border-zinc-300 bg-zinc-200 text-zinc-500"
                  : "border-zinc-900 bg-zinc-900 text-white hover:bg-zinc-800",
              ].join(" ")}
            >
              <Upload className="size-4" aria-hidden />
              {uploading ? "업로드 중..." : "이미지 업로드"}
            </button>
            <p className="max-w-xs text-center text-sm text-zinc-500 sm:text-left">
              파일을 고르면 자동으로 서버에 전송됩니다.
            </p>
          </div>
        </section>
      </div>

      {error && (
        <p
          className="mt-8 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {error}
        </p>
      )}

      {state.kind === "ready" && (
        <div className="mt-8 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50/80 dark:bg-zinc-900/80 p-4">
          <p className="break-all text-sm font-medium text-zinc-800 dark:text-zinc-200">
            선택한 파일: {state.fileName}
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element -- 로컬 blob URL 미리보기 */}
          <img
            src={state.previewUrl}
            alt={state.fileName}
            className="mt-3 max-h-80 rounded-lg border border-zinc-200 dark:border-zinc-700 object-contain"
          />
          {result && (
            <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
              서버 저장 완료 · {result.contentType} ·{" "}
              {result.sizeBytes.toLocaleString("ko-KR")}
              바이트
            </p>
          )}
        </div>
      )}
    </>
  );
}
