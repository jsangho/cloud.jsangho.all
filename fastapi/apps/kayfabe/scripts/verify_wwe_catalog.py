"""WWE.com Career Highlights vs real_title_catalog 대조."""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

# `python -m apps.kayfabe.scripts.verify_wwe_catalog` 시 apps/ 가 path 에 없을 수 있음
_APPS_ROOT = Path(__file__).resolve().parents[2]
if str(_APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(_APPS_ROOT))

from kayfabe.app.services.real_title_catalog import individual_title_acquisitions

WWE_SLUGS: dict[str, str] = {
    "AJ Lee": "aj-lee",
    "AJ Styles": "aj-styles",
    "Alexa Bliss": "alexa-bliss",
    "Andrade": "andrade",
    "Angelo Dawkins": "angelo-dawkins",
    "Asuka": "asuka",
    "Austin Theory": "austin-theory",
    "Axiom": "axiom",
    "Bayley": "bayley",
    "Becky Lynch": "becky-lynch",
    "Bo Dallas": "bo-dallas",
    "Brie Bella": "brie-bella",
    "Brock Lesnar": "brock-lesnar",
    "Bron Breakker": "bron-breakker",
    "CM Punk": "cmpunk",
    "Charlotte Flair": "charlotte-flair",
    "Cody Rhodes": "cody-rhodes",
    "Dexter Lumis": "dexter-lumis",
    "Dominik Mysterio": "dominik-mysterio",
    "Dragon Lee": "dragon-lee",
    "Drew McIntyre": "drew-mcintyre",
    "Ethan Page": "ethan-page",
    "Finn Bálor": "finn-balor",
    "Gunther": "gunther",
    "IYO SKY": "iyo-sky",
    "JD McDonagh": "jd-mcdonagh",
    "Jacy Jayne": "jacy-jayne",
    "Jey Uso": "jey-uso",
    "Jimmy Uso": "jimmy-uso",
    "Joe Gacy": "joe-gacy",
    "John Cena": "john-cena",
    "Johnny Gargano": "johnny-gargano",
    "Karrion Kross": "karrion-kross",
    "LA Knight": "la-knight",
    "Lash Legend": "lash-legend",
    "Liv Morgan": "liv-morgan",
    "Logan Paul": "logan-paul",
    "Lyra Valkyria": "lyra-valkyria",
    "Montez Ford": "montez-ford",
    "Myles Borne": "myles-borne",
    "Naomi": "naomi",
    "Nathan Frazer": "nathan-frazer",
    "Nia Jax": "nia-jax",
    "Oba Femi": "oba-femi",
    "Paige": "paige",
    "Penta": "penta",
    "Randy Orton": "randy-orton",
    "Rey Mysterio": "reymysterio",
    "Rhea Ripley": "rhea-ripley",
    "Roman Reigns": "roman-reigns",
    "Rusev": "rusev",
    "Sami Zayn": "sami-zayn",
    "Seth Rollins": "seth-rollins",
    "Solo Sikoa": "solo-sikoa",
    "Stephanie Vaquer": "stephanie-vaquer",
    "Tiffany Stratton": "tiffany-stratton",
    "Tommaso Ciampa": "tommaso-ciampa",
    "Tony D'Angelo": "tony-dangelo",
    "Trick Williams": "trick-williams",
    "The Miz": "the-miz",
    "Sol Ruca": "sol-ruca",
    "Alex Shelley": "alex-shelley",
    "Chris Sabin": "chris-sabin",
    "Brad Baylor": "brad-baylor",
    "Ricky Smokes": "ricky-smokes",
}

