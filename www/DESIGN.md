---
omd: 0.1
brand: KayFabe
bootstrapped_from: twitch
bootstrapped_at: 2026-08-04
tokens:
  source: project-promoted (ramp = Tailwind v4 amber)
  note: "구조(단일 액션 색 + 하강 램프, radius 스케일, shadowless, 2단 depth, motion)는 twitch canonical에서 빌리고, 색상 값은 기존 www 코드에서 실제로 쓰이던 것을 승격했다. Ultraviolet 자리에 챔피언십 골드, LIVE 자리에 WWE 레드가 들어간다. 알파 값(카드 스크림 rgba(0,0,0,0.6), 골드 글로우 rgba(212,175,55,0.15), 입력 링 rgba(212,175,55,0.35))은 prose로만 유지한다. 승격 근거는 파일 하단 omd:attribution 참조."
  colors:
    primary: "#fcbb00"
    link: "#d4af37"
    primary-hover: "#f99c00"
    primary-deep: "#b75000"
    ramp: { 50: "#fffbeb", 100: "#fef3c6", 200: "#fee685", 300: "#ffd236", 400: "#fcbb00", 500: "#f99c00", 600: "#dd7400", 700: "#b75000", 800: "#953d00", 900: "#7b3306", 950: "#461901" }
    # 기본 테마는 라이트다 (2026-09-29 사용자 결정). 아래 ink·body·canvas·
    # surface-*·live·data·data-surface는 **라이트 값**이고, 다크 값은
    # colors-dark에 둔다. 두 벌 다 globals.css의 같은 토큰 이름을 채운다.
    ink: "#1c1917"
    body: "#44403c"
    muted: "#78716c"
    # 표면은 순백을 쓰지 않는다 (2026-09-29 사용자 — "너무 밝아").
    # 첫 라이트 값(#fafaf9 / #ffffff) → 웜 페이퍼(#f4f1ec) → 지금 값으로
    # 두 번 내렸다 (2026-09-30 사용자 — "하얀색 바탕 말고"). 카드 면은
    # 그대로 두고 캔버스만 내려 계단을 벌린 것이다.
    canvas: "#e6e2da"
    surface-section: "#ded9cf"
    surface-card: "#fcfbf9"
    surface-card-alt: "#f6f3ef"
    surface-border: "#d2ccc1"
    surface-alt: "#1c1917"
    on-primary: "#0c0a09"
    live: "#dc2626"
    data: "#2563eb"
    data-ramp: { 100: "#dbeafe", 200: "#93c5fd", 300: "#60a5fa", 400: "#3b82f6", 500: "#2563eb", 600: "#1b44b5", 700: "#16307a" }
    data-surface: "#eff6ff"
  colors-dark:
    # 토글로 들어가는 다크 — KAYFABE 2.0까지의 값을 그대로 보존한다.
    # 라이트를 기본으로 돌리면서 **한 픽셀도 바꾸지 않았다.**
    ink: "#fafafa"
    body: "#d6d3d1"
    canvas: "#08090b"
    surface-section: "#0d0f12"
    surface-card: "#101317"
    surface-card-alt: "#14171c"
    surface-border: "#252a31"
    live: "#e63946"
    data: "#3b82f6"
    data-surface: "#101a2e"
    info: "#3b82f6"
    chart-categorical: ["#3b82f6", "#b08d1f", "#0ea5a0", "#8b5cf6", "#d2650f", "#db2777"]
    chart-status: { win: "#0ea372", loss: "#e63946", pending: "#64748b" }
    chart-sequential-light: ["#7eb3f7", "#4a90f0", "#2563eb", "#1b44b5", "#16307a"]
    chart-sequential-dark: ["#dbeafe", "#93c5fd", "#60a5fa", "#3b82f6", "#2563eb"]
  typography:
    family: { display: "Oswald", body: "Pretendard" }
    display-hero: { size: 31, weight: 600, lineHeight: 1.1, use: "PLE 히어로 헤드라인, Oswald (--font-sport)" }
    section:      { size: 20, weight: 400, lineHeight: 1.2, use: "섹션 링크·푸터, Oswald" }
    heading:      { size: 16, weight: 600, lineHeight: 1.3, use: "카드 선반 제목 — 'PLE 예측', '랭킹'" }
    body:         { size: 14, weight: 400, lineHeight: 1.4, use: "본문 + 고밀도 UI 텍스트, Pretendard" }
    button:       { size: 14, weight: 600, lineHeight: 1.0, use: "버튼 레이블, Pretendard SemiBold" }
    caption:      { size: 12, weight: 400, lineHeight: 1.2, use: "LIVE 배지, 픽 수, 매치 메타데이터" }
  spacing: { xs: 4, sm: 8, md: 12, base: 16, lg: 18, xl: 24, xxl: 40 }
  rounded: { sm: 2, md: 4, lg: 8, full: 9000 }
  shadow:
    none: "none"
    input-ring: "rgba(212,175,55,0.35) 0px 0px 0px 1px inset"
  components:
    button-primary: { type: button, bg: "#fcbb00", fg: "#0c0a09", radius: "9000px", height: "32px", font: "14px / 600", use: "예측 제출 / 회원가입 CTA — 단 하나의 골드 액션, 풀 pill" }
    button-secondary: { type: button, fg: "#fafafa", radius: "9000px", height: "32px", font: "14px / 600", use: "로그인 — 반투명 rgba(250,250,250,0.12) 채움 pill" }
    input-search: { type: input, bg: "#101317", fg: "#fafafa", radius: "8px", height: "36px", padding: "0px 12px", font: "14px / 400", use: "슈퍼스타·PLE 검색 필드, inset rgba(212,175,55,0.35) 1px 링" }
    nav-link: { type: tab, fg: "#fafafa", font: "14px / 400", active: "text #d4af37", use: "상단 내비 항목 — PLE / 랭킹 / 기록 / 샵. 활성 = 메탈릭 골드" }
    card-match: { type: card, bg: "#101317", radius: "4px", use: "PLE 매치 카드 — 대진 중심, 그림자 없음" }
    badge-live: { type: badge, bg: "#e63946", fg: "#fafafa", radius: "4px", padding: "1px 5px", font: "12px / 400", use: "진행 중인 PLE 표시 — LIVE 전용 레드" }
    badge-picks: { type: badge, fg: "#fafafa", radius: "2px", padding: "0px 4px", font: "14px / 400", use: "픽 수 오버레이 — rgba(0,0,0,0.6) 스크림 pill" }
    avatar: { type: avatar, radius: "9000px", use: "슈퍼스타 / 유저 아바타 — 완전한 원" }
  components_harvested: true
---

<!-- omd:unresolved: radius — 이 스펙은 twitch 구조를 따라 2/4/8/9000px를 쓰지만, 현재 globals.css는 `--radius: 0.625rem`(10px) 기반의 shadcn 기본 스케일(6/8/10/14)로 돌고 있다. 색 정렬 단계에서는 radius를 건드리지 않았다 — 바꾸면 shadcn 컴포넌트 26개의 형태가 한꺼번에 달라진다. 별도 결정 후 적용할 것. -->

# Design System of KayFabe

## 1. Visual Theme & Atmosphere

KayFabe는 **WWE Sports Analytics & Prediction Platform**이다 (2026-08-20 사용자 결정 · KAYFABE 2.0). 라이브 이벤트를 둘러싸는 화면이라는 점은 그대로지만, 화면이 하는 일이 하나 늘었다 — 경기를 예측하게 하고, **그 예측의 근거와 성적을 데이터로 보여 주는 것**이다. 팬사이트와 갈리는 자리가 여기다: 화면의 주인공은 장식이 아니라 **숫자와 그 출처**다.

