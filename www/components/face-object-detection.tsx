"use client";

import { useCallback, useRef, useState } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { parseApiError } from "@/lib/api";

type UploadState =
  | { kind: "empty" }
  | { kind: "ready"; fileName: string; previewUrl: string };

type FaceBoundingBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
};
type FacePrediction = { name: string; confidence: number };
type FaceIdentification = {
  box: FaceBoundingBox;
  predictions: FacePrediction[];
};
type FaceIdentificationResult = {
  image_path: string;
  identifications: FaceIdentification[];
};

type ImageSize = { width: number; height: number };

const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png"]);

function topPrediction(
  identification: FaceIdentification,
): FacePrediction | undefined {
  return identification.predictions[0];
}

export function FaceObjectDetection({ className }: { className?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<FaceIdentificationResult | null>(null);
  const [state, setState] = useState<UploadState>({ kind: "empty" });
  const [imageSize, setImageSize] = useState<ImageSize | null>(null);

  const identifyFile = useCallback(async (file: File) => {
    setError(null);
    setSubmitting(true);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch("/api/vision/identify", {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(parseApiError(data, res.status));
      }
      setResult(data as FaceIdentificationResult);
    } catch {
      setError("얼굴 인식 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  }, []);

  const ingestFile = useCallback(
    (file: File | undefined) => {
      setError(null);
      setResult(null);
      setImageSize(null);
      if (!file) return;

      if (!ACCEPTED_TYPES.has(file.type)) {
        setError("jpg 또는 png 이미지 파일만 업로드할 수 있습니다.");
        return;
      }

      const previewUrl = URL.createObjectURL(file);
      setState({ kind: "ready", fileName: file.name, previewUrl });

      void identifyFile(file);
    },
    [identifyFile],
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
    <div className={cn("flex flex-col", className)}>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="sr-only"
        aria-hidden
        tabIndex={-1}
        onChange={onInputChange}
      />

      <button
        type="button"
        onClick={openPicker}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        disabled={submitting}
        aria-label="얼굴 이미지를 여기에 놓거나 클릭하여 선택"
        className={[
          "flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
          submitting
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
          {submitting
            ? "얼굴 인식 중..."
            : "얼굴 이미지를 이 영역에 끌어다 놓기"}
        </p>
        <p className="mt-1 text-sm text-zinc-500">
          {submitting
            ? "잠시만 기다려 주세요."
            : "jpg, png 만 지원 · 또는 클릭해서 탐색기에서 선택"}
        </p>
      </button>

      {error && (
        <p
          className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {error}
        </p>
      )}

      {state.kind === "ready" && (
        <div className="mt-6 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50/80 dark:bg-zinc-900/80 p-4">
          <p className="mb-3 break-all text-sm font-medium text-zinc-800 dark:text-zinc-200">
            선택한 파일: {state.fileName}
          </p>
          <div className="relative w-full overflow-hidden rounded-lg">
            {/* eslint-disable-next-line @next/next/no-img-element -- 로컬 blob URL 미리보기 + bbox 오버레이 */}
            <img
              src={state.previewUrl}
              alt={state.fileName}
              className="h-auto max-h-[70vh] w-full rounded-lg border border-zinc-200 dark:border-zinc-700 object-contain"
              onLoad={(e) => {
                const img = e.currentTarget;
                setImageSize({
                  width: img.naturalWidth,
                  height: img.naturalHeight,
                });
              }}
            />
            {result &&
              imageSize &&
              result.identifications.map((identification, index) => {
                const { box } = identification;
                const prediction = topPrediction(identification);
                const left = (box.x1 / imageSize.width) * 100;
                const top = (box.y1 / imageSize.height) * 100;
                const width = ((box.x2 - box.x1) / imageSize.width) * 100;
                const height = ((box.y2 - box.y1) / imageSize.height) * 100;
                return (
                  <div
                    key={index}
                    className="absolute border-2 border-emerald-400"
                    style={{
                      left: `${left}%`,
                      top: `${top}%`,
                      width: `${width}%`,
                      height: `${height}%`,
                    }}
                  >
                    {prediction && (
                      <span className="absolute -top-6 left-0 whitespace-nowrap rounded bg-emerald-500 px-1.5 py-0.5 text-xs font-semibold text-white">
                        {prediction.name}{" "}
                        {(prediction.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                );
              })}
          </div>

          {result && (
            <div className="mt-4 space-y-2">
              {result.identifications.length === 0 && (
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  이미지에서 얼굴을 찾지 못했습니다.
                </p>
              )}
              {result.identifications.map((identification, index) => {
                const prediction = topPrediction(identification);
                return (
                  <p
                    key={index}
                    className="text-sm text-zinc-700 dark:text-zinc-300"
                  >
                    얼굴 {index + 1}:{" "}
                    <span className="font-semibold">
                      {prediction?.name ?? "알 수 없음"}
                    </span>
                    {prediction &&
                      ` (확신도 ${(prediction.confidence * 100).toFixed(0)}%)`}
                  </p>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
