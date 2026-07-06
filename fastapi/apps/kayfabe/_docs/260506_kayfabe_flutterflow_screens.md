# Kayfabe App — FlutterFlow 화면 설계 명세서

> **태그**: #kayfabe #flutterflow #화면설계 #프로레슬링  
> **날짜**: 2026-05-06  
> **버전**: v0.1 (MVP)  
> **상태**: 🟡 개발 의뢰용 초안

---

## 📁 전체 페이지 구조

```
kayfabe/
├── 01_LoginPage          ← 구글 로그인
├── 02_BrandListPage      ← 단체 브랜드 목록
└── 03_BrandDetailPage    ← 브랜드 상세 정보
```

---

## 01. LoginPage — 로그인 화면

### 🎯 목적
- 앱 진입 시 첫 화면
- 구글 계정으로 로그인
- 등록된 이메일 유저만 접근 허용 (현재는 클릭 시 무조건 로그인 성공 처리)

---

### 🖼️ 레이아웃 구성

```
┌─────────────────────────────┐
│                             │
│                             │
│        [앱 로고 / 아이콘]    │
│        KAYFABE              │
│        프로레슬링 정보 허브   │
│                             │
│                             │
│   ┌─────────────────────┐   │
│   │  🔵 Google로 로그인  │   │
│   └─────────────────────┘   │
│                             │
│   등록된 계정만 입장 가능     │
│                             │
└─────────────────────────────┘
```

---

### 🧩 위젯 목록

| 위젯명            | 타입              | 설명                                      |
| ----------------- | ----------------- | ----------------------------------------- |
| `AppLogo`         | Image / Icon      | 앱 로고 또는 레슬링 테마 아이콘            |
| `AppTitle`        | Text              | "KAYFABE" — Bold, 대형 타이포             |
| `AppSubtitle`     | Text              | "프로레슬링 정보 허브" — 서브 텍스트       |
| `GoogleLoginBtn`  | Button            | 구글 로그인 버튼 (Google 공식 스타일)      |
| `FooterNotice`    | Text              | "등록된 계정만 입장 가능합니다"            |

---

### ⚙️ 액션 (Actions)

| 트리거                  | 액션                                      | 조건                    |
| ----------------------- | ----------------------------------------- | ----------------------- |
| `GoogleLoginBtn` 클릭   | `Navigate to` → `BrandListPage`           | 현재: 무조건 성공 처리   |
| *(추후 구현)* 로그인 실패 | `Show Snackbar` "등록되지 않은 계정입니다" | 이메일 허용 목록 검증 시 |

> ⚠️ **개발 메모**: 현재 단계에서는 구글 로그인 버튼 클릭 시  
> 이메일 검증 없이 `BrandListPage`로 바로 이동합니다.  
> 추후 Firestore `allowed_users` 컬렉션과 연동하여 화이트리스트 검증 추가 예정.

---

### 🎨 스타일 가이드

| 속성           | 값                              |
| -------------- | ------------------------------- |
| 배경색         | `#0D0D0D` (다크 블랙)           |
| 앱 타이틀 색상 | `#FFD700` (골드)                |
| 서브텍스트 색상 | `#AAAAAA` (그레이)              |
| 버튼 스타일    | White background, Google 공식 UI |
| 폰트           | Bold Sans-serif (예: Oswald)    |

---

---

## 02. BrandListPage — 브랜드 목록 화면

### 🎯 목적
- 로그인 성공 후 진입하는 메인 화면
- 프로레슬링 단체(브랜드) 목록 표시
- 각 브랜드 카드를 탭하면 상세 화면으로 이동

---

### 🖼️ 레이아웃 구성

