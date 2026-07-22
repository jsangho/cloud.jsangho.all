#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-.}"
PRIVATE_PEM="$OUT_DIR/jwt_private.pem"
PUBLIC_PEM="$OUT_DIR/jwt_public.pem"

if [[ -e "$PRIVATE_PEM" || -e "$PUBLIC_PEM" ]]; then
  echo "이미 존재함: $PRIVATE_PEM 또는 $PUBLIC_PEM — 기존 키를 덮어쓰지 않습니다." >&2
  echo "다른 출력 경로를 지정하거나(첫 인자로 디렉터리 전달) 기존 파일을 정리한 뒤 다시 실행하세요." >&2
  exit 1
fi

openssl genrsa -out "$PRIVATE_PEM" 2048
openssl rsa -in "$PRIVATE_PEM" -pubout -out "$PUBLIC_PEM"

escape_pem() {
  sed ':a;N;$!ba;s/\n/\\n/g' "$1"
}

echo
echo "PEM 파일 생성 완료:"
echo "  $PRIVATE_PEM  → auth 전용 .env의 JWT_PRIVATE_KEY로"
echo "  $PUBLIC_PEM   → 그 외 컨테이너 .env의 JWT_PUBLIC_KEY로"
echo
echo "--- .env에 그대로 붙여넣을 값 (개행이 \\n으로 이스케이프됨) ---"
echo
printf 'JWT_PRIVATE_KEY=%s\n' "$(escape_pem "$PRIVATE_PEM")"
echo
printf 'JWT_PUBLIC_KEY=%s\n' "$(escape_pem "$PUBLIC_PEM")"
echo
echo "PEM 원본은 *.pem이 .gitignore에 이미 등록되어 있어 커밋되지 않습니다."
echo "위 값을 .env에 옮긴 뒤에는 이 PEM 파일을 삭제해도 됩니다: rm $PRIVATE_PEM $PUBLIC_PEM"