**기본 테마는 라이트다** (2026-09-29 사용자 결정 — "너무 어둡고 우중충하다"). 캔버스는 웜 그레이(`#e6e2da`)이고 그 위에 카드 표면(`#fcfbf9`)이 한 단 떠 있다. 어두운 표면에서 카드를 밝게 올리던 방향을 그대로 뒤집은 것이다 — 그림자 없는 시스템이므로 카드가 뜨는 일은 **명도차 하나가 전부**이고, 그래서 계단 값이 붙어 있으면 화면 전체가 한 덩어리로 읽힌다(그것이 이전 다크 화면의 실제 문제였다: 캔버스·섹션·카드가 2~3% 안에 몰려 있었다). 구역을 나누는 경계선은 `#d2ccc1`, 텍스트는 순흑이 아닌 잉크(`#1c1917`)다.

**라이트 표면에 순백을 쓰지 않는다** (2026-09-29 사용자 — "너무 밝아"). 첫 라이트 값은 캔버스 `#fafaf9` · 카드 `#ffffff`였는데, 그림자가 없는 이 시스템에서는 화면의 거의 전부가 표면이라 98% 밝기가 그대로 눈에 들어온다. 한 단 낮추면서 **계단의 방향과 간격은 그대로 두고** 전체 밝기만 내렸다. 부수 효과로 경계가 살아난다 — 카드↔캔버스 명도비가 1.04(사실상 계단 없음)에서 1.09가 됐다.

**그 뒤 캔버스를 한 단 더 내렸다** (2026-09-30 사용자 — "하얀색 바탕 말고"). 웜 페이퍼(`#f4f1ec`)는 95% 밝기라 화면에서 여전히 흰색으로 읽혔다. 배경에 색을 주려고 그 위에 저알파 워시를 깔아 봤지만 레드는 분홍 얼룩, 골드는 누런 기가 됐다 — **밝은 표면 위의 저알파 워시는 어떤 색이든 얼룩으로 읽힌다.** 워시로 풀 문제가 아니라 캔버스 값 자체의 문제였다. 노란기를 더하는 대신 **명도만** 89%로 내렸다(`#e6e2da`). 온도는 웜 뉴트럴 그대로라 골드 CTA·스톤 글자색과 따로 놀지 않고, 카드↔캔버스 명도비가 1.09에서 **1.17**로 벌어져 카드가 확실히 떠오른다. `--surface-2`도 같이 내린다 — 이 값은 캔버스보다 **어두워야** 안쪽 구역이 물러나는데, 캔버스만 내리면 둘이 뒤집혀 구역이 되레 떠오른다.

**라이트에 색을 주는 일은 면이 맡는다.** 워시가 막힌 자리를 `.arena-band` 가 받는다 — 번짐이 아니라 경계가 또렷한 전폭 면 하나로 구역을 세운다. 밴드는 캔버스보다 **밝은** 카드 면(`--surface-card`)이고 아래에 경계선 하나를 둔다(다크에서는 반대로 한 단 어두운 `--surface-2`를 쓴다 — 밝은 면을 그대로 올리면 아레나 글로우와 겹쳐 떠 보인다). 아레나 글로우 네 겹은 **다크 전용**으로 내려갔다.

중립은 순수 회색이 아니라 **웜 뉴트럴(stone)** 이다 — 골드 액션과 온도가 같아야 한 화면에서 따로 놀지 않는다.

다크는 **토글로 남는다**(`enableSystem`이 켜져 있어 OS가 다크면 다크로 뜬다). KAYFABE 2.0까지의 다크 값은 `colors-dark`에 그대로 보존했고 한 픽셀도 바꾸지 않았다 — 근흑색 캔버스(`#08090b`) · 카드(`#101317`) · 경계(`#252a31`) · 근백색 잉크(`#fafafa`).

**역할색은 테마마다 값이 다르고 뜻은 같다.** 흰 표면에서는 대비가 모자라 그대로 쓸 수 없기 때문이다 — `#fcbb00`은 흰 배경에서 1.8:1, `#e63946`은 3.8:1, `#3b82f6`은 3.1:1이다. 라이트는 각각 램프 아래 단계(`#dd7400` · `#dc2626` · `#2563eb`)를 쓴다.

**색은 셋이고, 각자 하나의 뜻만 갖는다** (KAYFABE 2.0의 핵심 규칙).

| 색 | 뜻 | 쓰는 자리 |
|---|---|---|
| **골드** `#fcbb00` · `#d4af37` | 랭킹 · 성취 | 예측 제출 / 회원가입 CTA · 순위 · 벨트 · 활성 내비 |
| **레드** `#e63946` | WWE · LIVE · 경고 | 진행 중 표시 · 실패 · 파괴적 동작 |
| **블루** `#3b82f6` | AI · 데이터 · 분석 | AI 예측 · 차트 · 데이터 센터 · AI LAB |

**셋을 섞으면 셋 다 뜻을 잃는다.** 골드를 분석 화면의 강조색으로 쓰면 "가져갈 수 있는 것"이라는 뜻이 흐려지고, 블루를 장식으로 쓰면 "여기부터 데이터"라는 신호가 사라진다. AI LAB이 유일하게 블루를 주인공으로 쓰는 화면이고, 나머지 화면에서 블루는 데이터가 있는 자리에만 선다.

그중 **챔피언십 골드**(`#fcbb00`)가 브랜드의 얼굴이다. 이 색은 중요한 순간에만 예약된다 — **예측 제출**과 **회원가입** CTA만이 풀 pill 골드로 렌더되고, 상호작용 링크와 활성 상태는 더 깊고 금속적인 골드(`#d4af37`)로 내려가며, hover(`#f99c00`)와 pressed/서페이스(`#b75000`)가 같은 색상 램프를 따라 더 내려간다. 벨트가 금색인 이유와 같다 — 이 화면에서 금색은 "가져갈 수 있는 것"을 뜻하고, 그래서 아무 데나 칠하면 뜻이 사라진다. 골드의 모든 단계는 통제된 명도 곡선 위의 계산된 스텝이지 즉흥적인 선택이 아니다.

타이포그래피는 두 목소리로 갈린다. **Oswald**(`--font-sport`)가 브랜드·디스플레이 표면을 맡아 PLE 히어로와 챔피언십 헤드라인의 압축된 스포츠 캐스터 톤을 낸다. 제품 안쪽의 고밀도 화면은 **Pretendard**가 14px / weight 400의 일꾼 크기로 돌고, 이 플랫폼을 정의하는 고빈도 메타데이터 — **LIVE** 배지(`#e63946`), 픽 수, 매치 태그 — 에서 12px로 떨어진다. 지오메트리는 pill 우선이다. 버튼과 아바타는 풀 radius(9000px)이고, 기능적 크롬(칩·배지·검색·카드)은 2–16px 계단으로 조인다. 엘리베이션은 사실상 없다. 깊이는 경기 카드 자체와 썸네일 위의 반투명 스크림(`rgba(0,0,0,0.6)`)에서 오지, 드롭 섀도우에서 오지 않는다.

