'use client'

import { usePathname } from 'next/navigation'

/**
 * 이 앱이 아는 경로로 되돌린다 — 포트폴리오로 옮기며 생긴 자리다 (2026-10-06).
 *
 * 제품은 원래 `/`·`/home`·`/me` 처럼 **최상위**에 살았는데, 포트폴리오 앱 안에서는
 * `/login` 과 `/admin` 이 이미 KAYFABE 것이라 통째로 `/s` 아래로 내려왔다
 * (`app/(supersub)/s/…`). 주소창은 `middleware.ts` 의 rewrite 덕에 여전히
 * `supersub.jsangho.cloud/home` 이지만, **`usePathname()` 이 어느 쪽을 돌려주는지는
 * 렌더가 서버에서 났는지 클라이언트에서 났는지에 따라 갈린다.**
 *
 * 🔴 그 갈림에 기대지 않는다. 여기서 접두사를 떼면 어느 쪽이 와도 같은 답이 된다 —
 * 제품 코드의 `pathname === '/me'` 같은 비교를 한 줄도 안 고쳐도 되는 이유다.
 * (배경 사진·인트로·알약이 전부 이 비교로 켜지고 꺼진다.)
 */
export function useSsPathname(): string {
  const raw = usePathname() ?? '/'
  if (raw === PREFIX) return '/'
  return raw.startsWith(`${PREFIX}/`) ? raw.slice(PREFIX.length) : raw
}

/** 라우트 그룹 안에서 제품이 사는 자리. `middleware.ts` 의 값과 같아야 한다. */
const PREFIX = '/s'
