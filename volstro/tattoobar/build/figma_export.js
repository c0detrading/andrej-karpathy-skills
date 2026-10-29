// Turns the built TattooBar site into a Figma development plugin that draws every page as editable layers.
// Run: node volstro/tattoobar/build/figma_export.js volstro/tattoobar/site volstro/tattoobar/figma-plugin
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const [SITE, OUT] = process.argv.slice(2).map(p => path.resolve(p));
const PAGES = [['index', 'Home'], ['tattoo', 'Tattoo and piercing'], ['bar', 'The bar'], ['events', 'Events'],
  ['learn', 'Learn'], ['art', 'The art'], ['aftercare', 'Aftercare']];
const VIEWS = [
  { name: 'Desktop', width: 1440, height: 900, grid: { count: 4, gutter: 6, offset: 24 } },
  { name: 'Phone', width: 390, height: 844, grid: { count: 2, gutter: 6, offset: 20 } },
];
const TOKENS = { Concrete: '#D5D6D2', Formwork: '#B3B6B3', Ink: '#17181A', Steel: '#4C5256', Paper: '#F3F3F0', UV: '#5536E8', White: '#FFFFFF' };

// Runs inside the page. Returns a tree of frames, texts, images and svgs in page coordinates.
function capture() {
  const sx = window.scrollX, sy = window.scrollY;
  const r1 = v => Math.round(v * 10) / 10;
  const color = s => {
    const m = s && s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    const a = p.length > 3 ? p[3] : 1;
    if (a === 0) return null;
    const hex = '#' + p.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
    return a === 1 ? hex : hex + Math.round(a * 255).toString(16).padStart(2, '0').toUpperCase();
  };
  const px = v => parseFloat(v) || 0;
  const box = el => { const r = el.getBoundingClientRect(); return { x: r1(r.left + sx), y: r1(r.top + sy), w: r1(r.width), h: r1(r.height) }; };
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE', 'META', 'LINK']);
  const STRUCT = new Set(['HEADER', 'NAV', 'SECTION', 'FOOTER', 'FIGURE', 'FORM', 'MAIN', 'ARTICLE']);

  function radius(cs, w, h) {
    const one = v => v.endsWith('%') ? Math.min(w, h) * parseFloat(v) / 100 : px(v);
    const r = [cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomRightRadius, cs.borderBottomLeftRadius].map(one);
    return r.some(v => v > 0) ? r.map(r1) : null;
  }
  function fills(cs) {
    const out = [];
    const bg = color(cs.backgroundColor);
    if (bg) out.push({ type: 'solid', c: bg });
    const g = cs.backgroundImage.match(/^linear-gradient\((.*)\)$/);
    if (g) {
      const stops = [...g[1].matchAll(/(rgba?\([^)]+\))\s*([\d.]+%)?/g)].map(m => ({ c: color(m[1]) || '#00000000', p: m[2] ? parseFloat(m[2]) / 100 : null }));
      if (stops.length === 2 && stops[0].p === stops[1].p && stops[0].p !== null) {
        const p = stops[0].p;
        out.push({ type: 'vgrad', stops: [[0, stops[0].c], [p, stops[0].c], [p, stops[1].c], [1, stops[1].c]] });
      }
    }
    return out;
  }
  function stroke(cs) {
    const sides = ['Top', 'Right', 'Bottom', 'Left'].map(s => ({ w: px(cs['border' + s + 'Width']), c: color(cs['border' + s + 'Color']), st: cs['border' + s + 'Style'] }));
    const vis = sides.filter(s => s.w > 0 && s.c && s.st !== 'none');
    if (vis.length) return { c: vis[0].c, w: sides.map(s => (s.w > 0 && s.c && s.st !== 'none') ? s.w : 0), align: 'INSIDE' };
    const sh = cs.boxShadow;
    if (sh && sh !== 'none') {
      const m = sh.match(/(rgba?\([^)]+\))\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px(\s+inset)?/);
      if (m && +m[2] === 0 && +m[3] === 0 && +m[4] === 0 && +m[5] > 0 && color(m[1])) {
        const w = +m[5];
        return { c: color(m[1]), w: [w, w, w, w], align: m[6] ? 'INSIDE' : 'OUTSIDE' };
      }
    }
    return null;
  }
  function textStyle(el) {
    const cs = getComputedStyle(el);
    const fam = cs.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
    return {
      f: fam, wt: parseInt(cs.fontWeight, 10) || 400, sz: r1(px(cs.fontSize)),
      lh: cs.lineHeight === 'normal' ? null : r1(px(cs.lineHeight)),
      ls: cs.letterSpacing === 'normal' ? 0 : r1(px(cs.letterSpacing)),
      c: color(cs.color) || '#000000',
      tc: cs.textTransform === 'uppercase' ? 'UPPER' : cs.textTransform === 'lowercase' ? 'LOWER' : 'ORIGINAL',
      u: cs.textDecorationLine.includes('underline'),
    };
  }
  const isInline = cs => cs.display === 'inline';

  // Gather the text that flows directly in an element (through inline children only).
  function runsOf(el) {
    const runs = [], nodes = [];
    (function walk(node) {
      for (const ch of node.childNodes) {
        if (ch.nodeType === 3) { runs.push({ s: ch.data, el: ch.parentElement }); nodes.push(ch); }
        else if (ch.nodeType === 1) {
          if (ch.tagName === 'BR') { runs.push({ s: '\n', el: ch.parentElement, br: true }); continue; }
          if (SKIP.has(ch.tagName) || ch.tagName === 'svg' || ch.tagName === 'IMG') continue;
          const cs = getComputedStyle(ch);
          if (cs.display === 'none') continue;
          if (isInline(cs)) walk(ch);
        }
      }
    })(el);
    // collapse white space the way the browser does
    const out = [];
    let prevSpace = true;
    for (const r of runs) {
      let s = r.br ? '\n' : r.s.replace(/[ \t\n\r\f]+/g, ' ');
      if (!r.br && prevSpace && s.startsWith(' ')) s = s.slice(1);
      if (!s) continue;
      if (r.br && out.length) out[out.length - 1].s = out[out.length - 1].s.replace(/ +$/, '');
      prevSpace = r.br || s.endsWith(' ');
      out.push({ s, st: textStyle(r.el) });
    }
    if (out.length) out[out.length - 1].s = out[out.length - 1].s.replace(/ +$/, '');
    const clean = out.filter(o => o.s.length);
    return { runs: clean, nodes, text: clean.map(o => o.s).join('') };
  }

  function textNode(el, cs) {
    const { runs, nodes, text } = runsOf(el);
    if (!text.trim()) return null;
    const rects = [];
    for (const n of nodes) {
      if (!n.data.trim()) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const r of rg.getClientRects()) if (r.width > 0 && r.height > 0) rects.push(r);
    }
    if (!rects.length) return null;
    const tops = [...new Set(rects.map(r => Math.round(r.top / 3)))];
    let single = tops.length === 1 && !text.includes('\n');
    // Big headings keep the browser's line breaks, so Figma's slightly different letter widths can't re-wrap them
    const textNodes = nodes.filter(n => n.data.trim());
    if (!single && runs.length === 1 && textNodes.length === 1 && runs[0].st.sz >= 28) {
      const n = textNodes[0], breaks = new Set();
      let prevTop = null;
      for (let i = 0; i < n.data.length; i++) {
        if (/\s/.test(n.data[i])) continue;
        const rg = document.createRange(); rg.setStart(n, i); rg.setEnd(n, i + 1);
        const rr = rg.getClientRects()[0];
        if (!rr) continue;
        if (prevTop !== null && rr.top > prevTop + rr.height / 2) breaks.add(i);
        prevTop = rr.top;
      }
      if (breaks.size) {
        let raw = '';
        for (let i = 0; i < n.data.length; i++) raw += (breaks.has(i) ? '\u0000' : '') + n.data[i];
        runs[0].s = raw.replace(/[ \t\n\r\f]+/g, ' ').replace(/ ?\u0000 ?/g, '\n').trim();
        single = true;
      }
    }
    const first = rects.reduce((a, b) => (b.top < a.top - 1 || (Math.abs(b.top - a.top) <= 1 && b.left < a.left)) ? b : a);
    const lh = cs.lineHeight === 'normal' ? first.height : px(cs.lineHeight);
    const er = el.getBoundingClientRect();
    const cl = er.left + px(cs.borderLeftWidth) + px(cs.paddingLeft);
    const cw = er.width - px(cs.borderLeftWidth) - px(cs.borderRightWidth) - px(cs.paddingLeft) - px(cs.paddingRight);
    let align = { center: 'CENTER', right: 'RIGHT', end: 'RIGHT', justify: 'JUSTIFIED' }[cs.textAlign] || 'LEFT';
    const left = Math.min(...rects.map(r => r.left)), right = Math.max(...rects.map(r => r.right));
    let x, w;
    if (single && align === 'LEFT') { x = left; w = right - left; }
    else if (single) {
      w = Math.max(cw, (right - left) * 1.06 + 4);
      x = align === 'CENTER' ? cl + cw / 2 - w / 2 : cl + cw - w;
    } else { x = cl; w = cw; }
    return { t: 'text', x: r1(x + sx), y: r1(first.top - (lh - first.height) / 2 + sy), w: r1(w), single, align, runs };
  }

  function pseudo(el, cs, which) {
    const p = getComputedStyle(el, which);
    if (!p.content || p.content === 'none' || p.content === 'normal') return null;
    const er = el.getBoundingClientRect();
    const bg = color(p.backgroundColor);
    if (p.position === 'absolute' && bg) {
      return { t: 'frame', name: 'Marker', x: r1(er.left + px(cs.borderLeftWidth) + px(p.left) + sx), y: r1(er.top + px(cs.borderTopWidth) + px(p.top) + sy),
        w: r1(px(p.width)), h: r1(px(p.height)), fill: [{ type: 'solid', c: bg }], radius: radius(p, px(p.width), px(p.height)), children: [] };
    }
    const m = p.content.match(/^"(.*)"$/);
    if (m && m[1].trim()) {
      const st = textStyle(el); const ps = getComputedStyle(el, which);
      st.wt = parseInt(ps.fontWeight, 10) || st.wt;
      const cr = er.right - px(cs.paddingRight) - px(cs.borderRightWidth);
      const lh = st.lh || st.sz * 1.2;
      return { t: 'text', x: r1(cr - 40 + sx), y: r1(er.top + px(cs.paddingTop) + px(cs.borderTopWidth) + sy), w: 40, single: true, align: 'RIGHT', runs: [{ s: m[1], st: Object.assign(st, { lh }) }] };
    }
    return null;
  }

  function nameOf(el) {
    if (el.matches('.page')) return 'Page';
    if (el.tagName === 'HEADER') return 'Header';
    if (el.tagName === 'FOOTER') return 'Footer';
    if (el.matches('.book-bar')) return 'Booking bar (fixed to the bottom on phones)';
    if (el.matches('.hero')) return 'Hero';
    if (el.matches('.band')) return 'Hero words and photo';
    if (el.matches('.tiles')) return 'Tiles';
    if (el.matches('.nav')) return 'Navigation';
    if (el.matches('.btn, .filter')) return 'Button: ' + el.textContent.trim().replace(/\s+/g, ' ');
    if (el.matches('.tile')) return 'Tile: ' + ((el.querySelector('.cap, .big') || {}).textContent || '').trim();
    if (el.matches('.panel')) { const h = el.querySelector('h3, .big, blockquote'); return 'Panel' + (h ? ': ' + h.textContent.trim().slice(0, 30) : ''); }
    if (el.matches('section, .page-head')) { const h = el.querySelector('h1, h2'); return h ? h.textContent.trim().replace(/\s+/g, ' ').replace(/^./, c => c.toUpperCase()) : (el.getAttribute('aria-label') || 'Section'); }
    if (el.matches('.work-grid')) return 'Work grid';
    if (el.matches('.rows')) return 'List';
    if (el.matches('.field')) return 'Field: ' + ((el.querySelector('label') || {}).textContent || '');
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') return 'Input';
    const cls = (el.getAttribute('class') || '').split(/\s+/).filter(c => !/^c\d|^call$/.test(c))[0];
    return cls ? cls.replace(/-/g, ' ').replace(/^./, c => c.toUpperCase()) : el.tagName.toLowerCase();
  }

  function walk(el) {
    if (SKIP.has(el.tagName) || el.matches('.skip')) return [];
    // closed dropdowns: keep the summary button, drop the hidden panel
    const closed = el.parentElement && el.parentElement.closest('details:not([open])');
    if (closed && !el.closest('summary')) return [];
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return [];
    const b = box(el);
    const visible = b.w > 0 && b.h > 0;

    if (el.tagName === 'IMG') {
      if (!visible) return [];
      const pos = cs.objectPosition.split(' ').map(v => v.endsWith('%') ? parseFloat(v) / 100 : 0.5);
      return [{ t: 'image', name: el.alt || el.getAttribute('src').split('/').pop(), ...b, src: el.getAttribute('src'),
        nw: el.naturalWidth, nh: el.naturalHeight, gray: /grayscale\(1\)/.test(cs.filter), pos, radius: radius(cs, b.w, b.h) }];
    }
    if (el.tagName === 'svg') {
      if (!visible) return [];
      const c = el.cloneNode(true);
      c.setAttribute('width', b.w); c.setAttribute('height', b.h);
      const fill = color(getComputedStyle(el).fill) || '#000000';
      c.querySelectorAll('path, circle, rect, polygon').forEach(p => p.setAttribute('fill', fill.slice(0, 7)));
      c.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      return [{ t: 'svg', name: 'Star', ...b, svg: new XMLSerializer().serializeToString(c) }];
    }

    // Inline elements: their text belongs to the nearest block above, so only look for boxes inside them
    if (isInline(cs) && !['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return [...el.children].flatMap(walk);

    const kids = [];
    const before = visible ? pseudo(el, cs, '::before') : null;
    if (before) kids.push(before);
    if (visible && el.tagName === 'LI' && el.parentElement.tagName === 'OL' && cs.listStyleType !== 'none') {
      const st = textStyle(el); st.wt = 600;
      const idx = [...el.parentElement.children].indexOf(el) + 1;
      const t = textNode(el, cs);
      kids.push({ t: 'text', x: r1(b.x - 26), y: t ? t.y : b.y, w: 22, single: true, align: 'RIGHT', runs: [{ s: idx + '.', st }] });
    }
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) && visible) {
      const st = textStyle(el);
      let s = el.tagName === 'SELECT' ? el.options[el.selectedIndex].text : el.value;
      if (!s && el.type === 'date') s = 'dd/mm/yyyy';
      if (!s && el.placeholder) { s = el.placeholder; st.c = color(getComputedStyle(el, '::placeholder').color) || '#757575'; }
      if (s) {
        const lh = st.lh || st.sz * 1.25; st.lh = lh;
        const top = el.tagName === 'TEXTAREA' ? b.y + px(cs.paddingTop) + px(cs.borderTopWidth) : b.y + b.h / 2 - lh / 2;
        kids.push({ t: 'text', x: r1(b.x + px(cs.paddingLeft) + px(cs.borderLeftWidth)), y: r1(top), w: r1(b.w - px(cs.paddingLeft) - px(cs.paddingRight) - 2),
          single: el.tagName !== 'TEXTAREA', align: el.tagName === 'TEXTAREA' ? 'LEFT' : 'LEFT', fixed: true, runs: [{ s, st }] });
      }
      if (el.tagName === 'SELECT') {
        const cx = b.x + b.w - 22, cy = b.y + b.h / 2 - 4;
        kids.push({ t: 'svg', name: 'Chevron', x: r1(cx), y: r1(cy), w: 12, h: 8, svg: '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8" viewBox="0 0 12 8"><path d="M1 1.5l5 5 5-5" fill="none" stroke="#17181A" stroke-width="1.6"/></svg>' });
      }
    } else if (visible) {
      const t = textNode(el, cs);
      if (t) kids.push(t);
    }
    for (const ch of el.children) kids.push(...walk(ch));
    const after = visible ? pseudo(el, cs, '::after') : null;
    if (after) kids.push(after);

    const f = visible ? fills(cs) : [];
    const s = visible ? stroke(cs) : null;
    const clip = ['hidden', 'clip'].includes(cs.overflowX) || ['hidden', 'clip'].includes(cs.overflowY);
    const op = parseFloat(cs.opacity);
    const isField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
    const needFrame = visible && (f.length || s || clip || op < 1 || isField || STRUCT.has(el.tagName) || el.matches('.page, .btn, .tile, .panel, .rows, .field, .label') ||
      (kids.length > 1 && !isInline(cs)));
    if (!needFrame) return kids;
    return [{ t: 'frame', name: nameOf(el), ...b, fill: f, stroke: s, radius: radius(cs, b.w, b.h), clip, opacity: op < 1 ? op : undefined, children: kids }];
  }

  const body = document.body;
  const bcs = getComputedStyle(body);
  return {
    w: document.documentElement.clientWidth,
    h: Math.ceil(document.documentElement.scrollHeight),
    bg: color(bcs.backgroundColor) || '#FFFFFF',
    children: [...body.children].flatMap(walk),
  };
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch();
  const frames = [];
  const srcs = new Set();
  for (const v of VIEWS) {
    for (const [file, title] of PAGES) {
      const p = await b.newPage({ viewport: { width: v.width, height: v.height } });
      await p.goto('file://' + path.join(SITE, file + '.html'), { waitUntil: 'networkidle' });
      await p.addStyleTag({ content: '.book-bar{position:static!important} body{padding-bottom:0!important}' });
      await p.evaluate(async () => {
        await document.fonts.ready;
        for (let y = 0; y < document.body.scrollHeight; y += 500) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 25)); }
        window.scrollTo(0, 0);
        // the open-now line changes through the day; show it in a neutral state
        document.querySelectorAll('[data-status] span').forEach(s => { s.textContent = s.textContent.replace(/ (open until|opens at|closed for today|closed today).*$/, ' open until 23:00'); });
        await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
      });
      await p.waitForTimeout(400);
      const data = await p.evaluate(capture);
      (function collect(n) { if (n.t === 'image') srcs.add(n.src); (n.children || []).forEach(collect); })({ children: data.children });
      frames.push({ name: `${v.name} / ${title}`, view: v.name, grid: v.grid, ...data });
      console.log(v.name, file, data.h + 'px');
      await p.close();
    }
  }
  await b.close();

  // Photos, resized for Figma and embedded in the plugin
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'tb-figma-'));
  const images = {};
  for (const s of srcs) {
    const out = path.join(tmp, path.basename(s));
    execFileSync('convert', [path.join(SITE, s), '-resize', '1400x1400>', '-strip', '-quality', '80', out]);
    images[s] = fs.readFileSync(out).toString('base64');
  }
  const data = { tokens: TOKENS, frames, images };

  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify({
    name: 'TattooBar website import',
    id: 'tattoobar-website-import',
    api: '1.0.0',
    main: 'code.js',
    editorType: ['figma'],
    documentAccess: 'dynamic-page',
    networkAccess: { allowedDomains: ['none'] },
  }, null, 2) + '\n');
  const builder = fs.readFileSync(path.join(__dirname, 'figma_builder.js'), 'utf8');
  fs.writeFileSync(path.join(OUT, 'code.js'), '// Generated by build/figma_export.js. Draws the TattooBar website into Figma.\nvar DATA = ' + JSON.stringify(data) + ';\n' + builder);
  const size = fs.statSync(path.join(OUT, 'code.js')).size;
  console.log('frames', frames.length, 'images', srcs.size, 'code.js', (size / 1e6).toFixed(1) + ' MB');
})();
