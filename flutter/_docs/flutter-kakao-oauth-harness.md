# HARNESS (Flutter): 카카오 소셜 로그인 — 모바일 클라이언트 연동

> **범위:** `flutter/` 앱 전용. 서버 구현·Redis 스키마·DB 마이그레이션은 [`fastapi/_docs/flutter-kakao-oauth-harness.md`](../../fastapi/_docs/flutter-kakao-oauth-harness.md)에 있다.
> **대상 저장소:** `cloud.jsangho.all`
> **작업 주체:** Claude Code
> **작성일:** 2026-08-03
> **상태:** 구현·실기기 검증 완료 (2026-08-03, 갤럭시 A35 / Android 16). Android 전용 — iOS 프로젝트는 여전히 없다
> **상위 규칙:** [루트 CLAUDE.md](../../CLAUDE.md) · [flutter/CLAUDE.md](../CLAUDE.md)
> **관련 문서:** [안드로이드 실기기 하네스](flutter-android-harness.md) · [아이폰 하네스](flutter-iphone-harness.md)

---

## 0. 이 문서를 읽는 방법

- **§2 결정사항**은 확정이다. 재논의하지 말고 그대로 구현한다.
- **§3 금지사항**을 위반하는 코드는 작성 즉시 폐기 대상이다.
- **§5 API 계약**은 백엔드 문서 §7과 **글자 그대로 같아야 한다.** 한쪽만 고치지 않는다.
- **§7 작업 단위**를 순서대로 진행하고, 각 단위 종료 시 **§9 검증 기준**과 **§10 하네스 게이트**를 통과해야 다음으로 넘어간다.
- 판단이 필요하면 **임의로 결정하지 말고 §11에 기록한 뒤 멈춘다.**
- ⚠️ **서버가 먼저다.** §5의 엔드포인트가 실제로 존재하기 전에는 앱에서 검증할 수 없다. 백엔드 T1~T4 완료 전에는 이 문서의 F4 이후를 시작하지 않는다.

---

## 1. 현재 앱 실측 (2026-08-03)

| 항목 | 현재 상태 | 이 작업에 대한 함의 |
|---|---|---|
| 앱 성격 | 시계/알람/스톱워치 + 인트로 영상 (`lib/screens/`) | **인증 코드가 전무하다.** 로그인 화면·세션 상태·인증된 화면 전환이 전부 신규다 |
| `lib/` 구조 | `main.dart` · `screen.dart` · `screens/` · `widgets/` · `theme/` — 레이어 구분 없음 | 인증 코드를 어느 구조에 넣을지 결정이 필요하다 ❓ (§11) |
| 의존성 | `video_player`만. **HTTP 클라이언트·보안 저장소·카카오 SDK 전부 없음** | §4의 패키지를 새로 추가해야 한다 |
| 상태 관리 | 없음 (`setState` 수준) | 세션 상태를 어떻게 전역 노출할지 결정 필요 ❓ |
| 플랫폼 | `android/` · `web/` · `windows/` 존재. **`ios/` 디렉터리 없음** | iOS 카카오 로그인을 하려면 `flutter create --platforms=ios .`로 iOS 프로젝트를 먼저 생성해야 한다 ❓ |
| `applicationId` | `com.example.jsh_flutter` (Flutter 기본값) | 카카오 콘솔에 **패키지명 + 키 해시**를 등록해야 하므로 실제 사용할 값으로 먼저 확정한다 ❓ |
| Dart / Flutter | `sdk: ^3.12.2` → Flutter 3.44 라인, minSdk = Flutter 기본(24) | 카카오 SDK 요구사항(Android 21+ / iOS 12+)은 충족 |
| 린트 | `analysis_options.yaml` — `avoid_print: error`, `prefer_single_quotes` 등 | **`print`로 토큰을 찍으면 빌드가 에러**로 막힌다. 잘된 설정이니 유지한다 |
| 테스트 | `test/widget_test.dart` 1개 | 인증 로직 테스트가 신규 |

---

## 2. 확정된 결정사항 (변경 금지)

### D-1. 앱은 **인가 코드(authorization code)만** 획득한다

카카오 access token 발급은 **서버가** 한다. 앱은 `code`를 받아 서버로 넘기고, 그 대가로 **자체 JWT 쌍**을 받는다.

