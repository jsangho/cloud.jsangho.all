import 'package:flutter/material.dart';

/// WWE 링 아이콘 — 웹의 KayfabeMark SVG를 CustomPaint로 재현
class RingLogo extends StatelessWidget {
  final double size;

  const RingLogo({super.key, this.size = 64});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: const Color(0xFF050505),
        borderRadius: BorderRadius.circular(size * 0.28125),
        border: Border.all(color: const Color(0xFF52525B), width: 0.5),
        boxShadow: [
          BoxShadow(color: const Color(0x73DC2626), blurRadius: size * 0.75),
        ],
      ),
      clipBehavior: Clip.hardEdge,
      child: CustomPaint(size: Size(size, size), painter: const _RingPainter()),
    );
  }
}

class _RingPainter extends CustomPainter {
  const _RingPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 32.0;

    // 아레나 라디알 그라데이션 오버레이
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()
        ..shader = const RadialGradient(
          center: Alignment(0, -0.64),
          radius: 0.72,
          colors: [Color(0xD9292524), Color(0x590C0A09), Colors.transparent],
          stops: [0.0, 0.55, 1.0],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );

    // 링 매트 (사다리꼴)
    canvas.drawPath(
      Path()
        ..moveTo(0, 24.5 * s)
        ..lineTo(16 * s, 19.8 * s)
        ..lineTo(32 * s, 24.5 * s)
        ..lineTo(32 * s, 32 * s)
        ..lineTo(0, 32 * s)
        ..close(),
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF44403C), Color(0xFF292524), Color(0xFF0C0A09)],
          stops: [0.0, 0.45, 1.0],
        ).createShader(Rect.fromLTWH(0, 19 * s, size.width, 13 * s)),
    );

    canvas.drawPath(
      Path()
        ..moveTo(2 * s, 32 * s)
        ..lineTo(2 * s, 25.8 * s)
        ..lineTo(16 * s, 21.6 * s)
        ..lineTo(30 * s, 25.8 * s)
        ..lineTo(30 * s, 32 * s)
        ..close(),
      Paint()..color = const Color(0x8C1C1917),
    );

    // 링 포스트 (좌우)
    final postPaint = Paint()..color = const Color(0xFF3F3F46);
    canvas.drawRect(
      Rect.fromLTWH(1.5 * s, 8.2 * s, 2.7 * s, 13.3 * s),
      postPaint,
    );
    canvas.drawRect(
      Rect.fromLTWH(27.8 * s, 8.2 * s, 2.7 * s, 13.3 * s),
      postPaint,
    );

    final innerPostPaint = Paint()..color = const Color(0xFF52525B);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(3.8 * s, 7.6 * s, 2.2 * s, 13.8 * s),
        Radius.circular(0.4 * s),
      ),
      innerPostPaint,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(26.0 * s, 7.6 * s, 2.2 * s, 13.8 * s),
        Radius.circular(0.4 * s),
      ),
      innerPostPaint,
    );

    // 포스트 캡 (골드)
    final capPaint = Paint()..color = const Color(0xFFA16207);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(3.4 * s, 7.2 * s, 3.0 * s, 2.2 * s),
        Radius.circular(0.35 * s),
      ),
      capPaint,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(25.6 * s, 7.2 * s, 3.0 * s, 2.2 * s),
        Radius.circular(0.35 * s),
      ),
      capPaint,
    );

    // 로프 3개 (위→아래, 레드 그라데이션)
    _drawRope(canvas, size, s, 3.2, 10.1, 28.8, 11.05, const [
      Color(0xFF991B1B),
      Color(0xFFDC2626),
      Color(0xFF7F1D1D),
    ]);
    _drawRope(canvas, size, s, 2.3, 13.35, 29.7, 14.65, const [
      Color(0xFFB91C1C),
      Color(0xFFEF4444),
      Color(0xFF991B1B),
    ]);
    _drawRope(canvas, size, s, 1.4, 17.1, 30.6, 18.85, const [
      Color(0xFFDC2626),
      Color(0xFFF87171),
      Color(0xFFB91C1C),
    ]);

    // 로프 하이라이트 라인
    _drawLine(canvas, s, 3.2, 10.1, 28.8, 10.1, const Color(0x8CFECACA), 0.35);
    _drawLine(canvas, s, 2.3, 13.35, 29.7, 13.35, const Color(0xA6FECACA), 0.4);
    _drawLine(canvas, s, 1.4, 17.1, 30.6, 17.1, const Color(0xBFFFF1F2), 0.45);

    // W 로고 (링 위 중앙)
    final wPath = Path()
      ..moveTo(10.8 * s, 13.35 * s)
      ..lineTo(13.1 * s, 10.05 * s)
      ..lineTo(16.0 * s, 13.55 * s)
      ..lineTo(18.9 * s, 10.05 * s)
      ..lineTo(21.2 * s, 13.35 * s)
      ..lineTo(19.55 * s, 13.35 * s)
      ..lineTo(16.0 * s, 10.35 * s)
      ..lineTo(12.45 * s, 13.35 * s)
      ..close();

    canvas.drawPath(
      wPath,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFAFAFA), Color(0xFFE7E5E4), Color(0xFFD6D3D1)],
        ).createShader(Rect.fromLTWH(10 * s, 9 * s, 12 * s, 5 * s)),
    );
    canvas.drawPath(
      wPath,
      Paint()
        ..color = const Color(0xFF7F1D1D)
        ..strokeWidth = 0.2 * s
        ..style = PaintingStyle.stroke,
    );

    // 링 위 인물 실루엣 힌트
    final figurePaint = Paint()
      ..color = const Color(0x8057534E)
      ..strokeWidth = 0.45 * s
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(16 * s, 20.2 * s),
      Offset(14.2 * s, 18.8 * s),
      figurePaint,
    );
    canvas.drawLine(
      Offset(16 * s, 20.2 * s),
      Offset(17.8 * s, 18.8 * s),
      figurePaint,
    );
  }

  void _drawRope(
    Canvas canvas,
    Size size,
    double s,
    double lx,
    double y1,
    double rx,
    double y2,
    List<Color> colors,
  ) {
    canvas.drawPath(
      Path()
        ..moveTo(lx * s, y1 * s)
        ..quadraticBezierTo(size.width * 0.5, (y1 - 0.4) * s, rx * s, y1 * s)
        ..lineTo(rx * s, y2 * s)
        ..quadraticBezierTo(size.width * 0.5, (y2 - 0.4) * s, lx * s, y2 * s)
        ..close(),
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: colors,
        ).createShader(Rect.fromLTWH(0, y1 * s, size.width, (y2 - y1) * s)),
    );
  }

  void _drawLine(
    Canvas canvas,
    double s,
    double x1,
    double y1,
    double x2,
    double y2,
    Color color,
    double width,
  ) {
    canvas.drawLine(
      Offset(x1 * s, y1 * s),
      Offset(x2 * s, y2 * s),
      Paint()
        ..color = color
        ..strokeWidth = width * s
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
