import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// 카카오 네이티브 앱 키 — AndroidManifest의 커스텀 스킴에 박히는 값이다.
// `--dart-define`은 Dart 코드에만 닿아서 매니페스트를 채울 수 없으므로 Gradle 쪽에서
// 따로 읽는다. 우선순위: gradle 프로퍼티(-PKAKAO_NATIVE_APP_KEY) > local.properties.
//
// 비밀값이 아니지만(앱 바이너리에 들어가는 게 정상) local.properties는 git에서 제외돼
// 있으므로 개발자마다 자기 키를 넣으면 된다. 값이 비면 스킴이 "kakao"가 되어
// 리다이렉트가 돌아오지 않는다 — 실기기 검증 전에 반드시 채운다.
val kakaoNativeAppKey: String = (project.findProperty("KAKAO_NATIVE_APP_KEY") as String?)
    ?: rootProject.file("local.properties").let { file ->
        if (file.exists()) {
            Properties().apply { file.inputStream().use { load(it) } }
                .getProperty("kakao.nativeAppKey", "")
        } else {
            ""
        }
    }

android {
    namespace = "cloud.jsangho.kayfabe"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // 카카오 콘솔에 등록하는 패키지명이 이 값이다 — 런타임 패키지명은 namespace가
        // 아니라 applicationId다. 바꾸면 콘솔 재등록 + 기존 설치본과 단절이 생긴다.
        applicationId = "cloud.jsangho.kayfabe"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        manifestPlaceholders["kakaoNativeAppKey"] = kakaoNativeAppKey
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
