# Flutter 아이폰 실기기 하네스

> 아이폰 **실제 기기**에 이 저장소의 Flutter 앱을 올려 실행·디버깅하기 위한 절차.
> **macOS + Xcode 가 반드시 필요하다** (Windows·Linux에서는 iOS 빌드 자체가 불가능).
> 안드로이드 쪽은 [`flutter-android-harness.md`](flutter-android-harness.md), 코딩 규칙은 [`flutter/CLAUDE.md`](../CLAUDE.md).

**검증 기준일**: 2026-07-31 (아래 버전은 이 시점의 stable 기준)

---

## 0. 먼저 확인 — 이 저장소에는 `ios/` 가 없다

현재 `flutter/` 에는 `android` · `web` · `windows` 만 있고 **`ios/` 디렉터리가 존재하지 않는다.**
아이폰에 올리려면 macOS에서 iOS 플랫폼 폴더부터 생성해야 한다.

```bash
cd flutter
flutter create --platforms=ios --org com.<본인도메인역순> .
```

- `--org` 값이 Bundle Identifier 앞부분이 된다 → `com.example` 을 그대로 쓰지 않는다.
  (안드로이드 쪽 `applicationId` 가 `com.example.jsh_flutter` 로 남아 있는 문제를 반복하지 않기 위함)
- 생성 후 `ios/` 는 커밋 대상이다. `ios/Pods/` · `ios/.symlinks/` 는 `.gitignore` 로 제외된다.

---

## 1. 대상 버전 (Toolchain Matrix)

| 항목 | 버전 | 비고 |
|------|------|------|
| Flutter | **3.44.x stable** (최신 패치 3.44.7) | `pubspec.yaml` 의 `sdk: ^3.12.2` 와 같은 라인 |
| Dart | **3.12.x** | — |
| Xcode | **26.5 stable** (26.6 RC 공개) | 공식 권장은 "App Store 최신 버전" |
| macOS | **Tahoe 26.x** | Xcode 26.6 은 macOS 26.2 이상 요구 |
| iOS 지원 범위 | **iOS 13 ~ 26** (CI 검증은 18) | iOS 12 이하 미지원 |
| 개발자 모드(Developer Mode) | **iOS 16 이상 필수** | iOS 15 이하에는 해당 설정이 없음 |
| 네이티브 의존성 관리 | **Swift Package Manager (기본)** | Flutter **3.44부터 SwiftPM 이 기본값** |
| CocoaPods | 유지보수 모드 (fallback) | SwiftPM 미지원 플러그인이 있을 때만 |
| Mac 하드웨어 | Apple Silicon · Intel 모두 가능 | — |

> **CocoaPods 관련 서술은 대부분 폐기됐다.** Flutter 3.44부터 iOS·macOS 네이티브 의존성은
> SwiftPM이 기본으로 처리하고, `flutter run` 이 SwiftPM 통합을 자동으로 추가한다.
> CocoaPods 레지스트리는 **2026-12-02부로 읽기 전용**이 된다. §3 참조.

---

## 2. Mac 준비 (1회)

```bash
# 1) Xcode 설치 후 커맨드라인 도구 경로 지정 + 최초 실행 세팅
sudo sh -c 'xcode-select -s /Applications/Xcode.app/Contents/Developer && xcodebuild -runFirstLaunch'

# 2) 라이선스 동의
sudo xcodebuild -license

# 3) iOS 플랫폼 SDK 내려받기 (Xcode 첫 설치 시 필수)
xcodebuild -downloadPlatform iOS

# 4) 진단 — [✓] Xcode 항목이 통과해야 한다
flutter doctor -v
```

`flutter doctor` 가 `Xcode installation is incomplete` 나 `CocoaPods not installed` 를 띄우면
그 메시지에 적힌 명령만 그대로 따른다. **미리 `sudo gem install` 을 하지 않는다** (§3).

---

## 3. CocoaPods — 이제 기본이 아니다

옛 가이드의 아래 두 줄은 **더 이상 실행하지 않는다.**

```bash
# ❌ 폐기: 시스템 Ruby 에 sudo 로 gem 설치 → 권한·버전 충돌의 주원인
sudo gem install cocoapods
# ❌ 폐기: Apple Silicon ffi 워크어라운드. 현재 Ruby·ffi 에서는 불필요
sudo gem uninstall ffi && sudo gem install ffi -- --enable-libffi-alloc
```