**Key Characteristics:**
- **세 색 세 뜻**: 골드 = 랭킹·성취 · 레드 `#e63946` = WWE·LIVE · 블루 `#3b82f6` = AI·데이터
- 단 하나의 채도 높은 브랜드 액션 색으로서의 챔피언십 골드(`#fcbb00`) — 예측 제출, 회원가입
- 상호작용을 위한 하강 골드 램프: 링크 `#d4af37` → hover `#f99c00` → deep `#b75000`
- 브랜드/디스플레이는 Oswald, 고밀도 제품 UI는 Pretendard 14px / 400
- **숫자가 주인공이다** — KPI와 통계는 크고 굵게, 그 옆의 크롬은 물러난다
- 흰 바탕의 순수 검정이 아니라, 근흑색 캔버스(`#08090b`) 위의 근백색 잉크(`#fafafa`)
- **표면이 계단을 이룬다**: 캔버스 `#08090b` → 구역 `#0d0f12` → 카드 `#101317` → 카드 안 카드 `#14171c`, 경계 `#252a31`
- 다크를 기본으로 하되 라이트 테마를 동등하게 취급하는 접근성 우선 시스템
- pill로 통일한 브랜드 크롬(9000px 버튼 + 아바타), 2·6·8·12·16px 계단의 기능 radius
- 그림자 없음: 깊이는 엘리베이션이 아니라 표면 계단과 반투명 스크림에서 온다
- **과한 네온·AI 장식을 쓰지 않는다** — 이 화면은 대시보드이지 SF가 아니다

## 2. Color Palette & Roles

### Primary
골드는 **11단 램프**로 정의되고, 아래 시맨틱 역할이 그 램프를 가리킨다. 램프 값은 Tailwind v4 `amber` 팔레트와 정확히 같다 — 앱의 골드 169곳이 원래 그 유틸리티로 칠해져 있었고, 토큰으로 옮기면서 색이 바뀌지 않게 기준을 그쪽에 맞췄다.

| 단계 | 값 | | 단계 | 값 |
|---|---|---|---|---|
| `brand-50` | `#fffbeb` | | `brand-500` | `#f99c00` |
| `brand-100` | `#fef3c6` | | `brand-600` | `#dd7400` |
| `brand-200` | `#fee685` | | `brand-700` | `#b75000` |
| `brand-300` | `#ffd236` | | `brand-800` | `#953d00` |
| `brand-400` | `#fcbb00` | | `brand-900` | `#7b3306` |
| | | | `brand-950` | `#461901` |

- **Championship Gold** (`brand-400` `#fcbb00`, 라이트에서는 `brand-600` `#dd7400`): 기본 브랜드 색이자 시스템에서 유일하게 채도 높은 액션 색상. 예측 제출 CTA와 회원가입 버튼을 받친다.
- **Metallic Gold** (`#d4af37`): 챔피언 버튼(`.btn-champion`) 테두리와 글로우 전용. **램프 밖의 별도 값**이고 테마와 무관하다 — 벨트의 금속 질감을 내는 자리라 램프의 주황 계열과 다르다.
- **Gold Hover** (`brand-500` `#f99c00`, 라이트 `brand-700`): hover / 보조 강조.
- **Gold Deep** (`brand-700` `#b75000`, 라이트 `brand-800`): pressed 상태와 챔피언십 패널.

### Ink & Text
- **Ink** (`#fafafa`): 본문 텍스트, 헤딩, 내비 레이블, 강한 UI 텍스트. 순수 흰색 대신 쓰는, 미세하게 따뜻한 근백색.
- **Body Stone** (`#d6d3d1`): 보조 본문과 설명.
- **Muted Stone** (`#78716c`): 3차 텍스트, 비활성 내비 링크, 캡션, 메타데이터.

### Data & Analytics (블루 축 — KAYFABE 2.0)

**AI와 데이터가 있는 자리에만 선다.** 장식으로 쓰면 "여기부터 데이터"라는 신호가 사라진다.

| 토큰 | 값 | 자리 |
|---|---|---|
| `--data-400` (`--data`) | `#3b82f6` | 기본 — AI 예측 승률, 차트 1계열, 데이터 강조 |
| `--data-300` / `--data-500` | `#60a5fa` / `#2563eb` | hover / pressed·진한 면 |
| `--data-100` ~ `--data-700` | `#dbeafe` … `#16307a` | 순차 램프의 재료 |
| `--data-surface` | 다크 `#101a2e` · 라이트 `#eff6ff` | AI LAB 카드 표면 — 캔버스보다 파랑 쪽으로 반 발짝 |

`--info`는 같은 값을 가리키는 **옛 이름**이다. 새 코드는 `text-data`·`bg-data-400`을 쓴다.

### 팀 프로젝트 출처 (포트폴리오 전용 · 티얼)

포트폴리오(`jsangho.cloud`)의 기술 칩은 **그 기술이 어느 프로젝트의 것인지**를 말한다. 중립 칩은 혼자 만든 것, 색이 붙은 칩은 팀에서 맡은 몫이다.

| 토큰 | 라이트 | 다크 | 자리 |
|---|---|---|---|
| `--team-a` | `#2563eb` (= `--data`) | `#3b82f6` | 첫 번째 팀 프로젝트 — SUPER-SUB |
| `--team-b` | `#0f766e` | `#0d9488` | 두 번째 팀 프로젝트 — GAON |

🔴 **`--team-b`(티얼)가 §7의 "네 번째 채도 높은 색을 섞지 않는다"에 대한 유일한 예외다** (2026-10-07 사용자 결정). 팀 프로젝트가 둘이 되면서 한 색으로는 둘이 한 덩어리로 읽혔고, 「누르면 어느 팀인지 나온다」는 해법이 거부됐다. 이 색은 **포트폴리오 표면 밖으로 나가지 않는다** — 제품 화면(KAYFABE)에 티얼을 쓰지 않는다.

**값은 눈으로 고르지 않았다.** 첫 후보였던 바이올렛(`#7c3aed`)은 녹색약 시뮬레이션에서 파랑과 **ΔE 0.6**으로 붙는다 — 적중/실패 짝을 경고 대역이라 적게 만든 6.5보다도 한참 아래다. 티얼은 정상시 21.5 · 적색약 21.1 · 녹색약 20.5(라이트 기준)로 전부 안전 대역이다.

**단계는 두 칩의 시각 무게가 같아지게 잡았다.** 카드 대비 기준 라이트 5.29(파랑 5.00) · 다크 4.97(파랑 5.06). 한쪽이 더 밝으면 그 프로젝트가 더 중요해 보인다. 다크에서 `--team-b`를 한 단 올리는 이유는 `#0f766e`가 근흑색 카드에서 3.40이라 글자에 못 쓰기 때문이다.

**색만으로 말하지 않는다.** 범례가 칩과 팀 이름을 짝지어 보여 주고, 칩을 누르면 툴팁 첫 줄이 다시 팀 이름을 적는다.

### Surface & Neutral

**표면이 계단을 이룬다** (KAYFABE 2.0). 예전에는 `--card`가 `--background`와 같은 값이라 그림자 없는 시스템에서 카드가 배경에서 안 떠올랐다 — 대시보드는 카드가 정보 계층을 만드는 화면이므로 계단을 실제로 둔다.

| 단 | 값 | 자리 |
|---|---|---|
| Canvas | `#08090b` | 페이지 배경 |
| Section | `#0d0f12` | 페이지 안쪽 구역 · 차트 표면 |
| Card | `#101317` | 카드·필드·세그먼트 |
| Card Alt | `#14171c` | 카드 안의 카드 (에이전트 리포트 등) |
| Border | `#252a31` | 구역·카드 경계선 |

- **On Primary** (`#0c0a09`): 골드 위에 얹히는 텍스트. 골드는 밝은 색이라 그 위 텍스트는 어두워야 한다.

### PLE Event Palette

각 PLE는 **자기 색 정체성**을 갖는다 — 로얄럼블은 블루×레드, 섬머슬램은 오렌지, 레슬매니아는 골드, MITB는 그린. 이건 브랜드 골드와 **별개 축**이고, 서로 섞이면 안 된다.

