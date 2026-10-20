"""명부(선수·관계자)의 품질을 한 번에 점검한다. **쓰지 않는다 — 보고만 한다.**

## 왜 필요한가

2026-10-12에 아래를 전부 **손으로** 찾았고 한 세션이 걸렸다. 질의가 매번 달랐다.

    Stepahnie Vaquer                     철자 오류 → 위키 대조가 '방출자'로 오판할 뻔했다
    19997-09-06                          연도가 다섯 자리
    WWE PerFormance Center               대문자 오타로 같은 센터가 둘로 갈림
    Booker TWild Samoan Training Center  구분자 `|` 누락으로 사람과 학교가 붙음
    CSV ↔ DB 드리프트 4건                 로더를 돌리면 방출자가 되살아날 상태였다

같은 것을 다음에 다시 찾지 않으려고 묶었다. 예측 쪽의
`check_knowledge_coverage.py`가 하는 일을 명부 쪽에서 한다.

## 보는 것 일곱

1. **CSV ↔ DB 드리프트** — 로더를 돌리면 **무엇이 지워지고 무엇이 추가되는지**.
   `load_wrestlers_csv.py`는 CSV에 없는 DB 행을 지우므로, 이 목록을 보지 않고
   돌리면 사고가 난다.
2. **생년월일 형식** — `YYYY-MM-DD`가 아닌 값. `????-07-16`(연도 미상)은
   정상으로 본다 — 생일 보드가 그 꼴을 센다.
3. **미래이거나 터무니없이 오래된 생년월일** — 오타를 잡는다.
4. **트레이너 표기 갈림** — 대소문자·공백만 다른 이름 묶음. 같은 사람이 둘로
   세어지는 자리다.
5. **구분자 누락 의심** — 낱말 중간에서 대문자가 새로 시작하는 트레이너 이름
   (`Booker TWild...`). 사람과 학교가 붙은 꼴이다. `McCool`·`DeMott`처럼
   이름이 원래 품는 대문자는 봐준다.
6. **빈 칸 비율** — 화면이 분모로 쓰는 값이라 갑자기 떨어지면 알아야 한다.
7. **CSV ↔ 정적 카탈로그 드리프트** — `wwe_roster_catalog.WWE_ROSTER`는 손으로
   적는 **세 번째 명부**다(자동 동기화 없음). 어긋나면 기록 페이지에서 선수가
   목록에 안 뜨거나 방출자가 남는데 **에러는 안 난다**. 2026-10-20에 10명이
   어긋나 있었다.

**판정하지 않는 것**: 누가 방출됐는지. 그건 바깥 출처가 필요하고 사람이 본다
(메모리 `roster-release-sync`).

## 종료 코드

- `0` — 정상. **지적이 있어도 0이다** (전부 사람이 판단할 거리다).
- `2` — 사용법 오류.
- `4` — `DATABASE_URL`이 비어 있다(더미 모드).

실행 — EC2 컨테이너 안에서:

    cd /app/fastapi && PYTHONUTF8=1 PYTHONPATH=apps:. python \\
        apps/kayfabe/scripts/check_roster_health.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

_APPS_DIR = Path(__file__).resolve().parents[2]
if str(_APPS_DIR) not in sys.path:
    sys.path.insert(0, str(_APPS_DIR))

import asyncio  # noqa: E402

from sqlalchemy import text  # noqa: E402

from core.matrix.grid_oracle_database_manager import engine  # noqa: E402
from kayfabe.app.services.data_center_stats import trainer_names  # noqa: E402
from kayfabe.app.services.wwe_roster_catalog import (  # noqa: E402
    RETAINED_FOR_RECORDS,
    WWE_ROSTER,
)

EXIT_NO_DATABASE = 4

_CSV_PATH = (
    Path(__file__).resolve().parents[1] / "_docs" / "wwe_active_roster_cleaned.csv"
)
_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PARTIAL_DATE = re.compile(r"^(\d{4}|\?{4})-(\d{2}|\?{2})-(\d{2}|\?{2})$")
#: `Lance StormStu Hart` 처럼 **소문자 뒤에 대문자**가 붙은 자리 — 사람과 학교가
#: 구분자 없이 붙은 꼴이다.
_GLUED = re.compile(r"(?<=[a-z])(?=[A-Z])")

#: `Booker TWild Samoan...` 처럼 **대문자 뒤에 대문자**가 오는 자리. 앞이 `Booker T`
#: 같은 머리글자로 끝나면 경계의 양쪽이 다 대문자여서 위 규칙이 못 본다. 뒤 대문자에
#: 소문자가 따라올 때만 보기 때문에 `WWE`·`NXT` 같은 약어는 쪼개지 않는다.
_GLUED_AFTER_INITIAL = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")

#: 낱말 안에 대문자를 **정상적으로** 품는 접두사. 이것들을 빼지 않으면
#: `DeMott`·`McCool`·`LaBron` 같은 이름이 전부 걸린다 — 실측으로 오탐 5건이
#: 전부 이 꼴이었다. 정규식 lookbehind로는 낱말 첫머리를 못 봐서 따로 센다.
_NAME_PREFIXES = ("mc", "mac", "de", "du", "da", "di", "la", "le", "van", "von", "o'")


def _looks_glued(name: str) -> bool:
    """구분자가 빠진 것처럼 보이는가. **이름다운 대문자는 봐준다.**"""
    for word in name.split():
        for match in _GLUED.finditer(word):
            prefix = word[: match.start()].casefold()
            if prefix in _NAME_PREFIXES:
                continue
            return True
        if _GLUED_AFTER_INITIAL.search(word):
            return True
    return False


#: 생년월일이 이 범위를 벗어나면 오타로 본다.
_OLDEST_YEAR = 1930


def _csv_names() -> set[str]:
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return {
        r[0].strip()
        for r in rows[1:]
        if r and r[0].strip() and not r[0].startswith("#")
    }


def _csv_brands() -> dict[str, str | None]:
    """CSV 이름 → 브랜드. 브랜드는 `#RAW` 같은 구분행이 정한다."""
    brands: dict[str, str | None] = {}
    brand: str | None = None
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            head = row[0].strip()
            if head.startswith("#"):
                brand = head[1:].strip()
            elif head != "name":
                brands[head] = brand
    return brands


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _report_catalog_drift() -> int:
    """CSV 와 `WWE_ROSTER` 가 어긋난 자리.

    방향마다 기준이 다르다 — 섞으면 거짓 양성이 난다.

    * **카탈로그에만 있음** → CSV **전 구간**과 비교한다. Evolve를 빼고 비교하면
      Evolve 선수(`Kale Dixon`)가 방출자로 잡힌다. `RETAINED_FOR_RECORDS`는 뺀다.
    * **CSV에만 있음** → 카탈로그는 Evolve를 다루지 않으므로(`ROSTER_SOURCE`)
      Evolve 구간을 빼고 비교한다.
    """
    brands = _csv_brands()
    csv_all = set(brands)
    csv_scope = {n for n, b in brands.items() if b != "Evolve"}
    catalog = {e["name"].strip(): e for e in WWE_ROSTER}

    only_catalog = sorted(set(catalog) - csv_all - RETAINED_FOR_RECORDS)
    only_csv = sorted(csv_scope - set(catalog))

    print("\n== 7. CSV ↔ 정적 카탈로그 드리프트 (손으로 맞춰야 한다)")
    for name in only_catalog:
        print(f"   [방출?] 카탈로그에만 있음 {name}")
    for name in only_csv:
        print(f"   [누락]  카탈로그에 없음   {name}")

    mismatch = _catalog_value_mismatch(catalog)
    for line in mismatch:
        print(f"   [불일치] {line}")

    total = len(only_catalog) + len(only_csv) + len(mismatch)
    if not total:
        print(f"   없음 — 카탈로그 {len(catalog)}명이 CSV와 맞는다")
    return total


def _catalog_value_mismatch(catalog: dict[str, dict]) -> list[str]:
    """두 명부에 다 있는 선수의 값이 어긋난 자리."""
    out: list[str] = []
    with _CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            entry = catalog.get(name)
            if not entry or name.startswith("#"):
                continue
            for column, key in (
                ("real_name", "real_name"),
                ("birth_date", "birth_date"),
                ("height", "height_cm"),
                ("weight", "weight_kg"),
            ):
                csv_value = (row.get(column) or "").strip()
                entry_value = entry.get(key)
                if not csv_value or entry_value is None:
                    continue
                if key.endswith(("_cm", "_kg")):
                    number = _first_number(csv_value)
                    if number is not None and abs(number - float(entry_value)) > 0.6:
                        out.append(
                            f"{name} {column}: CSV {csv_value} ≠ 카탈로그 {entry_value}"
                        )
                elif csv_value != str(entry_value):
                    out.append(
                        f"{name} {column}: CSV {csv_value!r} ≠ 카탈로그 {entry_value!r}"
                    )
    return out


def _first_number(value: str) -> float | None:
    """`168 cm`·`131.5kg`·`178cm(200cm)` 에서 앞의 숫자만 꺼낸다."""
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


async def main() -> int:
    if engine is None:
        print("DATABASE_URL이 비어 있습니다 — 더미 모드에서는 점검할 수 없습니다.")
        return EXIT_NO_DATABASE

    async with engine.connect() as conn:
        wrestlers = (
            await conn.execute(
                text("SELECT name, birth_date, trainer, brand FROM wrestlers")
            )
        ).all()
        staff = (
            await conn.execute(text("SELECT name, birth_date, role FROM wwe_staff"))
        ).all()

    findings = 0
    print(f"선수 {len(wrestlers)}명 · 관계자 {len(staff)}명\n")

    # 1. CSV ↔ DB 드리프트
    csv_names = _csv_names()
    db_names = {n for n, *_ in wrestlers}
    only_db = sorted(db_names - csv_names)
    only_csv = sorted(csv_names - db_names)
    print("== 1. CSV ↔ DB 드리프트 (로더를 돌리면 이대로 움직인다)")
    if only_db or only_csv:
        findings += len(only_db) + len(only_csv)
        for n in only_db:
            print(f"   [지워짐] DB에만 있음  {n}")
        for n in only_csv:
            print(f"   [추가됨] CSV에만 있음 {n}")
    else:
        print("   없음 — 로더를 돌려도 아무것도 안 바뀐다")

    # 2·3. 날짜
    print("\n== 2. 생년월일 형식")
    today = date.today()
    bad_format: list[str] = []
    suspect: list[str] = []
    for label, rows in (("선수", wrestlers), ("관계자", staff)):
        for row in rows:
            name, raw = row[0], (row[1] or "").strip()
            if not raw:
                bad_format.append(f"{label} {name}: 빈 값")
                continue
            if _FULL_DATE.match(raw):
                year = int(raw[:4])
                if year > today.year or year < _OLDEST_YEAR:
                    suspect.append(f"{label} {name}: {raw}")
                continue
            if _PARTIAL_DATE.match(raw):
                continue  # `????-07-16` 등 — 생일 보드가 다룬다
            bad_format.append(f"{label} {name}: {raw!r}")
    for line in bad_format:
        print(f"   [형식] {line}")
    findings += len(bad_format)
    if not bad_format:
        print("   없음")
    print("\n== 3. 터무니없는 연도")
    for line in suspect:
        print(f"   [의심] {line}")
    findings += len(suspect)
    if not suspect:
        print("   없음")

    # 4·5. 트레이너 표기
    by_norm: defaultdict[str, set[str]] = defaultdict(set)
    glued: set[str] = set()
    for _name, _birth, trainer, _brand in wrestlers:
        for who in trainer_names(trainer):
            by_norm[_norm(who)].add(who)
            if _looks_glued(who):
                glued.add(who)
    split = {k: v for k, v in by_norm.items() if len(v) > 1}
    print("\n== 4. 같은 트레이너가 여러 표기로 갈림")
    for _key, variants in sorted(split.items()):
        print(f"   [갈림] {' / '.join(sorted(variants))}")
    findings += len(split)
    if not split:
        print("   없음")
    print("\n== 5. 구분자 '|' 누락 의심")
    for who in sorted(glued):
        print(f"   [붙음] {who}")
    findings += len(glued)
    if not glued:
        print("   없음")

    # 6. 빈 칸 비율
    print("\n== 6. 빈 칸")
    for column, index in (("birth_date", 1), ("trainer", 2), ("brand", 3)):
        empty = sum(1 for r in wrestlers if not (r[index] or "").strip())
        print(f"   선수   {column:12} 빈 값 {empty}/{len(wrestlers)}")
    for column, index in (("birth_date", 1), ("role", 2)):
        empty = sum(1 for r in staff if not (r[index] or "").strip())
        print(f"   관계자 {column:12} 빈 값 {empty}/{len(staff)}")

    # 7. CSV ↔ 정적 카탈로그
    findings += _report_catalog_drift()

    print(f"\n지적 {findings}건 — **쓰지 않았습니다.** 판단은 사람이 합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