**현재 기준**

| 상황 | 조치 |
|------|------|
| 순수 Flutter 앱 · 플러그인이 SwiftPM 지원 | **아무것도 설치하지 않는다.** SwiftPM 이 기본으로 동작 |
| SwiftPM 미지원 플러그인이 있음 | `brew install cocoapods` (Homebrew 설치본) |
| 기존 프로젝트를 SwiftPM 으로 이관 | `flutter upgrade` 후 `flutter run` 하면 통합이 자동 추가됨 |

> `sudo gem` 대신 Homebrew 를 쓰는 이유: macOS 시스템 Ruby 는 SIP 보호를 받고 버전이 고정돼 있어
> gem 설치가 깨지기 쉽다. Homebrew 설치본은 독립 바이너리라 이 문제가 없다.

---

## 4. 아이폰 준비

1. **케이블 연결** — 폰의 데이터 케이블로 아이폰과 Mac 을 직결한다.
   충전 전용 케이블·저가 허브는 인식되지 않는다.
2. 아이폰에 뜨는 **[이 컴퓨터를 신뢰하시겠습니까?] → [신뢰]**, 이어서 기기 암호 입력.
3. **개발자 모드 활성화 (iOS 16 이상 필수)**
   `설정 → 개인정보 보호 및 보안 → 개발자 모드` → ON → **재부팅** → 부팅 후 `켜기` 탭 → 암호 입력.
   - 이 메뉴는 **Mac 에 한 번 연결한 뒤에야 나타난다.** 안 보이면 연결 상태에서 다시 확인한다.
4. **개발자 인증서 신뢰** (첫 설치 후 "신뢰할 수 없는 개발자" 로 뜰 때)
   `설정 → 일반 → VPN 및 기기 관리 → [개발자 앱] → 본인 Apple ID → 신뢰`

---

## 5. 서명 설정 (Xcode, 최초 1회)

```bash
open ios/Runner.xcworkspace     # 없으면 ios/Runner.xcodeproj
```

| 순서 | 위치 | 할 일 |
|------|------|-------|
| ① | 좌측 네비게이터 | **Runner** 프로젝트 선택 |
| ② | TARGETS | **Runner** 선택 |
| ③ | 탭 | **Signing & Capabilities** |
| ④ | Bundle Identifier | 전 세계에서 유일한 값으로 변경 (예: `com.jsangho.jshflutter`) |
| ⑤ | Automatically manage signing | 체크 |
| ⑥ | Team | Apple ID 로그인 후 개인 팀(Personal Team) 선택 |

**무료 Apple ID(Personal Team) 제약** — 유료 개발자 프로그램($99/년) 없이도 실기기 실행은 되지만:

| 제약 | 내용 |
|------|------|
| 인증서 수명 | **7일** — 만료되면 앱이 실행되지 않아 재설치 필요 |
| 앱 개수 | 기기당 동시에 3개까지 |
| 사용 불가 기능 | 푸시 알림 · iCloud · Sign in with Apple 등 일부 Capability |
| 배포 | TestFlight · App Store 업로드 불가 |

---

## 6. 실행 하네스

```bash
flutter devices                        # 아이폰이 목록에 뜨는지 확인
flutter run -d <device-id>             # debug 실행 (hot reload 가능)
#   r = hot reload,  R = hot restart,  q = 종료
flutter run -d <device-id> --release   # 릴리스 성능 측정 (hot reload 불가)
flutter attach -d <device-id>          # 이미 떠 있는 앱에 디버거만 연결
```

Android Studio · VS Code 에서는 기기 드롭다운에서 아이폰을 고르고 ▶ 실행한다.

### 무선(Wi-Fi) 실행

케이블로 한 번 페어링한 뒤에는 무선으로 실행할 수 있다.
Xcode → `Window → Devices and Simulators` → 기기 선택 → **`Connect via network`** 체크.
Mac 과 아이폰이 **같은 네트워크**에 있어야 하며, 첫 빌드 전송은 유선보다 느리다.

---

## 7. 폐기된 안내 — "iOS 14 이상은 Release 스킴으로 바꿔라"