| 이벤트 | 토큰 접두사 | 축 |
|---|---|---|
| WrestleMania | `--ple-wrestlemania-*` | 골드 (100~900) |
| SummerSlam | `--ple-summerslam-*` | 오렌지 |
| Royal Rumble | `--ple-royal-rumble-*` | 블루 × 레드 |
| Elimination Chamber | `--ple-elimination-chamber-*` | 스틸 그레이 |
| Money in the Bank | `--ple-mitb-*` | 그린 |
| Champions | `--ple-champions-*` | 옐로우 |
| TBD | `--ple-tbd-accent` · `-neutral` | 미정 |

공용 중립은 `--ple-surface-light` · `--ple-surface-dark` · `--ple-white` · `--ple-black`이다.

**값은 RGB 트리플릿으로 둔다** (`--ple-wrestlemania-500: 251, 191, 36;`). 자리마다 알파가 달라 `rgba(var(--x), 0.55)` 형태로 써야 하고, `color-mix`로 바꾸면 합성 결과가 미세하게 달라진다.

**레슬매니아가 골드라는 이유로 `--brand`를 쓰지 않는다.** 브랜드 골드를 바꾸면 레슬매니아 카드까지 따라 바뀌고, §7의 "골드를 퍼뜨리지 않는다"가 깨진다.

### Signal
- **LIVE Red** (`#e63946`): 진행 중인 PLE 위의 상태 표시 · 실패 · 파괴적 동작. **"지금 진행 중"과 "틀렸다"에만 쓴다** — 일반 강조색이 아니다. (2026-08-20에 `#e02020`에서 옮겼다: 새 표면 계단 위에서 채도가 덜 튀고, 적중/실패 짝의 초록과 밝기가 맞는다.)
- **Data Blue** (`#3b82f6` = `--data`): AI · 데이터 · 분석. 위 §Data & Analytics 참조.

### Chart Palette (검증 통과 — 눈으로 고르지 않았다)

**`dataviz` 검증기(`validate_palette.js`)로 다섯 검사를 재서 통과시킨 값이다**: 밝기 대역 · 채도 바닥 · 색각 이상 분리(OKLab ΔE) · 정상시 분리 · 표면 대비. **다크(`#0d0f12`)와 라이트(당시 `#ffffff`) 양쪽에서 통과**하므로 계열 색은 테마와 무관하게 한 벌을 쓴다.

> **라이트 표면을 한 단 내리면서 여유가 줄었다** (2026-09-29). 카드(`#fcfbf9`) 기준 계열 색의 표면 대비는 2.94~3.62이고, `--chart-3`(`#0ea5a0`)이 3:1 아래(2.94)로 내려간다. 순백에서도 3.04라 **원래 경계선에 있던 값**이다 — 표면 변경이 만든 문제라기보다 드러낸 문제에 가깝다. 계열 값 재조정은 별도 작업으로 남겨 뒀다.

| 순서 | 토큰 | 값 | 뜻 |
|---|---|---|---|
| 1 | `--chart-1` | `#3b82f6` | AI · 데이터 |
| 2 | `--chart-2` | `#b08d1f` | 랭킹 · 사용자 (어두운 표면용 깊은 골드 단계) |
| 3 | `--chart-3` | `#0ea5a0` | |
| 4 | `--chart-4` | `#8b5cf6` | |
| 5 | `--chart-5` | `#d2650f` | |
| 6 | `--chart-6` | `#db2777` | |

- **순서는 고정이다.** 계열이 필터로 줄어도 색이 사람을 따라간다 — 남은 계열을 다시 칠하지 않는다.
- **일곱 번째 계열에 새 색을 만들지 않는다.** "기타"로 접거나 화면을 나눈다.
- 두 계열 비교의 기본 짝은 **AI(`--chart-ai`) 대 사용자(`--chart-user`)** — 실측 ΔE 30.5로 넉넉히 갈린다.

**상태색은 계열 색으로 재사용하지 않는다.**

| 토큰 | 값 | 뜻 |
|---|---|---|
| `--chart-win` | `#0ea372` | 적중 |
| `--chart-loss` | `#e63946` (= LIVE) | 실패 |
| `--chart-pending` | `#64748b` | 미채점 |

> **적중/실패는 색만으로 말하지 않는다.** 이 초록↔빨강 짝은 색각 이상 시뮬레이션에서 ΔE 6.5(경고 대역)다 — 정상시에는 32.5로 잘 갈리지만 적록 색각에서는 붙는다. 그래서 이 짝을 쓰는 자리는 **라벨(적중/실패)이나 아이콘을 반드시 함께** 단다. 이건 권고가 아니라 이 값을 쓰기 위한 조건이다.

**크기를 나타내는 순차 램프**는 한 색상(블루)으로 밝은 쪽 → 어두운 쪽이다 (`--chart-seq-1..5`). 라이트와 다크가 다른 값을 쓰는 이유: 어두운 표면에서는 가장 어두운 단계가 바탕에 묻히고, 밝은 표면에서는 가장 밝은 단계가 묻힌다. 무지개 램프는 쓰지 않는다.

격자·축은 `--chart-grid` 하나로 물러나 있는다 — **데이터보다 진하면 안 된다.**

### Translucent (prose-only — alpha)
- **Soft Fill** (`rgba(250,250,250,0.12)`): 로그인 버튼과 보조 크롬의 반투명 채움.
- **Card Scrim** (`rgba(0,0,0,0.6)`): 카드 위 픽 수 pill 뒤에 깔리는 어두운 오버레이.
- **Gold Ring** (`rgba(212,175,55,0.35)`): 검색 필드와 챔피언 버튼의 1px inset 포커스/보더 링.
- **Gold Glow** (`rgba(212,175,55,0.15)`): 챔피언 표면의 외곽 글로우. 그림자가 아니라 발광으로 읽혀야 한다.

## 3. Typography Rules

### Font Family
- **Display / Brand**: `Oswald` (`--font-sport`) — 압축된 그로테스크. 브랜드 헤드라인, PLE 히어로, 챔피언십 타이틀을 맡는다. 스포츠 중계 자막의 수직 압축감이 이 서체의 일이다.
- **Body / Product UI**: `Pretendard` — 고밀도 제품의 일꾼. 한글·라틴이 작은 크기에서 함께 읽혀야 하므로 본문 기본값은 14px / weight 400이다.

### Hierarchy

| Role | Font | Size | Weight | Line Height | Notes |
|------|------|------|--------|-------------|-------|
| Brand Hero | Oswald | ~31px (1.94rem) | 600 | 1.1 | PLE 히어로 헤드라인 |
| Brand Section | Oswald | 20px (1.25rem) | 400 | 1.2 | 섹션·푸터 링크 |
| Shelf Heading | Oswald | 16px (1.00rem) | 600 | 1.3 | 카드 선반 제목 — "PLE 예측", "랭킹" |
| Body / UI | Pretendard | 14px (0.88rem) | 400 | 1.4 | 본문 + 고밀도 UI 텍스트 |
| Button | Pretendard | 14px (0.88rem) | 600 | 1.0 | 버튼 레이블 (SemiBold) |
| Caption | Pretendard | 12px (0.75rem) | 400 | 1.2 | LIVE 배지, 픽 수, 메타데이터 |

