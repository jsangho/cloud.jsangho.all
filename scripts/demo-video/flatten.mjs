/** 정지 컷을 25fps 프레임으로 펼쳐 하드링크로 깐다 — concat demuxer의 duration이 믿을 게 못 돼서 */
import { readFileSync, mkdirSync, rmSync, linkSync } from "node:fs";

const DIR = `${process.env.DEMO_OUT ?? "/tmp/kayfabe-demo"}/`;
const FPS = 25;
const FLAT = `${DIR}flat`;
rmSync(FLAT, { recursive: true, force: true });
mkdirSync(FLAT, { recursive: true });

const lines = readFileSync(`${DIR}frames.txt`, "utf8").trim().split("\n");
let out = 0;
let carry = 0; // 반올림 오차를 다음 컷으로 넘겨 전체 길이를 유지한다
for (let i = 0; i < lines.length; i++) {
  const m = lines[i].match(/^file '(.+)'$/);
  if (!m) continue;
  const d = Number(lines[i + 1]?.match(/^duration ([\d.]+)$/)?.[1] ?? 0);
  if (!d) continue;
  const exact = d * FPS + carry;
  const n = Math.max(1, Math.round(exact));
  carry = exact - n;
  for (let k = 0; k < n; k++) linkSync(m[1], `${FLAT}/${String(out++).padStart(6, "0")}.png`);
}
console.log(`flat frames: ${out} → ${(out / FPS).toFixed(2)}s`);
