"""카탈로그 vs WWE.com Career Highlights 상세 감사 (횟수·라벨·날짜 목록)."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

_APPS_ROOT = Path(__file__).resolve().parents[2]
if str(_APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(_APPS_ROOT))

from kayfabe.app.services.real_title_catalog import individual_title_acquisitions
from kayfabe.scripts.verify_wwe_catalog import (  # noqa: E402
    MANUAL_WWE_HIGHLIGHTS,
    WWE_SLUGS,
    catalog_count_map,
    count_map,
    fetch_html,
    label_to_key,
    parse_career_highlights,
)

_KAYFABE_ROOT = Path(__file__).resolve().parents[1]
OUT = _KAYFABE_ROOT / "reports" / "wwe_audit_detail.json"


def belt_groups(reigns: list[tuple[str, str]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for belt, won in reigns:
        groups[belt].append(won)
    return dict(groups)


def main() -> int:
    catalog = individual_title_acquisitions()
    rows: list[dict] = []
    issues: list[dict] = []

    for name in sorted(catalog):
        slug = WWE_SLUGS.get(name)
        reigns = catalog[name]
        cat_by_belt = belt_groups(reigns)
        cat_counts = catalog_count_map(reigns)

        wwe_source = "live"
        wwe_titles: list[tuple[str, int]] = []
        fetch_error: str | None = None

        if name in MANUAL_WWE_HIGHLIGHTS:
            wwe_source = "manual"
            wwe_titles = MANUAL_WWE_HIGHLIGHTS[name]
        elif slug:
            try:
                wwe_titles = parse_career_highlights(fetch_html(slug))
            except Exception as exc:  # noqa: BLE001
                fetch_error = str(exc)
                wwe_source = "error"
        else:
            wwe_source = "no_slug"

        wwe_counts = count_map(wwe_titles) if wwe_titles else {}
        wwe_by_key: dict[str, list[str]] = defaultdict(list)
        for label, count in wwe_titles:
            wwe_by_key[label_to_key(label)].append(f"{label} (x{count})")

        count_diff = {
            k: {"catalog": cat_counts.get(k, 0), "wwe": wwe_counts.get(k, 0)}
            for k in sorted(set(cat_counts) | set(wwe_counts))
            if cat_counts.get(k, 0) != wwe_counts.get(k, 0)
        }

        row = {
            "name": name,
            "slug": slug,
            "wwe_source": wwe_source,
            "fetch_error": fetch_error,
            "catalog_total_reigns": len(reigns),
            "catalog_by_belt": {k: len(v) for k, v in cat_by_belt.items()},
            "catalog_dates_by_belt": cat_by_belt,
            "wwe_highlights": wwe_titles,
            "wwe_counts": wwe_counts,
            "count_diff": count_diff,
            "uses_manual_wwe": name in MANUAL_WWE_HIGHLIGHTS,
        }
        rows.append(row)

        if count_diff or fetch_error or wwe_source == "no_slug":
            issues.append(
                {
                    "name": name,
                    "count_diff": count_diff,
                    "fetch_error": fetch_error,
                    "wwe_source": wwe_source,
                    "uses_manual_wwe": name in MANUAL_WWE_HIGHLIGHTS,
                }
            )

    report = {
        "total_wrestlers": len(rows),
        "issue_count": len(issues),
        "manual_override_names": sorted(MANUAL_WWE_HIGHLIGHTS),
        "rows": rows,
        "issues": issues,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"total={len(rows)} issues={len(issues)} manual={len(MANUAL_WWE_HIGHLIGHTS)}")
    for item in issues[:20]:
        print(
            item["name"],
            item.get("count_diff") or item.get("fetch_error") or item["wwe_source"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