# WWE Career Highlights 라벨 → 카탈로그 belt normalize 키
LABEL_TO_KEY: list[tuple[str, str]] = [
    ("women's intercontinental champion", "women's intercontinental"),
    ("women's united states champion", "women's united states"),
    ("women's world champion", "women's world"),
    ("women's tag team champion", "women's tag"),
    ("wwe women's tag team champion", "women's tag"),
    ("wwe women's champion", "wwe women's"),
    ("raw women's champion", "raw women's"),
    ("smackdown women's champion", "smackdown women's"),
    ("nxt uk women's champion", "nxt uk women's"),
    ("first-ever nxt uk women's champion", "nxt uk women's"),
    ("nxt women's champion", "nxt women's"),
    ("nxt women's north american champion", "nxt women's north american"),
    ("nxt north american champion", "nxt north american"),
    ("nxt tag team champion", "nxt tag"),
    ("undisputed wwe universal champion", "undisputed universal"),
    ("undisputed wwe tag team champion", "undisputed tag"),
    ("world tag team champion", "world tag"),
    ("wwe tag team champion", "wwe tag"),
    ("raw tag team champion", "raw tag"),
    ("smackdown tag team champion", "smackdown tag"),
    ("universal champion", "universal"),
    ("world heavyweight champion", "world heavyweight"),
    ("men's crown jewel champion", "wwe crown jewel"),
    ("women's crown jewel champion", "wwe crown jewel"),
    ("wwe crown jewel championship", "wwe crown jewel"),
    ("wwe crown jewel champion", "wwe crown jewel"),
    ("crown jewel champion", "wwe crown jewel"),
    ("2024 wwe crown jewel champion", "wwe crown jewel"),
    ("wwe champion", "wwe championship"),
    ("undisputed wwe champion", "undisputed wwe"),
    ("intercontinental champion", "intercontinental"),
    ("intercontinental title", "intercontinental"),
    ("raw tag team champion", "raw tag"),
    ("raw tag team", "raw tag"),
    ("nxt heritage cup champion", "nxt heritage cup"),
    ("united states champion", "united states"),
    ("nxt champion", "nxt championship"),
    ("ecw champion", "ecw"),
    ("world champion", "world heavyweight"),
    ("divas champion", "divas"),
    ("wwe divas champion", "divas"),
    ("money in the bank winner", "mitb"),
    ("royal rumble winner", "royal rumble"),
]


def fetch_html(slug: str) -> str:
    url = f"https://www.wwe.com/superstars/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


_HIGHLIGHT_START = (
    r"(?="
    r"WWE Champion|WWE Women's Champion|WWE Women's Tag Team Champion|WWE Tag Team Champion|"
    r"World Heavyweight Champion|World Tag Team Champion|"
    r"Raw Women's Champion|Raw Tag Team Champion|"
    r"SmackDown Women's Champion|SmackDown Tag Team Champion|"
    r"NXT UK Women's Champion|NXT Women's Champion|NXT Women's Tag Team Champion|"
    r"NXT Champion|NXT Tag Team Champion|NXT North American Champion|"
    r"NXT Women's North American Champion|NXT Cruiserweight Champion|"
    r"Women's World Champion|Women's Tag Team Champion|"
    r"Women's Intercontinental Champion|Women's United States Champion|"
    r"Universal Champion|Intercontinental Champion|United States Champion|"
    r"Undisputed WWE Universal Champion|Undisputed WWE Tag Team Champion|"
    r"Divas Champion|WWE Divas Champion|"
    r"Money in the Bank|Royal Rumble|Crown Jewel Champion|"
    r"First-ever NXT UK Women's Champion|"
    r"\d{4} WWE"
    r")"
)


def parse_career_highlights(page_html: str) -> list[tuple[str, int]]:
    text = re.sub(r"<[^>]+>", " ", page_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"Career Highlights\s*(.*?)\s*close\s", text, flags=re.I)
    if not m:
        return []
    block = m.group(1)
    titles: list[tuple[str, int]] = []
    for part in re.split(_HIGHLIGHT_START, block, flags=re.I):
        part = part.strip(" ,;")
        if not part or part.lower().startswith("wwe hall of fame"):
            continue
        count = 1
        cm = (
            re.search(r"\(x(\d+)[^)]*\)", part, flags=re.I)
            or re.search(r"\((\d+)x\)", part, flags=re.I)
            or re.search(r"Champion\s*\((\d+)\)\s*$", part, flags=re.I)
        )
        if cm:
            count = int(cm.group(1))
            part = re.sub(
                r"\(x\d+[^)]*\)|\(\d+x\)|Champion\s*\(\d+\)\s*$", "", part, flags=re.I
            ).strip()
        # "2023 and 2024 Royal Rumble" 등 비챔피언십 문구 오인 방지
        if re.search(r"\d{4}\s+and\s+\d{4}", part) and "champion" in part.lower():
            count = max(count, 2)
        # "2024 WWE Women's Crown Jewel Champion" 등 연도 접두 유지
        part = re.sub(
            r"\b\d{4}\s+and\s+\d{4}\s+royal rumble.*$", "", part, flags=re.I
        ).strip()
        if "tna" in part.lower():
            continue
        part = re.sub(r"\band\b.*$", "", part, flags=re.I).strip()
        part = re.sub(r"\bWinner\b.*$", "", part, flags=re.I).strip()
        part = re.sub(r"\b\d{4}\b(?!\s*WWE)", "", part).strip()
        if not part:
            continue
        titles.append((part, count))
    # "Undisputed" + "WWE Champion (x3)" 분리 병합
    merged: list[tuple[str, int]] = []
    i = 0
    while i < len(titles):
        label, count = titles[i]
        if label.strip().lower() == "undisputed" and i + 1 < len(titles):
            nxt_label, nxt_count = titles[i + 1]
            nl = nxt_label.lower()
            if "wwe champion" in nl:
                merged.append((f"Undisputed {nxt_label}", nxt_count))
                i += 2
                continue
            if "wwe tag team champion" in nl or "tag team champion" in nl:
                merged.append(("Undisputed WWE Tag Team Champion", nxt_count))
                i += 2
                continue
        merged.append((label, count))
        i += 1
    return merged


