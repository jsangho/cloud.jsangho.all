---
name: auto-memory-mechanics
description: "How this memory/ directory itself loads — MEMORY.md's 200-line auto-load cap, per-topic files read on demand, enable/disable switches, and the repo-side mirror that is NOT auto-loaded"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 039f9b26-5d52-4757-8a32-25d51381cebc
  modified: 2026-07-29T02:50:40.692Z
---

**로딩 규칙**

| 대상 | 언제 로드되나 | 제한 |
|------|---------------|------|
| `MEMORY.md` | 매 세션 시작 시 시스템 프롬프트에 자동 로드 | **첫 200줄까지만** |
| `MEMORY.md` 200줄 초과분 | 자동 로드 안 됨 | 필요할 때 직접 읽어야 함 |
| 개별 메모 파일 (`*.md`) | 필요할 때만 | 시작 시 전부 로드하지 않음 |
| `CLAUDE.md` | 길이와 무관하게 전체 로드 | 200줄 제한 **적용 안 됨** |

200줄 제한은 자동 메모리 전용 설정이다. `CLAUDE.md` 와 헷갈리지 말 것 — 다만 `CLAUDE.md` 도 200줄 이내로 유지하면 지시사항 준수율이 올라간다.

**설계 결론:** `MEMORY.md` 는 인덱스로만 쓴다. 본문을 넣으면 200줄을 넘기고 넘긴 부분은 안 읽힌다. 한 줄 요약(훅)이 실제 검색 인터페이스이므로 — Claude는 그 한 줄만 보고 파일을 열지 말지 결정한다 — "디버깅 관련" 같은 뭉뚱그린 문구 대신 구체적으로 쓴다. 상세는 개별 파일에 두면 필요할 때만 읽히므로 길어도 비용이 없다. `MEMORY.md` 가 200줄에 가까워지면 요약 줄을 개별 파일로 밀어 넣고 인덱스 줄만 남긴다. (2026-07-29 기준 5~7줄 수준이라 여유 많음)

**활성화/비활성화:** 기본 활성화. 끄려면 `export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` 또는 `settings.json` 에 `"autoMemoryEnabled": false`. 다시 켜려면 환경변수를 지우거나 `true` 로. `/memory` 명령어 안의 토글로도 켜고 끌 수 있다.

**서브에이전트:** 서브에이전트도 자체 자동 메모리를 유지할 수 있다. 커스텀 서브에이전트 설정에서 활성화하면 각 에이전트가 독립적인 메모리를 쌓는다 — 메인 세션 메모리와 공유되지 않으므로, 에이전트별로 다른 맥락을 축적시키고 싶을 때 쓴다.

**경로 — 심볼릭 링크로 하나로 합침 (2026-07-29):**

실체는 **저장소 안**에 하나만 있다. 홈 쪽 경로는 그것을 가리키는 심볼릭 링크다.

```
C:\Users\hi\.claude\projects\--wsl-localhost-Ubuntu-home-ho-projects-cloud-jsangho-all\memory
   → (symlink) \\wsl.localhost\Ubuntu\home\ho\projects\cloud.jsangho.all
                 \.claude\projects\--wsl-localhost-Ubuntu-home-ho-projects-cloud-jsangho-all\memory
```

- 따라서 **복사·동기화 작업이 필요 없다.** 어느 쪽 경로로 쓰든 같은 파일이고, git에 그대로 추적된다.
- 링크 생성은 **관리자 권한**이 필요해서 사용자가 관리자 PowerShell에서 1회 실행했다.
  (개발자 모드가 켜져 있어도 UNC 경로 대상 링크에는 적용되지 않는다.)
- **WSL이 꺼져 있으면 메모리를 못 읽는다.** 세션 시작 시 메모리가 통째로 비어 보이면 이걸 먼저 의심한다.
- 링크가 풀렸는지 확인: `Get-Item <홈경로> | Select-Object LinkType, Target`

디렉터리 이름은 작업 디렉터리 경로를 인코딩한 것이다: `\\wsl.localhost\Ubuntu\home\ho\projects\cloud.jsangho.all` → `--wsl-localhost-Ubuntu-home-ho-projects-cloud-jsangho-all`. 같은 홈 디렉터리에 `--wsl-localhost-Ubuntu-home-ho-cloud-jsangho-all`(옛 경로), `--wsl-localhost-Ubuntu-home-ho-projects`(상위 폴더) 같은 헷갈리는 이름이 함께 있으니 **`projects-cloud-jsangho-all` 로 끝나는 것**을 고른다.

**⚠ 이 디렉터리는 git에 커밋된다.** 심볼릭 링크 이후 메모리가 곧 저장소 파일이므로, 여기에 메모를 쓸 때
비밀번호·API 키·토큰 같은 자격 증명을 **절대 값으로 적지 않는다**. 키 이름과 어느 `.env` 에 있는지만 적는다.
(2026-07-29에 `server_remote_access_jsangho.md` 의 pgvector/pgAdmin 비밀번호를 이 이유로 참조 형태로 치환했다.
`CLAUDE.md` "키·비밀번호를 코드나 문서에 하드코딩하지 않는다" 와 같은 규칙이다.)

**형식 규칙 (2026-07-29 통일):** 한 파일 = 한 사실 + frontmatter. 주제별 묶음(`debugging.md`, `patterns.md` 등)으로 뭉뚱그리지 않는다 — 자동 메모리가 스스로 메모를 쓸 때 만드는 형식과 맞추기 위함이다.