```
사용자        Flutter 앱                     API Server               Kakao
  |-- 로그인 탭 ->|                                                     |
  |              |-- 카카오톡/브라우저로 인가 요청 -------------------->|
  |              |<-- code (커스텀 스킴 리다이렉트) --------------------|
  |              |-- POST /auth/mobile/kakao { code, device* } ------->|
  |              |                          |-- 토큰 교환·프로필 조회 ->|
  |              |<-- { token, refreshToken, user } -------------------|
  |              |-- refreshToken → flutter_secure_storage             |
```

### D-2. 토큰 저장 매체

| 값 | 저장 위치 | 이유 |
|---|---|---|
| refresh token | **`flutter_secure_storage`** (Keychain / Keystore) | 재로그인 비용이 크고 수명이 길다(60일) |
| access token | 메모리 (앱 실행 중) | 15분 수명. 디스크에 남길 이유가 없다 |
| `device_id` | `flutter_secure_storage` | 앱 설치 단위 식별자. 재설치 시 새로 발급되는 것이 정상 |
| 카카오 access/refresh token | **저장하지 않는다** | 서버 전용 (백엔드 D-1) |

### D-3. 유저 정보의 출처는 **서버 응답뿐**이다

앱에서 `UserApi.instance.me()`를 호출해 얻은 값을 화면·저장소에 쓰지 않는다. 닉네임·이메일·역할은 `/auth/mobile/*` 응답의 `user` 객체만 신뢰한다.

### D-4. 세션은 플랫폼 격리다

앱이 받은 refresh token은 웹 엔드포인트에서 통하지 않는다(401). 앱의 "모든 기기 로그아웃"은 **모바일 세션만** 끊는다. 이 동작을 버그로 오해해 우회 코드를 넣지 않는다.

### D-5. 401 처리는 **single-flight 리프레시**

동시에 여러 요청이 401을 받아도 리프레시는 **정확히 한 번만** 수행하고, 나머지 요청은 그 결과를 기다렸다 재시도한다.

---

## 3. 금지사항

- ❌ `client_secret` · `KAKAO_REST_API_KEY`를 앱에 포함 (네이티브 앱 키만 앱에 들어간다)
- ❌ refresh token을 `SharedPreferences` · 파일 · 로그에 저장
- ❌ 카카오 access token을 서버로 보내 로그인 시도 (D-1 위반)
- ❌ `UserApi.instance.me()` 결과를 앱 상태의 진실로 사용 (D-3)
- ❌ `print`/`debugPrint`로 토큰·인가 코드 출력 (`avoid_print: error`로 이미 차단됨 — 우회 금지)
- ❌ 401 응답에 대해 **무한 재시도** 또는 리프레시 실패 후 재리프레시
- ❌ 서버 응답의 에러 메시지를 그대로 노출하지 않고 삼켜버리기 (사용자에게는 한국어 문구, 원문은 비노출)
- ❌ TLS 검증 우회(`badCertificateCallback` 등) — 디버그 목적이라도 커밋 금지
- ❌ 인증 로직을 위젯 `build()` 안에서 직접 호출

---

## 4. 의존성 및 플랫폼 설정

### 4.1 추가할 패키지 (`pubspec.yaml`)

| 패키지 | 용도 | 비고 |
|---|---|---|
| `kakao_flutter_sdk_user` | 인가 코드 획득 | 전체 번들(`kakao_flutter_sdk`)이 아니라 **필요한 모듈만** 넣는다 |
| `flutter_secure_storage` | refresh token · device_id 저장 | D-2 |
| `dio` | HTTP + interceptor | 401 single-flight 인터셉터가 필요해 `http` 대신 선택 |
| `device_info_plus` | `deviceName` · `os` 수집 | |
| `package_info_plus` | `appVersion` 수집 | |

> 버전은 추가 시점의 최신 stable로 `flutter pub add`가 정하게 둔다. **문서에 적힌 버전을 그대로 믿지 말고** `flutter pub outdated`로 확인한다.

### 4.2 Android