```
┌─────────────────────────────┐
│  KAYFABE           [👤 아이콘]│  ← AppBar
├─────────────────────────────┤
│  🏷️ 단체 브랜드              │  ← 섹션 타이틀
├─────────────────────────────┤
│  ┌───────────────────────┐  │
│  │ [로고]  WWE            │  │  ← BrandCard
│  │         World Wrestling│  │
│  │         Entertainment  │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ [로고]  AEW            │  │
│  │         All Elite      │  │
│  │         Wrestling      │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ [로고]  NJPW           │  │
│  │         신일본 프로레슬링│  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ [로고]  TNA / Impact   │  │
│  └───────────────────────┘  │
│  ┌───────────────────────┐  │
│  │ [로고]  ROH            │  │
│  │         Ring of Honor  │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

---

### 🧩 위젯 목록

| 위젯명           | 타입           | 설명                                        |
| ---------------- | -------------- | ------------------------------------------- |
| `AppBar`         | AppBar         | 타이틀 "KAYFABE" + 유저 아이콘              |
| `SectionTitle`   | Text           | "단체 브랜드"                               |
| `BrandListView`  | ListView       | 브랜드 카드 목록 (스크롤 가능)              |
| `BrandCard`      | Container      | 로고 이미지 + 단체명 + 부제                 |
| `BrandLogo`      | Image          | 각 단체 로고 이미지                         |
| `BrandName`      | Text           | 단체 약칭 (예: WWE, AEW)                    |
| `BrandFullName`  | Text           | 단체 전체명 (서브텍스트)                    |
| `ChevronIcon`    | Icon           | 우측 화살표 `›` — 상세 이동 안내           |

---

### 📋 브랜드 초기 데이터 목록

| 브랜드 ID | 약칭   | 전체명                          | 국가   |
| --------- | ------ | ------------------------------- | ------ |
| `wwe`     | WWE    | World Wrestling Entertainment   | 🇺🇸 미국 |
| `aew`     | AEW    | All Elite Wrestling             | 🇺🇸 미국 |
| `njpw`    | NJPW   | 新日本プロレスリング             | 🇯🇵 일본 |
| `tna`     | TNA    | Total Nonstop Action / Impact   | 🇺🇸 미국 |
| `roh`     | ROH    | Ring of Honor                   | 🇺🇸 미국 |

> 💡 **데이터 구조 메모**: 향후 Firestore `brands` 컬렉션으로 관리 예정.  
> 현재는 FlutterFlow 내부 `App State` 또는 `Static Data`로 구성.

---

### ⚙️ 액션 (Actions)

| 트리거             | 액션                                                     |
| ------------------ | -------------------------------------------------------- |
| `BrandCard` 탭     | `Navigate to` → `BrandDetailPage` (브랜드 ID 파라미터 전달) |

---

### 🎨 스타일 가이드

| 속성           | 값                              |
| -------------- | ------------------------------- |
| 배경색         | `#0D0D0D`                       |
| AppBar 색상    | `#1A1A1A`                       |
| 카드 배경      | `#1E1E1E`                       |
| 카드 테두리    | `#FFD700` (좌측 강조 border)    |
| 브랜드명 색상  | `#FFFFFF`                       |
| 서브텍스트 색상 | `#888888`                      |
| 카드 간격      | `12px`                          |
| 카드 radius    | `12px`                          |

---

---

## 03. BrandDetailPage — 브랜드 상세 화면

### 🎯 목적
- 선택된 브랜드의 상세 정보 표시
- 브랜드 소개, 주요 타이틀, 방송 정보, 주요 선수 등 노출

---

### 🖼️ 레이아웃 구성

```
┌─────────────────────────────┐
│  ← 뒤로가기       WWE       │  ← AppBar
├─────────────────────────────┤
│                             │
│      [브랜드 배너 이미지]    │
│                             │
├─────────────────────────────┤
│  ℹ️ 브랜드 소개              │
│  World Wrestling             │
│  Entertainment은 ...         │
├─────────────────────────────┤
│  🏆 주요 타이틀              │
│  • WWE Championship          │
│  • Universal Championship    │
│  • Intercontinental Title    │
├─────────────────────────────┤
│  📺 방송 정보                │
│  • RAW — 매주 월요일         │
│  • SmackDown — 매주 금요일   │
├─────────────────────────────┤
│  🌍 공식 링크                │
│  [ 공식 웹사이트 바로가기 ]  │
└─────────────────────────────┘
```

---

### 🧩 위젯 목록

