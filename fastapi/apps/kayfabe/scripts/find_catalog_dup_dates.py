"""같은 날짜에 여러 벨트가 기록된 카탈로그 항목 탐지."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

_APPS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_APPS_ROOT))

from kayfabe.app.services.real_title_catalog import individual_title_acquisitions

_KAYFABE_ROOT = Path(__file__).resolve().parents[1]
out = _KAYFABE_ROOT / "reports" / "catalog_dup_dates.json"
issues = []
for name, reigns in sorted(individual_title_acquisitions().items()):
    by_date: dict[str, list[str]] = defaultdict(list)
    for belt, won in reigns:
        by_date[won].append(belt)
    for date, belts in sorted(by_date.items()):
        if len(belts) > 1:
            issues.append({"name": name, "date": date, "belts": belts})

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(issues))
