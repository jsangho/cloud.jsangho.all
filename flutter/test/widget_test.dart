import 'package:flutter_test/flutter_test.dart';
import 'package:jsh_flutter/main.dart';

void main() {
  testWidgets('IntroScreen smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const KayfabeApp());
    await tester.pumpAndSettle();

    expect(find.text('KayFabe'), findsOneWidget);
    expect(find.text('예측 시작하기'), findsOneWidget);
    expect(find.text('랭킹 보기'), findsOneWidget);
  });
}
