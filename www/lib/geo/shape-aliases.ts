/**
 * DB가 적는 나라 이름 → 지도 도형 이름.
 *
 * **경계 데이터와 로스터 CSV는 서로를 모른다.** Natural Earth는 공식 국가만
 * 그리므로 `England`·`Scotland`라는 도형이 없고(둘 다 United Kingdom의 일부),
 * 미국은 `United States of America`로 적는다. 이 표가 없으면 **지도가 조용히
 * 아무 색도 칠하지 않는다** — 가장 큰 두 칸이 바로 그 자리다.
 *
 * 목록(오른쪽)은 DB 이름 그대로 보여 준다. 잉글랜드와 스코틀랜드를 합치는 것은
 * **지도를 그리기 위한 타협**이지 데이터의 사실이 아니라서, 화면이 그 사실을
 * 함께 적는다.
 */
export const COUNTRY_SHAPE_ALIASES: Record<string, string> = {
  "United States": "United States of America",
  England: "United Kingdom",
  Scotland: "United Kingdom",
  Wales: "United Kingdom",
  "Northern Ireland": "United Kingdom",
  "Bosnia and Herzegovina": "Bosnia and Herz.",
  "Dominican Republic": "Dominican Rep.",
};

/** 지도에서 이 이름으로 찾는다. 별칭이 없으면 DB 이름 그대로다. */
export function shapeNameOf(country: string): string {
  return COUNTRY_SHAPE_ALIASES[country] ?? country;
}
