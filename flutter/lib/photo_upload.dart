/// 카메라로 찍은 사진을 서버를 거쳐 S3로 올린다.
///
/// 흐름: 촬영(OS 카메라) → 우리 서버로 multipart POST → 서버가 S3에 저장.
///
/// 앱에 AWS 자격증명을 넣지 않는다. 앱이 아는 것은 우리 서버 주소와 자기 JWT뿐이고,
/// S3 키·버킷·권한은 전부 서버가 쥔다. 앱에 AWS 키를 넣으면 바이너리를 뜯는 누구나
/// 버킷에 접근할 수 있다.
library;

import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;

import 'auth.dart';
import 'theme/clock_colors.dart';

/// 서버의 사진 업로드 엔드포인트.
///
/// `/api/vision/*`은 얼굴 인식·비전 분석 전용 입구라 쓰지 않는다 — 목적이 다르고,
/// 거기에 섞으면 두 관심사의 보관 정책·수명이 엉킨다.
const kPhotoUploadPath = '/api/photos';

// ── 모델 ─────────────────────────────────────────────────────────────────

@immutable
class UploadedPhoto {
  final String photoId;
  final String key;
  final int sizeBytes;
  final String contentType;

  const UploadedPhoto({
    required this.photoId,
    required this.key,
    required this.sizeBytes,
    required this.contentType,
  });

  factory UploadedPhoto.fromJson(Map<String, dynamic> json) {
    return UploadedPhoto(
      photoId: (json['photoId'] ?? '').toString(),
      key: (json['key'] as String?) ?? '',
      sizeBytes: (json['sizeBytes'] as int?) ?? 0,
      contentType: (json['contentType'] as String?) ?? '',
    );
  }
}

/// 사용자에게 보여줄 한국어 문구로 옮긴 실패. 서버 원문은 노출하지 않는다.
class PhotoUploadFailure implements Exception {
  final String message;
  final String? debugDetail;

  const PhotoUploadFailure(this.message, [this.debugDetail]);

  @override
  String toString() => 'PhotoUploadFailure: $message';
}

// ── 업로드 클라이언트 ─────────────────────────────────────────────────────

/// 서버가 받아주는 형식. 서버 쪽 검증과 **같은 값이어야 한다** —
/// 여기서 먼저 걸러야 사용자가 업로드를 기다린 뒤에 거절당하지 않는다.
const _allowedExtensions = {'.jpg', '.jpeg', '.png'};

/// 서버 상한과 맞춘다. 넘으면 전송조차 시작하지 않는다.
const kMaxPhotoBytes = 10 * 1024 * 1024;

class PhotoUploader {
  final Dio _dio;

  const PhotoUploader(this._dio);

  Future<UploadedPhoto> upload(
    File file, {
    void Function(int sent, int total)? onProgress,
  }) async {
    final extension = p.extension(file.path).toLowerCase();
    if (!_allowedExtensions.contains(extension)) {
      throw const PhotoUploadFailure('JPG 또는 PNG 사진만 올릴 수 있습니다.');
    }

    final size = await file.length();
    if (size > kMaxPhotoBytes) {
      throw const PhotoUploadFailure('사진 용량이 너무 큽니다. (최대 10MB)');
    }

    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        file.path,
        filename: p.basename(file.path),
      ),
    });

    Response<dynamic> response;
    try {
      response = await _dio.post<dynamic>(
        kPhotoUploadPath,
        data: form,
        onSendProgress: onProgress,
      );
    } on DioException catch (error) {
      throw PhotoUploadFailure(_message(error), error.message);
    }

    final body = response.data;
    if (body is! Map<String, dynamic>) {
      throw const PhotoUploadFailure('서버 응답을 이해하지 못했습니다.');
    }
    return UploadedPhoto.fromJson(body);
  }

  static String _message(DioException error) {
    return switch (error.response?.statusCode) {
      400 => 'JPG 또는 PNG 사진만 올릴 수 있습니다.',
      401 => '로그인이 필요합니다.',
      413 => '사진 용량이 너무 큽니다.',
      503 => '사진 보관소에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.',
      null => switch (error.type) {
        DioExceptionType.connectionTimeout ||
        DioExceptionType.sendTimeout ||
        DioExceptionType.receiveTimeout => '네트워크가 느립니다. 잠시 후 다시 시도해 주세요.',
        _ => '서버에 연결하지 못했습니다. 네트워크를 확인해 주세요.',
      },
      _ => '사진을 올리지 못했습니다.',
    };
  }
}

// ── 화면 ─────────────────────────────────────────────────────────────────

/// 촬영 → 업로드 화면.
///
/// OS 카메라 앱을 띄우는 방식이라 앱이 카메라 권한을 직접 요청하지 않는다
/// (Android는 인텐트 위임, iOS는 `Info.plist` 설명 문구만 필요).
class PhotoCaptureScreen extends StatefulWidget {
  const PhotoCaptureScreen({super.key});

