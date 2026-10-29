// Makes the one long markup PDF the user draws on: every page at desktop size on the left,
// the same pages at phone size in two columns on the right, each labelled with its page name.
// usage: node markup_pdf.js <site dir> <out.pdf>
// The user marks it up on an iPad and sends screenshots or the PDF back.
const { chromium } = require('playwright'); const { execFileSync } = require('child_process');
const path = require('path'); const fs = require('fs'); const os = require('os');
const [SITE, PDF] = process.argv.slice(2).map(p => path.resolve(p));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'markup-'));
const files = fs.readdirSync(SITE).filter(f => f.endsWith('.html')).sort((a, b) => (a === 'index.html' ? -1 : b === 'index.html' ? 1 : 0));

(async () => {
  const b = await chromium.launch(); const shots = { d: [], p: [] };
  for (const [tag, w, h, dsf] of [['d', 1440, 900, 1.5], ['p', 390, 844, 2]]) for (const f of files) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dsf });
    await p.goto('file://' + path.join(SITE, f), { waitUntil: 'networkidle' });
    // fixed bars would otherwise be drawn once at the top of a full-page screenshot
    await p.addStyleTag({ content: '[class*="book-bar"],[class*="sticky-bar"]{position:static!important} body{padding-bottom:0!important}' });
    await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise(r => setTimeout(r, 25)); } scrollTo(0, 0); });
    await p.waitForTimeout(500);
    const name = f === 'index.html' ? 'Home' : (await p.title()).split('|')[0].trim() || f;
    const png = path.join(TMP, `${tag}-${f}.png`), jpg = png.replace('.png', '.jpg');
    await p.screenshot({ path: png, fullPage: true });
    execFileSync('convert', [png, '-quality', '82', jpg]);
    shots[tag].push({ name, jpg, h: await p.evaluate(() => document.documentElement.scrollHeight), w });
    await p.close();
  }
  const cols = [[], []], ch = [0, 0];
  for (const s of shots.p) { const i = ch[0] <= ch[1] ? 0 : 1; cols[i].push(s); ch[i] += s.h + 120; }
  const block = s => `<div><div class="lab">${s.name}</div><img src="file://${s.jpg}" style="width:${s.w}px"></div>`;
  const html = `<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#fff;font-family:Arial,sans-serif;color:#17181A}
.wrap{display:flex;gap:160px;padding:80px;align-items:flex-start}
.col{display:flex;flex-direction:column;gap:120px}
.head{font-size:44px;font-weight:700;margin-bottom:-60px}
.lab{font-size:30px;font-weight:700;margin-bottom:14px}
img{display:block;outline:2px solid #B3B6B3}
</style><div class="wrap">
<div class="col"><div class="head">Desktop</div>${shots.d.map(block).join('')}</div>
<div class="col"><div class="head">Phone</div>${cols[0].map(block).join('')}</div>
<div class="col"><div class="head">&nbsp;</div>${cols[1].map(block).join('')}</div></div>`;
  const hp = path.join(TMP, 'long.html'); fs.writeFileSync(hp, html);
  const p = await b.newPage({ viewport: { width: 1440 + 2 * 390 + 480, height: 1000 } });
  await p.goto('file://' + hp, { waitUntil: 'load' });
  const [W, H] = await p.evaluate(() => [document.querySelector('.wrap').scrollWidth, document.querySelector('.wrap').scrollHeight]);
  // PDF pages over 200 inches don't open in every app, so shrink to fit
  const scale = Math.min(1, 14000 / (H * 0.75));
  await p.pdf({ path: PDF, width: Math.ceil(W * scale) + 'px', height: Math.ceil(H * scale) + 'px', scale, printBackground: true, pageRanges: '1', margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await b.close(); fs.rmSync(TMP, { recursive: true, force: true });
  console.log(`${PDF}: 1 page, ${files.length} pages of the site, shrunk to ${Math.round(scale * 100)}%`);
})();