### Principles
- **두 서체, 두 역할**: Oswald가 브랜드/디스플레이 목소리(압축, 개성)이고 Pretendard가 기능적 읽기 목소리(고밀도, 중립, 작은 크기에서 한글·라틴 동시 가독)다. 둘은 절대 역할을 바꾸지 않는다.
- **14px가 일꾼이다**: 제품은 거의 전부 14px / 400으로 돌아 매치 선반의 정보 밀도를 최대로 끌어올린다.
- **액션은 SemiBold, 콘텐츠는 regular**: 버튼 레이블과 선반 제목만 weight 600으로 뛰고, 정보성 텍스트는 전부 400에 머문다.
- **12px 메타데이터 층**: 이 플랫폼의 밀도를 만드는 별도 캡션 티어 — LIVE 상태, 픽 수, 매치 태그.

## 4. Component Stylings

### Buttons

**예측 제출 (Primary / Championship Gold)**
- Background: `#fcbb00`
- Text: `#0c0a09`
- Radius: 9000px
- Height: 32px
- Font: 14px Pretendard weight 600
- Use: 기본 CTA — 예측 제출, 회원가입 — 단 하나의 골드 액션

**로그인 (Secondary)**
- Text: `#fafafa`
- Radius: 9000px
- Height: 32px
- Font: 14px Pretendard weight 600
- Use: 보조 내비 액션 — 반투명 `rgba(250,250,250,0.12)` 채움, 풀 pill

### Inputs & Forms

**Search Field**
- Background: `#101317`
- Text: `#fafafa`
- Radius: 8px
- Padding: 0px 12px
- Height: 36px
- Font: 14px Pretendard weight 400
- Use: 슈퍼스타·PLE 검색 입력 — 실선 보더 대신 1px inset `rgba(212,175,55,0.35)` 골드 링

### Cards & Containers

**PLE 매치 카드**
- Background: `#101317`
- Radius: 4px
- Use: 캔버스 위의 매치 / 카테고리 카드 — 대진 중심, 그림자 없음, 헤어라인 없음

### Badges

**LIVE Indicator**
- Background: `#e63946`
- Text: `#fafafa`
- Radius: 4px
- Padding: 1px 5px
- Font: 12px Pretendard weight 400
- Use: 진행 중인 PLE의 "LIVE" 상태 배지 — 레드는 이 자리와 실패에만 선다

**픽 수 Pill**
- Text: `#fafafa`
- Radius: 2px
- Padding: 0px 4px
- Font: 14px Pretendard weight 400
- Use: 카드 위 픽 수 오버레이 — `rgba(0,0,0,0.6)` 스크림 위에 앉는다

### Navigation
- Background: `#08090b`
- Text: `#fafafa`
- Font: 14px Pretendard weight 400
- Active: 활성 항목에 메탈릭 골드 `#d4af37` 텍스트
- Use: 상단 내비 ("PLE", "랭킹", "기록", "샵"); 비활성 링크는 `#78716c`로 죽인다

### Avatars
- Radius: 9000px (완전한 원)
- Use: 슈퍼스타와 유저 아바타 전반

## 5. Layout Principles

### Spacing System
- 기본 단위: 4px
- 스케일: 4px, 8px, 12px, 16px, 18px, 24px, 40px
- 특이점: 고밀도 제품 크롬은 메타데이터를 4–8px 간격으로 채우고, 선반과 섹션 리듬은 24–40px로 열린다

### Grid & Container
- 상단 유틸리티 바 + 스크롤되는 매치 카드 선반에 콘텐츠 영역을 내주는 구조
- 매치 카드는 반응형 다열 캐러셀로 배열된다 ("이번 PLE", "랭킹", 카테고리 행)
- 진행 중인 PLE가 있을 때 그 카드가 지배적 요소가 되고, 모든 크롬은 그것을 압도하지 않는 크기로 잡힌다
- 브랜드/랜딩 표면은 큰 Oswald 헤드라인을 쓰는 중앙 정렬 단일 컬럼

### Whitespace Philosophy
- **밀도 우선**: KayFabe는 정보 밀도가 높은 제품이다 — 매치 선반, 픽 수, 카테고리. 여백은 측정되고 기능적이며, 장식적 공백이 아니다.
- **경기가 주인공이다**: 레이아웃은 라이브 콘텐츠를 액자에 넣기 위해 존재한다. 크롬은 물러난다(근흑색 캔버스, 죽인 스톤 메타데이터).
- **평면 분절**: 표면은 보더나 그림자가 아니라 표면 계단(`#08090b` → `#0d0f12` → `#101317`)과 구조로 나뉜다.

### Border Radius Scale

**실제 쓰이는 사다리는 Tailwind 기본 계단이다** (2026-10-01 실측으로 문서를 코드에 맞췄다). 원래 적혀 있던 2·4·8·9000 넷은 초기 PLE 화면만 설명했고, 그 뒤 들어온 카드·다이얼로그·패널이 전부 `lg`·`xl`·`2xl` 로 올라가 있었다 — 209곳이다. 문서가 모르는 값을 코드가 쓰면 훅이 매번 "off-scale" 로 잡고, 그 경고가 쌓이면 아무도 안 본다.

| 단계 | 값 | 자리 | 실측 |
|---|---|---|---|
| Micro | 2px (`rounded-sm`) | 픽 수 pill, 조밀한 오버레이 | 13 |
| Compact | 6px (`rounded-md`) | 칩·배지·작은 버튼·입력 | 48 |
| Medium | 8px (`rounded-lg`) | 검색 필드, 패널 안쪽 블록 | 88 |
| Large | 12px (`rounded-xl`) | 카드 — **기본 카드 반경** | 110 |
| XL | 16px (`rounded-2xl`) | 히어로 영상·예측 카드 같은 큰 면 | 51 |
| Full | 9000px (`rounded-full`) | 버튼과 아바타 — 브랜드 pill | 60 |

- **새 값을 끼워 넣지 않는다.** 위 여섯이 전부다. `rounded-[10px]` 같은 임의 값은 쓰지 않는다.
- 4px(`rounded-[4px]`)는 PLE 매치 카드 한 곳에만 남아 있다 — 새로 쓰지 않는다.
- **반경은 중첩에서 커진다**: 바깥 면이 안쪽 요소보다 한 단 이상 크다. 같은 값이면 안쪽이 바깥 모서리를 뚫고 나온 것처럼 보인다.

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat (Level 0) | 그림자 없음 | 페이지 배경, 내비, 버튼, 매치 카드 |
| Step (Level 0.5) | 표면 계단 `#08090b` → `#0d0f12` → `#101317` → `#14171c` | 구역·카드·카드 안 카드 (KAYFABE 2.0) |
| Scrim (Level 1) | `rgba(0,0,0,0.6)` 오버레이 | 카드 썸네일 위의 픽 수 / 메타데이터 pill |
| Ring (Level 2) | `rgba(212,175,55,0.35) 0px 0px 0px 1px inset` | 검색 필드 보더/포커스 링, 챔피언 버튼 테두리 |

**Shadow Philosophy**: 그림자가 거의 없는 시스템이다. 내비, 버튼, 헤딩, 매치 카드 전부 `box-shadow: none`이다. 카드 스택 엘리베이션은 없다. 깊이 장치는 둘뿐이다 — (1) 카드 썸네일 위로 메타데이터를 띄우는 반투명 어두운 스크림(`rgba(0,0,0,0.6)`), (2) 폼 필드와 챔피언 표면의 inset 골드 링. 챔피언 표면에만 예외적으로 외곽 글로우(`rgba(212,175,55,0.15)`)가 허용되는데, 이것은 엘리베이션이 아니라 발광이다 — 벨트가 조명을 받는 방식이지 카드가 떠 있는 방식이 아니다. 강조가 필요하면 골드나 LIVE 레드를 집지, 그림자를 집지 않는다.

