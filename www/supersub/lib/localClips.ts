'use client'

/**
 * 올린 클립을 **브라우저에만** 들고 있는 자리 — 목업 사본 전용 (2026-10-06).
 *
 * 실제 서비스는 바이트가 S3 로 간다(계약 PER-002 — 앱 서버를 안 지난다).
 * 이 사본에는 S3 가 없고, 그렇다고 **서버 메모리에 영상을 쌓지 않는다** —
 * Vercel 인스턴스는 수시로 내려가서 「될 때도 있고 안 될 때도 있는」 재생이
 * 되는데, 그게 제일 나쁜 결과다.
 *
 * 그래서 서버는 바이트를 받아 **버리고**(`videos/sink`), 재생은 지금 창이
 * 들고 있는 파일로 한다. 🔴 **새로고침하면 재생만 못 한다** — 목록·분석
 * 결과는 그대로다. 그 사실을 화면이 말한다(`MyVideos` 의 안내).
 *
 * 키는 서버가 준 `storage_key` 를 그대로 쓴다. 그래야 목록·리포트·재생이
 * 같은 이름으로 서로를 가리키고, **실제 백엔드로 바꿔도 부르는 쪽이 안 바뀐다.**
 */

/** 목업이 내주는 저장 키의 생김새. 실물은 `videos/<user_id>/<uuid>.mp4` 다. */
const LOCAL_PREFIX = 'local:'

/** `storage_key` → 이 창에서만 유효한 `blob:` 주소. */
const urls = new Map<string, string>()

export function isLocalKey(storageKey: string | undefined | null): boolean {
  return typeof storageKey === 'string' && storageKey.startsWith(LOCAL_PREFIX)
}

/**
 * 올린 파일을 이 키로 기억한다. 올리기 직전에 부른다.
 *
 * 🔴 **같은 키로 다시 부르면 앞의 주소를 되돌려준다**(`revokeObjectURL`).
 * 안 그러면 큰 영상을 여러 번 올릴 때 메모리가 쌓이기만 한다.
 */
export function rememberLocalClip(storageKey: string, file: Blob): void {
  if (!isLocalKey(storageKey)) return
  const old = urls.get(storageKey)
  if (old) URL.revokeObjectURL(old)
  urls.set(storageKey, URL.createObjectURL(file))
}

/** 이 창이 그 클립을 아직 들고 있으면 재생 주소, 아니면 `null`. */
export function localClipUrl(storageKey: string): string | null {
  return urls.get(storageKey) ?? null
}