`Product → Scheme → Edit Scheme → Build Configuration → Release` 로 바꾸라는 옛 안내는
**iOS 14 초기 + 구버전 Flutter 의 디버거 연결 버그에 대한 임시 회피책**이었다. 현재는 해당 없다.

**Release 스킴으로 바꾸면 hot reload · hot restart · 디버거 · DevTools 를 전부 잃는다.**
디버그 실행이 안 될 때는 스킴을 건드리지 말고 아래 실제 원인을 확인한다.

| 실제 원인 | 조치 |
|-----------|------|
| 개발자 모드 꺼짐 (iOS 16+) | §4-3 |
| 개발자 인증서 미신뢰 | §4-4 |
| 무료 계정 7일 인증서 만료 | 재빌드·재설치 |
| Bundle ID 중복 | §5-④ 에서 고유값으로 변경 |

---

## 8. 트러블슈팅

| 증상 | 원인 / 조치 |
|------|-------------|
| `flutter devices` 에 아이폰이 없음 | 충전 전용 케이블 · [신뢰] 미승인 · Xcode 미실행. 케이블 교체 후 Xcode 를 한 번 실행 |
| `개발자 모드` 메뉴가 안 보임 | Mac 에 연결된 적 없음 → 연결 후 재확인 (iOS 15 이하엔 메뉴 자체가 없음) |
| `Untrusted Developer` | `설정 → 일반 → VPN 및 기기 관리` 에서 인증서 신뢰 (§4-4) |
| `No profiles for 'com.example.x' were found` | Bundle ID 가 템플릿 기본값이거나 중복 → 고유값으로 변경 |
| `Signing for "Runner" requires a development team` | Signing & Capabilities 에서 Team 미선택 (§5-⑥) |
| 7일마다 앱이 실행 안 됨 | 무료 계정 인증서 만료 — 정상 동작. 재설치하거나 유료 프로그램 가입 |
| `CocoaPods not installed` | 해당 플러그인이 SwiftPM 미지원인 경우에만 `brew install cocoapods` |
| `Xcode installation is incomplete` | §2 의 `-runFirstLaunch` · `-downloadPlatform iOS` 실행 |
| 빌드는 되는데 기기에서 즉시 종료 | 개발자 모드 OFF 또는 인증서 만료가 대부분 |

---

## 9. 이 저장소 환경 주의 (중요)

이 저장소의 개발 PC 는 **Windows + WSL2** 다 (Flutter SDK 도 `C:\Users\hi\flutter`).
**이 머신에서는 iOS 빌드가 불가능하다** — Xcode 가 macOS 전용이며 우회 수단은 없다.

| 선택지 | 비고 |
|--------|------|
| 별도 Mac 에서 작업 | 저장소를 clone 하고 §0 부터 진행 |
| macOS CI 러너 (GitHub Actions `macos-latest` 등) | 빌드·서명 자동화는 되지만 **실기기 hot reload 는 불가** |
| iOS 시뮬레이터 | 이것도 macOS 필요 |

따라서 이 문서는 **Mac 환경이 확보된 뒤** 실행하는 절차서다.
Windows 쪽에서 검증 가능한 범위는 `dart analyze` · `dart format` · Android · Web 뿐이다.

---

## 10. 하네스 게이트

코드 수정 후 반드시 실행한다 ([`flutter/CLAUDE.md`](../CLAUDE.md)).

```bash
dart analyze          # 린트 — avoid_print 위반은 에러
dart format .         # 포매팅
```

---

## 11. 참고 링크

| 문서 | URL |
|------|-----|
| Flutter iOS 설정 (공식) | https://docs.flutter.dev/platform-integration/ios/setup |
| Flutter 지원 플랫폼 (iOS 13~26) | https://docs.flutter.dev/reference/supported-platforms |
| Swift Package Manager (앱 개발자용) | https://docs.flutter.dev/packages-and-plugins/swift-package-manager/for-app-developers |
| CocoaPods 작별 공지 (Flutter 블로그) | https://flutter.dev/blog/saying-goodbye-to-cocoapods-swift-package-manager-is-soon-the-default-in-flutter |
| iOS 배포 (App Store) | https://docs.flutter.dev/deployment/ios |
| Xcode 릴리스 노트 | https://developer.apple.com/documentation/xcode-release-notes |