  @override
  State<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends State<PhotoCaptureScreen> {
  final _picker = ImagePicker();

  File? _preview;
  bool _busy = false;
  double _progress = 0;
  String? _error;
  UploadedPhoto? _uploaded;

  Future<void> _capture(ImageSource source) async {
    setState(() {
      _error = null;
      _uploaded = null;
    });

    final XFile? shot;
    try {
      shot = await _picker.pickImage(
        source: source,
        // 원본 그대로면 최신 폰에서 10MB를 넘기기 쉽다. 화질을 크게 해치지 않는
        // 선에서 줄여 업로드 실패와 데이터 사용량을 함께 낮춘다.
        imageQuality: 85,
        maxWidth: 2048,
      );
    } on PlatformException catch (error) {
      setState(() => _error = '카메라를 열지 못했습니다.');
      debugPrint('pickImage 실패: ${error.code}');
      return;
    }

    // 사용자가 그냥 뒤로 나간 경우 — 오류가 아니다.
    if (shot == null) return;

    final file = File(shot.path);
    if (!mounted) return;
    setState(() {
      _preview = file;
      _busy = true;
      _progress = 0;
    });

    try {
      final uploaded = await PhotoUploader(AuthScope.of(context).apiClient())
          .upload(
            file,
            onProgress: (sent, total) {
              if (!mounted || total <= 0) return;
              setState(() => _progress = sent / total);
            },
          );
      if (!mounted) return;
      setState(() {
        _busy = false;
        _uploaded = uploaded;
      });
    } on PhotoUploadFailure catch (failure) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = failure.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      appBar: AppBar(
        backgroundColor: kClockBg,
        title: const Text('사진 보관', style: TextStyle(color: kClockText)),
        iconTheme: const IconThemeData(color: kClockText),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(child: _Preview(file: _preview)),
              const SizedBox(height: 16),
              if (_busy) _ProgressBar(value: _progress),
              if (_error != null) _Banner(text: _error!, color: kClockRed),
              if (_uploaded != null)
                _Banner(
                  text: '보관 완료 · ${_formatBytes(_uploaded!.sizeBytes)}',
                  color: kClockGreen,
                ),
              const SizedBox(height: 16),
              _ActionButton(
                label: '사진 촬영',
                icon: Icons.photo_camera,
                background: kClockAccent,
                foreground: Colors.black,
                onPressed: _busy ? null : () => _capture(ImageSource.camera),
              ),
              const SizedBox(height: 10),
              _ActionButton(
                label: '갤러리에서 선택',
                icon: Icons.photo_library_outlined,
                background: kClockCard,
                foreground: kClockText,
                onPressed: _busy ? null : () => _capture(ImageSource.gallery),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)}MB';
  }
  return '${(bytes / 1024).toStringAsFixed(0)}KB';
}

class _Preview extends StatelessWidget {
  final File? file;

  const _Preview({required this.file});

  @override
  Widget build(BuildContext context) {
    if (file == null) {
      return Container(
        decoration: BoxDecoration(
          color: kClockCard,
          borderRadius: BorderRadius.circular(16),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.photo_camera_outlined,
                color: kClockDisabled,
                size: 48,
              ),
              SizedBox(height: 12),
              Text(
                '촬영한 사진이 여기에 표시됩니다',
                style: TextStyle(color: kClockSubText, fontSize: 14),
              ),
            ],
          ),
        ),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Image.file(file!, fit: BoxFit.cover, width: double.infinity),
    );
  }
}

class _ProgressBar extends StatelessWidget {
  final double value;

  const _ProgressBar({required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: value == 0 ? null : value,
              minHeight: 6,
              backgroundColor: kClockCard,
              valueColor: const AlwaysStoppedAnimation<Color>(kClockAccent),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '올리는 중… ${(value * 100).toStringAsFixed(0)}%',
            textAlign: TextAlign.center,
            style: const TextStyle(color: kClockSubText, fontSize: 13),
          ),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  final String text;
  final Color color;

  const _Banner({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: TextStyle(color: color, fontSize: 14, height: 1.4),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color background;
  final Color foreground;
  final VoidCallback? onPressed;

  const _ActionButton({
    required this.label,
    required this.icon,
    required this.background,
    required this.foreground,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null;
    return SizedBox(
      height: 52,
      child: Material(
        color: disabled ? kClockCard : background,
        borderRadius: BorderRadius.circular(12),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: Center(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icon,
                  color: disabled ? kClockDisabled : foreground,
                  size: 20,
                ),
                const SizedBox(width: 10),
                Text(
                  label,
                  style: TextStyle(
                    color: disabled ? kClockDisabled : foreground,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
