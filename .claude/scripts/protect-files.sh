#!/bin/bash
# PreToolUse(Write|Edit) 훅 — 비밀 파일 수정을 차단한다.
#
# 종료 코드 2 = 차단(메시지가 Claude에게 전달됨), 0 = 허용.
# JSON 파서가 없으면 경고만 남기고 허용한다 — 차단하면 모든 편집이 막힌다.

INPUT=$(cat)

# 파일 경로 추출: jq → node → python3 순으로 시도 (이 저장소는 jq가 없는 환경도 있음)
extract_path() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""'
  elif command -v node >/dev/null 2>&1; then
    printf '%s' "$INPUT" | node -e '
      let s = "";
      process.stdin.on("data", (d) => (s += d));
      process.stdin.on("end", () => {
        try {
          const i = (JSON.parse(s).tool_input) || {};
          process.stdout.write(i.file_path || i.path || "");
        } catch { process.stdout.write(""); }
      });'
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    i = json.load(sys.stdin).get("tool_input") or {}
    sys.stdout.write(i.get("file_path") or i.get("path") or "")
except Exception:
    sys.stdout.write("")'
  else
    printf '__NO_PARSER__'
  fi
}

FILE_PATH=$(extract_path)

if [ "$FILE_PATH" = "__NO_PARSER__" ]; then
  echo "protect-files: jq/node/python3 가 없어 경로를 확인할 수 없습니다 (허용)." >&2
  exit 0
fi

[ -z "$FILE_PATH" ] && exit 0

BASE=$(basename "$FILE_PATH")

# .env.example 은 키 목록 템플릿이라 편집을 허용한다 (루트 CLAUDE.md 환경 변수 규칙).
# .env.<대상>.example 도 같은 템플릿이므로 함께 허용한다.
case "$BASE" in
  .env.example | .env.sample | .env.template) exit 0 ;;
  .env.*.example | .env.*.sample | .env.*.template) exit 0 ;;
esac

# 차단 대상: .env / .env.<환경> / *.key / *.pem / secrets.*
case "$BASE" in
  .env | .env.*) BLOCKED=1 ;;
  *.key | *.pem) BLOCKED=1 ;;
  secrets.*) BLOCKED=1 ;;
  *) BLOCKED=0 ;;
esac

if [ "$BLOCKED" = "1" ]; then
  echo "보안 정책: $FILE_PATH 는 수정할 수 없습니다 (비밀 파일)." >&2
  echo "필요하면 사용자에게 직접 수정을 요청하세요." >&2
  exit 2
fi

exit 0