- `android/app/build.gradle.kts` — `applicationId`를 실제 값으로 확정한다 (§11).
- 카카오 콘솔에 **패키지명 + 키 해시(디버그/릴리스 각각)** 를 등록한다.
- `AndroidManifest.xml`에 카카오 인증 리다이렉트용 액티비티와 **커스텀 스킴** `kakao{NATIVE_APP_KEY}` 을 등록한다.
- 카카오톡 앱 실행 여부 조회를 위해 `<queries>` 항목이 필요하다(Android 11+ 패키지 가시성).
- 정확한 XML 블록은 카카오 공식 문서의 현재 버전을 확인해 적용한다 — 버전에 따라 액티비티 클래스명이 바뀐다.

### 4.3 iOS

- **`ios/` 디렉터리가 없다.** 먼저 iOS 프로젝트를 생성해야 한다 (§11).
- `Info.plist`에 커스텀 스킴 `kakao{NATIVE_APP_KEY}`(CFBundleURLSchemes)와 카카오톡 실행 조회 스킴(LSApplicationQueriesSchemes)을 등록한다.
- 실기기 검증 절차는 [아이폰 하네스](flutter-iphone-harness.md)를 따른다.

### 4.4 앱 설정값

| 값 | 주입 방법 | 비밀인가 |
|---|---|---|
| `KAKAO_NATIVE_APP_KEY` | `--dart-define` (빌드 시 주입) | 아니오 — 앱에 들어가는 게 정상 |
| `API_BASE_URL` | `--dart-define` | 아니오 |
| `client_secret` | **주입하지 않는다** | 예 — 서버 전용 |

`--dart-define-from-file`로 로컬 설정 파일을 쓰는 경우 그 파일은 `.gitignore`에 넣는다.

---

## 5. API 계약 (서버와 공유)

> **백엔드 문서 §7과 동일해야 한다.** 한쪽을 고치면 반드시 다른 쪽도 고친다.
> 모든 필드는 **camelCase**다. 기본 URL은 `API_BASE_URL`(예: `https://auth.jsangho.cloud`).

### 5.1 `POST /auth/mobile/kakao` — 로그인

요청
```json
{
  "code": "카카오 인가 코드",
  "redirectUri": "kakao{NATIVE_APP_KEY}://oauth",
  "deviceId": "앱 설치 단위 UUID",
  "deviceName": "iPhone 15",
  "os": "ios",
  "appVersion": "1.0.0+1"
}
```

응답 `200`
```json
{
  "token": "<access JWT>",
  "refreshToken": "<불투명 문자열>",
  "expiresIn": 900,
  "user": { "userId": 1, "nickname": "홍길동", "email": null, "role": "user" }
}
```

⚠️ `user.email`은 **null일 수 있다.** 카카오 이메일은 선택 동의 항목이다. 이메일을 화면 필수 요소로 만들지 않는다.

| 상태 | 앱의 처리 |
|---|---|
| 400 | 요청 조립 버그. 사용자에게 "로그인에 실패했습니다" 표시 후 로그인 화면 유지 |
| 401 | 인가 코드 만료/무효 → 로그인 재시도 안내 |
| 502 / 504 | "잠시 후 다시 시도해 주세요" — 자동 재시도는 1회까지만 |

### 5.2 `POST /auth/mobile/refresh` — 토큰 재발급

요청 `{ "refreshToken": "..." }` → 응답 `{ "token": "...", "refreshToken": "...", "expiresIn": 900 }`

- 응답의 **새 refresh token으로 즉시 교체 저장**한다(회전). 구 토큰을 다시 쓰면 서버가 탈취로 판단해 **모바일 세션 전체를 폐기**한다.
- 401이면 저장된 토큰을 **삭제하고 로그인 화면으로 복귀**한다. 재시도 금지.

### 5.3 `POST /auth/mobile/logout` · `/auth/mobile/logout-all`

`Authorization: Bearer <access JWT>` 필요. `logout`은 body `{ "refreshToken": "..." }`.
성공·실패와 무관하게 **앱의 로컬 토큰은 삭제**한다(서버가 죽어도 로그아웃은 되어야 한다).

### 5.4 `GET /auth/mobile/sessions` — 기기 목록

