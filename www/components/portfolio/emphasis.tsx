/**
 * `**강조**` 만 해석하는 최소 인라인 렌더러.
 *
 * 케이스 본문은 긴 한국어 문장이고, 그 안에서 **한 구절**만 굵어져야 읽는 눈이
 * 멈출 자리를 찾는다. 그렇다고 마크다운 파서를 들이지 않는다 — 필요한 문법이
 * 하나뿐인데 의존성을 더하면 그 파서가 허용하는 나머지 문법(링크·이미지·HTML)이
 * 전부 따라 들어온다.
 *
 * 그래서 `**` 로 쪼개 홀수 번째만 굵게 한다. 짝이 안 맞으면 마지막 조각이 그냥
 * 평문으로 남는다 — 깨지는 대신 안 굵어진다.
 */
export function Emphasis({ text }: { text: string }) {
  const parts = text.split("**");

  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <strong key={`${index}-${part}`} className="font-semibold text-foreground">
            {part}
          </strong>
        ) : (
          part
        ),
      )}
    </>
  );
}
