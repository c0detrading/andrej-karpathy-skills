// Makes the VOLSTRO portfolio PDF: one long page with every page of a finished site,
// desktop on the left and phone on the right, in a VOLSTRO frame, with "VOLSTRO" watermarked across every screen.
// For showing finished work to potential clients.
// usage: node portfolio_pdf.js <site dir> <out.pdf> "<client name>" "<one-line description>"
const { chromium } = require('playwright'); const { execFileSync } = require('child_process');
const path = require('path'); const fs = require('fs'); const os = require('os');
const [SITE, PDF] = process.argv.slice(2, 4).map(p => path.resolve(p));
const CLIENT = process.argv[4] || 'Client website';
const ABOUT = process.argv[5] || '';
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'portfolio-'));
let files = fs.readdirSync(SITE).filter(f => f.endsWith('.html'));
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// Burns a tiled diagonal "VOLSTRO" into a screenshot at full resolution.
// Light text with a dark edge, so it reads on light and dark parts of a screen.
function watermark(png, jpg, scale) {
  const size = Math.round(56 * scale), tile = png.replace('.png', '-tile.png');
  execFileSync('convert', ['-size', `${size * 7}x${size * 4.4}`, 'xc:none', '-font', 'Liberation-Sans-Bold', '-pointsize', String(size),
    '-kerning', String(size * 0.08), '-fill', 'rgba(255,255,255,0.34)', '-stroke', 'rgba(23,24,26,0.22)', '-strokewidth', String(Math.max(1, size / 30)),
    '-gravity', 'center', '-annotate', '-28x-28+0+0', 'VOLSTRO', tile]);
  execFileSync('composite', ['-tile', tile, png, png]);
  execFileSync('convert', [png, '-quality', '78', jpg]);
}

(async () => {
  const b = await chromium.launch(); const shots = { d: [], p: [] };
  // pages in the order of the site's own menu, then any others
  const nav = await b.newPage();
  await nav.goto('file://' + path.join(SITE, 'index.html'));
  const order = await nav.$$eval('header a[href$=".html"], nav a[href$=".html"]', as => as.map(a => a.getAttribute('href')));
  await nav.close();
  files = ['index.html', ...new Set(order.filter(f => files.includes(f) && f !== 'index.html')), ...files.filter(f => f !== 'index.html' && !order.includes(f)).sort()];
  for (const [tag, w, h, dsf] of [['d', 1440, 900, 1.25], ['p', 390, 844, 1.75]]) for (const f of files) {
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dsf });
    await p.goto('file://' + path.join(SITE, f), { waitUntil: 'networkidle' });
    await p.addStyleTag({ content: '[class*="book-bar"],[class*="sticky-bar"]{position:static!important} body{padding-bottom:0!important}' });
    await p.evaluate(async () => {
      for (let y = 0; y < document.body.scrollHeight; y += 500) { scrollTo(0, y); await new Promise(r => setTimeout(r, 25)); }
      scrollTo(0, 0);
      // live "open now" lines change through the day; show them open
      document.querySelectorAll('[data-status]').forEach(el => {
        const i = el.querySelector('i'), s = el.querySelector('span');
        if (i) i.className = 'open';
        if (s) s.textContent = s.textContent.replace(/ (opens at|closed for today|closed today|open until).*$/, el.dataset.status === 'bar' ? ' open until 23:00' : ' open until 21:00');
      });
    });
    await p.waitForTimeout(500);
    const name = f === 'index.html' ? 'Home' : (await p.title()).split('|')[0].trim() || f;
    const png = path.join(TMP, `${tag}-${f}.png`), jpg = png.replace('.png', '.jpg');
    await p.screenshot({ path: png, fullPage: true });
    watermark(png, jpg, dsf);
    shots[tag].push({ name, jpg, h: await p.evaluate(() => document.documentElement.scrollHeight), w });
    await p.close();
  }
  const cols = [[], []], ch = [0, 0];
  for (const s of shots.p) { const i = ch[0] <= ch[1] ? 0 : 1; cols[i].push(s); ch[i] += s.h + 120; }
  const block = s => `<div class="shot"><div class="lab">${esc(s.name)}</div><div class="frame" style="width:${s.w}px"><img src="file://${s.jpg}" style="width:${s.w}px"></div></div>`;
  const html = `<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&display=swap">
<style>
body{margin:0;background:#232522;color:#f3f0e8;font-family:"Space Grotesk",Arial,sans-serif}
.page{width:max-content;padding:0 80px}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:80px;padding:90px 0 70px;border-bottom:2px solid rgba(243,240,232,.2);margin-bottom:90px}
.word{font-size:150px;font-weight:600;letter-spacing:-.05em;line-height:.8}
.word i{font-style:normal;color:#b6c69f}
.about{text-align:right;display:grid;gap:12px}
.about .k{font-size:28px;color:#b6c69f}
.about .c{font-size:64px;font-weight:500;letter-spacing:-.03em;line-height:1}
.about .d{font-size:30px;color:#c9c6bc}
.wrap{display:flex;gap:160px;align-items:flex-start}
.col{display:flex;flex-direction:column;gap:120px}
.head{font-size:44px;font-weight:500;margin-bottom:-60px;color:#c9c6bc}
.lab{font-size:30px;font-weight:500;margin-bottom:16px}
.frame{outline:2px solid rgba(243,240,232,.25)}
.frame img{display:block}
.foot{display:flex;justify-content:space-between;padding:90px 0 100px;margin-top:110px;border-top:2px solid rgba(243,240,232,.2);font-size:34px;color:#c9c6bc}
.foot b{color:#f3f0e8;font-weight:600}
</style>
<div class="page">
  <div class="top">
    <div class="word">VOLSTRO<i>.</i></div>
    <div class="about"><div class="k">Website design</div><div class="c">${esc(CLIENT)}</div>${ABOUT ? `<div class="d">${esc(ABOUT)}</div>` : ''}<div class="d">${files.length} pages, desktop and phone</div></div>
  </div>
  <div class="wrap">
    <div class="col"><div class="head">Desktop</div>${shots.d.map(block).join('')}</div>
    <div class="col"><div class="head">Phone</div>${cols[0].map(block).join('')}</div>
    <div class="col"><div class="head">&nbsp;</div>${cols[1].map(block).join('')}</div>
  </div>
  <div class="foot"><span>Designed by <b>VOLSTRO</b>, London</span><span>hello@volstro.co.uk</span></div>
</div>`;
  const hp = path.join(TMP, 'portfolio.html'); fs.writeFileSync(hp, html);
  const p = await b.newPage({ viewport: { width: 1440 + 2 * 390 + 480, height: 1000 } });
  await p.goto('file://' + hp, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const [W, H] = await p.evaluate(() => [document.querySelector('.page').scrollWidth, document.querySelector('.page').scrollHeight]);
  // PDF pages over 200 inches don't open in every app, so shrink to fit
  const scale = Math.min(1, 14000 / (H * 0.75));
  await p.pdf({ path: PDF, width: Math.ceil(W * scale) + 'px', height: Math.ceil(H * scale) + 'px', scale, printBackground: true, pageRanges: '1', margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await b.close(); fs.rmSync(TMP, { recursive: true, force: true });
  console.log(`${PDF}: 1 page, ${files.length} pages of the site, shrunk to ${Math.round(scale * 100)}%`);
})();