```json
{ "sessions": [
  { "jti": "…", "deviceId": "…", "deviceName": "iPhone 15", "os": "ios",
    "appVersion": "1.0.0+1", "issuedAt": 1785000000, "current": true }
] }
```

---

## 6. 클라이언트 동작 규칙

### 6.1 인가 코드 획득

- 카카오톡이 설치돼 있으면 **카카오톡 경유**, 아니면 **웹 브라우저(Custom Tabs / SFSafariViewController)** 로 폴백한다.
- 폴백 조건 판정과 실제 API 이름(`isKakaoTalkInstalled` · `AuthCodeClient` 계열)은 **설치한 SDK 버전의 공식 문서로 확인**한다. 이 문서의 이름을 그대로 믿지 않는다.
- 사용자가 로그인을 취소한 경우(에러가 아님)와 실패를 구분해 처리한다 — 취소 시 에러 메시지를 띄우지 않는다.
- `redirectUri`는 요청과 서버 교환에서 **완전히 동일한 문자열**이어야 한다. 카카오 콘솔 등록값과도 일치해야 한다.

### 6.2 `device_id`

- 최초 실행 시 UUID를 생성해 `flutter_secure_storage`에 저장하고, 이후 재사용한다.
- 광고 식별자(IDFA/AAID)나 하드웨어 시리얼을 쓰지 않는다 — 스토어 정책·프라이버시 문제가 따라온다.
- 앱 재설치로 값이 바뀌는 것은 **정상**이다. 서버가 세션 상한(기기 5개)으로 정리한다.

### 6.3 401 인터셉터 (single-flight)

1. 요청이 401을 받는다.
2. 이미 리프레시가 진행 중이면 **그 Future에 합류**한다. 아니면 새로 시작한다.
3. 리프레시 성공 → 새 access token으로 **원 요청을 1회 재시도**.
4. 리프레시 실패(401) → 저장 토큰 삭제 → 대기 중인 모든 요청을 실패 처리 → 로그인 화면으로 복귀.
5. **리프레시 요청 자체는 인터셉터를 타지 않는다** (무한 루프 방지).
6. 재시도는 요청당 **최대 1회**. 두 번째 401은 그대로 올린다.

### 6.4 앱 시작 시 복원

- 저장된 refresh token이 있으면 **리프레시를 먼저 시도**하고, 성공 시 로그인 상태로 진입한다.
- 실패하면 조용히 로그아웃 상태로 두고, 오류 팝업을 띄우지 않는다(만료는 정상 상황이다).
- 이 판정이 끝나기 전에 인증이 필요한 화면을 그리지 않는다.

---

## 7. 작업 단위

각 단위는 독립 커밋. `[ ]` → `[x]`로 갱신하며 진행한다.
⚠️ F4부터는 **백엔드 T1~T4가 끝난 뒤** 착수한다.

> 구현은 전부 `lib/auth.dart` 한 파일에 있다(사용자 지시). 섹션 주석으로 구역을 나눴다.

### F1. 의존성·플랫폼 설정
- [x] §4.1 패키지 추가 + `uuid` (`flutter pub add`)
- [x] `applicationId` = **`cloud.jsangho.jsh_flutter`** (2026-08-03 확정). `namespace`·`MainActivity` 패키지와 모두 일치한다. ⚠️ 카카오 콘솔에 등록할 패키지명이 이 값이다 — 런타임 패키지명은 `namespace`가 아니라 `applicationId`다
- [x] Android 커스텀 스킴 — `AuthCodeHandlerActivity`에 intent-filter 추가. 스킴 값은 `build.gradle.kts`의 `manifestPlaceholders["kakaoNativeAppKey"]`로 주입하며, `-PKAKAO_NATIVE_APP_KEY` 또는 `android/local.properties`의 `kakao.nativeAppKey`에서 읽는다
  - **검증함**: `flutter build apk --debug` 성공, 병합된 매니페스트에 intent-filter가 들어갔고 `-PKAKAO_NATIVE_APP_KEY=abc123testkey`로 돌리면 `android:scheme="kakaoabc123testkey"`로 치환된다. 키가 비면 `android:scheme="kakao"`가 되어 **리다이렉트가 돌아오지 않는다**
