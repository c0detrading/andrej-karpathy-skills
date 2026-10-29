// Checks a static site before it goes to the user: every page at desktop and phone width.
// Reports sideways scrolling, broken images, console errors, failed loads and alignment near-misses,
// and saves full-page screenshots with the column grid drawn on top.
// usage: node check_site.js <site dir> <out dir> [--cols 4] [--gutter 6] [--margin 24] [--max 1680]
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');

const args = process.argv.slice(2);
const [SITE, OUT] = args.filter(a => !a.startsWith('--') && !/^\d+$/.test(a));
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? +args[i + 1] : d; };
const COLS = opt('cols', 4), GUT = opt('gutter', 6), MARGIN = opt('margin', 24), MAX = opt('max', 1680);
fs.mkdirSync(OUT, { recursive: true });
const pages = fs.readdirSync(SITE).filter(f => f.endsWith('.html')).sort((a, b) => (a === 'index.html' ? -1 : b === 'index.html' ? 1 : a.localeCompare(b)));

(async () => {
  const b = await chromium.launch();
  let problems = 0;
  for (const [tag, w, h] of [['desktop', 1440, 900], ['phone', 390, 844]]) {
    for (const f of pages) {
      const p = await b.newPage({ viewport: { width: w, height: h } });
      const errs = [];
      p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
      p.on('pageerror', e => errs.push('script: ' + e));
      p.on('requestfailed', r => errs.push('failed load: ' + r.url()));
      await p.goto('file://' + path.resolve(SITE, f), { waitUntil: 'networkidle' });
      await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 30)); } scrollTo(0, 0); });
      await p.waitForTimeout(500);
      const r = await p.evaluate(({ COLS, GUT, MARGIN, MAX, desktop }) => {
        const vw = document.documentElement.clientWidth;
        const out = { scroll: document.documentElement.scrollWidth > vw + 1, broken: [], nearMiss: [] };
        out.broken = [...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'));
        if (desktop) {
          // column edges of the page grid
          const inner = Math.min(vw - 2 * MARGIN, MAX), left0 = (vw - inner) / 2;
          const cw = (inner - GUT * (COLS - 1)) / COLS, edges = [];
          for (let i = 0; i < COLS; i++) { edges.push(left0 + i * (cw + GUT)); edges.push(left0 + i * (cw + GUT) + cw); }
          const seen = new Set();
          for (const el of document.querySelectorAll('h1, h2, h3, p, a.btn, button, img, .panel, li, blockquote, label, input, textarea, select')) {
            const rc = el.getBoundingClientRect();
            if (!rc.width || !rc.height || getComputedStyle(el).visibility === 'hidden') continue;
            for (const [side, x] of [['left', rc.left], ['right', rc.right]]) {
              const d = Math.min(...edges.map(e => Math.abs(e - x)));
              if (d > 1 && d <= 8) {
                const key = el.tagName + Math.round(x) + Math.round(rc.top / 200);
                if (seen.has(key)) continue; seen.add(key);
                out.nearMiss.push(`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} "${(el.textContent || el.alt || '').trim().slice(0, 30)}" ${side} edge ${d.toFixed(1)}px off a column line (y=${Math.round(rc.top + scrollY)})`);
              }
            }
          }
          // draw the grid for the screenshot
          const o = document.createElement('div');
          o.style.cssText = `position:absolute;top:0;left:${left0}px;width:${inner}px;height:${document.documentElement.scrollHeight}px;display:grid;grid-template-columns:repeat(${COLS},1fr);gap:${GUT}px;pointer-events:none;z-index:9999`;
          for (let i = 0; i < COLS; i++) { const c = document.createElement('div'); c.style.cssText = 'border-left:1px solid rgba(255,0,0,.7);border-right:1px solid rgba(255,0,0,.7)'; o.appendChild(c); }
          document.body.style.position = 'relative'; document.body.appendChild(o);
        }
        return out;
      }, { COLS, GUT, MARGIN, MAX, desktop: tag === 'desktop' });
      const issues = [];
      if (r.scroll) issues.push('page scrolls sideways');
      r.broken.forEach(s => issues.push('broken image: ' + s));
      issues.push(...errs);
      problems += issues.length;
      console.log(`${tag} ${f}: ${issues.length ? issues.join('; ') : 'ok'}`);
      if (r.nearMiss.length) console.log('  alignment near-misses (check these are deliberate):\n    ' + r.nearMiss.slice(0, 15).join('\n    ') + (r.nearMiss.length > 15 ? `\n    …and ${r.nearMiss.length - 15} more` : ''));
      await p.screenshot({ path: path.join(OUT, `${f.replace('.html', '')}-${tag}${tag === 'desktop' ? '-grid' : ''}.png`), fullPage: true });
      await p.close();
    }
  }
  await b.close();
  console.log(problems ? `${problems} problem(s) found` : 'no problems found');
  console.log('screenshots in ' + OUT + ' (desktop ones have the column grid drawn on top)');
})();
