# Flutter 안드로이드 실기기 하네스

> 안드로이드 **실제 기기**에 이 저장소의 Flutter 앱을 올려 실행·디버깅하기 위한 절차.
> 연결 방식은 두 가지다 — **USB 케이블**(폰의 데이터 케이블을 개발 PC에 직결) · **Wi-Fi 무선 디버깅**.
> 코딩 규칙은 [`flutter/CLAUDE.md`](../CLAUDE.md), 상위 규칙은 [루트 CLAUDE.md](../../CLAUDE.md).

**검증 기준일**: 2026-07-31 (아래 버전은 이 시점의 stable 기준)

---

## 1. 대상 버전 (Toolchain Matrix)

| 항목 | 버전 | 근거 |
|------|------|------|
| Flutter | **3.44.x stable** (2026-05-18 릴리스 / 이 PC 설치본 **3.44.2**) | `pubspec.yaml` 의 `sdk: ^3.12.2` 가 Dart 3.12 = Flutter 3.44 라인 |
| Dart | **3.12.x** | 위와 동일 |
| Android Studio | **2025.3.x (Otter 계열) 이상** | Flutter/Dart 플러그인 최신판이 요구 |
| JDK | **17** | `android/app/build.gradle.kts` 의 `JavaVersion.VERSION_17` · Kotlin `JVM_17` |
| Gradle | **9.1.0** | `android/gradle/wrapper/gradle-wrapper.properties` |
| Android Gradle Plugin (AGP) | **9.0.1** | `android/settings.gradle.kts` |
| Kotlin | **2.3.20** | `android/settings.gradle.kts` |
| compileSdk / targetSdk | **36** (Android 16) | `flutter.compileSdkVersion` · `flutter.targetSdkVersion` 기본값 |
| minSdk | **24** (Android 7.0) | `flutter.minSdkVersion` 기본값 |
| 무선 디버깅 최소 요건 | **Android 11 / API 30 이상** | `adb pair` 지원 시작 버전 |

> **API 16(Android 4.1) 기준 서술은 폐기됐다.** Flutter 3.44 의 최소 지원은 **API 24**이며,
> 그보다 낮은 기기는 빌드 자체가 되지 않는다.

**Google Play 정책**: 2026-08-31부터 신규 앱·업데이트는 **targetSdk 36(Android 16) 이상**이어야
제출된다(기존 앱 유지는 35 이상). 이 저장소는 Flutter 기본값을 그대로 쓰므로 이미 충족한다.

---

## 2. 사전 준비 (PC 쪽, 1회)

1. **Android Studio 설치** 후 SDK Manager에서 다음을 설치한다.
   `Tools → SDK Manager → Languages & Frameworks → Android SDK`
   - **SDK Platforms** 탭 → `Android 16.0 ("Baklava"/API 36)`
   - **SDK Tools** 탭 → `Android SDK Platform-Tools`(adb 포함) · `Android SDK Build-Tools` · `Android SDK Command-line Tools`
   - **SDK Tools** 탭 → `Google USB Driver` — **Windows에서 USB 연결할 때만 필요**. macOS·Linux에는 항목 자체가 없다.
2. **Flutter · Dart 플러그인** 설치 (`Settings → Plugins`).
3. **라이선스 동의 + 진단**:
   ```bash
   flutter doctor --android-licenses   # 전부 y
   flutter doctor -v                   # Android toolchain 항목이 ✓ 여야 한다
   ```
4. `adb` 가 PATH에 없으면 `<SDK>/platform-tools` 를 PATH에 추가한다.
   - Windows 기본 경로: `%LOCALAPPDATA%\Android\Sdk\platform-tools`

---

## 3. 개발자 옵션 활성화 (USB·무선 공통)

Android 11 이후 경로가 통일됐다. **버전별 분기는 더 이상 필요 없다.**

| 단계 | 경로 (AOSP / Pixel, Android 11~16) |
|------|------------------------------------|
| ① 개발자 옵션 해제 | `설정 → 휴대전화 정보 → 빌드 번호` **7회 탭** → 화면 잠금 인증 |
| ② 개발자 옵션 진입 | `설정 → 시스템 → 개발자 옵션` |
| ③ USB 디버깅 | 개발자 옵션 → **USB 디버깅** ON |
| ④ 무선 디버깅 | 개발자 옵션 → **무선 디버깅** ON (Android 11+) |