- [x] `<queries>` — SDK(`kakao_flutter_sdk_common`)가 자체 매니페스트로 카카오톡 패키지 가시성을 이미 제공한다. 앱에서 중복 선언하지 않았다 (병합 결과에 `com.kakao.talk`·`.alpha`·`.sandbox` 확인)
- [ ] iOS — **미착수.** `ios/` 디렉터리가 여전히 없다 (§11)
- [x] `KakaoSdk.init`을 `main()`에서 1회 수행 (`--dart-define=KAKAO_NATIVE_APP_KEY=...`)

### F2. 보안 저장소
- [x] `AuthStorage`(인터페이스) + `SecureAuthStorage`(flutter_secure_storage 구현) — `readRefreshToken` / `writeRefreshToken` / `clear`
- [x] `device_id` 생성·조회 (없으면 UUID v4 생성해 저장)
- [x] access token은 `AuthApiClient._accessToken`에 **메모리로만** 유지 (D-2)

### F3. 기기 메타 수집
- [x] `DeviceMetaCollector` — `deviceName` · `os` · `appVersion`
- [x] Android/iOS 분기를 수집기 안에서 흡수 (호출부는 분기하지 않는다)

### F4. 인증 API 클라이언트
- [x] `Dio` 구성 (baseUrl · connect 5s / receive 10s · JSON)
- [x] §5의 5개 엔드포인트 호출부 전부 (`kakao` · `refresh` · `logout` · `logout-all` · `sessions`)
- [x] 서버 에러 → 한국어 문구 매핑. 원문은 `AuthFailure.debugDetail`에만 담고 화면에 내보내지 않는다

### F5. 인터셉터
- [x] `Authorization: Bearer` 자동 부착
- [x] §6.3 single-flight 401 처리
- [x] 리프레시 경로 자기 참조 차단 + **로그인 경로도 제외** (로그인의 401은 인가 코드 무효라 리프레시로 못 푼다)
- [x] 리프레시 성공 시 새 refresh token 즉시 저장
- ⚠️ `validateStatus`를 완화하면 4xx가 정상 응답으로 넘어와 `onError`가 안 불리고 인터셉터가 통째로 죽는다. 기본값을 유지해야 한다 (실제로 한 번 밟은 함정)

### F6. 로그인 UI / 세션 상태
- [x] `AuthScreen` + 카카오 로그인 버튼 (가이드 기본형: `#FEE500` 배경 / 85% 불투명 검정 라벨)
- [x] 로그인 취소는 조용히 원복, 실패·네트워크 오류는 각각 다른 문구
- [x] 로그아웃 · 모든 기기 로그아웃 진입점 — `AccountScreen`. 로그아웃 후에는 `pushAndRemoveUntil`로 스택을 비워, 뒤로 가기로 인증된 화면에 돌아갈 수 없게 한다
- [x] 기기 목록 화면 (`GET /auth/mobile/sessions`) — 현재 기기를 초록색 "이 기기"로 표시
- [x] 진입점: `MainMenuScreen`의 "계정" 카드
- [x] 앱 시작 시 세션 복원 (§6.4). 복원 판정이 끝나기 전에는 다음 화면을 그리지 않는다

### F7. 테스트 (`flutter/test/auth_test.dart`) — 14개, 전체 18개 통과
- [x] 리프레시 성공 → 원 요청 재시도 1회
- [x] **동시 401 5건 → 리프레시 호출 정확히 1회** (D-5 회귀 방지)
- [x] 리프레시 401 → 저장소 비워지고 세션 만료 콜백 발화
- [x] 재시도 후 다시 401 → 무한 루프 없이 종료 (요청 2회·리프레시 1회로 고정)
- [x] 회전된 refresh token이 저장소에 반영되는지
- [x] `user.email`이 null인 응답 파싱 성공
- [x] 네트워크 오류로 리프레시 실패 시 저장 토큰을 **지우지 않음** (만료와 장애를 구분)
- [x] 로그아웃은 서버 호출이 실패해도 로컬 토큰을 지움
- [x] 서버 원문이 사용자 문구로 새어 나가지 않음
- [x] 복원 실패 시 컨트롤러가 로그아웃으로 확정되고 `restored`가 완료됨 (인트로 무한 대기 방지)
- [x] 모든 기기 로그아웃도 서버 실패와 무관하게 로컬 토큰을 지움
- [x] 기기 목록 파싱 + 현재 기기 구분, 빈 목록 처리
- [x] 저장소·HTTP는 fake로 대체 (실제 카카오·서버 호출 없이 돈다)

