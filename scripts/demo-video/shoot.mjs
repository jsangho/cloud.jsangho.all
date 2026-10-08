/**
 * KAYFABE 시연영상 촬영 — _docs/kayfabe-demo-video-flow.md 의 숏 리스트를 그대로 따른다.
 *
 * 실시간 녹화가 아니라 **프레임 단위 결정적 촬영**이다. 한 프레임마다 스크롤·커서·자막을
 * 직접 세팅하고 스크린샷을 찍어 모아 붙인다. 그래서 커서가 순간이동하지 않고(문서 §4),
 * 길이가 정확히 90초로 떨어진다. 대신 장식 애니메이션(티커·LIVE 맥박)은 멈춰 둔다 —
 * 캡처가 실시간보다 느려서 그대로 두면 재생할 때 티커만 6배속으로 흐른다.
 */
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";

const CHROME = process.env.CHROME_PATH ?? "/home/ho/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome";
const B = process.env.SITE ?? "https://kayfabe.jsangho.cloud";
// 프레임·목록은 저장소 밖에 쌓는다 — DEMO_OUT 로 지정한다
const DIR = `${process.env.DEMO_OUT ?? "/tmp/kayfabe-demo"}/`;
const FRAMES = `${DIR}frames`;
const FPS = 25;

rmSync(FRAMES, { recursive: true, force: true });
mkdirSync(FRAMES, { recursive: true });