**제조사 UI 차이** (경로만 다르고 항목명은 동일):

| 제조사 | 빌드 번호 위치 | 개발자 옵션 위치 |
|--------|----------------|------------------|
| 삼성 One UI | `설정 → 휴대전화 정보 → 소프트웨어 정보 → 빌드번호` | `설정` 최하단 |
| 샤오미 HyperOS/MIUI | `설정 → 내 기기 → 전체 사양 → MIUI 버전` | `설정 → 추가 설정 → 개발자 옵션` |
| Pixel / AOSP | `설정 → 휴대전화 정보 → 빌드 번호` | `설정 → 시스템 → 개발자 옵션` |

> Android 11부터 개발자 옵션 상위의 **[고급]** 하위 메뉴는 사라졌다.
> 옛 가이드의 `시스템 → 고급 → 개발자 옵션` 경로는 무시한다.

---

## 4. USB 케이블로 연결하기

여기서 **USB** 는 폰에 딸려온 **데이터 케이블로 폰과 개발 PC를 직접 연결**하는 것을 뜻한다.

### 4-1. 절차

1. **데이터 전송이 가능한 케이블**을 쓴다. 충전 전용 케이블은 전원만 통해서 `adb devices` 에 아무것도 안 잡힌다.
   → 의심되면 다른 케이블로 바꿔 본다. 이 원인이 실제로 가장 흔하다.
2. 폰 ↔ PC 를 케이블로 연결한다. 허브·독을 거치면 인식이 불안정하므로 **PC 본체 포트에 직결**한다.
3. 폰 알림에서 **USB 모드를 `파일 전송 / Android Auto`(MTP)** 로 바꾼다. `충전만` 상태에서는 디버깅이 붙지 않는 기기가 있다.
4. 폰에 뜨는 **`USB 디버깅을 허용하시겠습니까?`** RSA 지문 다이얼로그에서 **[이 컴퓨터에서 항상 허용]** 체크 후 허용.
5. (Windows만) 기기가 안 잡히면 `Google USB Driver` 설치 여부와 제조사 OEM 드라이버를 확인한다.
   (Linux는 `udev` 규칙이 필요하다 → `sudo apt install android-sdk-platform-tools-common`. macOS는 드라이버 불필요.)

### 4-2. 검증

```bash
adb devices -l          # <serial>  device  usb:... 로 나와야 한다
flutter devices         # 기기가 목록에 뜨는지 확인
flutter run -d <device-id>
```

Android Studio에서는 상단 **기기 선택 드롭다운**에 폰 모델명이 뜨면 정상이다. ▶ 실행.

---

## 5. Wi-Fi 무선 디버깅 (Android 11 / API 30 이상)

케이블 없이 붙는 **권장 방식**이다. PC와 폰이 **같은 네트워크**에 있어야 하고,
게스트 망·AP 격리(클라이언트 간 통신 차단)가 걸린 공유기에서는 실패한다.

### 5-1. CLI (권장)

1. 폰: `개발자 옵션 → 무선 디버깅` ON → **[페어링 코드로 기기 페어링]** 탭
   → 6자리 코드 · `IP:페어링포트` 가 화면에 표시된다.
2. PC (**페어링 포트**로 1회만):
   ```bash
   adb pair 192.168.0.10:37129     # 화면의 IP:페어링포트
   # Enter pairing code: 123456
   ```
3. 무선 디버깅 **메인 화면의 `IP:포트`**(페어링 포트와 다르다)로 접속:
   ```bash
   adb connect 192.168.0.10:41235
   adb devices -l                   # 192.168.0.10:41235  device
   flutter run -d 192.168.0.10:41235
   ```

> **포트가 두 개**인 것이 핵심이다. 페어링 포트는 페어링 전용이고, 실제 연결은 메인 화면 포트로 한다.
> 페어링은 기기당 1회면 되지만, **연결 포트는 무선 디버깅을 껐다 켜거나 재부팅하면 바뀐다** → `adb connect` 만 다시 한다.

### 5-2. Android Studio GUI

기기 드롭다운 → **`Pair Devices Using Wi-Fi`** → QR 코드 스캔(폰: 무선 디버깅 → *QR 코드로 기기 페어링*).
`adb pair` 를 대신해 준다.

