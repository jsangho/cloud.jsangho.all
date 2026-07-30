#!/bin/bash
# stdin에서 JSON 입력을 읽음
INPUT=$(cat)

# 수정하려는 파일 경로 추출
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // ""')

# 보호할 패턴 목록
PROTECTED=(
  ".env"
  ".env.*"
  "*.key"
  "secrets.*"
)

for PATTERN in "${PROTECTED[@]}"; do
  if [[ "$FILE_PATH" == *$PATTERN* ]]; then
    # 종료 코드 2: 작업 차단, 메시지를 Claude에게 전달
    echo "보안 정책: $FILE_PATH 파일은 수정할 수 없습니다." >&2
    exit 2
  fi
done

exit 0