## 7. Do's and Don'ts

### Do
- 챔피언십 골드(`#fcbb00`)는 기본 액션에만 — 예측 제출, 회원가입 — 단 하나의 브랜드 액션 색으로 유지한다
- 상호작용은 골드 램프를 따라 내려간다: 링크 `#d4af37`, hover `#f99c00`, deep `#b75000`
- 브랜드/디스플레이는 Oswald, 고밀도 제품 UI는 Pretendard 14px / 400
- 흰 바탕 순수 검정 대신 근흑색 캔버스(`#08090b`) 위 근백색 잉크(`#fafafa`)
- 시스템을 평평하게 유지한다 — 드롭 섀도우 없음, 깊이는 표면 계단과 반투명 스크림으로
- 버튼과 아바타는 풀 pill(9000px), 기능 크롬은 2·6·8·12·16px 계단
- WWE 레드 `#e63946`은 LIVE·실패에만 예약한다
- **블루는 AI·데이터가 있는 자리에만 쓴다** — 그것이 "여기부터 데이터"라는 신호다
- **숫자를 크게 세운다** — KPI·통계는 화면에서 가장 굵고, 설명은 그 아래 작게
- **실제 데이터만 보여 준다** — 표본이 부족한 지표는 숨기고, 없는 숫자는 만들지 않는다 (§14)
- 경기가 시각 위계를 소유하게 둔다 — 크롬은 조용하고 촘촘하게

### Don't
- 골드를 여러 요소에 퍼뜨리지 않는다 — 단일 액션 신호가 희석되고, 벨트의 의미가 사라진다
- 본문 텍스트에 순수 흰색(`#ffffff`)을 쓰지 않는다 — 근백색 잉크 `#fafafa`를 예약한다
- 드롭 섀도우나 카드 스택 엘리베이션을 더하지 않는다 — 이 시스템은 설계상 평평하다
- LIVE 레드를 진행 중 상태와 실패 외의 어떤 것에도 쓰지 않는다
- **네 번째 채도 높은 브랜드 색상을 섞지 않는다** — 골드·레드·블루가 정체성이고 그 셋으로 끝이다. **예외는 하나뿐이다**: 포트폴리오 표면의 `--team-b`(티얼)가 팀 프로젝트 둘을 가른다 (§2 「팀 프로젝트 출처」). 제품 화면으로 넘어오지 않는다
- **블루를 장식으로 쓰지 않는다** — AI 사이트처럼 보이게 만드는 순간 WWE가 사라진다. 네온 글로우·회로 무늬·"AI스러운" 그래픽은 쓰지 않는다
- **차트 색을 즉흥적으로 고르지 않는다** — `--chart-*` 토큰만 쓰고, 새 팔레트가 필요하면 검증기를 돌린다 (§2 Chart Palette)
- **이중 축 차트를 만들지 않는다** — 단위가 다른 두 지표는 차트를 나눈다
- **숫자를 지어내지 않는다** — 예시 수치를 실제 데이터처럼 세우지 않는다
- PLE 이벤트 색에 `--brand-*`를 쓰지 않는다 — 이벤트 정체성과 브랜드 액션 색은 별개 축이다 (§2 PLE Event Palette)
- 고밀도 제품 UI를 Oswald로 조판하지 않는다 — 제품 UI는 Pretendard의 것이고 Oswald는 브랜드/디스플레이다
- 버튼이나 아바타에 각진 모서리를 쓰지 않는다 — 그것들은 풀 pill이다
- 크롬이 경기보다 밝아지지 않게 한다 — 초점은 UI가 아니라 경기다

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | <640px | 내비가 오프캔버스 드로어로 접힘; 단일 컬럼 선반; 매치 카드 전체 너비 |
| Tablet | 640-1024px | 행당 매치 카드 2–3장; 축약 내비 |
| Desktop | 1024-1440px | 전체 내비 + 상단 바 + 다열 캐러셀 |
| Large Desktop | >1440px | 더 넓은 선반, 캐러셀당 더 많은 카드 |

### Touch Targets
- 버튼은 32px 높이, 풀 pill, 편안하게 탭 가능
- 검색 필드는 36px 높이
- 매치 카드는 모바일에서 엄지로 누르기 좋은 크기

### Collapsing Strategy
- 내비: 데스크톱 고정 레일 → 모바일 오프캔버스 드로어
- 매치 캐러셀: 다열 → 축소 → 단일 컬럼
- 진행 중 PLE 카드: 컨테이너 → 모바일 전체 너비
- 메타데이터 pill(LIVE, 픽 수)은 모든 크기에서 카드 위에 유지된다

### Image Behavior
- 카드 썸네일은 어떤 크기에서도 그림자를 갖지 않는다 — 평면 시스템과 일관되게
- 픽 수와 LIVE pill은 모든 브레이크포인트에서 `rgba(0,0,0,0.6)` 스크림으로 썸네일에 겹친다
- 카드는 뷰포트 전반에서 4px radius를 유지한다

## 9. Agent Prompt Guide

### Quick Color Reference
- Primary CTA: Championship Gold (`#fcbb00`) — Tailwind `bg-primary`
- 링크 / 활성: Metallic Gold (`#d4af37`) — `text-brand-link`
- Hover: Gold Hover (`#f99c00`) — `hover:bg-brand-hover`
- Deep surface: Gold Deep (`#b75000`) — `bg-brand-deep`
- 헤딩 / 본문 텍스트: Ink (`#fafafa`) — `text-foreground`
- 보조 텍스트: Body Stone (`#d6d3d1`)
- Muted / 비활성: Muted Stone (`#78716c`) — `text-muted-foreground`
- Canvas: (`#08090b`) — `bg-background`; Section: (`#0d0f12`) — `bg-surface-2`; Card: (`#101317`) — `bg-card`
- LIVE 시그널: (`#e63946`) — `bg-live` / `text-live`; AI·데이터: (`#3b82f6`) — `text-data` / `bg-data-400`
- 차트: `--chart-1..6` (계열) · `--chart-ai` / `--chart-user` (두 편) · `--chart-win` / `--chart-loss` (상태)

> 하드코딩 hex 대신 위의 Tailwind 유틸리티를 쓴다. 토큰은 `app/globals.css`의 `:root` / `.dark` / `@theme inline` 세 곳에서만 정의된다.

### Example Component Prompts
- "캔버스 `bg-background` 위 상단 내비를 만든다. `text-foreground` Pretendard 14px/400 링크, 활성 항목은 `text-brand-link`. 검색 필드(`bg-card`, 8px radius, inset 골드 1px 링). 우측: 로그인 pill(반투명 채움, `text-foreground`, 9000px)과 예측 제출 pill(`bg-primary text-primary-foreground`, 14px 600, 9000px, 32px 높이)."
- "PLE 매치 카드를 디자인한다: `bg-card` 위 대진 중심 카드, 4px radius, 그림자 없음. 좌상단에 LIVE 배지(`bg-live text-foreground`, 4px radius, 1px 5px 패딩, 12px), 좌하단에 픽 수 pill(`rgba(0,0,0,0.6)` 스크림 위 `text-foreground`, 2px radius)를 겹친다."
- "브랜드 히어로를 만든다: 큰 Oswald 헤드라인 weight 600, `text-foreground`. 골드 CTA 하나 — `bg-primary text-primary-foreground`, 풀 pill(9000px), 14px Pretendard 600."
- "랭킹 행을 만든다: Oswald 선반 제목 16px/600, 그 아래 슈퍼스타 카드 캐러셀. 원형(9000px) 아바타, Pretendard 14px/400 이름은 `text-foreground`, 메타데이터는 `text-muted-foreground`."