// ── 자막·카드 오버레이 (페이지 안에 직접 그린다 — 사이트가 쓰는 Pretendard/Oswald를 그대로 쓴다)
const OVERLAY = () => {
  // Next.js 하이드레이션이 body에 끼워 넣은 노드를 걷어내므로, 매번 있는지 보고 다시 세운다
  const install = () => {
    if (document.getElementById("__demo_layer")) return;
    const css = document.createElement("style");
    css.id = "__demo_css";
    css.textContent = `
      /* 전부 멈추면 모달 같은 등장 애니메이션이 첫 키프레임(투명)에 갇힌다 —
         멈추는 것은 끝나지 않는 장식 모션뿐이고, 그건 JS로 이름을 보고 고른다 (freezeDecor) */
      html { scroll-behavior: auto !important; }
      ::-webkit-scrollbar { width: 0 !important; height: 0 !important; }

      #__demo_layer {
        position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;
        font-family: 'Pretendard Variable', Pretendard, system-ui, sans-serif;
        color: #1c1917;
      }
      #__demo_sub {
        position: absolute; left: 0; right: 0; bottom: 0; min-height: var(--sub-h, 152px);
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
        background: #faf9f6;
        border-top: 1px solid rgba(28,25,23,0.12);
        padding: 24px 80px 28px;
        opacity: 0;
      }
      /* F컷처럼 읽어야 할 블록이 화면 아래쪽에 붙어 있는 자리에서는 자막을 위로 올린다.
         높이는 아래 띠와 같게 두고, 사이트 헤더(110px) 바로 밑에 붙인다 — 헤더를 덮으면
         그 컷만 제품 크롬이 사라져 슬라이드처럼 보인다 */
      #__demo_sub.top {
        bottom: auto; top: 110px;
        border-top: 1px solid rgba(28,25,23,0.12);
        border-bottom: 1px solid rgba(28,25,23,0.12);
      }
      #__demo_sub.on { opacity: 1; }
      #__demo_sub .line {
        font-size: 42px; font-weight: 500; line-height: 1.25; letter-spacing: -0.015em;
        text-align: center; white-space: nowrap;
      }
      #__demo_sub .cap {
        font-size: 21px; font-weight: 400; color: #78716c; letter-spacing: 0.01em;
      }
      #__demo_sub b { font-weight: 700; color: #dd7400; }
      #__demo_sub .red { font-weight: 700; color: #dc2626; }
      #__demo_sub .num { font-weight: 700; color: #2563eb; font-variant-numeric: tabular-nums; }
      #__demo_sub .mono {
        font-family: 'Geist Mono', ui-monospace, monospace; font-size: 34px; letter-spacing: -0.02em;
      }

      #__demo_card {
        position: absolute; inset: 0; background: #faf9f6;
        display: none; flex-direction: column; align-items: center; justify-content: center; gap: 0;
      }
      #__demo_card.on { display: flex; }
      #__demo_card .brand {
        font-family: Oswald, 'Pretendard Variable', sans-serif;
        font-size: 148px; font-weight: 600; line-height: 1; letter-spacing: 0.02em; color: #1c1917;
      }
      #__demo_card .rule { width: 132px; height: 7px; background: #dd7400; margin: 34px 0 36px; }
      #__demo_card .big { font-size: 46px; font-weight: 600; line-height: 1.45; text-align: center; letter-spacing: -0.015em; }
      #__demo_card .small { font-size: 26px; font-weight: 400; color: #78716c; margin-top: 28px; letter-spacing: 0.01em; }
      #__demo_card .small b { color: #dd7400; font-weight: 600; }

      #__demo_cursor { position: absolute; left: 0; top: 0; width: 30px; height: 30px; opacity: 0; transform: translate(-3px,-2px); }
      #__demo_cursor.on { opacity: 1; }
      #__demo_ripple {
        position: absolute; width: 0; height: 0; border-radius: 999px;
        border: 3px solid rgba(221,116,0,0.85); opacity: 0;
      }
    `;
    document.head.appendChild(css);

    const layer = document.createElement("div");
    layer.id = "__demo_layer";
    layer.innerHTML = `
      <div id="__demo_card"></div>
      <div id="__demo_ripple"></div>
      <svg id="__demo_cursor" viewBox="0 0 24 24" fill="none">
        <path d="M5 2.5 L5 19.5 L9.4 15.4 L12.2 21.4 L15.2 20 L12.4 14.2 L18.6 14 Z"
              fill="#1c1917" stroke="#faf9f6" stroke-width="1.4" stroke-linejoin="round"/>
      </svg>
      <div id="__demo_sub"></div>`;
    document.body.appendChild(layer);

    window.__demo = {
      sub(lines, opts) {
        install();
        const el = document.getElementById("__demo_sub");
        el.style.setProperty("--sub-h", `${opts?.minH ?? 152}px`);
        el.classList.toggle("top", opts?.pos === "top");
        if (!lines || !lines.length) { el.classList.remove("on"); el.innerHTML = ""; return; }
        el.innerHTML = lines
          .map((l) => (typeof l === "string" ? `<div class="line">${l}</div>` : `<div class="cap">${l.cap}</div>`))
          .join("");
        el.classList.add("on");
      },
      /** 끝나지 않는 장식 모션만 멈춘다 — 티커·LIVE 맥박 (실시간 모션은 재생 속도와 어긋난다) */
      freezeDecor() {
        for (const a of document.getAnimations()) {
          const inf = a.effect?.getTiming?.().iterations === Infinity;
          if (inf || /ticker|pulse|marquee|spin/i.test(a.animationName ?? "")) { a.currentTime = 0; a.pause(); }
        }
      },
      /** 컷의 순서를 지키려고 프레임에서 빼는 블록 (C컷 전까지의 무결성 배너) */
      mask(on) {
        install();
        const h = [...document.querySelectorAll("h2")].find((e) => e.textContent.trim() === "이 숫자를 믿어도 되나");
        const card = h?.parentElement?.parentElement;
        if (card) card.style.display = on ? "none" : "";
        return !!card;
      },
      /** 행의 「근거」 버튼 좌표 — 감사 페이지로 들어가는 길이다 */
      evidenceButton(matchTitle) {
        const label = [...document.querySelectorAll("*")]
          .find((e) => e.children.length === 0 && e.textContent.trim() === matchTitle);
        if (!label) return null;
        const r = label.getBoundingClientRect();
        const btn = [...document.querySelectorAll("a,button")]
          .filter((b) => b.textContent.trim() === "근거")
          .map((b) => ({ rc: b.getBoundingClientRect() }))
          .sort((a, c) => Math.abs(a.rc.top - r.top) - Math.abs(c.rc.top - r.top))[0];
        return btn ? { x: Math.round(btn.rc.left + btn.rc.width / 2), y: Math.round(btn.rc.top + btn.rc.height / 2) } : null;
      },
      subOpacity(v) { install(); document.getElementById("__demo_sub").style.opacity = String(v); },
      card(html) {
        install();
        const el = document.getElementById("__demo_card");
        if (!html) { el.classList.remove("on"); el.innerHTML = ""; return; }
        el.innerHTML = html; el.classList.add("on");
      },
      cardOpacity(v) { install(); document.getElementById("__demo_card").style.opacity = String(v); },
      cursor(x, y) {
        install();
        const c = document.getElementById("__demo_cursor");
        if (x == null) { c.classList.remove("on"); return; }
        c.classList.add("on"); c.style.left = `${x}px`; c.style.top = `${y}px`;
      },
      ripple(x, y, t) {
        install();
        const r = document.getElementById("__demo_ripple");
        if (t == null) { r.style.opacity = "0"; return; }
        const size = 10 + 54 * t;
        r.style.width = `${size}px`; r.style.height = `${size}px`;
        r.style.left = `${x - size / 2}px`; r.style.top = `${y - size / 2}px`;
        r.style.opacity = String(1 - t);
      },
      scroll(y) { window.scrollTo(0, y); },
      videoAt(t) {
        const v = document.querySelector("video");
        if (!v) return false;
        v.pause(); v.currentTime = t; return true;
      },
    };
  };
  if (document.body) install();
  else document.addEventListener("DOMContentLoaded", install);
};

