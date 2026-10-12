"""TopoJSON → 정적 SVG path. **지도 라이브러리를 쓰지 않기 위한 빌드 도구다.**

출신 분포 지도 둘(미국 주 · 세계)을 그리는데, Recharts에는 지도가 없고
`react-simple-maps`+topojson을 넣으면 의존성이 둘 는다. DESIGN.md §16이 차트
라이브러리를 고른 이유 자체가 "새 의존성을 더하지 않는다"라서, **투영을 여기서
미리 계산해 평범한 `<path d="...">` 문자열로 떨군다.** 화면은 `fill`만 바꾼다.

**한 번 돌리고 결과를 커밋하는 도구다** — 앱은 이 스크립트를 부르지 않는다.
경계가 바뀔 일이 없으니 런타임에 계산할 이유도 없다.

입력(둘 다 퍼블릭 도메인 경계 데이터):

    https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json        (US Census)
    https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json (Natural Earth)

출력:

    www/lib/geo/us-states-paths.ts
    www/lib/geo/world-countries-paths.ts

실행:

    python3 scripts/build_geo_paths.py <states-10m.json> <countries-110m.json>
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

#: 좌표를 적는 소수 자릿수. 1이면 1/10 user unit이고, 1000 폭 지도에서 눈에 안 띈다.
#: 0으로 내리면 파일이 20% 더 작아지는 대신 작은 섬이 각져 보인다.
_PRECISION = 1

#: 이 면적(제곱 user unit) 미만인 고리는 버린다. 1000폭 기준 0.5는 한 점 수준이다.
_MIN_RING_AREA = 0.5

#: Douglas-Peucker 허용 오차(user unit). **파일 크기를 정하는 손잡이다.**
#: 1000폭 지도에서 0.7이면 화면 1px 안쪽이라 눈에 안 띄고, 점 수가 1/4로 준다.
#: 세계 지도는 더 작게 그려지고(폭 ~700px) 나라가 176개라 거칠게 깎는다 —
#: 그러지 않으면 **칠하지도 않을 해안선이 번들의 대부분**이 된다.
_TOLERANCE_US = 0.7
_TOLERANCE_WORLD = 1.6


def decode_arcs(topology: dict) -> list[list[tuple[float, float]]]:
    """TopoJSON의 델타 인코딩 arc를 경위도 좌표열로 푼다."""
    sx, sy = topology["transform"]["scale"]
    tx, ty = topology["transform"]["translate"]
    out: list[list[tuple[float, float]]] = []
    for arc in topology["arcs"]:
        x = y = 0
        points: list[tuple[float, float]] = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * sx + tx, y * sy + ty))
        out.append(points)
    return out


def ring_of(arc_indexes: list[int], arcs: list[list[tuple[float, float]]]):
    """arc 인덱스 목록 → 고리 하나. 음수 인덱스는 그 arc를 뒤집어 쓴다는 뜻이다."""
    ring: list[tuple[float, float]] = []
    for index in arc_indexes:
        arc = arcs[~index][::-1] if index < 0 else arcs[index]
        ring.extend(arc if not ring else arc[1:])
    return ring


def rings_of(geometry: dict, arcs) -> list[list[tuple[float, float]]]:
    kind = geometry["type"]
    if kind == "Polygon":
        return [ring_of(r, arcs) for r in geometry["arcs"]]
    if kind == "MultiPolygon":
        return [ring_of(r, arcs) for poly in geometry["arcs"] for r in poly]
    return []


def conic_equal_area(lon0: float, lat0: float, p1: float, p2: float):
    """Albers 등적원뿔 투영 하나. d3의 `geoConicEqualArea`와 같은 식이다."""
    r1, r2 = math.radians(p1), math.radians(p2)
    n = (math.sin(r1) + math.sin(r2)) / 2
    c = math.cos(r1) ** 2 + 2 * n * math.sin(r1)
    rho0 = math.sqrt(c - 2 * n * math.sin(math.radians(lat0))) / n

    def project(lon: float, lat: float) -> tuple[float, float]:
        theta = n * math.radians(lon - lon0)
        rho = math.sqrt(max(c - 2 * n * math.sin(math.radians(lat)), 0.0)) / n
        # **y를 뒤집는다.** 이 식은 북쪽이 +y인데 SVG는 y가 아래로 자란다.
        # 뒤집지 않으면 플로리다가 메인주 위에 그려진다 (실측).
        return rho * math.sin(theta), -(rho0 - rho * math.cos(theta))

    return project


def equirectangular(lon: float, lat: float) -> tuple[float, float]:
    return lon, -lat


def split_antimeridian(
    ring: list[tuple[float, float]],
) -> list[list[tuple[float, float]]]:
    """날짜변경선을 넘는 고리를 조각으로 자른다.

    **자르지 않으면 지도를 가로지르는 줄무늬가 생긴다.** 등장방형에서 경도
    +179와 -179는 화면의 양 끝인데, 폴리곤은 그 둘을 직선으로 잇는다 — 러시아
    (추코트카)와 피지가 실제로 그래서 **지도 전체 폭을 덮는 띠 세 개**가 그려져
    있었다(2026-10-12 실측).

    조각은 경계(±180)에 점을 하나 끼워 닫는다. 그래야 잘린 자리가 화면 가장자리에
    딱 붙고, 안쪽으로 비스듬한 빈 삼각형이 생기지 않는다.
    """
    pieces: list[list[tuple[float, float]]] = [[]]
    for point in ring:
        current = pieces[-1]
        if current:
            prev_lon, prev_lat = current[-1]
            lon, lat = point
            if abs(lon - prev_lon) > 180:
                # 두 점 사이 어디서 선을 넘는가 — 위도는 선형 보간으로 잡는다.
                east = 180.0 if prev_lon > 0 else -180.0
                gap = (360 - abs(lon - prev_lon)) or 1.0
                ratio = (abs(east - prev_lon)) / gap
                crossing_lat = prev_lat + (lat - prev_lat) * min(max(ratio, 0.0), 1.0)
                current.append((east, crossing_lat))
                pieces.append([(-east, crossing_lat)])
        pieces[-1].append(point)
    return [piece for piece in pieces if len(piece) >= 3]


def fit(
    shapes: dict[str, list[list[tuple[float, float]]]],
    *,
    box: tuple[float, float, float, float],
) -> dict[str, list[list[tuple[float, float]]]]:
    """투영된 좌표를 `box`(x, y, w, h) 안에 비율 유지로 맞춘다."""
    xs = [p[0] for rings in shapes.values() for ring in rings for p in ring]
    ys = [p[1] for rings in shapes.values() for ring in rings for p in ring]
    if not xs:
        return shapes
    x0, y0, w, h = box
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    scale = min(w / span_x, h / span_y) if span_x and span_y else 1.0
    off_x = x0 + (w - span_x * scale) / 2 - min(xs) * scale
    off_y = y0 + (h - span_y * scale) / 2 - min(ys) * scale
    return {
        key: [[(p[0] * scale + off_x, p[1] * scale + off_y) for p in ring] for ring in rings]
        for key, rings in shapes.items()
    }


def simplify(ring: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker. **이 함수가 번들 크기를 정한다.**

    경계 데이터는 화면 해상도보다 훨씬 촘촘하다 — 1000폭 지도에서 1px보다 작은
    굴곡은 그려도 보이지 않는데 좌표는 그대로 번들에 실린다. 실측으로 이 한 줄이
    266KB를 60KB 아래로 끌어내렸다.
    """
    if len(ring) < 3:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        start, end = stack.pop()
        ax, ay = ring[start]
        bx, by = ring[end]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        worst, worst_at = -1.0, -1
        for i in range(start + 1, end):
            px, py = ring[i]
            if norm == 0:
                dist = math.hypot(px - ax, py - ay)
            else:
                dist = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if dist > worst:
                worst, worst_at = dist, i
        if worst > tolerance and worst_at > 0:
            keep[worst_at] = True
            stack.append((start, worst_at))
            stack.append((worst_at, end))
    return [p for p, k in zip(ring, keep, strict=True) if k]