### 5-3. 레거시 `adb tcpip` (Android 10 이하 전용)

```bash
adb tcpip 5555            # USB로 붙은 상태에서 실행
adb connect <폰IP>:5555   # 케이블 분리 후
```

인증 없이 5555 포트가 열리므로 **같은 망의 누구나 접속 가능**하다. Android 11+ 에서는 쓰지 않는다.

---

## 6. 실행 하네스 (기기 연결 후)

```bash
flutter devices                     # 연결 확인
flutter run -d <device-id>          # debug 실행 (hot reload 가능)
#   r  = hot reload,  R = hot restart,  q = 종료
flutter run -d <device-id> --release   # 릴리스 성능 측정용 (hot reload 불가)
flutter attach -d <device-id>       # 이미 떠 있는 앱에 디버거만 붙이기
```

**코드 수정 후 반드시 실행** (`flutter/CLAUDE.md` 게이트):

```bash
dart analyze          # 린트 — avoid_print 위반은 에러
dart format .         # 포매팅
```

---

## 7. 이 저장소 고유 사항

- **패키지명이 아직 템플릿 기본값이다** — `android/app/build.gradle.kts` 의
  `namespace` · `applicationId` 가 `com.example.jsh_flutter` 이고 TODO 주석이 남아 있다.
  개발·디버깅에는 문제없지만 **배포 전에는 반드시 고유 ID로 바꾼다**.
- **릴리스 서명이 debug 키다** — `buildTypes.release` 가 `signingConfigs.getByName("debug")` 를 쓴다.
  `flutter run --release` 로 실기기 확인은 되지만 스토어 업로드는 불가하다.
- **Gradle JDK 는 17로 맞춘다** — `Settings → Build Tools → Gradle → Gradle JDK` 에서
  Android Studio 번들 JBR 17을 선택한다. 다른 JDK를 쓰면 Kotlin `jvmTarget` 과 어긋나 빌드가 깨진다.

### WSL2 환경 주의 — **Android 빌드는 WSL 경로에서 실패한다** (실측 확인)

이 저장소는 WSL2(`/home/ho/...`)에 있지만 **Flutter SDK 는 Windows 쪽**(`C:\Users\hi\flutter`)에 설치돼 있다.
WSL 셸에서 `/mnt/c/.../flutter` 를 직접 호출하면 CRLF 때문에 스크립트가 깨지므로
`flutter` 는 Windows 에서 실행해야 하는데, **그것만으로는 부족하다.**

Windows 의 `flutter` 로 `\\wsl.localhost\...` 경로의 이 프로젝트를 빌드하면
`flutter pub get` 은 통과하지만 **Gradle 단계에서 반드시 실패한다** (2026-07-31 실측):

```
Running Gradle task 'assembleDebug'...
FAILURE: Build failed with an exception.
> Could not create service of type BuildLifecycleController ...
   > Could not create service of type FileHasher using BuildSessionServices.createFileHasher().
      > java.io.IOException: 잘못된 기능입니다        # = Incorrect function
BUILD FAILED in 4s
```

Gradle 의 파일 해셔가 SMB(네트워크 드라이브) 위에서 동작하지 못해서 생기는 문제다.
같은 소스를 **Windows 로컬 경로로 복사하면 71.7초 만에 정상 빌드된다** — 원인은 경로 하나뿐이다.

| 실행 경로 | `flutter pub get` | `flutter build apk --debug` |
|-----------|-------------------|------------------------------|
| `\\wsl.localhost\Ubuntu\home\ho\...\flutter` | ✓ | ✗ `FileHasher` IOException |
| `C:\...\<로컬 경로>` | ✓ | ✓ 71.7s |

**따라서 실기기 실행을 하려면 둘 중 하나를 택해야 한다.**

| 선택지 | 내용 |
|--------|------|
| **A. Windows 로컬 경로에 체크아웃** (권장) | 저장소를 `C:\dev\...` 등에 clone 하고 Windows Flutter·Android Studio 로 작업. adb·USB·무선 전부 그대로 동작 |
| **B. WSL 안에 리눅스 Flutter + Android SDK 설치** | 현재 WSL 에는 둘 다 없다. 설치하면 WSL 경로에서 직접 빌드 가능. 기기는 **무선 디버깅**(`adb connect`)으로 붙이는 게 가장 간단 |

