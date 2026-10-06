'use client'

import PillButton from '@/supersub/components/ui/PillButton'

/**
 * 「이건 목업이다」를 **로그인 화면에서 한 번** 말한다 (2026-10-06).
 *
 * 이 사본은 `supersub.jsangho.cloud` 에만 올라가고 백엔드가 없다 — 보이는 수치와
 * 선수는 전부 `supersub/server/backend/mock.ts` 가 만든 것이다. 🔴 **그 사실을
 * 안 적으면 보는 사람이 운영 중인 서비스로 읽는다.**
 *
 * 그리고 **팀 프로젝트라는 것을 같이 적는다.** 화면과 앱은 백성검, 서버·데이터는
 * 정어진, 일정·통합은 박민호 몫이고, 내가 맡은 것은 영상에서 자세를 재고 채점하는
 * 쪽이다. 개인 도메인에 올라가는 화면이라 이 줄이 없으면 전부 한 사람이 만든
 * 것으로 읽힌다.
 *
 * 🔴 **로그인 화면에만 둔다.** 제품 안쪽까지 띠를 두르면 그 화면들의 배치가
 * 틀어지고(저 안은 화면마다 제 높이를 꽉 채워 쓴다), 보여 주려던 것을 가린다.
 */
export default function MockDemoNotice({
  onFill,
}: {
  /** 데모 계정을 입력칸에 바로 넣는다. */
  onFill: (email: string, password: string) => void
}) {
  return (
    <div
      className="mb-5 w-full rounded-2xl px-4 py-3.5 text-sm"
      style={{
        border: '1px solid color-mix(in srgb, var(--ss-fg) 22%, transparent)',
        background: 'color-mix(in srgb, var(--ss-fg) 6%, transparent)',
      }}
    >
      <p style={{ color: 'var(--ss-fg)' }}>목업 데모 — 실제 데이터가 아닙니다</p>
      <p
        className="mt-1 text-xs"
        style={{ color: 'color-mix(in srgb, var(--ss-fg) 60%, transparent)' }}
      >
        팀 프로젝트 4명 · 화면 백성검 · 분석 정상호
      </p>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div
          className="text-xs leading-relaxed"
          style={{ color: 'color-mix(in srgb, var(--ss-fg) 75%, transparent)' }}
        >
          <div>{DEMO_EMAIL}</div>
          <div>{DEMO_PASSWORD}</div>
        </div>
        <PillButton
          variant="white"
          onClick={() => onFill(DEMO_EMAIL, DEMO_PASSWORD)}
          className="shrink-0"
        >
          바로 넣기
        </PillButton>
      </div>

      {/* 🔴 **올리기가 되게 한 뒤로는 말이 달라졌다** (2026-10-06). 전에는
          「올리기는 동작하지 않습니다」였는데 지금은 끝까지 돈다 — 대신 두
          가지가 진짜가 아니라, 그 둘을 적는다. 하나라도 빼면 보는 사람이
          자기 영상을 잰 값으로 읽는다. */}
      <p
        className="mt-3 text-xs leading-relaxed"
        style={{ color: 'color-mix(in srgb, var(--ss-fg) 45%, transparent)' }}
      >
        영상을 올려 분석까지 돌려 보실 수 있습니다. 다만 분석 결과는 미리 넣어 둔 본보기라
        누가 올려도 같고, 올린 영상은 이 창에서만 재생됩니다.
      </p>
    </div>
  )
}

/* 🔴 `supersub/server/backend/mock.ts` 의 `DEMO_EMAIL`·`DEMO_PASSWORD` 와 **같아야
   한다.** 거기 것이 정본이고 여기는 화면에 보여 주는 사본이다 — 목업 전용 계정이라
   비밀이 아니다(그 파일도 저장소에 그대로 있다). */
const DEMO_EMAIL = 'demo@super-sub.example'
const DEMO_PASSWORD = 'supersub2026'