### Iteration Guide
1. 챔피언십 골드(`#fcbb00`)가 단일 액션 색이다 — 퍼뜨리지 않는다
2. 상호작용은 골드 램프를 내려간다: `#d4af37` 링크 → `#f99c00` hover → `#b75000` deep
3. 브랜드/디스플레이는 Oswald, 제품 UI는 Pretendard 14px/400 — 둘은 바뀌지 않는다
4. 그림자 없음 — 평면 표면. 스크림(`rgba(0,0,0,0.6)`)이 카드 메타데이터를 띄운다
5. 버튼 + 아바타는 풀 pill(9000px); 배지 6px · 입력 8px · 카드 12px · 큰 면 16px
6. 텍스트는 근흑색 캔버스 `#08090b` 위 근백색 잉크 `#fafafa`, 흰 바탕 순수 검정이 아니다
7. WWE 레드 `#e63946`은 LIVE·실패 전용 · 블루 `#3b82f6`는 AI·데이터 전용 — 둘 다 일반 액센트가 아니다
8. 크롬을 조용하게 유지한다 — 경기가 주인공이다

---

## 10. Voice & Tone

KayFabe의 목소리는 **경기를 아는 사람의 것**이다 — 팬을 가르치려 들지 않고, 같은 자리에서 같은 경기를 보는 사람으로 말한다. 레지스터는 대화체이고 뜨겁되, 종목 안쪽의 언어(케이페이브, 히트/베이비페이스, 푸시, 카드)를 배타적이지 않게 쓴다. 그리고 회사보다 슈퍼스타와 예측하는 사람을 일관되게 중심에 둔다. 다른 플랫폼이 "사용자"에게 말할 때, KayFabe는 같은 라이브 순간에 함께 있는 참여자에게 말한다.

| Context | Tone |
|---|---|
| 제품 CTA | 직접적이고 마찰 없음. "예측 제출", "로그인", "픽 보기". |
| 브랜드 / 마케팅 | 에너지 있고, 커뮤니티를 축하하며, 종목 문화에 유창하게. |
| 라이브 / 상태 | 간결하고 사실적. "LIVE", 픽 수, 카테고리 태그 — 한눈에 들어오는 정보. |
| 결과 / 적중 | 결과를 과장하지 않는다. 맞았으면 맞았다고, 틀렸으면 틀렸다고 담백하게. |
| 접근성 / 포용 | 진지하고 포용적. 예측은 아는 사람만의 것이 아니다. |

**Voice samples:**
[FILL IN: 이 프로젝트가 실제로 쓴 문구를 그대로 옮긴다. 레퍼런스의 브랜드 문구를 가져다 쓰지 말 것.]

**Forbidden register**: 커뮤니티 문화를 무시하는 기업체 경직, 슈퍼스타를 가리는 과장, 전문용어의 벽, 그리고 라이브 순간을 즉각적이고 현재적인 것 이외의 무언가로 다루는 태도.

<!-- omd:limitation §11-13은 프로젝트 고유의 사실 정보를 요구한다. 출시 전 교체할 것. 지어내지 말 것. -->

## 11. Brand Narrative

[FILL IN: 이 프로젝트가 언제·왜 시작됐고, 무엇을 거부하며 무엇을 받아들이는지. 창립 시점·인수·리브랜드 같은 사실은 실제로 있었던 것만 적는다.]

## 12. Principles

[FILL IN: 3–5개 원칙. 각 항목은 "원칙 문장 + *UI implication:* 그 원칙이 화면에서 무엇을 강제하는가" 형태로 쓴다.]

## 13. Personas

[FILL IN: 공개적으로 관찰 가능한 사용자 세그먼트에 기반한 가상 아키타입 2–4개. 실존 인물이 아님을 명시한다.]

## 14. States

| State | Treatment |
|---|---|
| **Empty (예정된 PLE 없음)** | 근흑색 캔버스(`#08090b`). 지금 열린 경기가 없다는 Ink(`#fafafa`) 한 줄과, 지난 기록으로 보내는 골드 CTA 하나. 무거운 일러스트 없음. |
| **Empty (검색 결과 없음)** | 결과가 없다는 Muted Stone(`#78716c`) 한 줄, 질의어를 되비추고 범위를 넓히라고 제안. 차분하고 사실적. |
| **Loading (선반 / 캐러셀)** | `#08090b` 위 최종 치수의 스켈레톤 매치 카드, 4px radius, 평면 펄스 — 그림자 shimmer 없음, 그림자 없는 시스템과 일관되게. |
| **Loading (예측 제출 중)** | 버튼 영역 인라인 스피너; 주변 크롬은 상호작용 가능 상태를 유지한다. |
| **Error (경기 취소 / 카드 변경)** | 해당 매치가 Ink로 변경 상태를 보여주고 아래에 대체 매치를 제안한다 — 절대 막다른 길로 두지 않는다. |
| **Error (폼 검증)** | 입력 아래 필드 단위 메시지. "필수"가 아니라 무엇이 유효한지 설명한다. |
| **Success (예측 저장됨)** | 짧은 인라인 확인; 픽 컨트롤이 즉시 상태를 뒤집는다. 축하 블로커 없음 — 액션은 즉각적이다. |
| **Skeleton** | 최종 치수의 `#101317` 블록, 2–4px radius, 평면 펄스. |
| **표본 부족 (지표를 못 낸다)** | **숫자를 만들지 않는다.** 그 지표가 있어야 할 자리에 Muted Stone 한 줄로 *무엇이 모자란지*를 적는다 — "표본 12건 · 정밀도는 50건부터 표시합니다". 0%나 임시값으로 채우지 않는다 (§7). |
| **표본이 작은 채로 낼 때** | 값 옆에 **분모를 함께** 세운다 — "적중률 100% (12/12)". 분모 없는 백분율은 과장이다. |
| **Disabled** | 불투명도를 낮춘 표면과 텍스트; 골드 액션은 회색으로 변하는 대신 흐려져 브랜드 읽힘을 보존한다. |

## 15. Motion & Easing

**Durations**:

| Token | Value | Use |
|---|---|---|
| `motion-fast` | 120ms | Hover, 버튼 프레스, 포커스 링 |
| `motion-standard` | 200ms | 선반 노출, 드롭다운, 내비 확장/축소 |
| `motion-slow` | 320ms | 페이지 단위 전환, 테마 전환 |

**Easings**:

| Token | Curve | Use |
|---|---|---|
| `ease-enter` | `cubic-bezier(0.2, 0.6, 0.25, 1)` | 도착 — 메뉴, 패널, 카드 |
| `ease-exit` | `cubic-bezier(0.4, 0.0, 1, 1)` | 사라짐 |
| `ease-standard` | `cubic-bezier(0.25, 0.1, 0.25, 1)` | 양방향 전환 |

**Motion rules**: 고밀도 제품 안에서 모션은 기능적이고 빠르게 머물러 경기와 경쟁하지 않는다. hover와 프레스는 `motion-fast`로 반응하고, 선반과 내비는 `motion-standard / ease-enter`로 펼쳐진다. LIVE 배지의 맥박(`wwe-live-pulse`)은 이 규칙의 유일한 예외로, 상태가 살아 있음을 알리는 정보이지 장식이 아니다. 표현적인 브랜드 수준 애니메이션은 랜딩·마케팅 표면에 살지, 돌아가는 경기 위에 얹히지 않는다. `prefers-reduced-motion: reduce`에서는 모든 전환이 즉시로 붕괴하고, 제품은 완전히 기능한다.

