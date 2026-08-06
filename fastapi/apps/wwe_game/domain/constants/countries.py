"""국가 25개와 권역 매핑 (하네스 §3-D14).

**이벤트는 권역에 붙고 국가는 서술 슬롯이다.** 국가마다 전용 카드를 만들면 25 × 5장이
되어 덱 목표(100~120장)를 지역 카드만으로 채우게 된다. 그래서 카드는 권역 6개에만 붙고,
국가는 `{venue}`·`{crowd}` 슬롯과 화면 표시에만 쓴다.

한국은 유일한 국가 단위 예외다 — 자체 권역 `KR`을 갖는다. 예외를 늘리면 결국
"국가당 5장"으로 돌아가 이 구조의 취지가 사라진다.

`Country`가 `wrestler_identity.py`가 아니라 여기 있는 이유: 25개 목록과 권역 매핑은
같이 움직이는 하나의 데이터다. 열거형만 떼어 놓으면 국가를 추가할 때 두 파일을 고쳐야
하고, 매핑을 빠뜨려도 아무도 못 잡는다. 하네스 §6 배치와 다른 점이다.
"""

from __future__ import annotations

from enum import StrEnum

from wwe_game.domain.exceptions import UnknownCountryError


class Region(StrEnum):
    """이벤트 카드가 붙는 단위. 카드 코드의 접두사와 같다."""

    NA = "na"
    EU = "eu"
    JP = "jp"
    LATAM = "latam"
    OCE = "oce"
    KR = "kr"


class Country(StrEnum):
    """출신 국가. 값은 ISO 3166-1 alpha-2."""

    # 북미
    US = "US"
    CA = "CA"
    # 유럽
    GB = "GB"
    IE = "IE"
    DE = "DE"
    FR = "FR"
    ES = "ES"
    IT = "IT"
    PL = "PL"
    SE = "SE"
    RU = "RU"
    GR = "GR"
    # 일본
    JP = "JP"
    # 라틴아메리카
    MX = "MX"
    BR = "BR"
    AR = "AR"
    CL = "CL"
    CO = "CO"
    PR = "PR"
    DO = "DO"
    # 오세아니아
    AU = "AU"
    NZ = "NZ"
    TO = "TO"
    FJ = "FJ"
    # 한국 (국가 단위 예외)
    KR = "KR"


COUNTRY_REGION: dict[Country, Region] = {
    Country.US: Region.NA,
    Country.CA: Region.NA,
    Country.GB: Region.EU,
    Country.IE: Region.EU,
    Country.DE: Region.EU,
    Country.FR: Region.EU,
    Country.ES: Region.EU,
    Country.IT: Region.EU,
    Country.PL: Region.EU,
    Country.SE: Region.EU,
    Country.RU: Region.EU,
    Country.GR: Region.EU,
    Country.JP: Region.JP,
    Country.MX: Region.LATAM,
    Country.BR: Region.LATAM,
    Country.AR: Region.LATAM,
    Country.CL: Region.LATAM,
    Country.CO: Region.LATAM,
    Country.PR: Region.LATAM,
    Country.DO: Region.LATAM,
    Country.AU: Region.OCE,
    Country.NZ: Region.OCE,
    Country.TO: Region.OCE,
    Country.FJ: Region.OCE,
    Country.KR: Region.KR,
}

# 매핑 없는 국가를 고를 수 없어야 한다 (하네스 §11-16). 런타임에 빠뜨리면 이벤트 조건이
# 조용히 통과해 버리므로, 임포트 시점에 터뜨린다.
_unmapped = set(Country) - set(COUNTRY_REGION)
if _unmapped:  # pragma: no cover - 임포트 시 구조 검증
    raise RuntimeError(f"권역 매핑이 없는 국가: {sorted(c.value for c in _unmapped)}")


def region_of(country: Country) -> Region:
    """국가가 속한 권역. 이벤트 추첨의 `regions` 조건이 이 값을 본다."""
    try:
        return COUNTRY_REGION[country]
    except KeyError as exc:
        raise UnknownCountryError(
            f"권역에 매핑되지 않은 국가입니다: {country}"
        ) from exc