`lib/` 편집·`dart analyze` 처럼 빌드가 필요 없는 작업은 지금 구조 그대로 해도 된다.

### WSL 셸에서 Windows 툴 호출하기 (검증된 형태)

```bash
# adb 는 .exe 라 WSL 에서 바로 실행된다
/mnt/c/Users/hi/AppData/Local/Android/Sdk/platform-tools/adb.exe devices -l

# flutter 는 .bat 이라 cmd.exe 경유가 필요하다 (UNC 경로는 pushd 로 드라이브 매핑)
cmd.exe /c "pushd \\wsl.localhost\Ubuntu\home\ho\projects\cloud.jsangho.all\flutter && C:\Users\hi\flutter\bin\flutter.bat devices"
```

빌드가 아닌 명령(`devices` · `doctor` · `pub get`)은 이 형태로 WSL 에서 그대로 쓸 수 있다.

### 환경 검증 결과 (2026-07-31 실측)

| 항목 | 상태 |
|------|------|
| Flutter | 3.44.2 stable (Windows) · `flutter doctor` **Android toolchain ✓** |
| Android SDK | 36.1.0 · platforms `android-36`, `android-36.1` · build-tools 36.0.0 / 36.1.0 / 37.0.0 |
| Android Studio | `AI-261.23567.138` (2026.1 계열) |
| adb | 정상 동작 (`%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`) |
| **Google USB Driver** | **미설치** — `extras/google/usb_driver` 없음. §4 의 USB 연결 전에 SDK Manager 에서 설치할 것 |
| 연결된 안드로이드 기기 | 없음 (`flutter devices` 에 Windows · Chrome · Edge 만) |
| `flutter doctor` 미해결 항목 | Visual Studio 미설치 — **Windows 데스크톱 앱 전용이라 Android 실행과 무관** |

---

## 8. 트러블슈팅

| 증상 | 원인 / 조치 |
|------|-------------|
| `adb devices` 가 비어 있음 | 충전 전용 케이블 · USB 모드가 `충전만` · 허브 경유. 케이블 교체 후 PC 직결 |
| `unauthorized` | 폰의 RSA 허용 다이얼로그 미승인. 개발자 옵션 → **USB 디버깅 승인 취소** 후 재연결 |
| `offline` | `adb kill-server && adb start-server` → 재연결. 그래도면 케이블 재삽입 |
| Windows에서만 인식 안 됨 | `Google USB Driver` 미설치 또는 제조사 OEM 드라이버 필요 |
| Linux에서만 인식 안 됨 | udev 규칙 없음 → `sudo apt install android-sdk-platform-tools-common` 후 재로그인 |
| `adb pair` 실패 | 페어링 **포트**가 아닌 연결 포트를 씀 · 다른 Wi-Fi 대역/게스트망 · AP 격리 |
| 재부팅 후 무선 연결 끊김 | 정상 동작. 포트가 바뀌므로 `adb connect <IP>:<새 포트>` 재실행 |
| `Android license status unknown` | `flutter doctor --android-licenses` 실행 후 전부 `y` |
| `Unsupported class file major version` / jvmTarget 불일치 | Gradle JDK 가 17이 아님 (§7) |
| `flutter run` 은 되는데 Studio 에서 기기가 안 보임 | Flutter 플러그인 미설치 또는 Studio 재시작 필요 |
| `FileHasher` / `java.io.IOException: 잘못된 기능입니다` | WSL(네트워크) 경로에서 Gradle 빌드를 시도함 → 프로젝트를 Windows 로컬 경로로 옮긴다 (§7 WSL2 주의) |

---

## 9. 참고 링크

| 문서 | URL |
|------|-----|
| Flutter Android 설치·설정 | https://docs.flutter.dev/get-started/install/windows/mobile |
| adb 공식 문서 (무선 디버깅 포함) | https://developer.android.com/tools/adb |
| 개발자 옵션 설정 | https://developer.android.com/studio/debug/dev-options |
| Play targetSdk 요구사항 | https://support.google.com/googleplay/android-developer/answer/11926878 |
| Flutter 3.44 릴리스 노트 | https://docs.flutter.dev/release/release-notes |