## 16. Charts & Data Display (KAYFABE 2.0)

**차트 라이브러리는 Recharts다** (`recharts@2.15.0`). 새로 고른 것이 아니라 **이미 이 저장소에 있고 `/admin`이 쓰고 있는** 라이브러리다 — 새 의존성을 더하지 않는다는 결정의 결과다. React 19를 peer로 선언하고 SVG로 렌더하므로 아래 CSS 변수 토큰을 `fill`·`stroke`에 그대로 넣을 수 있다.

### 형태부터 고른다 (색은 마지막이다)

| 데이터가 하는 일 | 형태 |
|---|---|
| 숫자 하나가 결론이다 (적중률, 총 경기 수) | **차트가 아니라 KPI 타일** — 큰 숫자 + 분모 + 한 줄 설명 |
| 항목 간 크기 비교 (선수별 승수) | 가로 막대 |
| 시간에 따른 변화 (연도별 승률, 모델 성적 추이) | 선 그래프 |
| 부분과 전체 (승/패/무) | 누적 막대 하나 — **원형 차트를 쓰지 않는다** |
| 두 편의 대결 (AI 대 사용자) | 두 계열 막대 · `--chart-ai` / `--chart-user` |
| 승률 같은 비율 하나 | 가로 미터 바 + 숫자 |

### 마크

- 선 2px · 마커 ≥ 8px · 막대 끝은 4px 라운드, 바닥은 축에 붙인다
- 채워진 면 사이에는 **2px 표면 간격**을 둔다 (누적 막대의 칸, 인접 막대 모두)
- 값 라벨은 **골라서만** 단다 — 모든 점에 숫자를 붙이지 않는다
- 격자·축은 `--chart-grid`, 텍스트는 항상 잉크 토큰(`--foreground` · `--muted-foreground`) — **계열 색으로 글자를 칠하지 않는다**
- 계열이 둘 이상이면 범례가 **항상** 있고, 넷 이하면 직접 라벨도 함께 단다 (색만으로 정체를 말하지 않는다)

### 상호작용

HTML 차트는 그 자체로 상호작용한다. 선·면에는 크로스헤어 + 툴팁, 막대·점·셀에는 마크별 툴팁을 **기본으로** 단다. 필터는 차트 위 한 줄에 모은다. KPI 타일만 예외다.

### 숫자를 어떻게 쓰는가

- KPI는 Oswald가 아니라 **Pretendard의 큰 굵은 숫자**다 — 압축 서체는 숫자를 세로로 눌러 자릿수를 헷갈리게 한다
- 표 안의 숫자는 자릿수를 맞춘다 (`tabular-nums`)
- 비율은 **분모와 함께** 쓴다 — "100% (12/12)" (§14)

---

<!--
omd:attribution

base: twitch 레퍼런스 (.claude/data/references/twitch/DESIGN.md, verified 2026-06-17)
mode: inspired — 구조만 빌리고 색은 이 프로젝트 값을 승격 (omd:init Phase 3, 사용자 선택 2안)

twitch에서 빌린 것 (구조, 변경 금지):
  - "단 하나의 채도 높은 액션 색 + 하강 램프 4단" 규율
  - "액션 색과 분리된 단 하나의 상태 시그널 색" 규율
  - spacing 스케일 (4/8/12/16/18/24/40), radius 스케일 (2/4/8/9000)
  - shadowless 철학과 2단 depth 모델 (스크림 + inset 링)
  - 타이포 계층 수치 (31/20/16/14/14/12, weight 600/400/600/400/600/400)
  - motion duration·easing 토큰
  - §1-10, §14-15의 섹션 구조와 서술 리듬

이 프로젝트에서 승격한 색 (전부 기존 www 코드에 실재하던 값. 창작 없음):
  | 역할 | 값 | 승격 근거 |
  |---|---|---|
  | 골드 램프 50~950 | Tailwind v4 `amber` 값 그대로 | TSX의 `amber-*` 유틸리티 **169곳** — 앱 골드의 압도적 다수 |
  | primary | brand-400 #fcbb00 (라이트 brand-600) | 램프에서 지정 |
  | link | #d4af37 | `.btn-champion` 테두리·글로우의 메탈릭 골드. 램프 밖 |
  | primary-hover | brand-500 #f99c00 (라이트 brand-700) | 램프에서 지정 |
  | primary-deep | brand-700 #b75000 (라이트 brand-800) | 램프에서 지정 |
  | ink | #fafafa | components/kayfabe-logo.tsx |
  | body | #d6d3d1 | components/kayfabe-logo.tsx |
  | muted | #78716c | tsx 6회 |
  | canvas | #0a0a0c | tsx 8회 — 최다 사용 배경 |
  | surface-alt | #1c1917 | components/kayfabe-logo.tsx |
  | on-primary | #0c0a09 | components/kayfabe-logo.tsx 2회 |
  | live | #e02020 | globals.css `rgba(224,32,32,…)` 10회 |
  | info | #3b82f6 | globals.css `rgba(59,130,246,…)` 9회 |

서체: Roobert → Oswald (`--font-sport`, 기존), Inter → Pretendard (globals.css가 이미 로드)
도메인 명사: 라이브 스트림 → PLE 이벤트, 채널 타일 → 매치 카드, 시청자 수 → 픽 수, 크리에이터 → 슈퍼스타

골드 램프 기준을 바꾼 이유 (2026-08-04, 초판 정정):
  초판은 골드를 globals.css의 raw `rgba(251,191,36,…)` 계열(#fbbf24 / #ca8a04 / #a16207)에서
  뽑았다. 그 값들은 Tailwind **v3** amber와 같아 "amber-400 = #fbbf24"로 적었는데, 이 프로젝트는
  **v4**이고 v4는 팔레트를 oklch로 재구성하면서 amber가 주황 쪽으로 이동했다(400 = #fcbb00,
  600 = #dd7400, 700 = #b75000). 즉 앱에는 골드가 둘이었다 — CSS의 rgba 골드 19곳과
  TSX의 v4 amber 골드 169곳.
  사용처가 9배 많은 TSX 쪽을 기준으로 삼아 램프를 v4 값으로 맞췄다. 덕분에 `amber-*` →
  `brand-*` 치환 169곳이 색 변화 0으로 끝났다(램프 11단계 값 일치로 검증).
  남은 불일치: globals.css의 `rgba(251,191,36,…)` 계열 19곳은 아직 램프와 다르다.

미해결:
  - 파일 상단 omd:unresolved 참조 (radius 스케일이 코드와 다름)
  - (해결됨 2026-08-04) globals.css의 raw 골드는 램프에 접지 않고 이벤트 팔레트 토큰으로
    분리했다. 실측 결과 그 값들은 흩어진 브랜드 골드가 아니라 `.ple-card--wrestlemania` 등
    PLE별 고유색이었다. 브랜드 램프에 접으면 이벤트 정체성이 브랜드 색에 종속된다.
  - globals.css의 나머지 WWE 테마 클래스(상태 배지·패널·행 등) 59개 셀렉터 169건은
    아직 raw 리터럴이다. 이번 범위 밖.

구조 변경 (2026-08-04): §2에 `### PLE Event Palette` H3를 추가했다. twitch 레퍼런스에는
없는 섹션이지만, 이 제품에는 브랜드 색과 독립된 이벤트별 색 축이 실재하고 그걸 기록할 자리가
필요했다. 나머지 H2/H3 구조와 순서는 그대로다.

§11-13과 §10 Voice samples는 placeholder다. 사실 정보를 지어내지 않았다.
-->