def ring_area(ring: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def to_path(
    rings: list[list[tuple[float, float]]],
    *,
    tolerance: float,
    min_area: float = _MIN_RING_AREA,
) -> str:
    parts: list[str] = []
    for ring in rings:
        if len(ring) < 3 or ring_area(ring) < min_area:
            continue
        ring = simplify(ring, tolerance)
        if len(ring) < 3:
            continue
        pts = [f"{round(x, _PRECISION)},{round(y, _PRECISION)}" for x, y in ring]
        # 연속으로 같은 점이 나오면 버린다 — 반올림이 만든 중복이다.
        deduped = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(deduped) < 3:
            continue
        parts.append("M" + "L".join(deduped) + "Z")
    return "".join(parts)


#: `states-10m`에는 주 50개 + DC 말고 **해외 영토도 들어 있다**(괌 lon 144 ·
#: 아메리칸사모아 lon -170). 그것들을 본토와 같은 원뿔 투영에 넣으면 좌표가
#: 수십 배로 튀어 **본토가 화면 한구석에 뭉개진다** — 실측으로 48주가 폭 150px
#: 안에 들어갔다. 그래서 그릴 대상을 명시한다.
_SKIP_US = frozenset(
    {
        "Puerto Rico",
        "Guam",
        "American Samoa",
        "United States Virgin Islands",
        "Commonwealth of the Northern Mariana Islands",
    }
)


def build_us(topo: dict) -> list[dict]:
    """미국 주 — Albers USA 합성 (알래스카·하와이는 축소해 왼쪽 아래에 둔다)."""
    arcs = decode_arcs(topo)
    lower48 = conic_equal_area(-96, 37.5, 29.5, 45.5)
    alaska = conic_equal_area(-152, 60, 55, 65)
    hawaii = conic_equal_area(-157, 20, 8, 18)

    groups: dict[str, dict[str, list]] = {"main": {}, "ak": {}, "hi": {}}
    names: dict[str, str] = {}
    for geo in topo["objects"]["states"]["geometries"]:
        name = geo["properties"]["name"]
        if name in _SKIP_US:
            continue
        rings = rings_of(geo, arcs)
        if not rings:
            continue
        which = "ak" if name == "Alaska" else "hi" if name == "Hawaii" else "main"
        project = alaska if which == "ak" else hawaii if which == "hi" else lower48
        groups[which][name] = [[project(lon, lat) for lon, lat in ring] for ring in rings]
        names[name] = name

    placed = {
        **fit(groups["main"], box=(0, 0, 1000, 620)),
        # 인셋 자리는 **본토 폴리곤과 겹치지 않게** 실측해서 잡았다 — 애리조나
        # 남서쪽 끝이 (208, 457)까지 내려온다.
        **fit(groups["ak"], box=(8, 472, 185, 145)),
        **fit(groups["hi"], box=(240, 545, 105, 55)),
    }
    return [
        {"id": name, "name": name, "d": path}
        for name in sorted(placed)
        if (path := to_path(placed[name], tolerance=_TOLERANCE_US))
    ]


def build_world(topo: dict) -> list[dict]:
    """세계 — 등장방형. 남극은 뺀다(사람이 안 살고 아래쪽 1/4을 먹는다)."""
    arcs = decode_arcs(topo)
    shapes: dict[str, list] = {}
    for geo in topo["objects"]["countries"]["geometries"]:
        name = geo["properties"]["name"]
        if name == "Antarctica":
            continue
        rings = rings_of(geo, arcs)
        if not rings:
            continue
        shapes[name] = [
            [equirectangular(lon, max(lat, -60)) for lon, lat in piece]
            for ring in rings
            for piece in split_antimeridian(ring)
        ]
    placed = fit(shapes, box=(0, 0, 1000, 500))
    return [
        {"id": name, "name": name, "d": path}
        for name in sorted(placed)
        if (path := to_path(placed[name], tolerance=_TOLERANCE_WORLD, min_area=3.0))
    ]


_HEADER = """// **생성된 파일이다 — 손으로 고치지 않는다.**
// `scripts/build_geo_paths.py`가 퍼블릭 도메인 경계 데이터(%s)를 투영해 찍는다.
// 지도 라이브러리를 더하지 않으려고 투영을 빌드 시점에 끝낸 결과다.

export type GeoShape = {
  /** 색을 붙일 때 쓰는 키. 데이터 쪽 이름과 이 값이 맞아야 한다. */
  id: string;
  name: string;
  d: string;
};

export const %s_VIEWBOX = "%s";

export const %s: GeoShape[] = %s;
"""


def emit(path: Path, shapes: list[dict], *, const: str, viewbox: str, source: str) -> None:
    body = "[\n" + "".join(
        f'  {{ id: {json.dumps(s["id"])}, name: {json.dumps(s["name"])}, d: {json.dumps(s["d"])} }},\n'
        for s in shapes
    ) + "]"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HEADER % (source, const, viewbox, const, body), encoding="utf-8")
    print(f"{path}  {len(shapes)}개 · {path.stat().st_size // 1024}KB")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    root = Path(__file__).resolve().parents[1] / "www" / "lib" / "geo"
    us = build_us(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    world = build_world(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    emit(
        root / "us-states-paths.ts",
        us,
        const="US_STATES",
        viewbox="0 0 1000 620",
        source="us-atlas@3 states-10m, US Census",
    )
    emit(
        root / "world-countries-paths.ts",
        world,
        const="WORLD_COUNTRIES",
        viewbox="0 0 1000 500",
        source="world-atlas@2 countries-110m, Natural Earth",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
