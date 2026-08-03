import 'dart:async';

import 'package:flutter/material.dart';

import '../theme/clock_colors.dart';

/// 도시와 UTC 오프셋(분).
///
/// 서머타임은 반영하지 않는다 — 정확한 IANA 타임존이 필요하면 `timezone` 패키지가 필요하다.
class _City {
  final String name;
  final int offsetMinutes;

  const _City(this.name, this.offsetMinutes);
}

const _kCities = [
  _City('서울', 9 * 60),
  _City('도쿄', 9 * 60),
  _City('베이징', 8 * 60),
  _City('홍콩', 8 * 60),
  _City('싱가포르', 8 * 60),
  _City('방콕', 7 * 60),
  _City('델리', 5 * 60 + 30),
  _City('두바이', 4 * 60),
  _City('모스크바', 3 * 60),
  _City('파리', 60),
  _City('베를린', 60),
  _City('런던', 0),
  _City('상파울루', -3 * 60),
  _City('뉴욕', -5 * 60),
  _City('시카고', -6 * 60),
  _City('로스앤젤레스', -8 * 60),
  _City('시드니', 11 * 60),
  _City('오클랜드', 13 * 60),
];

/// 여러 도시의 현재 시각을 보여주는 세계 시계 화면.
class WorldClockScreen extends StatefulWidget {
  const WorldClockScreen({super.key});

  @override
  State<WorldClockScreen> createState() => _WorldClockScreenState();
}

class _WorldClockScreenState extends State<WorldClockScreen> {
  final List<_City> _selected = [
    _kCities[0], // 서울
    _kCities[13], // 뉴욕
    _kCities[11], // 런던
    _kCities[1], // 도쿄
  ];
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(
      const Duration(seconds: 1),
      (_) => setState(() {}),
    );
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _addCity() async {
    final remaining = _kCities
        .where((c) => !_selected.any((s) => s.name == c.name))
        .toList();
    if (remaining.isEmpty) return;

    final picked = await showModalBottomSheet<_City>(
      context: context,
      backgroundColor: kClockCard,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => SafeArea(
        child: ListView.separated(
          shrinkWrap: true,
          itemCount: remaining.length,
          separatorBuilder: (_, _) =>
              const Divider(color: kClockDivider, height: 1, thickness: 0.5),
          itemBuilder: (context, i) => ListTile(
            title: Text(
              remaining[i].name,
              style: const TextStyle(color: kClockText, fontSize: 17),
            ),
            trailing: Text(
              _offsetLabel(remaining[i].offsetMinutes),
              style: const TextStyle(color: kClockSubText, fontSize: 15),
            ),
            onTap: () => Navigator.of(context).pop(remaining[i]),
          ),
        ),
      ),
    );

    if (picked != null) setState(() => _selected.add(picked));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      appBar: AppBar(
        backgroundColor: kClockBg,
        surfaceTintColor: kClockBg,
        title: const Text(
          '세계 시계',
          style: TextStyle(
            color: kClockText,
            fontSize: 32,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          IconButton(
            onPressed: _addCity,
            icon: const Icon(Icons.add, color: kClockAccent),
            tooltip: '도시 추가',
          ),
        ],
      ),
      body: _selected.isEmpty
          ? const Center(
              child: Text(
                '도시를 추가하세요',
                style: TextStyle(color: kClockSubText, fontSize: 17),
              ),
            )
          : ListView.separated(
              itemCount: _selected.length,
              separatorBuilder: (_, _) => const Divider(
                color: kClockDivider,
                height: 1,
                thickness: 0.5,
                indent: 20,
              ),
              itemBuilder: (context, i) {
                final city = _selected[i];
                return Dismissible(
                  key: ValueKey(city.name),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    color: kClockRed,
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 24),
                    child: const Icon(Icons.delete, color: kClockText),
                  ),
                  onDismissed: (_) => setState(() => _selected.removeAt(i)),
                  child: _CityRow(city: city),
                );
              },
            ),
    );
  }
}

// ── 도시 한 줄 ───────────────────────────────────────────────────────────

class _CityRow extends StatelessWidget {
  final _City city;

  const _CityRow({required this.city});

  @override
  Widget build(BuildContext context) {
    final local = DateTime.now();
    final cityNow = local.toUtc().add(Duration(minutes: city.offsetMinutes));
    final diff = Duration(minutes: city.offsetMinutes) - local.timeZoneOffset;

    final hour12 = cityNow.hour % 12 == 0 ? 12 : cityNow.hour % 12;
    final period = cityNow.hour < 12 ? '오전' : '오후';

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _dayLabel(local, cityNow, diff),
                  style: const TextStyle(color: kClockSubText, fontSize: 13),
                ),
                const SizedBox(height: 2),
                Text(
                  city.name,
                  style: const TextStyle(
                    color: kClockText,
                    fontSize: 22,
                    fontWeight: FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
          Text(period, style: const TextStyle(color: kClockText, fontSize: 15)),
          const SizedBox(width: 4),
          Text(
            '$hour12:${cityNow.minute.toString().padLeft(2, '0')}',
            style: const TextStyle(
              color: kClockText,
              fontSize: 44,
              fontWeight: FontWeight.w300,
              fontFeatures: [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

/// "오늘, +2시간" 처럼 날짜 차이와 시차를 함께 나타낸다.
String _dayLabel(DateTime local, DateTime cityNow, Duration diff) {
  final localDay = DateTime(local.year, local.month, local.day);
  final cityDay = DateTime(cityNow.year, cityNow.month, cityNow.day);
  final dayDiff = cityDay.difference(localDay).inDays;

  final day = switch (dayDiff) {
    0 => '오늘',
    1 => '내일',
    -1 => '어제',
    _ => dayDiff > 0 ? '$dayDiff일 후' : '${-dayDiff}일 전',
  };

  if (diff == Duration.zero) return '$day, 현재 시간대';
  return '$day, ${_offsetLabel(diff.inMinutes)}';
}

/// 분 단위 시차를 "+5시간 30분" 형태로 바꾼다.
String _offsetLabel(int minutes) {
  final sign = minutes < 0 ? '-' : '+';
  final abs = minutes.abs();
  final hours = abs ~/ 60;
  final mins = abs % 60;
  if (mins == 0) return '$sign$hours시간';
  return '$sign$hours시간 $mins분';
}