// ── 프레임 수집
const manifest = [];
let frameNo = 0;
let page;

const pad = (n) => String(n).padStart(5, "0");
const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

async function snap(seconds) {
  await page.evaluate(() => window.__demo?.freezeDecor()).catch(() => {});
  const file = `f${pad(frameNo++)}.png`;
  await page.screenshot({ path: `${FRAMES}/${file}` });
  manifest.push({ file, dur: seconds });
}
/** 정지 컷 — 한 장만 찍고 그 길이만큼 물린다 (장식 모션을 멈춰 뒀으므로 손실이 없다) */
const hold = (sec) => snap(sec);
/** 움직이는 컷 — 매 프레임 상태를 갱신하며 찍는다 */
async function anim(sec, fn) {
  const n = Math.max(1, Math.round(sec * FPS));
  for (let i = 1; i <= n; i++) {
    await fn(easeInOut(i / n), i / n);
    await snap(1 / FPS);
  }
}
const total = () => manifest.reduce((a, f) => a + f.dur, 0);
const at = (label) => console.log(`  ${label.padEnd(34)} ${total().toFixed(2)}s`);

const sub = (lines, opts) => page.evaluate(([l, o]) => window.__demo.sub(l, o), [lines ?? null, opts ?? null]);
const mask = (on) => page.evaluate((v) => window.__demo.mask(v), on);
const card = (html) => page.evaluate((h) => window.__demo.card(h), html ?? null);
const scrollTo = (y) => page.evaluate((v) => window.__demo.scroll(v), y);
const cursor = (x, y) => page.evaluate(([a, b]) => window.__demo.cursor(a, b), [x, y]);

async function goto(url, { wait = 2600 } = {}) {
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(wait);
}
/** 커서를 느리게 옮긴다 (문서 §4 — 순간이동 금지) */
async function moveCursor(from, to, sec = 0.8) {
  await anim(sec, async (e) => {
    await cursor(from.x + (to.x - from.x) * e, from.y + (to.y - from.y) * e);
  });
}
async function clickAt(x, y, { hover = 0.4, after = 0 } = {}) {
  await hold(hover); // 무엇을 누르는지 보이게 멈춘다
  await page.mouse.click(x, y);
  await page.waitForTimeout(300);
  await anim(0.32, async (_, t) => {
    await page.evaluate(([a, b, c]) => window.__demo.ripple(a, b, c), [x, y, t]);
  });
  await page.evaluate(() => window.__demo.ripple(null, null, null));
  if (after) await hold(after);
}
async function scrollOver(from, to, sec = 1.2) {
  await anim(sec, async (e) => { await scrollTo(Math.round(from + (to - from) * e)); });
}
async function box(selector) {
  const b = await page.locator(selector).first().boundingBox();
  if (!b) throw new Error(`앵커를 못 찾았다: ${selector}`);
  return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
}

// ── 촬영
const browser = await chromium.launch({ executablePath: CHROME, args: ["--force-color-profile=srgb", "--hide-scrollbars"] });
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  colorScheme: "light",
  locale: "ko-KR",
  timezoneId: "Asia/Seoul",
  reducedMotion: "reduce",
});
await ctx.addInitScript(OVERLAY);
page = await ctx.newPage();

console.log("촬영 시작");

/* ── A. 0:00–0:07 · 타이틀 카드 + 랜딩 ───────────────────────────── */
await goto(`${B}/kayfabe`);
await card(`<div class="brand">KAYFABE</div><div class="rule"></div>
  <div class="big">WWE 경기 결과를 예측하고,<br><b style="color:#dd7400">그 예측을 검증하는</b> 플랫폼</div>
  <div class="small">혼자 만들었습니다 · <b>Next.js</b> · <b>FastAPI</b> · <b>pgvector</b></div>`);
await hold(2.3);
await anim(0.4, async (e) => { await page.evaluate((v) => window.__demo.cardOpacity(v), 1 - e); });
await card(null);
await page.evaluate(() => window.__demo.cardOpacity(1));
at("A 타이틀 카드");

