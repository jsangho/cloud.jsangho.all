/**
 * `/api/manager/*` 프록시가 관리자 토큰을 실어 보내는지 고정한다.
 *
 * 백엔드가 이 경로를 관리자 JWT로 잠갔으므로 헤더 하나가 빠지면 관리자 화면이
 * 401이 된다. Route Handler 는 `next/server` 에 묶여 이 러너로 실행할 수 없어서
 * 소스를 읽어 검사한다. 실제 전달은 `requireAdmin` 이 만든 `authHeaders` 가 맡는다.
 *
 * ```bash
 * cd www && pnpm test:manager-auth
 * ```
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

function routeFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return routeFiles(path);
    return entry.name === "route.ts" ? [path] : [];
  });
}

/** `fetch(` 부터 그 호출을 닫는 괄호까지 — 옵션 객체가 여러 줄이라 줄 단위로는 못 본다. */
function managerFetchCalls(source: string): string[] {
  const calls: string[] = [];
  for (const match of source.matchAll(/fetch\(/g)) {
    let depth = 0;
    let end = match.index;
    for (; end < source.length; end += 1) {
      if (source[end] === "(") depth += 1;
      if (source[end] === ")" && --depth === 0) break;
    }
    const call = source.slice(match.index, end + 1);
    if (call.includes("/api/manager/")) calls.push(call);
  }
  return calls;
}

test("/api/manager 를 부르는 Route Handler 는 전부 authHeaders 를 보낸다", () => {
  const calls = routeFiles(join(process.cwd(), "app/api")).flatMap((file) =>
    managerFetchCalls(readFileSync(file, "utf8")).map((call) => ({ file, call })),
  );

  assert.ok(calls.length >= 7, `프록시 호출을 못 찾았다: ${calls.length}건`);
  for (const { file, call } of calls) {
    assert.match(call, /guard\.authHeaders/, `${file} 가 인증 헤더 없이 백엔드를 부른다`);
  }
});