---

## 8. 실기기 검증 시나리오

| # | 시나리오 | 기대 |
|---|---|---|
| 1 | 카카오톡 설치 기기에서 로그인 | 카카오톡 전환 → 동의 → 앱 복귀 → 로그인 완료 |
| 2 | 카카오톡 미설치 기기에서 로그인 | 브라우저 폴백으로 동일 결과 |
| 3 | 동의 화면에서 취소 | 에러 팝업 없이 로그인 화면 유지 |
| 4 | 이메일 미동의 계정 | 로그인 성공, 이메일 자리 공란 |
| 5 | 앱 종료 후 재실행 | 재로그인 없이 세션 복원 |
| 6 | 비행기 모드에서 앱 실행 | 오류 팝업 없이 로그아웃/재시도 유도 |
| 7 | access token 만료 후 API 호출 | 자동 리프레시 후 성공 (사용자 체감 없음) |
| 8 | 서버에서 해당 세션 폐기 후 API 호출 | 로그인 화면으로 복귀 |
| 9 | 6번째 기기로 로그인 | 성공하고, 가장 오래된 기기가 목록에서 사라짐 |
| 10 | 앱 삭제 후 재설치 | 재로그인 필요(secure storage 소거) |

기기 연결·실행 절차는 [안드로이드 하네스](flutter-android-harness.md) / [아이폰 하네스](flutter-iphone-harness.md)를 따른다.

### 실측 결과 (2026-08-03, SM-A356N / Android 16, 무선 디버깅)

| # | 결과 |
|---|---|
| 1 | ✅ 카카오톡 전환(`TalkAuthCodeActivity`) → 동의 → 앱 복귀 → 로그인 완료 |
| 7 | ✅ 계정 화면 진입 시 `GET /auth/mobile/sessions` 200, 기기 목록 표시 |
| 2·3·4·5·6·8·9·10 | ⬜ 미확인 |

⚠️ **`flutter/_docs/flutter-android-harness.md` §7의 "WSL 경로에서 Gradle 빌드 실패" 서술은 낡았다.**
그 문서는 WSL에 Flutter·Android SDK가 없다는 전제로 쓰였으나, 현재는 둘 다 설치돼 있고
(`/home/ho/flutter`, `/home/ho/Android/Sdk`) WSL 경로에서 `flutter build apk --debug`가
정상 통과한다. 기기는 무선 디버깅(`adb connect`)으로 붙였다. 해당 문서를 갱신해야 한다.

---

## 9. 검증 기준 (Definition of Done)

- [ ] §7의 모든 체크박스 완료
- [ ] F7 테스트 전부 통과
- [ ] §8 시나리오 1~10을 실기기에서 확인
- [ ] 릴리스 APK/IPA 문자열 덤프에 `client_secret` 부재 (`strings`/`grep`으로 확인)
- [ ] 앱 로그 어디에도 토큰·인가 코드가 출력되지 않음
- [ ] `SharedPreferences`·평문 파일에 refresh token 부재
- [ ] 하드코딩된 시크릿 0건

---

## 10. 하네스 게이트 (코드 작성 후 필수)

```bash
cd flutter
dart analyze          # avoid_print 위반은 에러다
dart format .
flutter test
```

에러는 무시하지 않고 수정한 뒤 완료 보고한다.
⚠️ WSL 경로에서 Android 빌드가 실패하는 문제는 [안드로이드 하네스](flutter-android-harness.md) §7에 정리돼 있다 — 빌드가 깨지면 그 문서를 먼저 본다.

---

## 11. 미해결 질문 (구현 중 발견 시 여기에 기록하고 중단)