// 랜딩 아래 통계 띠(12/12 · 100%)가 C컷 미끼를 미리 흘리므로 자막 띠를 그만큼 높여 덮는다
const A_SUB = { minH: 212 };
await sub(["WWE 경기 결과를 예측하고,"], A_SUB);
// 히어로 영상은 프레임마다 직접 돌린다 — 실시간 재생은 캡처 속도와 어긋난다
await anim(1.9, async (_, t) => { await page.evaluate((v) => window.__demo.videoAt(v), t * 1.9); });
await sub(["<b>그 예측을 검증하는</b> 플랫폼"], A_SUB);
await anim(1.5, async (_, t) => { await page.evaluate((v) => window.__demo.videoAt(v), 1.9 + t * 1.5); });
await sub(["혼자 만들었습니다", { cap: "Next.js · FastAPI · pgvector · Neo4j" }], A_SUB);
await anim(0.9, async (_, t) => { await page.evaluate((v) => window.__demo.videoAt(v), 3.4 + t * 0.6); });
at("A 랜딩");

/* ── B. 0:07–0:18 · 예측은 어떻게 나오는가 ──────────────────────── */
await goto(`${B}/ai-lab/predictions`);
// 이 페이지에도 무결성 배너가 서 있다. C·D컷의 반전을 B가 먼저 흘리지 않게 가려 둔다
// (문서 C컷의 "크롭해 프레임 밖으로 뺀다"와 같은 뜻인데, 여기서는 페이지가 짧아 크롭이 안 된다)
if (!(await mask(true))) throw new Error("무결성 배너를 못 찾았다");
// 목록은 대회별로 접혀 있다 — 스크롤이 아니라 대회 칩을 눌러 들어간다 (문서 B컷)
await scrollTo(99999);
await sub(["분석기 셋이 따로 의견을 냅니다"]);
const chip = await box("button:has-text('Money in the Bank')");
await cursor(1560, 1000);
await moveCursor({ x: 1560, y: 1000 }, chip, 0.85);
await clickAt(chip.x, chip.y, { hover: 0.4, after: 0.45 });
await mask(true); // 필터로 다시 그려지면 인라인 스타일이 날아간다
at("B 대회 칩 클릭");

// 행을 눌러도 감사 페이지로 가지 않는다 — 지금 제품에서 그 길은 행의 「근거」 버튼이고,
// 열리는 것은 페이지가 아니라 분석기 셋을 나란히 보여 주는 모달이다 (문서 B컷은 옛 동작을 적고 있었다)
await scrollTo(99999); // 필터가 걸려 페이지가 짧아졌다 — 행이 자막 띠 위로 올라오게 끝까지 내린다
const ev = await page.evaluate(() => window.__demo.evidenceButton("Women's Money in the Bank Ladder Match"));
if (!ev) throw new Error("「근거」 버튼을 못 찾았다");
await sub(["<b>배당 · 루머 · 서사</b> 셋이 따로 읽습니다"]);
await moveCursor(chip, ev, 0.8);
await clickAt(ev.x, ev.y, { hover: 0.45 });
await page.waitForTimeout(900);
await cursor(null, null);
await hold(2.2);
await sub(["의견을 못 내면 <span class='red'>「의견 없음」</span>이라고 적습니다"]);
await hold(3.0);
at("B 근거 모달");

// 같은 예측의 감사 화면 — 의견을 못 낸 분석기의 가중치가 거기 적혀 있다
await goto(`${B}/ai-lab/audit/money-in-the-bank/mitb26-women`, { wait: 2600 });
await scrollTo(780);
await sub(["못 낸 의견은 <b>가중치 0</b>으로 합성합니다"]);
await hold(2.6);
at("B 분석기 리포트");

/* ── C. 0:18–0:26 · 성적 (미끼) ─────────────────────────────────── */
// 무결성 배너를 프레임 밖으로 밀어 KPI 스트립만 잡는다 (문서 C컷 — 크롭 대신 스크롤로 한다)
await goto(`${B}/ai-lab`);
await scrollTo(560);
await sub(["채점된 예측 <span class='num'>12건 중 12건</span> 적중"]);
await hold(3.6);
await sub(["적중률 <span class='num'>100%</span> <span class='num'>(12/12)</span>"]);
await hold(4.2);
at("C 적중률");

/* ── D. 0:26–0:44 · 반전 ★ ─────────────────────────────────────── */
// 크롭해 뒀던 위쪽을 되돌려 보여 준다 — 배너는 내내 그 자리에 있었다
await sub(["그런데 이 화면은 그 <span class='num'>100%</span>를"]);
await scrollOver(560, 150, 1.8);
await sub(["<span class='red'>성적으로 세지 않습니다</span>"]);
await hold(2.6);
await sub(["표본 12건 · 대회 1개 · <span class='red'>일반화 지표 아님</span>"]);
await hold(3.0);
at("D 무결성 배너");

