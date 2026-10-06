#!/usr/bin/env bash
# 팀 www(super-sub.cloud)를 포트폴리오 www(cloud.jsangho.all)로 네임스페이스해 옮긴다.
# 되풀이해 돌릴 수 있다 — 목적지를 먼저 지우고 다시 복사한다.
set -euo pipefail

SRC=/home/ho/projects/super-sub.cloud/www
DST=/home/ho/projects/cloud.jsangho.all/www

RS=(rsync -a --exclude '*.test.ts' --exclude '*.test.tsx' --exclude '__tests__')

echo "── 지우고 다시 — 이전 복사본"
rm -rf "$DST/supersub" "$DST/app/(supersub)" "$DST/app/api/supersub"
mkdir -p "$DST/supersub" "$DST/app/(supersub)/s" "$DST/app/api/supersub"

echo "── 비라우트 코드 → supersub/"
"${RS[@]}" "$SRC/src/components" "$DST/supersub/"
"${RS[@]}" "$SRC/src/lib"        "$DST/supersub/"
"${RS[@]}" "$SRC/src/server"     "$DST/supersub/"
cp "$SRC/src/proxy.ts"           "$DST/supersub/proxy.ts"
cp "$SRC/src/app/globals.css"    "$DST/supersub/globals.css"

echo "── 페이지 → app/(supersub)/s/"
for d in '(app)' login signup admin c; do
  "${RS[@]}" "$SRC/src/app/$d" "$DST/app/(supersub)/s/"
done
cp "$SRC/src/app/page.tsx"   "$DST/app/(supersub)/s/page.tsx"
cp "$SRC/src/app/layout.tsx" "$DST/app/(supersub)/s/layout.tsx"

echo "── API → app/api/supersub/"
"${RS[@]}" "$SRC/src/app/api/" "$DST/app/api/supersub/"

echo "── 공개 자산 → public/ (이름 충돌 0건을 확인하고 옮긴다)"
"${RS[@]}" --ignore-existing "$SRC/public/" "$DST/public/"

echo "── 임포트 재작성: @/ → @/supersub/"
# 포트폴리오의 @/* 는 ./* 를 가리키고 팀의 @/* 는 ./src/* 를 가리킨다.
# 임포트 구문 안에서만 바꾼다 — 주석·문자열의 @/ 는 건드리지 않는다.
mapfile -d '' FILES < <(find "$DST/supersub" "$DST/app/(supersub)" "$DST/app/api/supersub" \
  -type f \( -name '*.ts' -o -name '*.tsx' \) -print0)
printf '%s\0' "${FILES[@]}" | xargs -0 sed -i -E \
  -e "s#(from +['\"])@/#\1@/supersub/#g" \
  -e "s#(import\(['\"])@/#\1@/supersub/#g" \
  -e "s#(require\(['\"])@/#\1@/supersub/#g" \
  -e "s#(vi\.mock\(['\"])@/#\1@/supersub/#g"

# 루트 레이아웃의 `./globals.css` 는 supersub/ 로 옮겼으므로 별칭으로 가리킨다.
sed -i 's#import "./globals.css";#import "@/supersub/globals.css";#' "$DST/app/(supersub)/s/layout.tsx"

echo "── 결과"
echo "  supersub/            $(find "$DST/supersub" -type f | wc -l) 개"
echo "  app/(supersub)/      $(find "$DST/app/(supersub)" -type f | wc -l) 개"
echo "  app/api/supersub/    $(find "$DST/app/api/supersub" -type f | wc -l) 개"
echo "  남은 날 @/ 임포트     $(grep -rhoE "from +['\"]@/(components|lib|server)/" "$DST/supersub" "$DST/app/(supersub)" "$DST/app/api/supersub" 2>/dev/null | wc -l) 건 (0 이어야 한다)"