- [ ] **iOS 지원 여부** — `ios/` 디렉터리가 여전히 없다. 포함한다면 `flutter create --platforms=ios .` 실행 승인이 필요하다. 현재 구현은 iOS 코드 경로(`DeviceMetaCollector`)까지는 있으나 프로젝트가 없어 빌드 자체가 불가능하다.
- [x] **`applicationId`** — `cloud.jsangho.jsh_flutter`로 확정 (2026-08-03). `namespace`·`MainActivity` 패키지와 일치한다.
- [x] **`lib/` 구조** — 사용자 지시대로 `lib/auth.dart` 단일 파일에 모았다. 파일이 600줄을 넘어 더 커지면 그때 쪼갠다.
- [x] **상태 관리** — 라이브러리를 새로 넣지 않고 `ChangeNotifier` + `InheritedNotifier`(`AuthScope`)로 처리했다.
- [ ] **API 호스트** — `AuthConfig.apiBaseUrl` 기본값을 `https://auth.jsangho.cloud`로 뒀다. **추정값이다.** auth 컨테이너는 포트 미노출이고 cloudflared 라우팅에 달려 있어, 실기기 검증 전에 실제 노출 호스트를 확인해야 한다(백엔드 문서 §13).
- [ ] **카카오 콘솔 앱 구성** — 웹과 모바일을 한 앱으로 운영할지. 분리하면 회원번호가 달라져 웹/앱 계정이 서로 다른 유저가 된다(백엔드 문서 §13과 동일 질문).
- [ ] **푸시 토큰** — 세션 HASH의 `push_token`은 FCM/APNs 도입이 전제다. 이번 범위에 포함할지.
- [ ] **웹 타깃** — `web/`이 존재한다. Flutter Web에서도 카카오 로그인을 지원할지(지원 시 secure storage 전략이 통째로 달라진다).

---

## 12. 작업 로그

| 일시 | 작업 단위 | 내용 | 결과 |
|---|---|---|---|
| 2026-08-03 | — | 원본 지시서에서 Flutter 클라이언트 계약을 분리해 작성, 현재 앱 상태(인증 코드 전무·iOS 프로젝트 부재) 실측 | 문서만 작성, 코드 변경 없음 |
| 2026-08-03 | F1~F7 | `lib/auth.dart` 신설 — 설정·모델·보안 저장소·기기 메타·Dio 클라이언트(single-flight 401)·세션 상태·로그인 화면. Android 커스텀 스킴 배선 | `dart analyze` 무결점, `flutter test` 15건 통과, Gradle DSL 파싱 확인 |
| 2026-08-03 | 화면 흐름 | 인트로(4초) → 세션 있으면 `MainMenuScreen`, 없으면 `AuthScreen` → 로그인 성공 시 `MainMenuScreen`. 세션 복원은 인트로 재생 중 백그라운드로 진행 | `main.dart`·`intro_video_screen.dart` 수정 |
| 2026-08-03 | 테스트 보수 | `widget_test.dart`가 인트로 직후 `ClockHome`을 기대하고 있었으나, 이미 `MainMenuScreen`이 중간에 들어와 있어 깨진 상태였다. 메뉴를 거쳐 시계로 들어가도록 수정 | 기존 4건 복구 |
| 2026-08-03 | F4·F6 잔여 | `AccountScreen` 신설 — 계정 정보·기기 목록·로그아웃/모든 기기 로그아웃. `MainMenuScreen`에 "계정" 진입점 추가 | `dart analyze` 무결점, `flutter test` 18건 통과 |
| 2026-08-03 | F1 | `applicationId`를 `com.example.jsh_flutter` → `cloud.jsangho.jsh_flutter`로 확정 | `namespace`·`MainActivity` 패키지와 3중 일치. APK 재빌드로 확인 |

### 실기기 검증 전에 반드시 채워야 하는 값

```bash
# android/local.properties (git 제외됨)
kakao.nativeAppKey=<네이티브 앱 키>

flutter run \
  --dart-define=KAKAO_NATIVE_APP_KEY=<같은 값> \
  --dart-define=API_BASE_URL=https://auth.jsangho.cloud
```

`local.properties`의 값(매니페스트 스킴)과 `--dart-define` 값(Dart 쪽 `redirectUri`)이
**서로 달라도 빌드는 성공한다.** 그러면 리다이렉트가 앱으로 돌아오지 않고 로그인이 멈춘다.
서버 `KAKAO_MOBILE_REDIRECT_URI`·카카오 콘솔 등록값까지 네 곳이 모두 같아야 한다.