def label_to_key(label: str) -> str:
    s = label.lower().strip()
    if "world heavyweight" in s and "ecw" in s:
        return "world heavyweight"
    if "undisputed wwe champion" in s:
        return "undisputed wwe"
    if "women's" in s and "intercontinental" in s:
        return "women's intercontinental"
    if "women's" in s and "united states" in s:
        return "women's united states"
    # 긴(구체적) 패턴을 먼저 매칭해 세부 벨트명 오분류 방지
    for needle, key in sorted(
        LABEL_TO_KEY, key=lambda item: len(item[0]), reverse=True
    ):
        if needle in s:
            return key
    return s


def count_map(items: list[tuple[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for label, count in items:
        key = label_to_key(label)
        out[key] = out.get(key, 0) + count
    return out


# Career Highlights에 있으나 챔피언십 획득 이력이 아닌 항목 (대조 제외)
IGNORE_WWE_KEYS = frozenset(
    {
        "royal rumble",
        "royal rumble match",
        "money in the bank",
        "money in the bank ladder match",
        "mitb",
        "king of the ring",
        "24/7",
        "first-ever",
        "wwe hall of fame",
        "2023 wwe hall of fame inductee",
        "nxt heritage cup",
        "nxt",
        "women's",
        "wwe cruiserweight",
        "wcw",
        "aaa general manager",
    }
)

# WWE.com 페이지 파싱 불가·403 시 Career Highlights 수동 대조
MANUAL_WWE_HIGHLIGHTS: dict[str, list[tuple[str, int]]] = {
    "Bo Dallas": [
        ("NXT Championship", 1),
        ("Raw Tag Team Championship", 1),
    ],
    "Rey Mysterio": [
        ("WWE Champion", 1),
        ("World Heavyweight Champion", 2),
        ("Intercontinental Champion", 2),
        ("United States Champion", 3),
        ("WWE Tag Team Champion", 4),
        ("SmackDown Tag Team Champion", 1),
    ],
}


def catalog_count_map(reigns: list[tuple[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for belt, _ in reigns:
        key = label_to_key(belt)
        out[key] = out.get(key, 0) + 1
    return out


def main() -> int:
    catalog = individual_title_acquisitions()
    mismatches: list[dict] = []
    missing_slug: list[str] = []
    ok: list[str] = []

    for name in sorted(catalog):
        slug = WWE_SLUGS.get(name)
        if not slug:
            missing_slug.append(name)
            continue
        if name in MANUAL_WWE_HIGHLIGHTS:
            wwe_titles = MANUAL_WWE_HIGHLIGHTS[name]
        else:
            try:
                html = fetch_html(slug)
                wwe_titles = parse_career_highlights(html)
            except Exception as exc:  # noqa: BLE001
                mismatches.append({"name": name, "error": str(exc)})
                continue
        if not wwe_titles:
            mismatches.append(
                {"name": name, "slug": slug, "error": "no Career Highlights parsed"}
            )
            continue

        cat_counts = catalog_count_map(catalog[name])
        if cat_counts.get("ecw"):
            cat_counts = dict(cat_counts)
            cat_counts["world heavyweight"] = cat_counts.get(
                "world heavyweight", 0
            ) + cat_counts.pop("ecw")
        if name == "Bo Dallas" and cat_counts.get("wwe tag"):
            # Wyatt Sicks 태그는 WWE.com Bo Dallas Career Highlights 미표기
            cat_counts = dict(cat_counts)
            cat_counts.pop("wwe tag", None)
        wwe_counts = count_map(wwe_titles)
        # Undisputed WWE Champion (xN) 이 wwe championship 으로 잡히는 경우
        if cat_counts.get("undisputed wwe") and wwe_counts.get("wwe championship"):
            wwe_counts["undisputed wwe"] = max(
                wwe_counts.get("undisputed wwe", 0), wwe_counts.pop("wwe championship")
            )
        if cat_counts.get("undisputed wwe") and wwe_counts.get("undisputed"):
            wwe_counts["undisputed wwe"] = max(
                wwe_counts.get("undisputed wwe", 0), wwe_counts.pop("undisputed")
            )
        if cat_counts.get("undisputed tag") and wwe_counts.get("undisputed"):
            wwe_counts["undisputed tag"] = max(
                wwe_counts.get("undisputed tag", 0), wwe_counts.pop("undisputed")
            )
        if cat_counts.get("undisputed tag") and wwe_counts.get("wwe tag"):
            # Payback 2023 등: Undisputed + WWE Tag 동시 표기
            pass
        # 파서가 Women's IC를 intercontinental으로 쪼개는 경우 보정
        if "women's intercontinental" in cat_counts and wwe_counts.get(
            "intercontinental"
        ):
            wwe_counts["women's intercontinental"] = wwe_counts.pop("intercontinental")
        if "women's united states" in cat_counts and wwe_counts.get("united states"):
            wwe_counts["women's united states"] = wwe_counts.pop("united states")
        if "women's united states" in cat_counts and wwe_counts.get("women's"):
            wwe_counts["women's united states"] = max(
                wwe_counts.get("women's united states", 0), wwe_counts.pop("women's")
            )
        for garbled in list(wwe_counts):
            if "united states champion" in garbled and "women" in garbled:
                wwe_counts["women's united states"] = max(
                    wwe_counts.get("women's united states", 0), wwe_counts.pop(garbled)
                )
        if "wwe crown jewel" in cat_counts and wwe_counts.get("2024 wwe women's"):
            wwe_counts["wwe crown jewel"] = wwe_counts.pop("2024 wwe women's")
        for garbled in list(wwe_counts):
            if (
                "women" in garbled
                and "champion" in garbled
                and cat_counts.get("wwe women's")
            ):
                wwe_counts["wwe women's"] = max(
                    wwe_counts.get("wwe women's", 0), wwe_counts.pop(garbled)
                )
        for garbled in list(wwe_counts):
            if cat_counts.get("wwe crown jewel") and (
                "crown jewel" in garbled or garbled.startswith("2024 wwe")
            ):
                wwe_counts["wwe crown jewel"] = max(
                    wwe_counts.get("wwe crown jewel", 0), wwe_counts.pop(garbled)
                )
        if wwe_counts.get("women's") == 1 and not cat_counts.get("women's"):
            wwe_counts.pop("women's", None)
        all_keys = set(cat_counts) | set(wwe_counts)
        diff = {
            k: {"catalog": cat_counts.get(k, 0), "wwe": wwe_counts.get(k, 0)}
            for k in sorted(all_keys)
            if cat_counts.get(k, 0) != wwe_counts.get(k, 0)
            and k not in IGNORE_WWE_KEYS
            and not any(k.startswith(p) for p in IGNORE_WWE_KEYS)
            and k != "wwe"  # 범용 잔여 토큰
        }
        if diff:
            mismatches.append(
                {
                    "name": name,
                    "slug": slug,
                    "catalog_reigns": catalog[name],
                    "wwe_highlights": wwe_titles,
                    "diff": diff,
                }
            )
        else:
            ok.append(name)

    report = {
        "ok_count": len(ok),
        "mismatches": mismatches,
        "missing_slug": missing_slug,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    out_path = (
        Path(__file__).resolve().parents[1] / "reports" / "wwe_verify_report.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload, encoding="utf-8")
    sys.stdout.buffer.write(payload.encode("utf-8"))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