await goto(`${B}/ai-lab/audit/summerslam/ss26-n2-whc`);
await scrollTo(560);
await sub(["채점된 <span class='num'>12건 전부</span> <span class='red'>실격</span>입니다"]);
await hold(3.9);
await sub(["사유: 결과가 <b>기록된 다음에</b> 만들어진 예측"]);
await hold(3.4);
await sub(["<span class='mono'>8/04 결과 기록 → 8/05 예측 생성</span>"]);
await hold(2.6);
await sub(["시스템이 <b>자기 숫자를 먼저 기각</b>합니다"]);
await hold(2.4);
at("D 판정 블록");

/* ── E. 0:44–0:55 · 왜 실격인가 ─────────────────────────────────── */
await goto(`${B}/ai-lab/leakage`);
await scrollTo(300);
await sub(null);
await hold(1.3);
await sub(["<span class='red'>실격 11건</span>이 글 <b>한 개</b>에서 나왔습니다"]);
await scrollOver(300, 1080, 1.6);
await hold(2.6);
await sub([{ cap: "결과가 적힌 글" }, "<span class='mono'>en.wikipedia.org/wiki/SummerSlam_(2026)</span>"]);
await hold(3.0);
await sub(["어느 글이 <b>몇 건을 막았는지</b> 셉니다"]);
await hold(2.5);
at("E 근거 오염");

/* ── F. 0:55–1:08 · 재현 ────────────────────────────────────────── */
// 5단계 목록이 페이지 맨 아래에 붙어 있다 — 끝까지 내려도 아래 65px밖에 안 남으므로
// 이 컷만 자막을 위로 올린다. 아래에 띠를 두면 「안 됨」 세 줄이 가려져 컷의 요점이 사라진다
await goto(`${B}/ai-lab/audit/summerslam/ss26-n2-whc`);
await scrollTo(99999);
const TOP = { pos: "top" };
await sub(["예측 하나를 만드는 <span class='num'>5단계</span> 중"], TOP);
await hold(2.8);
await sub(["<span class='num'>2단계</span>만 재현됩니다"], TOP);
await hold(3.2);
await sub([{ cap: "안 되는 단계에는 이유가 붙는다" }, "「글을 다시 모으면 <span class='red'>옛 판본이 지워진다</span>」"], TOP);
await hold(3.6);
await sub(["<b>안 되는 이유까지</b> 화면에 적습니다"], TOP);
await hold(3.0);
at("F 재현");

/* ── G. 1:08–1:22 · 사전 판정 ───────────────────────────────────── */
await goto(`${B}/ai-lab/readiness`);
await scrollTo(300);
await sub(["끝난 경기를 변명하는 대신,"]);
await hold(2.0);
await sub(["<b>다음 대회를 미리 판정합니다</b>"]);
await hold(2.4);
await sub(["대회 <span class='num'>5개</span> — <b>전부 통과</b>"]);
await hold(2.6);
await scrollOver(300, 1250, 1.6);
await sub(["MITB까지 <span class='num'>D-2</span> · 5경기 전부 예측 완료"]);
await hold(2.8);
await sub(["통과인데도 <span class='red'>지뢰 2건</span>은 적어 둡니다"]);
await hold(2.6);
at("G 사전 판정");

/* ── H. 1:22–1:30 · 클로징 ──────────────────────────────────────── */
await sub(null);
await card(`<div class="big">적중률을 올리는 것보다<br>
  <b style="color:#dd7400">그 적중률을 믿을 수 있게 만드는 일</b>이<br>어려웠습니다</div>
  <div class="rule" style="margin:44px 0 34px"></div>
  <div class="brand" style="font-size:72px">KAYFABE</div>
  <div class="small">kayfabe.jsangho.cloud · github.com/jsangho</div>`);
await hold(7.6);
at("H 클로징");

console.log(`\n총 길이 ${total().toFixed(2)}s · 프레임 ${manifest.length}장`);

// ffmpeg concat 목록 (정지 컷은 한 장을 길게 문다)
const list = manifest.map((f) => `file '${FRAMES}/${f.file}'\nduration ${f.dur.toFixed(4)}`).join("\n");
writeFileSync(`${DIR}frames.txt`, `${list}\nfile '${FRAMES}/${manifest.at(-1).file}'\n`);
writeFileSync(`${DIR}timing.json`, JSON.stringify({ total: total(), frames: manifest.length }, null, 2));

await browser.close();
console.log("frames.txt 작성 완료");