| 위젯명             | 타입           | 설명                                      |
| ------------------ | -------------- | ----------------------------------------- |
| `AppBar`           | AppBar         | 뒤로가기 버튼 + 브랜드명 타이틀           |
| `BrandBanner`      | Image          | 브랜드 대표 배너 이미지 (전체 너비)       |
| `SectionIntro`     | Text           | "브랜드 소개" 섹션 타이틀                 |
| `IntroText`        | Text           | 브랜드 설명 텍스트                        |
| `SectionTitles`    | Text           | "주요 타이틀" 섹션 타이틀                 |
| `TitleList`        | ListView       | 보유 타이틀 목록                          |
| `SectionBroadcast` | Text           | "방송 정보" 섹션 타이틀                   |
| `BroadcastList`    | ListView       | 방영 프로그램 + 요일 목록                 |
| `OfficialLinkBtn`  | Button         | 공식 웹사이트 외부 링크                   |

---

### 📋 브랜드별 상세 데이터 예시

#### WWE
```
소개: 세계 최대 프로레슬링 단체. 1952년 설립.
주요 타이틀: WWE Championship, Universal Championship, Intercontinental Championship, Women's Championship
방송: RAW (월), SmackDown (금), NXT (화)
공식 사이트: https://www.wwe.com
```

#### AEW
```
소개: 2019년 창설된 신생 메이저 단체. WWE의 대안으로 급성장.
주요 타이틀: AEW World Championship, TNT Championship, AEW Tag Team Championship
방송: Dynamite (수), Collision (토)
공식 사이트: https://www.allelitewrestling.com
```

#### NJPW
```
소개: 일본 최대 프로레슬링 단체. 스트롱 스타일의 본고장.
주요 타이틀: IWGP World Heavyweight Championship, NEVER Openweight Championship
방송: 격주 대회 중계 (NJPW World 스트리밍)
공식 사이트: https://www.njpw1972.com
```

---

### ⚙️ 액션 (Actions)

| 트리거                | 액션                                    |
| --------------------- | --------------------------------------- |
| AppBar 뒤로가기       | `Navigate Back` → `BrandListPage`       |
| `OfficialLinkBtn` 탭  | `Launch URL` — 해당 브랜드 공식 사이트  |

---

### 🎨 스타일 가이드

| 속성              | 값                           |
| ----------------- | ---------------------------- |
| 배경색            | `#0D0D0D`                    |
| 섹션 타이틀 색상  | `#FFD700` (골드)             |
| 본문 텍스트 색상  | `#DDDDDD`                    |
| 구분선            | `#2A2A2A`                    |
| 공식 링크 버튼    | Gold border + 투명 배경      |
| 배너 이미지 높이  | `200px`                      |
| 섹션 간격         | `24px`                       |

---

---

## 🗺️ 네비게이션 플로우 요약

```
[LoginPage]
     │
     │ GoogleLoginBtn 탭 (무조건 성공)
     ▼
[BrandListPage]
     │
     │ BrandCard 탭 (브랜드 ID 전달)
     ▼
[BrandDetailPage]
     │
     │ 뒤로가기
     ▲
[BrandListPage]
```

---

## 🚧 추후 개발 예정 기능

| 기능                       | 우선순위 | 설명                                         |
| -------------------------- | -------- | -------------------------------------------- |
| 이메일 화이트리스트 검증   | 🔴 높음  | Firestore `allowed_users` 컬렉션 연동        |
| 선수 목록 화면             | 🟡 중간  | 각 브랜드별 소속 선수 리스트 및 프로필       |
| 이벤트 / PPV 캘린더        | 🟡 중간  | 브랜드별 대형 이벤트 일정                    |
| 경기 결과 피드             | 🟢 낮음  | 최신 대회 결과 표시                          |
| 즐겨찾기 / 북마크          | 🟢 낮음  | 관심 브랜드 또는 선수 저장                   |

---

## 📎 참고 자료

- FlutterFlow 공식 문서: https://docs.flutterflow.io
- Google Sign-In 연동 가이드: https://docs.flutterflow.io/authentication/google-sign-in
- Firestore 연동 가이드: https://docs.flutterflow.io/data-and-backend/firebase

---

*이 문서는 Claude AI와의 대화를 기반으로 생성된 에이전트 교육과정 개발 자료입니다.*
