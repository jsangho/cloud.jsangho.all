---
name: data-analyzer
description: 데이터 분석 작업을 수행합니다. CSV, JSON 파일 분석에 사용하세요.
tools:
  - Read       # 파일 읽기
  - Bash       # 분석 스크립트 실행
disallowedTools:
  - Write      # 파일 쓰기 차단
model: sonnet  # 사용할 모델
permissionMode: acceptEdits  # 파일 편집 자동 승인
maxTurns: 20   # 최대 실행 턴 수 제한
skills:        # 시작 시 사전 주입할 스킬
  - api-conventions
memory: user   # 세션 간 지속 메모리 (user/project/local)
isolation: worktree  # 독립 Git Worktree에서 실행
---
